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


def _accepted_request_id(raw: str | None) -> str:
    """Return the client's trace id only when it is a well-formed UUID.

    The header used to be trusted verbatim. It flows into `AuditLog.trace_id`,
    a `String(36)` column, so a longer value could fail the audit write outright;
    a repeated or hand-picked value also let a client blend its requests into
    another actor's trail. Anything that is not a UUID is replaced rather than
    rejected, so a malformed header never costs the caller their request.
    """
    if raw:
        candidate = raw.strip()
        try:
            return str(uuid.UUID(candidate))
        except ValueError:
            logger.debug("Geçersiz X-Request-ID biçimi yok sayıldı; yeni iz kimliği üretildi")
    return str(uuid.uuid4())


class TraceMiddleware(BaseHTTPMiddleware):
    """
    Middleware that establishes a unique Trace ID (Request ID) for tracking and auditing.
    Logs request initiation, completion duration, and status code.
    """
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # 1. Resolve Trace ID (accept a client/gateway X-Request-ID only if it is a UUID)
        request_id: str = _accepted_request_id(request.headers.get("X-Request-ID"))
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
