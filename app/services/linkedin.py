# """
# LinkedIn API service — OAuth 2.0 + Share on LinkedIn.

# Scopes:  w_member_social, openid, profile, email
# Products: Share on LinkedIn | Sign In with LinkedIn using OpenID Connect
# """

# import httpx
# from urllib.parse import urlencode
# from app.config import settings

# # ---------------------------------------------------------------------------
# # Constants
# # ---------------------------------------------------------------------------

# AUTH_URL     = "https://www.linkedin.com/oauth/v2/authorization"
# TOKEN_URL    = "https://www.linkedin.com/oauth/v2/accessToken"
# USERINFO_URL = "https://api.linkedin.com/v2/userinfo"
# POSTS_URL    = "https://api.linkedin.com/v2/posts"
# ASSETS_URL   = "https://api.linkedin.com/v2/assets?action=registerUpload"

# SCOPES = "openid profile email w_member_social"


# # ---------------------------------------------------------------------------
# # OAuth
# # ---------------------------------------------------------------------------

# def get_auth_url(state: str) -> str:
#     """Build the LinkedIn authorization redirect URL."""
#     params = {
#         "response_type": "code",
#         "client_id": settings.LINKEDIN_CLIENT_ID,
#         "redirect_uri": settings.LINKEDIN_REDIRECT_URI,
#         "state": state,
#         "scope": SCOPES,
#     }
#     return f"{AUTH_URL}?{urlencode(params)}"


# async def exchange_code_for_token(code: str) -> dict:
#     """Exchange an auth code for an access + refresh token."""
#     async with httpx.AsyncClient() as client:
#         resp = await client.post(
#             TOKEN_URL,
#             data={
#                 "grant_type": "authorization_code",
#                 "code": code,
#                 "redirect_uri": settings.LINKEDIN_REDIRECT_URI,
#                 "client_id": settings.LINKEDIN_CLIENT_ID,
#                 "client_secret": settings.LINKEDIN_CLIENT_SECRET,
#             },
#             headers={"Content-Type": "application/x-www-form-urlencoded"},
#         )
#         resp.raise_for_status()
#         return resp.json()


# async def get_user_info(access_token: str) -> dict:
#     """
#     Fetch the authenticated user's LinkedIn profile.
#     'sub' field = LinkedIn person URN (urn:li:person:XXXXX)
#     """
#     async with httpx.AsyncClient() as client:
#         resp = await client.get(
#             USERINFO_URL,
#             headers={"Authorization": f"Bearer {access_token}"},
#         )
#         resp.raise_for_status()
#         data = resp.json()
#         # Normalize sub → full URN
#         if "sub" in data and not data["sub"].startswith("urn:"):
#             data["author_urn"] = f"urn:li:person:{data['sub']}"
#         else:
#             data["author_urn"] = data.get("sub", "")
#         return data


# # ---------------------------------------------------------------------------
# # Text post
# # ---------------------------------------------------------------------------

# async def post_text(access_token: str, author_urn: str, text: str) -> dict:
#     """Post a plain-text share to LinkedIn."""
#     payload = {
#         "author": author_urn,
#         "commentary": text,
#         "visibility": "PUBLIC",
#         "distribution": {
#             "feedDistribution": "MAIN_FEED",
#             "targetEntities": [],
#             "thirdPartyDistributionChannels": [],
#         },
#         "lifecycleState": "PUBLISHED",
#         "isReshareDisabledByAuthor": False,
#     }
#     return await _post(access_token, payload)


# # ---------------------------------------------------------------------------
# # Image post
# # ---------------------------------------------------------------------------

# async def upload_image(access_token: str, author_urn: str, image_bytes: bytes) -> str:
#     """Upload an image to LinkedIn and return the asset URN."""
#     async with httpx.AsyncClient() as client:
#         # Step 1: Register upload
#         reg = await client.post(
#             ASSETS_URL,
#             json={
#                 "registerUploadRequest": {
#                     "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
#                     "owner": author_urn,
#                     "serviceRelationships": [{
#                         "relationshipType": "OWNER",
#                         "identifier": "urn:li:userGeneratedContent",
#                     }],
#                 }
#             },
#             headers={
#                 "Authorization": f"Bearer {access_token}",
#                 "Content-Type": "application/json",
#             },
#         )
#         reg.raise_for_status()
#         reg_data = reg.json()

#         upload_url = reg_data["value"]["uploadMechanism"][
#             "com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"
#         ]["uploadUrl"]
#         asset_urn = reg_data["value"]["asset"]

#         # Step 2: Upload binary
#         up = await client.put(
#             upload_url,
#             content=image_bytes,
#             headers={
#                 "Authorization": f"Bearer {access_token}",
#                 "Content-Type": "application/octet-stream",
#             },
#         )
#         up.raise_for_status()

#     return asset_urn


