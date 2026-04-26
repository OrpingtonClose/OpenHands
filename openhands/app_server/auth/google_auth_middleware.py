"""Middleware to enforce Google OAuth2 authentication on protected routes."""

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from openhands.app_server.auth.google_auth import (
    COOKIE_NAME,
    is_google_auth_enabled,
    verify_session_token,
)

PUBLIC_PATH_PREFIXES = (
    '/api/v1/auth/google/',
    '/api/v1/web-client/config',
    '/api/v1/status',
    '/assets',
    '/favicon',
    '/mcp',
)

PUBLIC_PATHS_EXACT = {
    '/',
    '/login',
    '/health',
}


class GoogleAuthMiddleware(BaseHTTPMiddleware):
    """Returns 401 for protected API routes when Google auth is enabled
    and the request does not carry a valid session cookie."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if not is_google_auth_enabled():
            return await call_next(request)

        path = request.url.path

        if path in PUBLIC_PATHS_EXACT:
            return await call_next(request)

        for prefix in PUBLIC_PATH_PREFIXES:
            if path.startswith(prefix):
                return await call_next(request)

        # Serve static frontend files without auth check
        if not path.startswith('/api/'):
            return await call_next(request)

        token = request.cookies.get(COOKIE_NAME)
        if not token:
            return JSONResponse(
                status_code=401,
                content={'error': 'Authentication required'},
            )

        claims = verify_session_token(token)
        if not claims:
            return JSONResponse(
                status_code=401,
                content={'error': 'Invalid or expired session'},
            )

        return await call_next(request)
