import hashlib
import time
import uuid
from collections import defaultdict, deque
from threading import Lock
from typing import Callable, Deque, TypeVar

from fastapi import HTTPException, status
from redis import Redis
from redis.exceptions import RedisError

from app.core.config import settings
from app.core.logging import logger

_Result = TypeVar("_Result")

_RATE_LIMIT_SCRIPT = """
local cutoff = tonumber(ARGV[1]) - tonumber(ARGV[2])
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', cutoff)
if redis.call('ZCARD', KEYS[1]) >= tonumber(ARGV[3]) then
    return 0
end
redis.call('ZADD', KEYS[1], ARGV[1], ARGV[4])
redis.call('PEXPIRE', KEYS[1], ARGV[2])
return 1
"""

_RECORD_FAILURE_SCRIPT = """
local failures = redis.call('INCR', KEYS[1])
if failures == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
end
if failures >= tonumber(ARGV[2]) then
    redis.call('SET', KEYS[2], '1', 'EX', ARGV[3])
end
return failures
"""


class SharedStateStore:
    def __init__(self) -> None:
        self._redis = (
            Redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=0.2,
                socket_timeout=0.2,
            )
            if settings.REDIS_URL
            else None
        )
        self._local_lock = Lock()
        self._attempts_by_ip: dict[str, Deque[float]] = defaultdict(deque)
        self._lockouts: dict[str, tuple[int, float]] = {}
        self._warned_about_fallback = False
        self._redis_retry_after = 0.0

    @staticmethod
    def _identity_key(identity: str) -> str:
        digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
        return f"drishti:login:{digest}"

    def _redis_call(
        self,
        operation: Callable[[Redis], _Result],
    ) -> tuple[bool, _Result | None]:
        if self._redis is None:
            if settings.is_production:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Shared state service is required but not configured.",
                )
            return False, None
        if (
            not settings.is_production
            and time.monotonic() < self._redis_retry_after
        ):
            return False, None
        try:
            return True, operation(self._redis)
        except RedisError as exc:
            if settings.is_production:
                logger.exception("Redis shared state is unavailable")
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Shared state service is temporarily unavailable.",
                ) from exc
            if not self._warned_about_fallback:
                logger.warning(
                    "Redis is unavailable; using process-local shared-state fallback."
                )
                self._warned_about_fallback = True
            self._redis_retry_after = time.monotonic() + 5
            return False, None

    def check_login_rate_limit(
        self,
        client_ip: str,
        email: str,
        *,
        window_seconds: int,
        max_attempts_per_ip: int,
    ) -> str | None:
        email_key = self._identity_key(email)
        now_ms = int(time.time() * 1000)

        def check_with_redis(client: Redis) -> str | None:
            if client.exists(f"{email_key}:locked"):
                return "account_locked"
            ip_key = self._identity_key(client_ip)
            allowed = client.eval(
                _RATE_LIMIT_SCRIPT,
                1,
                f"drishti:rate:{ip_key}",
                now_ms,
                window_seconds * 1000,
                max_attempts_per_ip,
                f"{now_ms}:{uuid.uuid4().hex}",
            )
            return None if allowed else "ip_rate_limited"

        redis_used, result = self._redis_call(check_with_redis)
        if redis_used:
            return result

        now = time.monotonic()
        with self._local_lock:
            failures, locked_until = self._lockouts.get(email, (0, 0.0))
            if locked_until > now:
                return "account_locked"
            if locked_until:
                self._lockouts.pop(email, None)
            attempts = self._attempts_by_ip[client_ip]
            while attempts and now - attempts[0] >= window_seconds:
                attempts.popleft()
            if len(attempts) >= max_attempts_per_ip:
                return "ip_rate_limited"
            attempts.append(now)
        return None

    def record_login_failure(
        self,
        email: str,
        *,
        failure_limit: int,
        lockout_seconds: int,
    ) -> int:
        email_key = self._identity_key(email)
        redis_used, failures = self._redis_call(
            lambda client: client.eval(
                _RECORD_FAILURE_SCRIPT,
                2,
                f"{email_key}:failures",
                f"{email_key}:locked",
                max(lockout_seconds, 1),
                failure_limit,
                max(lockout_seconds, 1),
            )
        )
        if redis_used:
            return int(failures)

        now = time.monotonic()
        with self._local_lock:
            count, locked_until = self._lockouts.get(email, (0, 0.0))
            if locked_until and locked_until <= now:
                count = 0
            count += 1
            if count >= failure_limit:
                locked_until = now + lockout_seconds
                self._lockouts[email] = (count, locked_until)
            else:
                self._lockouts[email] = (count, 0.0)
            return count

    def clear_login_failures(self, email: str) -> None:
        email_key = self._identity_key(email)
        redis_used, _ = self._redis_call(
            lambda client: client.delete(
                f"{email_key}:failures",
                f"{email_key}:locked",
            )
        )
        if not redis_used:
            with self._local_lock:
                self._lockouts.pop(email, None)

    def clear_login_state(self, email: str, client_ip: str) -> None:
        email_key = self._identity_key(email)
        ip_key = self._identity_key(client_ip)
        self._redis_call(
            lambda client: client.delete(
                f"{email_key}:failures",
                f"{email_key}:locked",
                f"drishti:rate:{ip_key}",
            )
        )
        with self._local_lock:
            self._lockouts.pop(email, None)
            self._attempts_by_ip.pop(client_ip, None)

    def get_dashboard_cache(self, key: str) -> tuple[bool, str | None]:
        return self._redis_call(lambda client: client.get(key))

    def set_dashboard_cache(self, key: str, value: str, ttl_seconds: int) -> bool:
        redis_used, _ = self._redis_call(
            lambda client: client.set(key, value, ex=ttl_seconds)
        )
        return redis_used

    def delete_dashboard_cache(self, key: str) -> bool:
        redis_used, _ = self._redis_call(lambda client: client.delete(key))
        return redis_used


shared_state = SharedStateStore()