# async def post_image(
#     access_token: str,
#     author_urn: str,
#     text: str,
#     image_bytes: bytes,
#     alt_text: str = "",
# ) -> dict:
#     """Upload image + post to LinkedIn."""
#     asset_urn = await upload_image(access_token, author_urn, image_bytes)

#     payload = {
#         "author": author_urn,
#         "commentary": text,
#         "visibility": "PUBLIC",
#         "distribution": {
#             "feedDistribution": "MAIN_FEED",
#             "targetEntities": [],
#             "thirdPartyDistributionChannels": [],
#         },
#         "content": {
#             "media": {
#                 "altText": alt_text or text[:125],
#                 "id": asset_urn,
#             }
#         },
#         "lifecycleState": "PUBLISHED",
#         "isReshareDisabledByAuthor": False,
#     }
#     return await _post(access_token, payload)


# # ---------------------------------------------------------------------------
# # Carousel (PDF) post
# # ---------------------------------------------------------------------------

# async def upload_document(
#     access_token: str,
#     author_urn: str,
#     pdf_bytes: bytes,
#     filename: str = "carousel.pdf",
# ) -> str:
#     """Upload a PDF carousel to LinkedIn and return the asset URN."""
#     async with httpx.AsyncClient() as client:
#         reg = await client.post(
#             ASSETS_URL,
#             json={
#                 "registerUploadRequest": {
#                     "recipes": ["urn:li:digitalmediaRecipe:feedshare-document"],
#                     "owner": author_urn,
#                     "serviceRelationships": [{
#                         "relationshipType": "OWNER",
#                         "identifier": "urn:li:userGeneratedContent",
#                     }],
#                 }
#             },
#             headers={
#                 "Authorization": f"Bearer {access_token}",
#                 "Content-Type": "application/json",
#             },
#         )
#         reg.raise_for_status()
#         reg_data = reg.json()

#         upload_url = reg_data["value"]["uploadMechanism"][
#             "com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"
#         ]["uploadUrl"]
#         asset_urn = reg_data["value"]["asset"]

#         up = await client.put(
#             upload_url,
#             content=pdf_bytes,
#             headers={
#                 "Authorization": f"Bearer {access_token}",
#                 "Content-Type": "application/octet-stream",
#             },
#         )
#         up.raise_for_status()

#     return asset_urn


# async def post_carousel(
#     access_token: str,
#     author_urn: str,
#     text: str,
#     pdf_bytes: bytes,
#     title: str = "Carousel",
# ) -> dict:
#     """Upload PDF + post carousel to LinkedIn."""
#     asset_urn = await upload_document(access_token, author_urn, pdf_bytes, f"{title}.pdf")

#     payload = {
#         "author": author_urn,
#         "commentary": text,
#         "visibility": "PUBLIC",
#         "distribution": {
#             "feedDistribution": "MAIN_FEED",
#             "targetEntities": [],
#             "thirdPartyDistributionChannels": [],
#         },
#         "content": {
#             "media": {
#                 "title": title,
#                 "id": asset_urn,
#             }
#         },
#         "lifecycleState": "PUBLISHED",
#         "isReshareDisabledByAuthor": False,
#     }
#     return await _post(access_token, payload)


# # ---------------------------------------------------------------------------
# # Shared POST helper
# # ---------------------------------------------------------------------------

# async def _post(access_token: str, payload: dict) -> dict:
#     """Send a POST to /v2/posts and return the result."""
#     async with httpx.AsyncClient() as client:
#         resp = await client.post(
#             POSTS_URL,
#             json=payload,
#             headers={
#                 "Authorization": f"Bearer {access_token}",
#                 "Content-Type": "application/json",
#                 "X-Restli-Protocol-Version": "2.0.0",
#             },
#         )
#         resp.raise_for_status()
#         post_id = (
#             resp.headers.get("x-restli-id")
#             or resp.headers.get("X-RestLi-Id")
#             or ""
#         )
#         return {
#             "success": True,
#             "linkedin_post_id": post_id,
#             "status_code": resp.status_code,
#         }


"""
LinkedIn API service — OAuth 2.0 + Share on LinkedIn.
Scopes:  w_member_social, openid, profile, email
"""

import httpx
from urllib.parse import urlencode
from app.config import settings

AUTH_URL     = "https://www.linkedin.com/oauth/v2/authorization"
TOKEN_URL    = "https://www.linkedin.com/oauth/v2/accessToken"
USERINFO_URL = "https://api.linkedin.com/v2/userinfo"
POSTS_URL    = "https://api.linkedin.com/v2/posts"
REST_POSTS   = "https://api.linkedin.com/rest/posts"

SCOPES = "openid profile email w_member_social"


# ---------------------------------------------------------------------------
# OAuth
# ---------------------------------------------------------------------------

def get_auth_url(state: str) -> str:
    params = {
        "response_type": "code",
        "client_id": settings.LINKEDIN_CLIENT_ID,
        "redirect_uri": settings.LINKEDIN_REDIRECT_URI,
        "state": state,
        "scope": SCOPES,
    }
    return f"{AUTH_URL}?{urlencode(params)}"


