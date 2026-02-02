"""
Logging configuration for Job Applier API.
Provides structured logging with proper formatting.
"""

import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from datetime import datetime

# Log directory
LOG_DIR = Path(os.getenv("LOG_DIR", Path(__file__).parent.parent / "logs"))
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Log level from environment
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()


class ColoredFormatter(logging.Formatter):
    """Custom formatter with colors for console output."""

    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
    }
    RESET = '\033[0m'

    def format(self, record):
        color = self.COLORS.get(record.levelname, self.RESET)
        record.levelname = f"{color}{record.levelname}{self.RESET}"
        return super().format(record)


def setup_logging(name: str = "job_applier") -> logging.Logger:
    """
    Setup and return a configured logger.

    Args:
        name: Logger name (default: job_applier)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)

    # Avoid duplicate handlers
    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

    # Console handler with colors
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_format = ColoredFormatter(
        '%(asctime)s | %(levelname)s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)

    # File handler with rotation
    file_handler = RotatingFileHandler(
        LOG_DIR / f"{name}.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5
    )
    file_handler.setLevel(logging.DEBUG)
    file_format = logging.Formatter(
        '%(asctime)s | %(levelname)s | %(name)s | %(funcName)s:%(lineno)d | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_format)
    logger.addHandler(file_handler)

    # Error file handler (errors and above)
    error_handler = RotatingFileHandler(
        LOG_DIR / f"{name}_errors.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(file_format)
    logger.addHandler(error_handler)

    return logger


# Create default logger
logger = setup_logging()


def log_request(method: str, path: str, user_id: str = None, status_code: int = None, duration_ms: float = None):
    """Log an HTTP request."""
    extra = {
        "method": method,
        "path": path,
        "user_id": user_id,
        "status_code": status_code,
        "duration_ms": duration_ms
    }
    logger.info(f"HTTP {method} {path} -> {status_code} ({duration_ms:.2f}ms)" if duration_ms else f"HTTP {method} {path}")


def log_application(app_id: str, user_id: str, job_url: str, status: str, error: str = None):
    """Log an application event."""
    if error:
        logger.error(f"Application {app_id} failed: {error}", extra={"user_id": user_id, "job_url": job_url})
    else:
        logger.info(f"Application {app_id} -> {status}", extra={"user_id": user_id, "job_url": job_url})


def log_ai_request(service: str, operation: str, tokens: int = None, cost: float = None, error: str = None):
    """Log an AI service request."""
    if error:
        logger.error(f"AI {service}.{operation} failed: {error}")
    else:
        logger.info(f"AI {service}.{operation} completed (tokens: {tokens}, cost: ${cost:.4f})" if cost else f"AI {service}.{operation} completed")


def log_browser_event(session_id: str, event: str, details: str = None):
    """Log a browser automation event."""
    logger.debug(f"Browser [{session_id}] {event}: {details}" if details else f"Browser [{session_id}] {event}")
