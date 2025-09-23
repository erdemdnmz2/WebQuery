from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import Response as StarletteResponse
from starlette.responses import RedirectResponse
from fastapi import Request
from auth import verify_token, get_user_id, is_session_valid
from fastapi.exceptions import HTTPException
from database import session_cache

class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> StarletteResponse:
        skip_auth_paths = [
            "/login", 
            "/register", 
            "/api/login", 
            "/api/register"
        ]
        
        if any(request.url.path.startswith(path) for path in skip_auth_paths):
            return await call_next(request)
        
        token = request.cookies.get("access_token")
        if not token:
            if request.url.path.startswith("/api/"):
                return StarletteResponse(
                    content='{"detail":"Token required"}',
                    status_code=401,
                    media_type="application/json"
                )
            return RedirectResponse(url="/login", status_code=302)
        try:
            payload = verify_token(token)
            if not payload:
                raise HTTPException(status_code=401, detail="Invalid token")
            user_id = int(get_user_id(payload=payload))
            if not user_id:
                raise HTTPException(status_code=401, detail="Invalid token")
            if not is_session_valid(user_id=user_id):
                session_cache.pop(user_id)
                raise HTTPException(status_code=401, detail="Invalid session")
        except Exception as e:
            print(e)
            if request.url.path.startswith("/api/"):
                return StarletteResponse(
                    content='{"detail":"Invalid token"}',
                    status_code=401,
                    media_type="application/json"
                )
            response = RedirectResponse(url="/login", status_code=302)
            response.delete_cookie(
                key="access_token",
                secure=False,
                samesite="strict",
                httponly=True
            )
            return response
        
        response = await call_next(request)
        return response