# """
# LinkedIn OAuth routes.

# Flow:
#   GET /auth/linkedin          → redirect user to LinkedIn login
#   GET /auth/linkedin/callback → exchange code for token, store in session
#   GET /auth/me                → return current user info
#   GET /auth/logout            → clear session
# """

# import secrets
# from fastapi import APIRouter, Request, HTTPException
# from fastapi.responses import RedirectResponse, JSONResponse

# from app.services.linkedin import get_auth_url, exchange_code_for_token, get_user_info
# from app.config import settings

# router = APIRouter(prefix="/auth", tags=["auth"])


# # ---------------------------------------------------------------------------
# # Helpers
# # ---------------------------------------------------------------------------

# def get_session(request: Request) -> dict:
#     return request.session


# def set_auth(request: Request, token_data: dict, user_info: dict):
#     request.session["access_token"]  = token_data["access_token"]
#     request.session["expires_in"]    = token_data.get("expires_in", 5183944)
#     request.session["linkedin_sub"]  = user_info.get("sub", "")
#     request.session["author_urn"]    = user_info.get("author_urn", "")
#     request.session["name"]          = user_info.get("name", "")
#     request.session["email"]         = user_info.get("email", "")
#     request.session["picture"]       = user_info.get("picture", "")


# def require_auth(request: Request) -> str:
#     """Return access_token or raise 401."""
#     token = request.session.get("access_token")
#     if not token:
#         raise HTTPException(status_code=401, detail="Not authenticated. Visit /auth/linkedin to connect.")
#     return token


# # ---------------------------------------------------------------------------
# # Routes
# # ---------------------------------------------------------------------------

# @router.get("/linkedin")
# async def linkedin_login(request: Request):
#     """Redirect user to LinkedIn OAuth consent screen."""
#     state = secrets.token_urlsafe(16)
#     request.session["oauth_state"] = state
#     return RedirectResponse(get_auth_url(state))


# @router.get("/linkedin/callback")
# async def linkedin_callback(request: Request, code: str = "", state: str = "", error: str = ""):
#     """Handle LinkedIn OAuth callback."""

#     # User denied access
#     if error:
#         return RedirectResponse(f"{settings.FRONTEND_URL}?auth_error={error}")

#     # Validate state to prevent CSRF
#     stored_state = request.session.pop("oauth_state", None)
#     if not stored_state or stored_state != state:
#         raise HTTPException(status_code=400, detail="Invalid OAuth state. Possible CSRF attack.")

#     if not code:
#         raise HTTPException(status_code=400, detail="No authorization code received.")

#     # Exchange code for token
#     try:
#         token_data = await exchange_code_for_token(code)
#     except Exception as e:
#         raise HTTPException(status_code=400, detail=f"Token exchange failed: {e}")

#     # Fetch user info
#     try:
#         user_info = await get_user_info(token_data["access_token"])
#     except Exception as e:
#         raise HTTPException(status_code=400, detail=f"Failed to fetch user info: {e}")

#     # Store in session
#     set_auth(request, token_data, user_info)

#     return RedirectResponse(f"{settings.FRONTEND_URL}?auth=success")


# @router.get("/me")
# async def get_me(request: Request):
#     """Return current authenticated user info."""
#     token = request.session.get("access_token")
#     if not token:
#         return JSONResponse({"authenticated": False})

#     return JSONResponse({
#         "authenticated": True,
#         "name":          request.session.get("name", ""),
#         "email":         request.session.get("email", ""),
#         "picture":       request.session.get("picture", ""),
#         "author_urn":    request.session.get("author_urn", ""),
#     })


# @router.get("/logout")
# async def logout(request: Request):
#     """Clear session and redirect to frontend."""
#     request.session.clear()
#     return RedirectResponse(f"{settings.FRONTEND_URL}?auth=logout")

"""
LinkedIn OAuth routes — token-based auth (no cookies).

Flow:
  GET /auth/linkedin           → redirect to LinkedIn login
  GET /auth/linkedin/callback  → exchange code, return token in redirect
  GET /auth/me                 → validate token, return user info
  GET /auth/logout             → client-side only (clear localStorage)
"""

import json
import secrets
import base64
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse

from app.services.linkedin import get_auth_url, exchange_code_for_token, get_user_info
from app.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])

# In-memory token store — maps token → user data
# For production, use Redis or Supabase
_token_store: dict[str, dict] = {}


def create_token(user_data: dict) -> str:
    token = secrets.token_urlsafe(32)
    _token_store[token] = user_data
    return token


def get_user_from_token(token: str) -> dict | None:
    return _token_store.get(token)


def require_auth(request: Request) -> tuple[str, str]:
    """Extract and validate Bearer token. Returns (token, author_urn)."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated.")
    token = auth_header.replace("Bearer ", "").strip()
    user = get_user_from_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")
    return token, user


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/linkedin")
async def linkedin_login(request: Request):
    state = secrets.token_urlsafe(16)
    request.session["oauth_state"] = state
    return RedirectResponse(get_auth_url(state))


@router.get("/linkedin/callback")
async def linkedin_callback(
    request: Request,
    code: str = "",
    state: str = "",
    error: str = "",
):
    if error:
        return RedirectResponse(f"{settings.FRONTEND_URL}?auth_error={error}")

    stored_state = request.session.pop("oauth_state", None)
    if not stored_state or stored_state != state:
        raise HTTPException(status_code=400, detail="Invalid OAuth state.")

    if not code:
        raise HTTPException(status_code=400, detail="No authorization code received.")

    try:
        token_data = await exchange_code_for_token(code)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Token exchange failed: {e}")

    try:
        user_info = await get_user_info(token_data["access_token"])
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch user info: {e}")

    # Store full user data including LinkedIn access token
    user_data = {
        "access_token":  token_data["access_token"],
        "author_urn":    user_info.get("author_urn", ""),
        "name":          user_info.get("name", ""),
        "email":         user_info.get("email", ""),
        "picture":       user_info.get("picture", ""),
        "authenticated": True,
    }

    app_token = create_token(user_data)

    # Redirect to frontend with token in URL — frontend stores in localStorage
    return RedirectResponse(
        f"{settings.FRONTEND_URL}?auth=success&token={app_token}"
    )


@router.get("/me")
async def get_me(request: Request):
    """Validate token and return user info."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return JSONResponse({"authenticated": False})

    token = auth_header.replace("Bearer ", "").strip()
    user  = get_user_from_token(token)

    if not user:
        return JSONResponse({"authenticated": False})

    return JSONResponse({
        "authenticated": True,
        "name":          user.get("name", ""),
        "email":         user.get("email", ""),
        "picture":       user.get("picture", ""),
        "author_urn":    user.get("author_urn", ""),
    })


@router.get("/logout")
async def logout(request: Request):
    """Token logout — frontend clears localStorage."""
    return JSONResponse({"success": True})