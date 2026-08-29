"""
Authentication Middleware
Her HTTP request için JWT token doğrulama ve session kontrolü yapar
"""
import logging
import os

from fastapi import Request
from fastapi.exceptions import HTTPException
from sqlalchemy import select
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import RedirectResponse
from starlette.responses import Response as StarletteResponse

from app_database.models import User
from authentication.services import get_user_id_from_payload, verify_token
from authentication.sessions import session_alive
from common.logging_config import user_id_var

logger = logging.getLogger(__name__)


class AuthMiddleware(BaseHTTPMiddleware):
    """
    JWT token validation middleware.
    
    For every request:
        1. Public endpoint check (login, register, health)
        2. Retrieves JWT token from access_token cookie
        3. Validates the token
        4. If invalid/missing, responds with 401 (for APIs) or redirects to /login (for web pages)
    """
    
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> StarletteResponse:
        """
        Processes the request, checking authentication.
        
        Args:
            request: The incoming HTTP request.
            call_next: The next middleware/endpoint handler.
        
        Returns:
            StarletteResponse: The HTTP response object.
        """
        skip_auth_paths: list[str] = [
            "/login", 
            "/register", 
            "/api/login", 
            "/api/register",
            "/api/refresh",
            "/health"
        ]
        
        if any(request.url.path.startswith(path) for path in skip_auth_paths):
            return await call_next(request)
        
        token: str | None = request.cookies.get("access_token")
        if not token:
            if request.url.path.startswith("/api/"):
                return StarletteResponse(
                    content='{"detail":"Token required"}',
                    status_code=401,
                    media_type="application/json"
                )
            return RedirectResponse(url="/login", status_code=302)
        try:
            payload: dict | None = verify_token(token)
            if not payload:
                raise HTTPException(status_code=401, detail="Invalid token")
            user_id: str | None = get_user_id_from_payload(payload=payload)
            if not user_id:
                raise HTTPException(status_code=401, detail="Invalid token")
                
            # Check JTI blacklist
            jti = payload.get("jti")
            if jti:
                app_db = request.app.state.context.app_db
                is_blacklisted = await app_db.is_token_blacklisted(jti)
                if is_blacklisted:
                    raise HTTPException(status_code=401, detail="Token has been revoked")
            session_id = payload.get("sid")
            if session_id is not None:
                app_db = request.app.state.context.app_db
                if not await session_alive(app_db, int(session_id), int(user_id)):
                    raise HTTPException(status_code=401, detail="Session has been revoked")

            # The middleware already has the user ID from the JWT. Load the
            # complete user once so account disablement takes effect before
            # any endpoint handler runs. The dependency reuses this object.
            app_db = request.app.state.context.app_db
            try:
                user_id_int = int(user_id)
            except (TypeError, ValueError) as exc:
                raise HTTPException(status_code=401, detail="Invalid token") from exc

            async with app_db.get_app_db() as db:
                result = await db.execute(select(User).where(User.id == user_id_int))
                authenticated_user = result.scalars().first()

            if authenticated_user is None or not authenticated_user.is_active:
                raise HTTPException(status_code=401, detail="Invalid token")

            request.state.authenticated_user = authenticated_user
        except Exception as exc:
            logger.warning("Kimlik doğrulama reddedildi: %s", type(exc).__name__)
            if request.url.path.startswith("/api/"):
                return StarletteResponse(
                    content='{"detail":"Invalid token"}',
                    status_code=401,
                    media_type="application/json"
                )
            response: RedirectResponse = RedirectResponse(url="/login", status_code=302)
            response.delete_cookie(
                key="access_token",
                secure=os.getenv("COOKIE_SECURE", "False").lower() == "true",
                samesite="strict",
                httponly=True
            )
            return response
        
        user_token = None
        if user_id:
            request.state.user_id = user_id
            user_token = user_id_var.set(user_id)
        
        try:
            response: StarletteResponse = await call_next(request)
            return response
        finally:
            if user_token:
                user_id_var.reset(user_token)
