"""Central configuration — everything tunable via environment variables.

The load-test HARD CAPS are the important safety knobs. A user can request
*less* than these via the admin UI, but never more: the server clamps/rejects
anything above them. They are deliberately modest so the tool stays a "test my
own app and watch it autoscale" toy, not a stress cannon.
"""
import os

# --- Identity / networking ---
# POD_NAME is injected by the Kubernetes Downward API (see app-deployment.yaml).
# Falls back to the OS hostname when run locally.
POD_NAME = os.getenv("POD_NAME") or os.uname().nodename
NAMESPACE = os.getenv("POD_NAMESPACE", "local")
NODE_NAME = os.getenv("NODE_NAME", "local")

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Public base URL the QR code should point phones at (the Ingress/ALB host).
# If unset, the app derives it from the incoming request. No trailing slash.
PUBLIC_URL = os.getenv("PUBLIC_URL", "").rstrip("/")

# Where the in-cluster load generator sends its traffic. HARDCODED to ourselves
# via env — there is no request field that can change this, so the generator can
# only ever hit this app. Default is loopback (the same pod).
SELF_PING_URL = os.getenv("SELF_PING_URL", "http://localhost:8000/ping")

# Admin bearer token for the load-test controls. Supplied via a k8s Secret.
# Empty token => admin actions are disabled (fail closed).
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")

# --- Session tracking ---
SESSION_TTL_SECONDS = int(os.getenv("SESSION_TTL_SECONDS", "30"))

# --- Load-test HARD CAPS (safety ceilings — cannot be exceeded) ---
MAX_RATE = int(os.getenv("LOADTEST_MAX_RATE", "200"))            # requests / second
MAX_CONCURRENCY = int(os.getenv("LOADTEST_MAX_CONCURRENCY", "50"))
MAX_DURATION_SECONDS = int(os.getenv("LOADTEST_MAX_DURATION", "120"))

# Auto-stop if the generator sees more than this fraction of failed requests.
LOADTEST_ERROR_ABORT_RATIO = float(os.getenv("LOADTEST_ERROR_ABORT_RATIO", "0.5"))
# Minimum sample before the error-ratio guard can trip (avoid early false trips).
LOADTEST_ERROR_ABORT_MIN = int(os.getenv("LOADTEST_ERROR_ABORT_MIN", "20"))

# Small artificial latency knob so response-time tiles show something moving.
BASE_LATENCY_MS = float(os.getenv("BASE_LATENCY_MS", "0"))
