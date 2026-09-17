"""Custom logging configuration with formatted timestamps."""

import logging
import sys
from typing import Optional


class CustomFormatter(logging.Formatter):
    """Format log messages with [HH:MM:SS] [LEVEL] message."""

    def format(self, record: logging.LogRecord) -> str:
        time_str = self.formatTime(record, "%H:%M:%S")
        record.asctime = f"[{time_str}]"
        # Optional color or clean level
        level_str = record.levelname
        msg = record.getMessage()
        if level_str in ("WARNING", "ERROR", "CRITICAL"):
            return f"[{time_str}] [{level_str}] {msg}"
        return f"[{time_str}] {msg}"


def setup_logger(name: str = "senac_monitor", level: str = "INFO") -> logging.Logger:
    """Configures and returns the main application logger."""
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Avoid duplicate handlers if already configured
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(getattr(logging, level.upper(), logging.INFO))
        formatter = CustomFormatter()
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    logger.propagate = False
    return logger


logger = setup_logger()
