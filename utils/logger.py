"""Structured logging for Quick Wins."""

import logging
import sys

_configured = False


def get_logger(name: str = "quickwins") -> logging.Logger:
    """Return a logger with consistent formatting."""
    global _configured
    logger = logging.getLogger(name)

    if not _configured:
        logger.setLevel(logging.DEBUG)
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.DEBUG)
        fmt = logging.Formatter(
            "[%(asctime)s] %(levelname)-7s %(name)s | %(message)s",
            datefmt="%H:%M:%S",
        )
        handler.setFormatter(fmt)
        logger.addHandler(handler)
        _configured = True

    return logger
