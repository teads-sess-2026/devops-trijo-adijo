"""Shared, cross-pod state backed by Redis.

Every pod reads and writes the same Redis, so counters, the live event feed,
active-session tracking and the load-test control flags are consistent no matter
which pod (or how many) are serving traffic. This is what makes the dashboard
totals correct while the HPA is adding and removing pods underneath us.
"""
import json
import time
import uuid
from time import perf_counter

import redis.asyncio as aioredis

from config import REDIS_URL, SESSION_TTL_SECONDS, POD_NAME

# Redis key layout (all namespaced under ping: / sess: / loadtest:).
K_TOTAL = "ping:total"
K_ERRORS = "ping:errors"
K_PODS = "ping:pods"            # hash pod -> count
K_POD_SEEN = "ping:pods_seen"   # hash pod -> last-seen epoch (liveness)
K_RECENT = "ping:recent"        # zset member -> epoch (for rate)
K_LATENCIES = "ping:latencies"  # capped list of recent latency ms
K_SESSIONS = "sess:active"      # zset session_id -> last-seen epoch
CHANNEL = "ping:events"         # pub/sub live feed

_LATENCY_SAMPLE = 500           # how many recent latencies to keep for percentiles
_RATE_WINDOW = 5.0              # seconds used to compute pings/sec
_POD_ACTIVE_WINDOW = 15.0       # a pod is "active" if it served within this many seconds
_POD_PRUNE_SECONDS = 300.0      # drop a pod from the panel after this long with no traffic

_redis: aioredis.Redis | None = None


def init(url: str = REDIS_URL) -> aioredis.Redis:
    global _redis
    _redis = aioredis.from_url(url, encoding="utf-8", decode_responses=True)
    return _redis


def r() -> aioredis.Redis:
    assert _redis is not None, "redis not initialised"
    return _redis


async def touch_session(session_id: str) -> None:
    """Renew a phone session's heartbeat."""
    if not session_id:
        return
    await r().zadd(K_SESSIONS, {session_id: time.time()})


async def record_ping(t0: float, source: str, session_id: str, status: int) -> dict:
    """Register one handled ping: update counters, feed, session, publish event.

    t0 is a perf_counter() taken at the start of the request handler, so the
    measured latency covers the real backend work (including this counter
    round-trip to Redis) and the response-time tiles reflect something real.
    """
    now = time.time()
    is_error = status >= 400
    pipe = r().pipeline()
    pipe.incr(K_TOTAL)
    if is_error:
        pipe.incr(K_ERRORS)
    pipe.hincrby(K_PODS, POD_NAME, 1)
    pipe.hset(K_POD_SEEN, POD_NAME, now)
    pipe.zadd(K_RECENT, {f"{now}:{uuid.uuid4().hex[:8]}": now})
    pipe.zremrangebyscore(K_RECENT, 0, now - 60)
    if session_id:
        pipe.zadd(K_SESSIONS, {session_id: now})
    results = await pipe.execute()
    total = results[0]

    latency_ms = (perf_counter() - t0) * 1000.0
    lat_pipe = r().pipeline()
    lat_pipe.lpush(K_LATENCIES, latency_ms)
    lat_pipe.ltrim(K_LATENCIES, 0, _LATENCY_SAMPLE - 1)
    await lat_pipe.execute()

    event = {
        "ts": now,
        "pod": POD_NAME,
        "source": source,
        "latency_ms": round(latency_ms, 1),
        "status": status,
        "session": session_id[:8] if session_id else None,
        "seq": total,
    }
    await r().publish(CHANNEL, json.dumps(event))
    return event


def _percentile(sorted_vals, pct):
    if not sorted_vals:
        return 0.0
    k = max(0, min(len(sorted_vals) - 1, int(round((pct / 100.0) * (len(sorted_vals) - 1)))))
    return sorted_vals[k]


async def get_stats() -> dict:
    now = time.time()
    pipe = r().pipeline()
    pipe.get(K_TOTAL)
    pipe.get(K_ERRORS)
    pipe.zremrangebyscore(K_SESSIONS, 0, now - SESSION_TTL_SECONDS)
    pipe.zcard(K_SESSIONS)
    pipe.zcount(K_RECENT, now - _RATE_WINDOW, now)
    pipe.lrange(K_LATENCIES, 0, _LATENCY_SAMPLE - 1)
    pipe.hgetall(K_PODS)
    pipe.hgetall(K_POD_SEEN)
    total, errors, _, active, recent_count, latencies, pods, pods_seen = await pipe.execute()

    # Decide which pods are alive. "active" = served within _POD_ACTIVE_WINDOW.
    # Pods idle beyond _POD_PRUNE_SECONDS are dropped from the panel and cleaned
    # out of Redis, so scaled-down pods fade and then disappear (no ghosts).
    seen = {k: float(v) for k, v in (pods_seen or {}).items()}
    kept_counts: dict[str, int] = {}
    pod_active: dict[str, bool] = {}
    stale: list[str] = []
    for pod, count in (pods or {}).items():
        idle = now - seen.get(pod, 0.0)
        if idle > _POD_PRUNE_SECONDS:
            stale.append(pod)
            continue
        kept_counts[pod] = int(count)
        pod_active[pod] = idle <= _POD_ACTIVE_WINDOW
    if stale:
        await r().hdel(K_PODS, *stale)
        await r().hdel(K_POD_SEEN, *stale)

    lat = sorted(float(x) for x in latencies) if latencies else []
    return {
        "total": int(total or 0),
        "errors": int(errors or 0),
        "pings_per_second": round((recent_count or 0) / _RATE_WINDOW, 1),
        "active_sessions": int(active or 0),
        "p50_ms": round(_percentile(lat, 50), 1),
        "p95_ms": round(_percentile(lat, 95), 1),
        "pods": kept_counts,
        "pod_active": pod_active,
        "active_pods": sum(1 for a in pod_active.values() if a),
        "serving_pod": POD_NAME,
    }


async def subscribe():
    """Return a pubsub subscribed to the live event channel."""
    pub = r().pubsub()
    await pub.subscribe(CHANNEL)
    return pub
