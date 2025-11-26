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


# Global debug flag
_debug_mode = False


def set_debug_mode(enabled: bool) -> None:
    """
    Enable or disable debug mode globally.

    Args:
        enabled: Whether to enable debug mode.
    """
    global _debug_mode
    _debug_mode = enabled
    # Update all existing loggers
    for logger_name in logging.Logger.manager.loggerDict:
        logger = logging.getLogger(logger_name)
        if logger.handlers:
            logger.setLevel(logging.DEBUG if enabled else logging.INFO)


def is_debug_mode() -> bool:
    """
    Check if debug mode is enabled.

    Returns:
        True if debug mode is enabled, False otherwise.
    """
    return _debug_mode


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
        logger.setLevel(logging.DEBUG if _debug_mode else logging.INFO)

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

