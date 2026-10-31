import hashlib
import json
import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from typing import Any

from app.core.logging import logger
from app.core.shared_state import shared_state
from app.schemas.analytics import DashboardStatsResponse


class DashboardStatsCache:
    def __init__(self, ttl_seconds: int, max_entries: int = 512):
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self._entries: OrderedDict[tuple[Any, ...], tuple[float, dict[str, Any]]] = (
            OrderedDict()
        )
        self._lock = threading.Lock()
        self._key_locks: dict[tuple[Any, ...], threading.Lock] = {}
        self._key_lock_users: dict[tuple[Any, ...], int] = {}

    @staticmethod
    def _redis_key(key: tuple[Any, ...]) -> str:
        serialized = json.dumps(key, separators=(",", ":"), default=str)
        digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        return f"drishti:analytics:dashboard:{digest}"

    def get(self, key: tuple[Any, ...]) -> DashboardStatsResponse | None:
        redis_key = self._redis_key(key)
        redis_used, payload = shared_state.get_dashboard_cache(redis_key)
        if redis_used:
            if payload is None:
                return None
            try:
                return DashboardStatsResponse.model_validate_json(payload)
            except ValueError:
                logger.warning("Discarding invalid cached dashboard response.")
                shared_state.delete_dashboard_cache(redis_key)
                return None

        now = time.monotonic()
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            expires_at, payload = entry
            if expires_at <= now:
                del self._entries[key]
                return None
            self._entries.move_to_end(key)
            return DashboardStatsResponse.model_validate(payload)

    def set(self, key: tuple[Any, ...], value: DashboardStatsResponse) -> None:
        redis_key = self._redis_key(key)
        if shared_state.set_dashboard_cache(
            redis_key,
            value.model_dump_json(),
            self.ttl_seconds,
        ):
            return

        now = time.monotonic()
        with self._lock:
            expired_keys = [
                cache_key
                for cache_key, (expires_at, _) in self._entries.items()
                if expires_at <= now
            ]
            for cache_key in expired_keys:
                del self._entries[cache_key]
            self._entries[key] = (
                now + self.ttl_seconds,
                value.model_dump(mode="python"),
            )
            self._entries.move_to_end(key)
            while len(self._entries) > self.max_entries:
                self._entries.popitem(last=False)

    def get_or_compute(
        self,
        key: tuple[Any, ...],
        compute: Callable[[], DashboardStatsResponse],
    ) -> DashboardStatsResponse:
        cached = self.get(key)
        if cached is not None:
            return cached
        with self._lock:
            key_lock = self._key_locks.setdefault(key, threading.Lock())
            self._key_lock_users[key] = self._key_lock_users.get(key, 0) + 1
        try:
            with key_lock:
                cached = self.get(key)
                if cached is not None:
                    return cached
                result = compute()
                self.set(key, result)
                return result
        finally:
            with self._lock:
                remaining_users = self._key_lock_users[key] - 1
                if remaining_users:
                    self._key_lock_users[key] = remaining_users
                else:
                    del self._key_lock_users[key]
                    del self._key_locks[key]
