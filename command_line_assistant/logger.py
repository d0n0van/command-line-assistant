"""Logging configuration for command-line-assistant."""

import logging
import sys
from typing import Optional

# Try to use systemd journal if available
try:
    from systemd import journal
    USE_JOURNAL = True
except ImportError:
    USE_JOURNAL = False
    journal = None


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Get a logger instance for the command-line-assistant.

    Args:
        name: Logger name. If None, uses 'command-line-assistant'.

    Returns:
        Configured logger instance.
    """
    logger_name = name or "command-line-assistant"
    logger = logging.getLogger(logger_name)

    # Only configure if not already configured
    if not logger.handlers:
        logger.setLevel(logging.INFO)

        if USE_JOURNAL:
            handler = journal.JournalHandler()
            handler.setFormatter(
                logging.Formatter("%(name)s: %(levelname)s: %(message)s")
            )
        else:
            handler = logging.StreamHandler(sys.stderr)
            handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                )
            )

        logger.addHandler(handler)

    return logger

