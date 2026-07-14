# Ping — traffic-generation app

A small FastAPI service that generates **realistic traffic and structured logs
on demand**, so the team can exercise logging, monitoring, and Kubernetes
autoscaling — safely, against this app only.

- **Dashboard** (`/`) — QR code + live tiles (total pings, pings/sec, active
  phones, p50/p95 latency, errors) + a live feed showing which **pod** served
  each request.
- **Mobile** (`/m`) — a big **Send Ping** button; each tap is a real request +
  a structured JSON log line.
- **Admin** (`/admin`) — a **Controlled Load Test** with hard caps, automatic
  stop, and an emergency stop button.

Shared state (counters, live feed, sessions, load-test flags) lives in **Redis**,
so totals stay correct across multiple pods as the app scales.

> Container image (`Dockerfile`) is here; building/pushing it and the cluster
> deployment (ECR, k8s manifests, Terraform) are handled separately as infra.

## Run locally

```bash
# 1. Redis
docker run -d --name pingredis -p 6379:6379 redis:7-alpine

# 2. Deps
pip install -r requirements.txt

# 3. Run
REDIS_URL=redis://localhost:6379/0 ADMIN_TOKEN=dev \
  uvicorn main:app --reload
```

On Windows (PowerShell), set env vars first, then run:

```powershell
docker run -d --name pingredis -p 6379:6379 redis:7-alpine
pip install -r requirements.txt
$env:REDIS_URL="redis://localhost:6379/0"; $env:ADMIN_TOKEN="dev"
uvicorn main:app --reload
```

Open:
- Dashboard — http://localhost:8000/
- Mobile — http://localhost:8000/m  (open in a second tab and tap **Send Ping**)
- Admin — http://localhost:8000/admin  (token: `dev`)

You don't need a phone: the admin **Controlled Load Test** drives the tiles and
feed on its own. Metrics: `/metrics`. Logs: structured JSON on stdout.

Testing from a phone on the same Wi-Fi? The QR encodes `localhost`, which the
phone can't reach — set `PUBLIC_URL=http://<your-LAN-IP>:8000` and start uvicorn
with `--host 0.0.0.0` (and allow it through the firewall). Cleanup:
`docker rm -f pingredis`.

## Configuration (environment variables)

| Var | Default | Purpose |
|---|---|---|
| `REDIS_URL` | `redis://localhost:6379/0` | Shared-state store |
| `ADMIN_TOKEN` | *(empty)* | Bearer token for `/admin/loadtest/*`; empty = admin disabled |
| `PUBLIC_URL` | *(derived from request)* | Base URL the QR code points at |
| `POD_NAME` | hostname | Which pod served a request (set via Downward API in k8s) |
| `SELF_PING_URL` | `http://localhost:8000/ping` | Load generator's fixed target |
| `LOADTEST_MAX_RATE` | `200` | Hard cap: requests/sec |
| `LOADTEST_MAX_CONCURRENCY` | `50` | Hard cap: concurrency |
| `LOADTEST_MAX_DURATION` | `120` | Hard cap: seconds |

## Controlled load test — safety

The generator exists to exercise **this app only**:

- **Fixed target.** It sends to `SELF_PING_URL` (loopback). No request field can
  redirect it — it cannot hit anything external.
- **Hard caps** (above): anything higher is rejected before it starts.
- **Automatic stop** at the duration deadline and if the error ratio crosses the
  threshold.
- **Emergency stop** flips a Redis flag every worker checks each tick, so it
  halts across all pods — even when pressed on a different pod than the runner.
- **Single run** cluster-wide via a Redis lock with a TTL dead-man's switch.

## Files

```
app/
  main.py        FastAPI routes (pages, /ping, SSE, /metrics, admin)
  state.py       Redis-backed shared state (counters, feed, sessions)
  loadtest.py    controlled generator (caps, auto/emergency stop)
  pages.py       dashboard / mobile / admin HTML
  config.py      env-driven settings + hard caps
  logs.py        structured JSON logging
  requirements.txt
  Dockerfile
```
