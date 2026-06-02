from datetime import datetime
from supabase import create_client, Client
from app.config import settings

_client: Client | None = None


def get_db() -> Client:
    global _client
    if _client is None:
        _client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
    return _client


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

async def save_post(post_data: dict) -> dict:
    """Insert a new post row and return it."""
    db = get_db()
    result = db.table("linkedin_posts").insert(post_data).execute()
    return result.data[0]


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

async def get_post(post_id: str) -> dict | None:
    db = get_db()
    result = db.table("linkedin_posts").select("*").eq("id", post_id).execute()
    return result.data[0] if result.data else None


async def get_all_posts(status: str | None = None) -> list[dict]:
    """Return all posts, optionally filtered by status."""
    db = get_db()
    query = db.table("linkedin_posts").select("*").order("created_at", desc=True)
    if status:
        query = query.eq("status", status)
    result = query.execute()
    return result.data


async def get_pending_sheets_posts() -> list[dict]:
    """Return draft posts that originated from Google Sheets."""
    db = get_db()
    result = (
        db.table("linkedin_posts")
        .select("*")
        .eq("status", "draft")
        .eq("input_type", "sheets")
        .execute()
    )
    return result.data


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------

async def update_post(post_id: str, updates: dict) -> dict:
    db = get_db()
    result = (
        db.table("linkedin_posts").update(updates).eq("id", post_id).execute()
    )
    return result.data[0]


async def mark_as_published(post_id: str, linkedin_post_id: str) -> dict:
    return await update_post(post_id, {
        "status": "published",
        "linkedin_post_id": linkedin_post_id,
        "posted_at": datetime.utcnow().isoformat(),
    })


async def mark_as_failed(post_id: str, reason: str) -> dict:
    return await update_post(post_id, {
        "status": "failed",
        "content": reason,  # store error in content for debugging
    })


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

async def delete_post(post_id: str) -> bool:
    db = get_db()
    result = db.table("linkedin_posts").delete().eq("id", post_id).execute()
    return len(result.data) > 0