"""
Trace Middleware Module
Generates a unique Trace ID for every request, logs request metrics, and exposes the ID in response headers.
"""
import logging
import time
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

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
        logger.info("İstek başladı: %s %s", request.method, request.url.path)
        
        start_time: float = time.time()
        try:
            response: Response = await call_next(request)
            
            # 4. Measure and log request completion
            process_time: float = (time.time() - start_time) * 1000
            logger.info(
                "İstek tamamlandı: %s %s - durum: %d - süre: %.2fms",
                request.method,
                request.url.path,
                response.status_code,
                process_time,
            )
            
            # 5. Expose Trace ID in response headers
            response.headers["X-Request-ID"] = request_id
            return response
        except Exception as exc:
            process_time: float = (time.time() - start_time) * 1000
            logger.error(
                "İstek başarısız oldu: %s %s - hata: %s - süre: %.2fms",
                request.method,
                request.url.path,
                type(exc).__name__,
                process_time,
            )
            raise
        finally:
            # 6. Reset contextvars to prevent memory leaks or context contamination
            trace_id_var.reset(trace_token)
