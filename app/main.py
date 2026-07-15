"""Ping traffic-generation app — FastAPI entrypoint.

Routes:
  GET  /            dashboard (QR + live tiles + feed)
  GET  /m           mobile "Send Ping" page
  POST /ping        the ping itself (users AND the load generator hit this)
  POST /heartbeat   keep a phone counted as an active session
  GET  /events      SSE stream: stats + live per-request feed
  GET  /stats       JSON snapshot
  GET  /metrics     Prometheus metrics (drives the HPA)
  GET  /admin       controlled load-test console
  POST /admin/loadtest/{start,stop,emergency-stop}, GET .../status
  GET  /healthz,/readyz
"""
import asyncio
import io
import json
import logging
import time
from contextlib import asynccontextmanager

import qrcode
import qrcode.image.svg
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, StreamingResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from pydantic import BaseModel, Field

import pages
import state
from config import ADMIN_TOKEN, BASE_LATENCY_MS, POD_NAME, PUBLIC_URL
from loadtest import CapError, LoadTester
from logs import log_event, setup_logging

logger = setup_logging()

# --- Prometheus metrics (each pod is scraped individually) ---
M_PINGS = Counter("pingapp_pings_total", "Total pings handled", ["pod", "source"])
M_ERRORS = Counter("pingapp_errors_total", "Total errored pings", ["pod"])
M_LATENCY = Histogram("pingapp_request_latency_seconds", "Ping handler latency", ["source"])
M_SESSIONS = Gauge("pingapp_active_sessions", "Active phone sessions (cluster-wide)")
M_LT = Gauge("pingapp_loadtest_running", "1 if a controlled load test is running")

tester: LoadTester


@asynccontextmanager
async def lifespan(app: FastAPI):
    state.init()
    await state.r().ping()
    global tester
    tester = LoadTester(lambda event, **f: log_event(
        logger, event, level=logging.WARNING if f.pop("level_warn", False) else logging.INFO, **f))
    log_event(logger, "startup", pod=POD_NAME)
    yield
    log_event(logger, "shutdown", pod=POD_NAME)


app = FastAPI(title="pingapp", lifespan=lifespan)


def _require_admin(authorization):
    if not ADMIN_TOKEN:
        raise HTTPException(503, "admin disabled: ADMIN_TOKEN is not set")
    if authorization != f"Bearer {ADMIN_TOKEN}":
        raise HTTPException(401, "unauthorized")


def _qr_svg(url: str) -> str:
    buf = io.BytesIO()
    qrcode.make(url, image_factory=qrcode.image.svg.SvgPathImage).save(buf)
    svg = buf.getvalue().decode()
    return svg[svg.find("<svg"):]


def _base_url(request: Request) -> str:
    if PUBLIC_URL:
        return PUBLIC_URL
    return str(request.base_url).rstrip("/")


# --- Pages ---
@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    mobile_url = _base_url(request) + "/m"
    return pages.dashboard(_qr_svg(mobile_url), mobile_url)


@app.get("/m", response_class=HTMLResponse)
async def mobile():
    return pages.mobile()


@app.get("/admin", response_class=HTMLResponse)
async def admin():
    return pages.admin()


# --- Core traffic ---
@app.post("/ping")
async def ping(request: Request, session: str = "", source: str = "user"):
    source = "loadtest" if source == "loadtest" else "user"
    t0 = time.perf_counter()
    if BASE_LATENCY_MS > 0:
        await asyncio.sleep(BASE_LATENCY_MS / 1000.0)
    status = 200

    event = await state.record_ping(t0, source, session, status)
    latency_ms = event["latency_ms"]
    M_PINGS.labels(POD_NAME, source).inc()
    M_LATENCY.labels(source).observe(latency_ms / 1000.0)
    if status >= 400:
        M_ERRORS.labels(POD_NAME).inc()

    log_event(logger, "ping", source=source, session=(session[:8] or None),
              latency_ms=latency_ms, status=status, seq=event["seq"])
    return {"pod": POD_NAME, "latency_ms": latency_ms,
            "seq": event["seq"], "status": status}


@app.post("/heartbeat")
async def heartbeat(session: str = ""):
    await state.touch_session(session)
    return {"ok": True}


@app.post("/name")
async def set_name(session: str = "", name: str = ""):
    await state.set_nick(session, name)
    return {"ok": True}


@app.get("/stats")
async def stats():
    return await state.get_stats()


@app.get("/events")
async def events(request: Request):
    async def stream():
        pub = await state.subscribe()
        last = 0.0
        try:
            snap = await state.get_stats()
            yield f"event: stats\ndata: {json.dumps(snap)}\n\n"
            while True:
                if await request.is_disconnected():
                    break
                msg = await pub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if msg and msg.get("type") == "message":
                    yield f"event: ping\ndata: {msg['data']}\n\n"
                now = time.time()
                if now - last >= 1.0:
                    last = now
                    yield f"event: stats\ndata: {json.dumps(await state.get_stats())}\n\n"
        finally:
            try:
                await pub.unsubscribe()
                await pub.aclose()
            except Exception:
                pass

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# --- Metrics ---
@app.get("/metrics")
async def metrics():
    s = await state.get_stats()
    M_SESSIONS.set(s["active_sessions"])
    lt = await tester.status()
    M_LT.set(1 if lt["status"] == "running" else 0)
    return PlainTextResponse(generate_latest().decode(), media_type=CONTENT_TYPE_LATEST)


# --- Admin: controlled load test ---
class LoadTestRequest(BaseModel):
    rate: int = Field(ge=1)
    concurrency: int = Field(ge=1)
    duration: int = Field(ge=1)


@app.post("/admin/loadtest/start")
async def lt_start(body: LoadTestRequest, authorization: str | None = Header(None)):
    _require_admin(authorization)
    try:
        return await tester.start(body.rate, body.concurrency, body.duration,
                                  requested_by="admin")
    except CapError as e:
        raise HTTPException(400, str(e))
    except RuntimeError as e:
        raise HTTPException(409, str(e))


@app.post("/admin/loadtest/stop")
async def lt_stop(authorization: str | None = Header(None)):
    _require_admin(authorization)
    return await tester.request_stop(who="admin")


@app.post("/admin/loadtest/emergency-stop")
async def lt_estop(authorization: str | None = Header(None)):
    _require_admin(authorization)
    return await tester.emergency_stop(who="admin")


@app.get("/admin/loadtest/status")
async def lt_status():
    return await tester.status()


# --- Health ---
@app.get("/healthz")
async def healthz():
    return {"status": "ok", "pod": POD_NAME}


@app.get("/readyz")
async def readyz():
    try:
        await state.r().ping()
        return {"status": "ready", "pod": POD_NAME}
    except Exception as e:
        return JSONResponse({"status": "not-ready", "error": str(e)}, status_code=503)
