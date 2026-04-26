"""Minimal auth status endpoints for Cloudflare Access authentication."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from openhands.app_server.auth.google_auth import (
    CF_ACCESS_HEADER,
    is_cloudflare_auth_enabled,
    verify_cf_token,
)

router = APIRouter(prefix='/auth/cf', tags=['Cloudflare Auth'])


@router.get('/status')
async def cf_auth_status(request: Request) -> JSONResponse:
    """Check if the user is authenticated via Cloudflare Access."""
    if not is_cloudflare_auth_enabled():
        return JSONResponse(
            status_code=404,
            content={'error': 'Cloudflare Access auth not configured'},
        )

    token = request.headers.get(CF_ACCESS_HEADER)
    if not token:
        return JSONResponse(status_code=401, content={'authenticated': False})
    claims = verify_cf_token(token)
    if not claims:
        return JSONResponse(status_code=401, content={'authenticated': False})
    return JSONResponse(
        content={
            'authenticated': True,
            'email': claims.get('email', ''),
        }
    )
