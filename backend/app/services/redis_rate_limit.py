from __future__ import annotations
import time
from app.core.config import get_settings
from app.services.rate_limit import limiter as memory_limiter

settings = get_settings()
_redis = None
try:
    if settings.REDIS_URL:
        import redis
        _redis = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True, socket_timeout=1)
        _redis.ping()
except Exception:
    _redis = None


def allow(key: str, limit: int, window_seconds: int = 60) -> bool:
    if _redis is None:
        return memory_limiter.allow(key, limit, window_seconds)
    bucket = f"lineage:rl:{key}"
    try:
        count = _redis.incr(bucket)
        if count == 1:
            _redis.expire(bucket, window_seconds)
        return count <= limit
    except Exception:
        return memory_limiter.allow(key, limit, window_seconds)


def status() -> dict[str, str | bool]:
    return {"backend": "redis" if _redis is not None else "in-memory-fallback", "distributed": _redis is not None}
