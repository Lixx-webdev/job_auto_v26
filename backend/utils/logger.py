from __future__ import annotations

import logging
import sys

import structlog

from backend.config import get_settings


def _configure_structlog() -> None:
    """Configure structlog once per process."""
    settings = get_settings()
    is_production = settings.LOG_LEVEL.upper() not in ("DEBUG",)

    shared_processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if is_production:
        # JSON output for log aggregation (e.g. Cloud Logging, Datadog)
        renderer = structlog.processors.JSONRenderer()
    else:
        # Human-friendly coloured output for local development
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
        foreign_pre_chain=shared_processors,
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(settings.LOG_LEVEL.upper())
    # Per-request HTTP lines drown out the useful logs; only show them at DEBUG.
    if settings.LOG_LEVEL.upper() != "DEBUG":
        for noisy in ("httpx", "httpx2", "httpcore"):
            logging.getLogger(noisy).setLevel(logging.WARNING)


# Configure once at import time
_configure_structlog()


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a structlog logger bound to *name*.

    Usage::

        logger = get_logger(__name__)
        logger.info("job_scraped", job_id=42, platform="linkedin")
    """
    return structlog.get_logger(name)
