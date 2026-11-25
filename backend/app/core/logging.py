"""Controlled logging with automatic secret redaction."""

from collections.abc import Mapping
import logging
import re
from typing import Pattern

_SECRET_PATTERNS: tuple[Pattern[str], ...] = (
    re.compile(r"AIza[0-9A-Za-z\-_]{20,}"),
    re.compile(r"sk-[0-9A-Za-z]{20,}"),
    re.compile(r"(?i)(api_key|token|secret|password|authorization)\s*[:=]\s*['\"]?[^\s'\",&]+"),
    re.compile(r"(?i)Bearer\s+[A-Za-z0-9\-._~+/]+=*"),
)


def redact_secrets(text: str) -> str:
    """Scrub potential credential tokens or keys before logging."""
    redacted = text
    for pat in _SECRET_PATTERNS:
        redacted = pat.sub("[REDACTED_SECRET]", redacted)
    return redacted


class SecretRedactingFilter(logging.Filter):
    """Logging filter that strips credential substrings from log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact_secrets(record.msg)
        if isinstance(record.args, Mapping):
            record.args = {
                k: redact_secrets(v) if isinstance(v, str) else v
                for k, v in record.args.items()
            }
        elif record.args:
            cleaned = []
            for arg in record.args:
                cleaned.append(redact_secrets(arg) if isinstance(arg, str) else arg)
            record.args = tuple(cleaned)
        return True


def get_logger(name: str) -> logging.Logger:
    """Return a consistently formatted logger with secret redaction enabled."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%SZ",
        )
        handler.setFormatter(formatter)
        handler.addFilter(SecretRedactingFilter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger
