# """
# Post management routes.

# GET    /posts              → list all posts (filterable by status)
# GET    /posts/{id}         → get single post
# POST   /posts/{id}/publish → post to LinkedIn now
# DELETE /posts/{id}         → delete a draft
# """

# from fastapi import APIRouter, Request, HTTPException, Query
# from fastapi.responses import JSONResponse, Response

# from app.routes.auth import require_auth
# from app.services.linkedin import post_text, post_image, post_carousel
# from app.services.image import get_image_bytes
# from app.db.database import (
#     get_all_posts,
#     get_post,
#     mark_as_published,
#     mark_as_failed,
#     delete_post,
# )

# router = APIRouter(prefix="/posts", tags=["posts"])


# # ---------------------------------------------------------------------------
# # Routes
# # ---------------------------------------------------------------------------

# @router.get("")
# async def list_posts(
#     request: Request,
#     status: str | None = Query(default=None, description="Filter by status: draft | published | failed"),
# ):
#     """Return all posts, optionally filtered by status."""
#     require_auth(request)
#     posts = await get_all_posts(status=status)
#     return JSONResponse(posts)


# @router.get("/{post_id}")
# async def get_single_post(request: Request, post_id: str):
#     """Return a single post by ID."""
#     require_auth(request)
#     post = await get_post(post_id)
#     if not post:
#         raise HTTPException(status_code=404, detail="Post not found.")
#     return JSONResponse(post)


# @router.post("/{post_id}/publish")
# async def publish_post(request: Request, post_id: str):
#     """
#     Post to LinkedIn immediately.
#     Handles text, image, and carousel post types.
#     """
#     access_token = require_auth(request)
#     author_urn   = request.session.get("author_urn", "")

#     if not author_urn:
#         raise HTTPException(status_code=401, detail="Author URN missing. Please re-authenticate.")

#     post = await get_post(post_id)
#     if not post:
#         raise HTTPException(status_code=404, detail="Post not found.")

#     if post["status"] == "published":
#         raise HTTPException(status_code=400, detail="Post already published.")

#     post_type = post["post_type"]
#     content   = post["content"]

#     try:
#         if post_type == "text":
#             result = await post_text(
#                 access_token=access_token,
#                 author_urn=author_urn,
#                 text=content,
#             )

#         elif post_type == "image":
#             image_path = post.get("image_url", "")
#             if not image_path:
#                 raise HTTPException(status_code=400, detail="No image found for this post.")

#             image_bytes = await get_image_bytes(image_path)
#             if not image_bytes:
#                 raise HTTPException(status_code=400, detail="Image file not found on disk.")

#             result = await post_image(
#                 access_token=access_token,
#                 author_urn=author_urn,
#                 text=content,
#                 image_bytes=image_bytes,
#                 alt_text=post.get("title", ""),
#             )

#         elif post_type == "carousel":
#             slides = post.get("slides")
#             if not slides:
#                 raise HTTPException(status_code=400, detail="No slides found for this carousel.")

#             from app.services.carousel import generate_carousel_pdf
#             from app.config import settings
#             pdf_bytes = generate_carousel_pdf(slides, author=settings.BRAND_NAME)

#             result = await post_carousel(
#                 access_token=access_token,
#                 author_urn=author_urn,
#                 text=content,
#                 pdf_bytes=pdf_bytes,
#                 title=post.get("title", "Carousel"),
#             )

#         else:
#             raise HTTPException(status_code=400, detail=f"Unknown post type: {post_type}")

#         # Mark as published in Supabase
#         await mark_as_published(post_id, result["linkedin_post_id"])

#         return JSONResponse({
#             "success":          True,
#             "linkedin_post_id": result["linkedin_post_id"],
#             "message":          "Post published successfully.",
#         })

#     except HTTPException:
#         raise
#     except Exception as e:
#         await mark_as_failed(post_id, str(e))
#         raise HTTPException(status_code=500, detail=f"Failed to publish: {e}")


