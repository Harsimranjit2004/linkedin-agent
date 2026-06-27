from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Literal

from app.routes.auth import get_user_from_token
from app.services.ai import run_agent
from app.db.database import get_post, update_post

router = APIRouter(prefix="/content", tags=["content"])


def _auth(request: Request) -> dict:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated.")
    token = auth.replace("Bearer ", "").strip()
    user = get_user_from_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")
    return user


class GenerateRequest(BaseModel):
    input_type:    Literal["topic", "youtube", "article", "notes"]
    input_content: str
    post_type:     Literal["text", "carousel", "image"] = "text"
    tone:          Literal["educational", "casual", "motivational", "storytelling"] = "educational"
    hook_style:    Literal["question", "bold_stat", "controversial", "personal_story"] = "question"
    length:        Literal["short", "medium", "long"] = "medium"


class EditRequest(BaseModel):
    content: str | None = None
    title:   str | None = None
    slides:  list[dict] | None = None


class RegenerateRequest(BaseModel):
    tone:       Literal["educational", "casual", "motivational", "storytelling"] | None = None
    hook_style: Literal["question", "bold_stat", "controversial", "personal_story"] | None = None
    length:     Literal["short", "medium", "long"] | None = None


@router.post("/generate")
async def generate_content(request: Request, body: GenerateRequest):
    _auth(request)
    if not body.input_content.strip():
        raise HTTPException(status_code=400, detail="input_content cannot be empty.")

    try:
        result = await run_agent(
            input_type=body.input_type,
            input_content=body.input_content,
            post_type=body.post_type,
            tone=body.tone,
            hook_style=body.hook_style,
            length=body.length,
        )
    except Exception as e:
        import traceback, sys
        print("="*60, file=sys.stderr, flush=True)
        print("GENERATE CRASHED:", file=sys.stderr, flush=True)
        traceback.print_exc(file=sys.stderr)
        sys.stderr.flush()
        print("="*60, file=sys.stderr, flush=True)
        raise HTTPException(status_code=500, detail=f"Agent crashed: {type(e).__name__}: {e}")

    if result.get("error"):
        raise HTTPException(status_code=500, detail=result["error"])

    return JSONResponse({
        "post_id":   result["post_id"],
        "post_type": result["post_type"],
        "title":     result["title"],
        "content":   result["content"],
        "slides":    result["slides"],
        "image_url": result["image_url"],
        "status":    "draft",
    })


@router.post("/regenerate/{post_id}")
async def regenerate_content(request: Request, post_id: str, body: RegenerateRequest):
    _auth(request)
    existing = await get_post(post_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Post not found.")
    if existing["status"] == "published":
        raise HTTPException(status_code=400, detail="Cannot regenerate a published post.")

    try:
        result = await run_agent(
            input_type=existing["input_type"],
            input_content=existing["input_content"],
            post_type=existing["post_type"],
            tone=body.tone or existing.get("tone", "educational"),
            hook_style=body.hook_style or existing.get("hook_style", "question"),
            length=body.length or "medium",
            sheets_row_id=existing.get("sheets_row_id", ""),
        )
    except Exception as e:
        import traceback, sys
        print("="*60, file=sys.stderr, flush=True)
        print("GENERATE CRASHED:", file=sys.stderr, flush=True)
        traceback.print_exc(file=sys.stderr)
        sys.stderr.flush()
        print("="*60, file=sys.stderr, flush=True)
        raise HTTPException(status_code=500, detail=f"Agent crashed: {type(e).__name__}: {e}")

    if result.get("error"):
        raise HTTPException(status_code=500, detail=result["error"])

    updated = await update_post(post_id, {
        "title":     result["title"],
        "content":   result["content"],
        "slides":    result["slides"] or None,
        "image_url": result["image_url"],
        "status":    "draft",
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
    user = _auth(request)
    post = await get_post(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found.")
    return JSONResponse({
        **post,
        "author_name":    user.get("name", ""),
        "author_picture": user.get("picture", ""),
    })


@router.put("/edit/{post_id}")
async def edit_post(request: Request, post_id: str, body: EditRequest):
    _auth(request)
    post = await get_post(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found.")
    if post["status"] == "published":
        raise HTTPException(status_code=400, detail="Cannot edit a published post.")
    updates = {}
    if body.content is not None: updates["content"] = body.content
    if body.title   is not None: updates["title"]   = body.title
    if body.slides  is not None: updates["slides"]  = body.slides
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update.")
    updated = await update_post(post_id, updates)
    return JSONResponse({"success": True, "post": updated})