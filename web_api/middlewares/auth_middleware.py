"""
Authentication Middleware
Her HTTP request için JWT token doğrulama ve session kontrolü yapar
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import Response as StarletteResponse
from starlette.responses import RedirectResponse
from fastapi import Request
import os
from authentication.services import verify_token, get_user_id_from_payload
from fastapi.exceptions import HTTPException

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
        except Exception as e:
            print(f"Auth verification failed: {e}")
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
        
        response: StarletteResponse = await call_next(request)
        return response