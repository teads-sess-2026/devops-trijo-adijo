"""Structured JSON logging to stdout.

One JSON object per line is exactly what Fluent Bit / Promtail want: they ship
each line to CloudWatch / Loki where every field becomes queryable. We never
print free-form text for app events — always a dict with an "event" key.
"""
import json
import logging
import sys
import time

from config import POD_NAME, NAMESPACE, NODE_NAME


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created))
            + f".{int(record.msecs):03d}Z",
            "level": record.levelname,
            "logger": record.name,
            "pod": POD_NAME,
            "namespace": NAMESPACE,
            "node": NODE_NAME,
            "msg": record.getMessage(),
        }
        # Anything passed via logger.info(msg, extra={"fields": {...}}) is merged
        # in at the top level so it is directly filterable in the log backend.
        fields = getattr(record, "fields", None)
        if fields:
            payload.update(fields)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, separators=(",", ":"))


def setup_logging() -> logging.Logger:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(logging.INFO)
    # uvicorn has its own loggers; route them through ours too.
    for name in ("uvicorn", "uvicorn.error"):
        lg = logging.getLogger(name)
        lg.handlers[:] = [handler]
        lg.propagate = False
    return logging.getLogger("pingapp")


def log_event(logger: logging.Logger, event: str, level: int = logging.INFO, **fields):
    """Emit one structured event line."""
    fields["event"] = event
    logger.log(level, event, extra={"fields": fields})
