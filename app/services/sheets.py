"""
Google Sheets poller — reads rows with status='pending' and triggers the agent.
Uses a Google Service Account for auth (no OAuth flow needed).

Sheet columns expected (in order):
| id | topic | input_type | post_type | tone | hook_style | length | status | notes |

- id:         unique row identifier (you fill this)
- topic:      the topic or URL to generate content from
- input_type: topic | youtube | article | notes
- post_type:  text | carousel | image
- tone:       educational | casual | motivational | storytelling
- hook_style: question | bold_stat | controversial | personal_story
- length:     short | medium | long
- status:     pending | processing | done | failed
- notes:      optional extra context for Claude
"""

import os
from google.oauth2 import service_account
from googleapiclient.discovery import build
from app.config import settings

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SHEET_NAME = "Posts"  # tab name in your Google Sheet
HEADER_ROW = 1        # row 1 is the header
STATUS_COL = "H"      # column H = status


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def get_sheets_service():
    """Build and return an authenticated Google Sheets service."""
    creds = service_account.Credentials.from_service_account_file(
        settings.GOOGLE_SERVICE_ACCOUNT_JSON,
        scopes=SCOPES,
    )
    return build("sheets", "v4", credentials=creds)


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

def get_pending_rows() -> list[dict]:
    """
    Fetch all rows where status == 'pending'.
    Returns a list of dicts with row data + row_number for updates.
    """
    if not settings.GOOGLE_SHEETS_ID:
        return []

    try:
        service = get_sheets_service()
        sheet = service.spreadsheets()

        result = sheet.values().get(
            spreadsheetId=settings.GOOGLE_SHEETS_ID,
            range=f"{SHEET_NAME}!A:I",
        ).execute()

        rows = result.get("values", [])
        if len(rows) <= HEADER_ROW:
            return []

        pending = []
        for i, row in enumerate(rows[HEADER_ROW:], start=HEADER_ROW + 1):
            # Pad row to 9 columns in case trailing cells are empty
            row = row + [""] * (9 - len(row))

            row_id, topic, input_type, post_type, tone, hook_style, length, status, notes = row[:9]

            if status.strip().lower() == "pending" and topic.strip():
                pending.append({
                    "row_number": i,
                    "sheets_row_id": row_id,
                    "topic": topic.strip(),
                    "input_type": input_type.strip() or "topic",
                    "post_type": post_type.strip() or "text",
                    "tone": tone.strip() or "educational",
                    "hook_style": hook_style.strip() or "question",
                    "length": length.strip() or "medium",
                    "notes": notes.strip(),
                })

        return pending

    except Exception as e:
        print(f"[Sheets] Error fetching rows: {e}")
        return []


# ---------------------------------------------------------------------------
# Update status
# ---------------------------------------------------------------------------

def update_row_status(row_number: int, status: str) -> bool:
    """
    Update the status column for a specific row.
    status: 'processing' | 'done' | 'failed'
    """
    if not settings.GOOGLE_SHEETS_ID:
        return False

    try:
        service = get_sheets_service()
        sheet = service.spreadsheets()

        sheet.values().update(
            spreadsheetId=settings.GOOGLE_SHEETS_ID,
            range=f"{SHEET_NAME}!{STATUS_COL}{row_number}",
            valueInputOption="RAW",
            body={"values": [[status]]},
        ).execute()

        return True

    except Exception as e:
        print(f"[Sheets] Error updating row {row_number}: {e}")
        return False


# ---------------------------------------------------------------------------
# Poll — called by the background task in main.py
# ---------------------------------------------------------------------------

async def poll_sheets() -> list[dict]:
    """
    Poll for pending rows, mark them as 'processing', return them.
    The agent picks these up and generates content.
    """
    pending = get_pending_rows()

    for row in pending:
        update_row_status(row["row_number"], "processing")

    return pending