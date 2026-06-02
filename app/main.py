"""
FastAPI entry point — wires all routes, middleware, and background tasks.
"""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.routes import auth, content, posts
from app.services.sheets import poll_sheets
from app.services.ai import run_agent
from app.db.database import update_post
import os
from fastapi.staticfiles import StaticFiles

# ---------------------------------------------------------------------------
# Background task — Google Sheets poller
# ---------------------------------------------------------------------------

async def sheets_poller():
    """
    Poll Google Sheets every 60 seconds for pending rows.
    Triggers the agent for each pending row and marks it done/failed.
    """
    while True:
        try:
            pending_rows = await poll_sheets()

            for row in pending_rows:
                try:
                    result = await run_agent(
                        input_type=row["input_type"],
                        input_content=row["topic"],
                        post_type=row["post_type"],
                        tone=row["tone"],
                        hook_style=row["hook_style"],
                        length=row["length"],
                        sheets_row_id=row["sheets_row_id"],
                    )

                    if result.get("error"):
                        print(f"[Sheets] Agent error for row {row['row_number']}: {result['error']}")
                        from app.services.sheets import update_row_status
                        update_row_status(row["row_number"], "failed")
                    else:
                        from app.services.sheets import update_row_status
                        update_row_status(row["row_number"], "done")
                        print(f"[Sheets] Generated post {result['post_id']} from row {row['row_number']}")

                except Exception as e:
                    print(f"[Sheets] Failed to process row {row['row_number']}: {e}")
                    from app.services.sheets import update_row_status
                    update_row_status(row["row_number"], "failed")

        except Exception as e:
            print(f"[Sheets] Poller error: {e}")

        await asyncio.sleep(60)


# ---------------------------------------------------------------------------
# Lifespan — startup / shutdown
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup — launch background poller only if Sheets is configured
    poller_task = None
    if settings.GOOGLE_SHEETS_ID:
        print("[Sheets] Starting poller...")
        poller_task = asyncio.create_task(sheets_poller())
    else:
        print("[Sheets] GOOGLE_SHEETS_ID not set — poller disabled.")

    yield

    # Shutdown — cancel poller
    if poller_task:
        poller_task.cancel()
        try:
            await poller_task
        except asyncio.CancelledError:
            pass
        print("[Sheets] Poller stopped.")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="LinkedIn Content Agent",
    description="AI-powered LinkedIn content pipeline — generate, preview, edit, post.",
    version="1.0.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL, "http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.APP_SECRET_KEY,
    max_age=60 * 60 * 24 * 7,  # 7 days
    https_only=False,           # set True in production
    same_site="lax",
)



IMAGE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "images")
os.makedirs(IMAGE_DIR, exist_ok=True)
app.mount("/images", StaticFiles(directory=IMAGE_DIR), name="images")


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(auth.router)
app.include_router(content.router)
app.include_router(posts.router)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health", tags=["meta"])
async def health():
    return {
        "status": "ok",
        "sheets_poller": bool(settings.GOOGLE_SHEETS_ID),
        "image_dir": IMAGE_DIR
    }


@app.get("/", tags=["meta"])
async def root():
    return {
        "message": "LinkedIn Content Agent API",
        "docs": "/docs",
        "auth": "/auth/linkedin",
    }