"""Cloudflare Access authentication for self-hosted OpenHands.

When a Cloudflare Access application is placed in front of OpenHands,
every request carries a signed JWT in the ``Cf-Access-Jwt-Assertion``
header. This module validates that JWT against Cloudflare's public
signing keys and extracts the authenticated user's email.

Required environment variables:
    CF_ACCESS_TEAM_NAME  – your Cloudflare Access team/org name
                           (e.g. ``mycompany`` → keys fetched from
                           ``https://mycompany.cloudflareaccess.com/cdn-cgi/access/certs``)
    CF_ACCESS_AUD        – the Application Audience (AUD) tag from
                           Cloudflare Access (found in the app config)

Optional:
    CF_ACCESS_ALLOWED_EMAILS – comma-separated allowlist of emails.
                               If empty, any Cloudflare-authenticated
                               email is accepted.
"""

import os
import time

import jwt
import requests

CF_ACCESS_TEAM_NAME = os.getenv('CF_ACCESS_TEAM_NAME', '')
CF_ACCESS_AUD = os.getenv('CF_ACCESS_AUD', '')
CF_ACCESS_ALLOWED_EMAILS = os.getenv('CF_ACCESS_ALLOWED_EMAILS', '')

CF_ACCESS_HEADER = 'Cf-Access-Jwt-Assertion'

_cached_public_keys: list | None = None
_keys_fetched_at: float = 0.0
_KEYS_TTL = 3600  # re-fetch keys every hour


def is_cloudflare_auth_enabled() -> bool:
    return bool(CF_ACCESS_TEAM_NAME and CF_ACCESS_AUD)


# Keep the old name as an alias so existing imports still work.
is_google_auth_enabled = is_cloudflare_auth_enabled


def _get_allowed_emails() -> set[str]:
    if not CF_ACCESS_ALLOWED_EMAILS:
        return set()
    return {e.strip().lower() for e in CF_ACCESS_ALLOWED_EMAILS.split(',') if e.strip()}


def _get_public_keys() -> list:
    """Fetch (and cache) Cloudflare Access public signing keys."""
    global _cached_public_keys, _keys_fetched_at

    now = time.time()
    if _cached_public_keys is not None and (now - _keys_fetched_at) < _KEYS_TTL:
        return _cached_public_keys

    certs_url = (
        f'https://{CF_ACCESS_TEAM_NAME}.cloudflareaccess.com/cdn-cgi/access/certs'
    )
    resp = requests.get(certs_url, timeout=10)
    resp.raise_for_status()
    jwks = resp.json()

    keys = []
    for key_data in jwks.get('keys', []):
        keys.append(jwt.algorithms.RSAAlgorithm.from_jwk(key_data))

    _cached_public_keys = keys
    _keys_fetched_at = now
    return keys


def verify_cf_token(token: str) -> dict | None:
    """Validate a Cloudflare Access JWT and return its claims, or None."""
    if not is_cloudflare_auth_enabled():
        return None

    keys = _get_public_keys()
    for key in keys:
        try:
            claims = jwt.decode(
                token,
                key=key,
                audience=CF_ACCESS_AUD,
                algorithms=['RS256'],
            )
            email = claims.get('email', '').lower()
            allowed = _get_allowed_emails()
            if allowed and email not in allowed:
                return None
            return claims
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
            continue
    return None
