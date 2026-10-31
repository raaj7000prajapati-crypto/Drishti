import time
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

import pytest

from app.schemas.analytics import DashboardStatsResponse, SystemImpactMetrics
from app.core.shared_state import shared_state
from app.services.dashboard_cache import DashboardStatsCache


@pytest.fixture(autouse=True)
def clear_redis_connection(monkeypatch):
    monkeypatch.setattr(shared_state, "_redis", None)


def _dashboard_stats(total: int = 0) -> DashboardStatsResponse:
    return DashboardStatsResponse(
        impact_metrics=SystemImpactMetrics(
            avg_resolution_days=0,
            overdue_percentage=0,
            duplicates_intercepted=0,
            sla_compliance_rate=100,
            total_complaints=total,
            total_resolved=0,
            total_in_progress=0,
            total_overdue=0,
        ),
        cases_by_department=[],
        status_distribution=[],
        timeline_last_6_months=[],
        role_breakdown=[],
        similarity_distribution=[],
        pending_delayed_flags=[],
    )


def test_dashboard_cache_expires_and_isolates_keys():
    cache = DashboardStatsCache(ttl_seconds=0.02)
    stats = _dashboard_stats(total=5)
    cache.set(("ADMIN", 1), stats)

    assert cache.get(("ADMIN", 1)).impact_metrics.total_complaints == 5
    assert cache.get(("OFFICIAL", 1)) is None
    time.sleep(0.03)
    assert cache.get(("ADMIN", 1)) is None


def test_dashboard_cache_coalesces_concurrent_misses():
    cache = DashboardStatsCache(ttl_seconds=1)
    call_lock = Lock()
    call_count = 0

    def calculate():
        nonlocal call_count
        with call_lock:
            call_count += 1
        time.sleep(0.03)
        return _dashboard_stats(total=7)

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(lambda _index: cache.get_or_compute(("ADMIN", 1), calculate), range(8)))

    assert call_count == 1
    assert all(result.impact_metrics.total_complaints == 7 for result in results)
    assert cache._key_locks == {}


def test_dashboard_cache_releases_lock_after_compute_error():
    cache = DashboardStatsCache(ttl_seconds=1)

    def fail():
        raise RuntimeError("dashboard calculation failed")

    with pytest.raises(RuntimeError, match="dashboard calculation failed"):
        cache.get_or_compute(("ADMIN", 1), fail)

    recovered = cache.get_or_compute(
        ("ADMIN", 1),
        lambda: _dashboard_stats(total=3),
    )
    assert recovered.impact_metrics.total_complaints == 3


def test_dashboard_cache_uses_redis_when_available(monkeypatch):
    class RedisDouble:
        values = {}

        def get(self, key):
            return self.values.get(key)

        def set(self, key, value, ex):
            self.values[key] = value
            return True

        def delete(self, key):
            return self.values.pop(key, None) is not None

    redis = RedisDouble()
    monkeypatch.setattr(shared_state, "_redis", redis)
    cache = DashboardStatsCache(ttl_seconds=10)
    stats = _dashboard_stats(total=9)

    cache.set(("ADMIN", 3), stats)

    assert cache.get(("ADMIN", 3)).impact_metrics.total_complaints == 9
    assert len(redis.values) == 1