# @router.delete("/{post_id}")
# async def remove_post(request: Request, post_id: str):
#     """Delete a draft post."""
#     require_auth(request)

#     post = await get_post(post_id)
#     if not post:
#         raise HTTPException(status_code=404, detail="Post not found.")

#     if post["status"] == "published":
#         raise HTTPException(status_code=400, detail="Cannot delete a published post.")

#     deleted = await delete_post(post_id)
#     if not deleted:
#         raise HTTPException(status_code=500, detail="Failed to delete post.")

#     return Response(status_code=204)
from fastapi import APIRouter, Request, HTTPException, Query
from fastapi.responses import JSONResponse, Response

from app.routes.auth import get_user_from_token
from app.services.linkedin import post_text, post_image, post_carousel
from app.services.image import get_image_bytes
from app.db.database import get_all_posts, get_post, mark_as_published, mark_as_failed, delete_post

router = APIRouter(prefix="/posts", tags=["posts"])


def _auth(request: Request) -> dict:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated.")
    token = auth.replace("Bearer ", "").strip()
    user = get_user_from_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")
    return user


@router.get("")
async def list_posts(request: Request, status: str | None = Query(default=None)):
    _auth(request)
    posts = await get_all_posts(status=status)
    return JSONResponse(posts)


@router.get("/{post_id}")
async def get_single_post(request: Request, post_id: str):
    _auth(request)
    post = await get_post(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found.")
    return JSONResponse(post)


@router.post("/{post_id}/publish")
async def publish_post(request: Request, post_id: str):
    user = _auth(request)
    access_token = user.get("access_token", "")
    author_urn   = user.get("author_urn", "")

    if not author_urn:
        raise HTTPException(status_code=401, detail="Author URN missing. Please re-authenticate.")

    post = await get_post(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found.")
    if post["status"] == "published":
        raise HTTPException(status_code=400, detail="Post already published.")

    post_type = post["post_type"]
    content   = post["content"]

    try:
        if post_type == "text":
            result = await post_text(access_token=access_token, author_urn=author_urn, text=content)

        elif post_type == "image":
            image_path = post.get("image_url", "")
            if not image_path:
                raise HTTPException(status_code=400, detail="No image found for this post.")
            image_bytes = await get_image_bytes(image_path)
            if not image_bytes:
                raise HTTPException(status_code=400, detail="Image file not found on disk.")
            result = await post_image(
                access_token=access_token, author_urn=author_urn,
                text=content, image_bytes=image_bytes, alt_text=post.get("title", ""),
            )

        elif post_type == "carousel":
            slides = post.get("slides")
            if not slides:
                raise HTTPException(status_code=400, detail="No slides found.")
            from app.services.carousel import generate_carousel_pdf
            from app.config import settings
            pdf_bytes = generate_carousel_pdf(slides, author=settings.BRAND_NAME)
            result = await post_carousel(
                access_token=access_token, author_urn=author_urn,
                text=content, pdf_bytes=pdf_bytes, title=post.get("title", "Carousel"),
            )
        else:
            raise HTTPException(status_code=400, detail=f"Unknown post type: {post_type}")

        await mark_as_published(post_id, result["linkedin_post_id"])
        return JSONResponse({"success": True, "linkedin_post_id": result["linkedin_post_id"]})

    except HTTPException:
        raise
    except Exception as e:
        await mark_as_failed(post_id, str(e))
        raise HTTPException(status_code=500, detail=f"Failed to publish: {e}")


@router.delete("/{post_id}")
async def remove_post(request: Request, post_id: str):
    _auth(request)
    post = await get_post(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found.")
    if post["status"] == "published":
        raise HTTPException(status_code=400, detail="Cannot delete a published post.")
    deleted = await delete_post(post_id)
    if not deleted:
        raise HTTPException(status_code=500, detail="Failed to delete post.")
    return Response(status_code=204)