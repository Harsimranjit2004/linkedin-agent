"""
LinkedIn OAuth routes.

Flow:
  GET /auth/linkedin          → redirect user to LinkedIn login
  GET /auth/linkedin/callback → exchange code for token, store in session
  GET /auth/me                → return current user info
  GET /auth/logout            → clear session
"""

import secrets
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse

from app.services.linkedin import get_auth_url, exchange_code_for_token, get_user_info
from app.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_session(request: Request) -> dict:
    return request.session


def set_auth(request: Request, token_data: dict, user_info: dict):
    request.session["access_token"]  = token_data["access_token"]
    request.session["expires_in"]    = token_data.get("expires_in", 5183944)
    request.session["linkedin_sub"]  = user_info.get("sub", "")
    request.session["author_urn"]    = user_info.get("author_urn", "")
    request.session["name"]          = user_info.get("name", "")
    request.session["email"]         = user_info.get("email", "")
    request.session["picture"]       = user_info.get("picture", "")


def require_auth(request: Request) -> str:
    """Return access_token or raise 401."""
    token = request.session.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated. Visit /auth/linkedin to connect.")
    return token


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/linkedin")
async def linkedin_login(request: Request):
    """Redirect user to LinkedIn OAuth consent screen."""
    state = secrets.token_urlsafe(16)
    request.session["oauth_state"] = state
    return RedirectResponse(get_auth_url(state))


@router.get("/linkedin/callback")
async def linkedin_callback(request: Request, code: str = "", state: str = "", error: str = ""):
    """Handle LinkedIn OAuth callback."""

    # User denied access
    if error:
        return RedirectResponse(f"{settings.FRONTEND_URL}?auth_error={error}")

    # Validate state to prevent CSRF
    stored_state = request.session.pop("oauth_state", None)
    if not stored_state or stored_state != state:
        raise HTTPException(status_code=400, detail="Invalid OAuth state. Possible CSRF attack.")

    if not code:
        raise HTTPException(status_code=400, detail="No authorization code received.")

    # Exchange code for token
    try:
        token_data = await exchange_code_for_token(code)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Token exchange failed: {e}")

    # Fetch user info
    try:
        user_info = await get_user_info(token_data["access_token"])
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch user info: {e}")

    # Store in session
    set_auth(request, token_data, user_info)

    return RedirectResponse(f"{settings.FRONTEND_URL}?auth=success")


@router.get("/me")
async def get_me(request: Request):
    """Return current authenticated user info."""
    token = request.session.get("access_token")
    if not token:
        return JSONResponse({"authenticated": False})

    return JSONResponse({
        "authenticated": True,
        "name":          request.session.get("name", ""),
        "email":         request.session.get("email", ""),
        "picture":       request.session.get("picture", ""),
        "author_urn":    request.session.get("author_urn", ""),
    })


@router.get("/logout")
async def logout(request: Request):
    """Clear session and redirect to frontend."""
    request.session.clear()
    return RedirectResponse(f"{settings.FRONTEND_URL}?auth=logout")