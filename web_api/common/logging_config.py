"""
Logging Configuration Module
Configures structured logging with dynamic Trace ID and User ID tracking using contextvars.
"""
import logging
from contextvars import ContextVar
from typing import Any

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

def setup_logging() -> None:
    """
    Initializes and configures the logging system with a custom formatter and context filters.
    """
    log_format: str = "%(asctime)s [%(levelname)s] [Trace: %(trace_id)s] [User: %(user_id)s] %(name)s: %(message)s"
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Clear existing handlers to prevent duplicate logs in some environments
    if root_logger.hasHandlers():
        root_logger.handlers.clear()
        
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # Custom formatter
    formatter = logging.Formatter(log_format)
    console_handler.setFormatter(formatter)
    
    # Inject ContextFilter
    context_filter = ContextFilter()
    console_handler.addFilter(context_filter)
    
    root_logger.addHandler(console_handler)
    
    # Suppress verbose loggers from libraries if needed
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
