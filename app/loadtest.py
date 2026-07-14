"""Controlled load generator.

Safety model — read this before touching it:

* TARGET IS FIXED. Requests only ever go to SELF_PING_URL (this app). There is
  no caller-supplied URL anywhere, so it cannot be aimed at anything external.
* HARD CAPS. rate / concurrency / duration are clamped to the MAX_* ceilings in
  config.py. Requests above the cap are rejected before anything starts.
* AUTOMATIC STOP. The run ends on its own at the duration deadline, and aborts
  early if the error ratio crosses the threshold.
* EMERGENCY STOP. A flag in Redis halts the run within one tick, and because the
  flag lives in Redis (not memory) the stop button works even when it is pressed
  on a different pod than the one running the generator.
* SINGLE RUN. A Redis lock (with a TTL dead-man's switch) guarantees only one
  generator runs cluster-wide; if its pod dies, the lock expires and everything
  stops.
"""
import asyncio
import time

import httpx

import state
from config import (
    SELF_PING_URL, POD_NAME,
    MAX_RATE, MAX_CONCURRENCY, MAX_DURATION_SECONDS,
    LOADTEST_ERROR_ABORT_RATIO, LOADTEST_ERROR_ABORT_MIN,
)

K_LOCK = "loadtest:lock"
K_STATE = "loadtest:state"
K_EMERGENCY = "loadtest:emergency"


class CapError(ValueError):
    """Requested parameters exceed the hard caps."""


def _clamp(rate, concurrency, duration):
    if rate < 1 or concurrency < 1 or duration < 1:
        raise CapError("rate, concurrency and duration must all be >= 1")
    if rate > MAX_RATE:
        raise CapError(f"rate {rate} exceeds max {MAX_RATE}")
    if concurrency > MAX_CONCURRENCY:
        raise CapError(f"concurrency {concurrency} exceeds max {MAX_CONCURRENCY}")
    if duration > MAX_DURATION_SECONDS:
        raise CapError(f"duration {duration} exceeds max {MAX_DURATION_SECONDS}")
    return rate, concurrency, duration


class LoadTester:
    def __init__(self, logger):
        self.log = logger
        self._task = None

    async def caps(self):
        return {
            "max_rate": MAX_RATE,
            "max_concurrency": MAX_CONCURRENCY,
            "max_duration_seconds": MAX_DURATION_SECONDS,
        }

    async def status(self):
        st = await state.r().hgetall(K_STATE)
        emergency = bool(await state.r().exists(K_EMERGENCY))
        st = st or {}
        return {
            "status": st.get("status", "idle"),
            "rate": int(st.get("rate", 0) or 0),
            "concurrency": int(st.get("concurrency", 0) or 0),
            "duration": int(st.get("duration", 0) or 0),
            "sent": int(st.get("sent", 0) or 0),
            "errors": int(st.get("errors", 0) or 0),
            "requested_by": st.get("requested_by"),
            "running_pod": st.get("running_pod"),
            "started_at": float(st.get("started_at", 0) or 0),
            "deadline": float(st.get("deadline", 0) or 0),
            "reason": st.get("reason"),
            "emergency": emergency,
            **(await self.caps()),
        }

    async def start(self, rate, concurrency, duration, requested_by):
        rate, concurrency, duration = _clamp(rate, concurrency, duration)

        # One run cluster-wide. Lock TTL outlives the run so a crashed pod frees it.
        got = await state.r().set(K_LOCK, POD_NAME, nx=True, ex=duration + 15)
        if not got:
            raise RuntimeError("a load test is already running")

        # Fresh run: clear any stale emergency flag from a previous run.
        await state.r().delete(K_EMERGENCY)
        now = time.time()
        await state.r().hset(K_STATE, mapping={
            "status": "running",
            "rate": rate,
            "concurrency": concurrency,
            "duration": duration,
            "sent": 0,
            "errors": 0,
            "requested_by": requested_by,
            "running_pod": POD_NAME,
            "started_at": now,
            "deadline": now + duration,
            "reason": "",
        })
        self.log("loadtest_start", rate=rate, concurrency=concurrency,
                 duration=duration, requested_by=requested_by)
        self._task = asyncio.create_task(self._run(rate, concurrency, now + duration))
        return await self.status()

    async def request_stop(self, who):
        """Graceful stop — the running loop notices and winds down."""
        await state.r().hset(K_STATE, mapping={"status": "stopping", "reason": f"stopped_by:{who}"})
        self.log("loadtest_stop_requested", by=who)
        return await self.status()

    async def emergency_stop(self, who):
        """Immediate kill switch. Works across pods via the Redis flag."""
        await state.r().set(K_EMERGENCY, who, ex=300)
        await state.r().hset(K_STATE, mapping={"status": "stopping", "reason": f"emergency:{who}"})
        self.log("loadtest_emergency_stop", by=who, level_warn=True)
        return await self.status()

    async def _should_stop(self, deadline, sent, errors):
        if time.time() >= deadline:
            return "duration_reached"
        if await state.r().exists(K_EMERGENCY):
            return "emergency"
        st = await state.r().hget(K_STATE, "status")
        if st == "stopping":
            return "stop_requested"
        if sent >= LOADTEST_ERROR_ABORT_MIN and errors / max(sent, 1) > LOADTEST_ERROR_ABORT_RATIO:
            return "error_ratio_exceeded"
        return None

    async def _run(self, rate, concurrency, deadline):
        interval = 1.0 / rate
        sem = asyncio.Semaphore(concurrency)
        sent = 0
        errors = 0
        loop = asyncio.get_event_loop()
        next_at = loop.time()
        last_poll = 0.0
        stop_reason = None

        async def one_request(client):
            nonlocal errors
            try:
                resp = await client.post(
                    SELF_PING_URL,
                    params={"source": "loadtest"},
                    headers={"X-Load-Test": "1"},
                    timeout=5.0,
                )
                if resp.status_code >= 400:
                    errors += 1
            except Exception:
                errors += 1
            finally:
                sem.release()

        try:
            async with httpx.AsyncClient() as client:
                while True:
                    # Check stop conditions ~2x/second (cheap, avoids hammering Redis).
                    if loop.time() - last_poll > 0.5:
                        last_poll = loop.time()
                        stop_reason = await self._should_stop(deadline, sent, errors)
                        await state.r().hset(K_STATE, mapping={"sent": sent, "errors": errors})
                        if stop_reason:
                            break

                    now = loop.time()
                    dispatched = 0
                    # Release paced "tickets", bounded by the concurrency semaphore.
                    while next_at <= now and dispatched < concurrency * 2:
                        if sem.locked() and sem._value == 0:  # all slots busy; let them drain
                            break
                        await sem.acquire()
                        asyncio.create_task(one_request(client))
                        next_at += interval
                        sent += 1
                        dispatched += 1
                    await asyncio.sleep(min(interval, 0.05))
        except asyncio.CancelledError:
            stop_reason = "cancelled"
            raise
        finally:
            await state.r().hset(K_STATE, mapping={
                "status": "idle",
                "sent": sent,
                "errors": errors,
                "reason": stop_reason or "finished",
            })
            await state.r().delete(K_LOCK)
            self.log("loadtest_finished", sent=sent, errors=errors, reason=stop_reason)
