"""
Authentication Middleware
Her HTTP request için JWT token doğrulama ve session kontrolü yapar
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import Response as StarletteResponse
from starlette.responses import RedirectResponse
from fastapi import Request
from authentication.services import verify_token, get_user_id_from_payload
from dependencies import get_session_cache
from fastapi.exceptions import HTTPException

class AuthMiddleware(BaseHTTPMiddleware):
    """
    JWT token ve session doğrulama middleware'i
    
    Her request'te:
        1. Public endpoint kontrolü (login, register)
        2. Cookie'den JWT token alınır
        3. Token doğrulanır
        4. Session geçerliliği kontrol edilir
        5. Token/session geçersizse redirect veya 401 döner
    
    Public Endpoints (authentication bypass):
        - /login, /register
        - /api/login, /api/register
    
    Error Handling:
        - API endpoint'leri: 401 JSON response
        - Web sayfaları: /login'e redirect (cookie silme ile)
    """
    
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> StarletteResponse:
        """
        Request'i işler, authentication kontrolü yapar
        
        Args:
            request: Gelen HTTP request
            call_next: Sonraki middleware/endpoint handler
        
        Returns:
            StarletteResponse: Response nesnesi
        
        Flow:
            1. Public endpoint ise -> direkt geç
            2. Token yoksa -> 401 veya redirect
            3. Token geçersizse -> 401 veya redirect (cookie sil)
            4. Session expired ise -> 401 veya redirect
            5. Her şey OK ise -> next middleware/handler
        """
        skip_auth_paths = [
            "/login", 
            "/register", 
            "/api/login", 
            "/api/register"
        ]
        
        if any(request.url.path.startswith(path) for path in skip_auth_paths):
            return await call_next(request)
        
        # Token'ı sadece cookie'den al
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
                user_id = get_user_id_from_payload(payload=payload)
                if not user_id:
                    raise HTTPException(status_code=401, detail="Invalid token")
                session_cache = get_session_cache(request)
                from authentication import config
                if not session_cache.is_valid(int(user_id), timeout_minutes=config.SESSION_TIMEOUT):
                    session_cache.remove(int(user_id))
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