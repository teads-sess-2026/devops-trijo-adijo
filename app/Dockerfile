# Ping traffic-generation app image.
# Small, non-root, single stage — plenty for a workshop service.

FROM python:3.12-slim

# Don't buffer stdout: we want structured JSON logs to reach the log pipeline
# (Fluent Bit / Promtail) immediately, not on process exit.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install deps first so the layer caches across code changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code.
COPY . .

# Run as an unprivileged user (defence in depth; also required by our
# securityContext runAsNonRoot in the Deployment).
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin appuser
USER 10001

EXPOSE 8000

# One worker: all shared state lives in Redis, and we scale by adding PODS
# (HPA), not threads. A single uvicorn worker keeps per-pod behaviour simple
# and the "which pod served this" story honest.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
