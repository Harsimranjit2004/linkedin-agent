"""
Image generation service — OpenAI gpt-image-2.
Generates a LinkedIn-optimized tech infographic based on post content.
"""

import os
import uuid
import base64
from openai import AsyncOpenAI
from app.config import settings

client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

IMAGE_DIR = os.path.join(os.path.dirname(__file__), "../../data/images")
os.makedirs(IMAGE_DIR, exist_ok=True)

# LinkedIn landscape — 1536x1024 matches optimal feed ratio
IMAGE_SIZE = "1536x1024"


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

def build_image_prompt(topic: str, post_content: str) -> str:
    """
    Build a gpt-image-2 prompt following OpenAI's prompting guide.
    Structure: canvas → subject → layout → typography → constraints
    Targets: dark minimal infographic, developer audience, LinkedIn feed
    """

    # Extract first 2-3 sentences of post for key context
    sentences = [s.strip() for s in post_content.replace("\n", " ").split(".") if len(s.strip()) > 20]
    key_points = ". ".join(sentences[:3]) if sentences else post_content[:300]

    return f"""
Create a professional tech infographic for a LinkedIn post about: {topic}

Canvas:
- Landscape format, dark navy background (#0A0E1A), LinkedIn feed dimensions
- Minimal color palette: deep navy base, single accent color (electric blue #4A9EFF or teal #00D4AA)
- Clean grid layout with generous whitespace

Content to visualize:
{key_points}

Layout structure:
- Bold headline text at top (topic title, white, large sans-serif)
- 3–4 key insight blocks arranged in a clean horizontal or grid layout
- Each block: short label + 1-line stat or insight, separated by subtle dividers
- Small decorative geometric shapes or thin lines as visual anchors (no clipart)
- Bottom-right: minimal author tag area (leave blank, just the space)

Typography:
- Primary text: white, bold, large and readable
- Secondary text: light gray (#A0B0C0), smaller
- All text must be legible at LinkedIn feed size
- Maximum 40 words total in the image

Visual style:
- Flat design with subtle depth — thin glowing lines, soft shadows on text blocks
- Isometric or flat icons only if they are extremely simple (no complex illustrations)
- Professional, minimal, like a well-designed Notion template or Linear dashboard
- NOT: gradient soup, neon overload, stock photo backgrounds, AI art clichés

Constraints:
- No watermarks, no logos, no photo-realistic elements
- No more than 2 colors + white/gray
- No decorative borders or heavy drop shadows
- Infographic must feel designed by a senior developer, not generated
""".strip()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def generate_image(topic: str, post_content: str) -> dict:
    """
    Generate a LinkedIn infographic using gpt-image-2.

    Returns:
        {
            "success": bool,
            "image_url": str,       # empty (gpt-image-2 returns b64)
            "local_path": str,      # saved to /data/images/
            "image_bytes": bytes,
            "error": str | None
        }
    """
    try:
        prompt = build_image_prompt(topic, post_content)

        response = await client.images.generate(
            model="gpt-image-2",
            prompt=prompt,
            size=IMAGE_SIZE,
            quality="medium",
            n=1,
        )

        image_bytes = base64.b64decode(response.data[0].b64_json)

        filename   = f"{uuid.uuid4().hex}.png"
        local_path = os.path.join(IMAGE_DIR, filename)
        with open(local_path, "wb") as f:
            f.write(image_bytes)

        return {
            "success":     True,
            "image_url":   "",
            "local_path":  local_path,
            "image_bytes": image_bytes,
            "error":       None,
        }

    except Exception as e:
        return {
            "success":     False,
            "image_url":   "",
            "local_path":  "",
            "image_bytes": b"",
            "error":       str(e),
        }


async def get_image_bytes(local_path: str) -> bytes | None:
    """Read saved image bytes from disk."""
    try:
        with open(local_path, "rb") as f:
            return f.read()
    except FileNotFoundError:
        return None