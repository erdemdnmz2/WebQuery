"""
Trace Middleware Module
Generates a unique Trace ID for every request, logs request metrics, and exposes the ID in response headers.
"""
import time
import uuid
import logging
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response
from fastapi import Request

from common.logging_config import trace_id_var

logger = logging.getLogger("web_api.trace")

class TraceMiddleware(BaseHTTPMiddleware):
    """
    Middleware that establishes a unique Trace ID (Request ID) for tracking and auditing.
    Logs request initiation, completion duration, and status code.
    """
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # 1. Resolve Trace ID (Check if client/gateway passed X-Request-ID, otherwise generate)
        request_id: str = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        
        # 2. Set Trace ID in contextvars for logging
        trace_token = trace_id_var.set(request_id)
        
        # 3. Log request initiation
        logger.info(f"Request started: {request.method} {request.url.path}")
        
        start_time: float = time.time()
        try:
            response: Response = await call_next(request)
            
            # 4. Measure and log request completion
            process_time: float = (time.time() - start_time) * 1000
            logger.info(
                f"Request completed: {request.method} {request.url.path} - "
                f"Status: {response.status_code} - Duration: {process_time:.2f}ms"
            )
            
            # 5. Expose Trace ID in response headers
            response.headers["X-Request-ID"] = request_id
            return response
        except Exception as e:
            process_time: float = (time.time() - start_time) * 1000
            logger.error(
                f"Request crashed: {request.method} {request.url.path} - "
                f"Error: {type(e).__name__} - Duration: {process_time:.2f}ms",
                exc_info=e
            )
            raise e
        finally:
            # 6. Reset contextvars to prevent memory leaks or context contamination
            trace_id_var.reset(trace_token)
