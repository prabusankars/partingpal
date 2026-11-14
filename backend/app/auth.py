import logging

import requests
from fastapi import Header, HTTPException, status
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2 import id_token

from .config import get_settings

log = logging.getLogger(__name__)

_google_request = GoogleRequest(session=requests.Session())


def is_allowed_admin(email: str, hosted_domain: str | None = None) -> bool:
    """Fail closed: with no allowlist configured nobody gets in."""
    s = get_settings()
    email = email.lower()
    domain = email.rsplit("@", 1)[-1]
    if email in s.allowed_emails:
        return True
    return bool(s.allowed_domains) and (domain in s.allowed_domains or (hosted_domain or "").lower() in s.allowed_domains)


def require_admin(
    authorization: str | None = Header(default=None),
    x_auth_token: str | None = Header(default=None),
) -> str:
    """Verify a Google ID token from the HR dashboard and return the admin's email."""
    s = get_settings()
    if s.auth_disabled:
        return "dev@localhost"
    if not s.google_client_id:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Admin sign-in is not configured")
    # The dashboard sends X-Auth-Token; a standard Bearer header works too.
    if x_auth_token:
        token = x_auth_token.strip()
    elif authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
    else:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sign in required")
    try:
        claims = id_token.verify_oauth2_token(token, _google_request, s.google_client_id)
    except ValueError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired, please sign in again")
    email = claims.get("email", "")
    if not email or not claims.get("email_verified"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Google account email is not verified")
    if not is_allowed_admin(email, claims.get("hd")):
        log.warning("Rejected admin sign-in for %s", email)
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This account is not allowed to access HR data")
    return email.lower()
