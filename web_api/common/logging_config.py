"""
Logging Configuration Module
Configures structured logging with dynamic Trace ID and User ID tracking using contextvars.
"""
import logging
import os
from contextvars import ContextVar

# Context variables to hold Request Trace ID and User ID throughout the request lifecycle
trace_id_var: ContextVar[str] = ContextVar("trace_id", default="-")
user_id_var: ContextVar[str] = ContextVar("user_id", default="-")

class ContextFilter(logging.Filter):
    """
    logging.Filter that injects trace_id and user_id context variables into every log record.
    """
    def filter(self, record: logging.LogRecord) -> bool:
        record.trace_id = trace_id_var.get()
        record.user_id = user_id_var.get()
        return True


def configured_log_level(value: str | None = None) -> int:
    """Resolve a configured log level without allowing an invalid value to fail startup."""
    level_name = (value if value is not None else os.getenv("LOG_LEVEL", "INFO")).upper()
    level = getattr(logging, level_name, None)
    return level if isinstance(level, int) else logging.INFO


def setup_logging() -> None:
    """
    Initializes and configures the logging system with a custom formatter and context filters.
    """
    log_format: str = "%(asctime)s [%(levelname)s] [Trace: %(trace_id)s] [User: %(user_id)s] %(name)s: %(message)s"
    
    configured_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = configured_log_level(configured_name)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Clear existing handlers to prevent duplicate logs in some environments
    if root_logger.hasHandlers():
        root_logger.handlers.clear()
        
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    
    # Custom formatter
    formatter = logging.Formatter(log_format)
    console_handler.setFormatter(formatter)
    
    # Inject ContextFilter
    context_filter = ContextFilter()
    console_handler.addFilter(context_filter)
    
    root_logger.addHandler(console_handler)

    if level == logging.INFO and configured_name != "INFO":
        root_logger.warning("Geçersiz LOG_LEVEL; INFO seviyesi kullanılıyor")
    
    # Suppress verbose loggers from libraries if needed
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
