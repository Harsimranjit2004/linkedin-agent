"""
Content generation routes.

POST /content/generate        → run the full agent pipeline
POST /content/regenerate/{id} → regenerate an existing draft with new settings
GET  /content/preview/{id}    → get post data for preview
PUT  /content/edit/{id}       → save edits to a draft
"""

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Literal

from app.routes.auth import require_auth
from app.services.ai import run_agent
from app.db.database import get_post, update_post

router = APIRouter(prefix="/content", tags=["content"])


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class GenerateRequest(BaseModel):
    input_type:   Literal["topic", "youtube", "article", "notes"]
    input_content: str
    post_type:    Literal["text", "carousel", "image"] = "text"
    tone:         Literal["educational", "casual", "motivational", "storytelling"] = "educational"
    hook_style:   Literal["question", "bold_stat", "controversial", "personal_story"] = "question"
    length:       Literal["short", "medium", "long"] = "medium"


class EditRequest(BaseModel):
    content:  str | None = None
    title:    str | None = None
    slides:   list[dict] | None = None


class RegenerateRequest(BaseModel):
    tone:       Literal["educational", "casual", "motivational", "storytelling"] | None = None
    hook_style: Literal["question", "bold_stat", "controversial", "personal_story"] | None = None
    length:     Literal["short", "medium", "long"] | None = None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/generate")
async def generate_content(request: Request, body: GenerateRequest):
    """
    Run the full LangGraph agent pipeline.
    Returns the saved draft with post_id for preview/edit/post.
    """
    require_auth(request)

    if not body.input_content.strip():
        raise HTTPException(status_code=400, detail="input_content cannot be empty.")

    result = await run_agent(
        input_type=body.input_type,
        input_content=body.input_content,
        post_type=body.post_type,
        tone=body.tone,
        hook_style=body.hook_style,
        length=body.length,
    )

    if result.get("error"):
        raise HTTPException(status_code=500, detail=result["error"])

    return JSONResponse({
        "post_id":    result["post_id"],
        "post_type":  result["post_type"],
        "title":      result["title"],
        "content":    result["content"],
        "slides":     result["slides"],
        "image_url":  result["image_url"],
        "status":     "draft",
    })


@router.post("/regenerate/{post_id}")
async def regenerate_content(request: Request, post_id: str, body: RegenerateRequest):
    """
    Regenerate an existing draft — reuse the original input,
    optionally override tone/hook/length.
    """
    require_auth(request)

    existing = await get_post(post_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Post not found.")

    if existing["status"] == "published":
        raise HTTPException(status_code=400, detail="Cannot regenerate a published post.")

    result = await run_agent(
        input_type=existing["input_type"],
        input_content=existing["input_content"],
        post_type=existing["post_type"],
        tone=body.tone or existing.get("tone", "educational"),
        hook_style=body.hook_style or existing.get("hook_style", "question"),
        length=body.length or "medium",
        sheets_row_id=existing.get("sheets_row_id", ""),
    )

    if result.get("error"):
        raise HTTPException(status_code=500, detail=result["error"])

    # Update existing row instead of creating a new one
    updated = await update_post(post_id, {
        "title":      result["title"],
        "content":    result["content"],
        "slides":     result["slides"] or None,
        "image_url":  result["image_url"],
        "status":     "draft",
    })

    return JSONResponse({
        "post_id":   post_id,
        "post_type": existing["post_type"],
        "title":     updated["title"],
        "content":   updated["content"],
        "slides":    updated["slides"],
        "image_url": updated["image_url"],
        "status":    "draft",
    })


@router.get("/preview/{post_id}")
async def preview_post(request: Request, post_id: str):
    """Return full post data for the preview screen."""
    require_auth(request)

    post = await get_post(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found.")

    # Include author info from session for the LinkedIn preview mock
    return JSONResponse({
        **post,
        "author_name":    request.session.get("name", ""),
        "author_picture": request.session.get("picture", ""),
    })


@router.put("/edit/{post_id}")
async def edit_post(request: Request, post_id: str, body: EditRequest):
    """Save manual edits to a draft before posting."""
    require_auth(request)

    post = await get_post(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found.")

    if post["status"] == "published":
        raise HTTPException(status_code=400, detail="Cannot edit a published post.")

    updates = {}
    if body.content is not None:
        updates["content"] = body.content
    if body.title is not None:
        updates["title"] = body.title
    if body.slides is not None:
        updates["slides"] = body.slides

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update.")

    updated = await update_post(post_id, updates)

    return JSONResponse({"success": True, "post": updated})