async def exchange_code_for_token(code: str) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": settings.LINKEDIN_REDIRECT_URI,
                "client_id": settings.LINKEDIN_CLIENT_ID,
                "client_secret": settings.LINKEDIN_CLIENT_SECRET,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp.raise_for_status()
        return resp.json()


async def get_user_info(access_token: str) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        resp.raise_for_status()
        data = resp.json()
        if "sub" in data and not data["sub"].startswith("urn:"):
            data["author_urn"] = f"urn:li:person:{data['sub']}"
        else:
            data["author_urn"] = data.get("sub", "")
        return data


# ---------------------------------------------------------------------------
# Text post
# ---------------------------------------------------------------------------

async def post_text(access_token: str, author_urn: str, text: str) -> dict:
    payload = {
        "author": author_urn,
        "commentary": text,
        "visibility": "PUBLIC",
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": [],
        },
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }
    return await _post(access_token, payload)


# ---------------------------------------------------------------------------
# Image post  (legacy assets API — requires Marketing API access)
# ---------------------------------------------------------------------------

async def upload_image(access_token: str, author_urn: str, image_bytes: bytes) -> str:
    ASSETS_URL = "https://api.linkedin.com/v2/assets?action=registerUpload"
    async with httpx.AsyncClient() as client:
        reg = await client.post(
            ASSETS_URL,
            json={
                "registerUploadRequest": {
                    "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
                    "owner": author_urn,
                    "serviceRelationships": [{
                        "relationshipType": "OWNER",
                        "identifier": "urn:li:userGeneratedContent",
                    }],
                }
            },
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
        )
        reg.raise_for_status()
        reg_data   = reg.json()
        upload_url = reg_data["value"]["uploadMechanism"][
            "com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"
        ]["uploadUrl"]
        asset_urn  = reg_data["value"]["asset"]

        up = await client.put(
            upload_url,
            content=image_bytes,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/octet-stream",
            },
        )
        up.raise_for_status()
    return asset_urn


async def post_image(
    access_token: str,
    author_urn: str,
    text: str,
    image_bytes: bytes,
    alt_text: str = "",
) -> dict:
    asset_urn = await upload_image(access_token, author_urn, image_bytes)
    payload = {
        "author": author_urn,
        "commentary": text,
        "visibility": "PUBLIC",
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": [],
        },
        "content": {
            "media": {
                "altText": alt_text or text[:125],
                "id": asset_urn,
            }
        },
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }
    return await _post(access_token, payload)


# ---------------------------------------------------------------------------
# Carousel (PDF) — LinkedIn Documents API (rest/documents)
# ---------------------------------------------------------------------------

async def upload_document(
    access_token: str,
    author_urn: str,
    pdf_bytes: bytes,
) -> str:
    """
    Upload a PDF using LinkedIn's Documents API.
    Returns the document URN: urn:li:document:{id}
    """
    LINKEDIN_VERSION = "202601"

    async with httpx.AsyncClient() as client:
        # Step 1 — Initialize upload
        init = await client.post(
            "https://api.linkedin.com/rest/documents?action=initializeUpload",
            json={"initializeUploadRequest": {"owner": author_urn}},
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "Linkedin-Version": LINKEDIN_VERSION,
                "X-Restli-Protocol-Version": "2.0.0",
            },
        )
        init.raise_for_status()
        init_data    = init.json()
        upload_url   = init_data["value"]["uploadUrl"]
        document_urn = init_data["value"]["document"]

        # Step 2 — Upload PDF bytes
        up = await client.put(
            upload_url,
            content=pdf_bytes,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/octet-stream",
            },
        )
        up.raise_for_status()

    return document_urn


async def post_carousel(
    access_token: str,
    author_urn: str,
    text: str,
    pdf_bytes: bytes,
    title: str = "Carousel",
) -> dict:
    """Upload PDF via Documents API + post to LinkedIn."""
    document_urn = await upload_document(access_token, author_urn, pdf_bytes)

    payload = {
        "author": author_urn,
        "commentary": text,
        "visibility": "PUBLIC",
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": [],
        },
        "content": {
            "media": {
                "title": title,
                "id": document_urn,
            }
        },
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }
    return await _post(access_token, payload, version="202601")


# ---------------------------------------------------------------------------
# Shared POST helper
# ---------------------------------------------------------------------------

async def _post(access_token: str, payload: dict, version: str | None = None) -> dict:
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
    }
    if version:
        headers["Linkedin-Version"] = version

    # Use REST posts endpoint when version header is present
    url = REST_POSTS if version else POSTS_URL

    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        post_id = (
            resp.headers.get("x-restli-id")
            or resp.headers.get("X-RestLi-Id")
            or ""
        )
        return {
            "success": True,
            "linkedin_post_id": post_id,
            "status_code": resp.status_code,
        }