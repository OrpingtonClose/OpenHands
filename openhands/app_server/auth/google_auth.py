"""Google OAuth2 authentication for self-hosted OpenHands."""

import hashlib
import os
import secrets
import time

import jwt
from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.config import Config

GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID', '')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET', '')
GOOGLE_AUTH_SECRET_KEY = os.getenv('GOOGLE_AUTH_SECRET_KEY', secrets.token_hex(32))
GOOGLE_AUTH_ALLOWED_EMAILS = os.getenv('GOOGLE_AUTH_ALLOWED_EMAILS', '')

COOKIE_NAME = 'oh_google_auth'
TOKEN_EXPIRY_SECONDS = 60 * 60 * 24 * 7  # 7 days


def is_google_auth_enabled() -> bool:
    return bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET)


def _get_allowed_emails() -> set[str]:
    if not GOOGLE_AUTH_ALLOWED_EMAILS:
        return set()
    return {
        e.strip().lower() for e in GOOGLE_AUTH_ALLOWED_EMAILS.split(',') if e.strip()
    }


def _create_session_token(user_email: str, user_name: str) -> str:
    payload = {
        'email': user_email,
        'name': user_name,
        'iat': int(time.time()),
        'exp': int(time.time()) + TOKEN_EXPIRY_SECONDS,
    }
    return jwt.encode(payload, GOOGLE_AUTH_SECRET_KEY, algorithm='HS256')


def verify_session_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, GOOGLE_AUTH_SECRET_KEY, algorithms=['HS256'])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None


def _build_oauth() -> OAuth:
    config = Config(
        environ={
            'GOOGLE_CLIENT_ID': GOOGLE_CLIENT_ID,
            'GOOGLE_CLIENT_SECRET': GOOGLE_CLIENT_SECRET,
        }
    )
    oauth = OAuth(config)
    oauth.register(
        name='google',
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_kwargs={'scope': 'openid email profile'},
    )
    return oauth


_oauth: OAuth | None = None


def _get_oauth() -> OAuth:
    global _oauth
    if _oauth is None:
        _oauth = _build_oauth()
    return _oauth


router = APIRouter(prefix='/auth/google', tags=['Google Auth'])


@router.get('/login')
async def google_login(request: Request) -> Response:
    """Redirect to Google OAuth2 consent screen."""
    if not is_google_auth_enabled():
        return JSONResponse(
            status_code=404, content={'error': 'Google auth not configured'}
        )
    oauth = _get_oauth()
    redirect_uri = str(request.url_for('google_callback'))
    # Generate a CSRF state token
    state = hashlib.sha256(secrets.token_bytes(32)).hexdigest()
    request.session['oauth_state'] = state
    return await oauth.google.authorize_redirect(request, redirect_uri, state=state)


@router.get('/callback')
async def google_callback(request: Request) -> Response:
    """Handle Google OAuth2 callback."""
    if not is_google_auth_enabled():
        return JSONResponse(
            status_code=404, content={'error': 'Google auth not configured'}
        )
    oauth = _get_oauth()
    token = await oauth.google.authorize_access_token(request)
    user_info = token.get('userinfo')
    if not user_info:
        return JSONResponse(
            status_code=401, content={'error': 'Failed to get user info'}
        )

    email = user_info.get('email', '').lower()
    name = user_info.get('name', '')

    allowed = _get_allowed_emails()
    if allowed and email not in allowed:
        return JSONResponse(
            status_code=403,
            content={'error': f'Email {email} is not allowed'},
        )

    session_token = _create_session_token(email, name)

    response = RedirectResponse(url='/')
    response.set_cookie(
        key=COOKIE_NAME,
        value=session_token,
        httponly=True,
        samesite='lax',
        max_age=TOKEN_EXPIRY_SECONDS,
        secure=request.url.scheme == 'https',
    )
    return response


@router.post('/logout')
async def google_logout() -> Response:
    """Clear the auth cookie."""
    response = JSONResponse(content={'message': 'Logged out'})
    response.delete_cookie(key=COOKIE_NAME)
    return response


@router.get('/status')
async def google_auth_status(request: Request) -> JSONResponse:
    """Check if the user is authenticated via Google."""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return JSONResponse(status_code=401, content={'authenticated': False})
    claims = verify_session_token(token)
    if not claims:
        return JSONResponse(status_code=401, content={'authenticated': False})
    return JSONResponse(
        content={
            'authenticated': True,
            'email': claims.get('email'),
            'name': claims.get('name'),
        }
    )
