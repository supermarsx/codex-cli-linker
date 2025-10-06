"""Logging configuration helpers (human + JSON + remote HTTP).

This module centralizes lightweight logging setup for the CLI:
 - Plain human-readable logs to stderr
 - Optional JSON logs to stdout (for piping/collection)
 - Optional file logs
 - Optional remote HTTP logs via a small buffered async handler

Design goals
 - No third‑party dependencies; stdlib logging only
 - Idempotent configuration for tests and repeated calls
 - Never block normal CLI flow on network issues or handler errors
"""

from __future__ import annotations
import json
import logging
import logging.handlers
import os
import sys
import urllib.parse
from typing import Optional


def configure_logging(
    verbose: bool,
    log_file: Optional[str] = None,
    log_json: bool = False,
    log_remote: Optional[str] = None,
    log_level: Optional[str] = None,
) -> None:
    """Configure the root logger according to CLI flags.

    Parameters
    - ``verbose``: When ``True``, sets level to ``DEBUG`` (unless ``log_level``
      overrides). Otherwise defaults to ``WARNING``.
    - ``log_file``: Optional path to tee logs to a file (plain text format).
    - ``log_json``: When ``True``, also emit JSON lines to stdout.
    - ``log_remote``: Optional URL to POST logs to (http/https). Emission is
      buffered and non-blocking.
    - ``log_level``: Optional explicit level name (debug, info, warning, error).

    Behavior
    - Removes any handlers previously added by this function to avoid
      duplicates across repeated invocations (common in tests).
    - Adds a plain stream handler to stderr, and optionally JSON, file, and
      remote HTTP handlers. Network failures are swallowed.
    """

    # Determine base level
    if log_level:
        ll = log_level.lower()
        level = {
            "debug": logging.DEBUG,
            "info": logging.INFO,
            "warning": logging.WARNING,
            "error": logging.ERROR,
        }.get(ll, logging.WARNING)
    else:
        level = logging.DEBUG if verbose else logging.WARNING

    logger = logging.getLogger()
    logger.setLevel(level)

    # Remove handlers added by previous configure_logging calls
    for h in list(logger.handlers):
        if getattr(h, "_added_by_configure_logging", False):
            logger.removeHandler(h)
            h.close()

    fmt = "%(levelname)s: %(message)s"
    stream = logging.StreamHandler()
    stream.setFormatter(logging.Formatter(fmt))
    setattr(stream, "_added_by_configure_logging", True)
    logger.addHandler(stream)

    if log_json:

        class JSONFormatter(logging.Formatter):
            """Minimal JSON formatter for structured log collection.

            Emits an object with ``level`` and ``message`` plus optional
            structured fields (``event``, ``provider``, ``model``, ``path``,
            ``duration_ms``, ``error_type``) when set via ``extra=...``.
            """

            def format(self, record):
                payload = {
                    "level": record.levelname,
                    "message": record.getMessage(),
                }
                # Include structured fields when provided
                for k in (
                    "event",
                    "provider",
                    "model",
                    "path",
                    "duration_ms",
                    "error_type",
                ):
                    if hasattr(record, k):
                        payload[k] = getattr(record, k)
                return json.dumps(payload)

        json_handler = logging.StreamHandler(sys.stdout)
        json_handler.setFormatter(JSONFormatter())
        setattr(json_handler, "_added_by_configure_logging", True)
        logger.addHandler(json_handler)

    if log_file:
        fh = logging.FileHandler(log_file)
        fh.setFormatter(logging.Formatter(fmt))
        setattr(fh, "_added_by_configure_logging", True)
        logger.addHandler(fh)

    if log_remote:
        parsed = urllib.parse.urlparse(log_remote)
        host = parsed.netloc
        url = parsed.path or "/"
        if parsed.query:
            url += "?" + parsed.query
        secure = parsed.scheme == "https"

        # Inner HTTP handler (sync); we will wrap with an async buffer.
        inner = logging.handlers.HTTPHandler(host, url, method="POST", secure=secure)

        class BufferedAsyncHandler(logging.Handler):
            """Non-blocking wrapper that ships records to an inner handler.

            Uses a background thread and a bounded queue to avoid blocking the
            main thread. When ``PYTEST_CURRENT_TEST`` is present, emits
            synchronously for deterministic unit tests.
            """

            def __init__(self, inner_handler: logging.Handler, maxsize: int = 256):
                super().__init__()
                import threading
                import queue

                self.inner = inner_handler
                self.q: "queue.Queue[logging.LogRecord]" = queue.Queue(maxsize=maxsize)
                self._stop = threading.Event()
                self._drops = 0
                self._cv = threading.Condition()

                def worker():
                    while True:
                        with self._cv:
                            while self.q.empty() and not self._stop.is_set():
                                self._cv.wait()
                            if self._stop.is_set() and self.q.empty():
                                break
                        try:
                            rec = self.q.get(block=False)
                        except Exception:
                            continue
                        try:
                            self.inner.emit(rec)
                        except Exception:  # pragma: no cover
                            # Swallow network errors; avoid breaking CLI
                            pass
                        finally:
                            try:
                                self.q.task_done()
                            except Exception:
                                pass

                self._t = threading.Thread(
                    target=worker, name="log-http-worker", daemon=True
                )
                self._t.start()

            def emit(self, record: logging.LogRecord) -> None:
                # In test environments, emit synchronously for determinism
                if os.environ.get("PYTEST_CURRENT_TEST"):
                    try:
                        self.inner.emit(record)
                    except Exception:
                        pass
                    return
                # Non-blocking enqueue. If full, drop oldest and try once more.
                with self._cv:
                    try:
                        self.q.put_nowait(record)
                    except Exception:
                        try:
                            _ = self.q.get_nowait()
                            self._drops += 1
                            self.q.put_nowait(record)
                        except Exception:
                            # queue still full; drop this record
                            self._drops += 1
                    self._cv.notify()

            def close(self) -> None:
                try:
                    self._stop.set()
                    with self._cv:
                        self._cv.notify_all()
                    # Give the worker a brief moment to drain
                    try:
                        self.q.join()
                    except Exception:
                        pass
                except Exception:
                    pass
                try:
                    self.inner.close()
                except Exception:
                    pass
                super().close()

        http_handler = BufferedAsyncHandler(inner)
        setattr(http_handler, "_added_by_configure_logging", True)
        logger.addHandler(http_handler)

    for handler in logger.handlers:
        handler.setLevel(level)


def log_event(event: str, level: int = logging.INFO, **fields) -> None:
    """Emit a structured event log at the given level.

    Common ``fields`` include ``provider``, ``model``, ``path``,
    ``duration_ms``, and ``error_type``. The function never raises.
    """
    try:
        logging.getLogger().log(level, event, extra={"event": event, **fields})
    except Exception:
        # Never let logging break CLI flow
        pass


# =============== Optional keychain storage (never required) ===============


__all__ = ["configure_logging", "log_event"]
