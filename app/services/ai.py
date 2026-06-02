"""
LangGraph agent — orchestrates the full content generation pipeline.

Flow:
  [input_node] → detect type, extract content
  [content_node] → Claude generates post
  [format_node] → format for post type (PDF / image / text)
  [save_node] → save draft to Supabase

Each node receives and returns AgentState (a TypedDict).
"""

import json
from typing import TypedDict, Literal, Any
from langgraph.graph import StateGraph, END
from anthropic import AsyncAnthropic

from app.config import settings, get_brand_voice
from app.services.youtube import get_transcript
from app.services.scraper import scrape_article
from app.services.carousel import generate_carousel_pdf
from app.services.image import generate_image
from app.db.database import save_post

anthropic = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

class AgentState(TypedDict):
    # Input
    input_type: Literal["topic", "youtube", "article", "notes", "sheets"]
    input_content: str          # raw input (topic text, URL, notes)
    post_type: Literal["text", "carousel", "image"]
    tone: str
    hook_style: str
    length: str
    sheets_row_id: str

    # Extracted
    extracted_content: str      # cleaned text passed to Claude

    # Generated
    title: str
    content: str                # final post text / caption
    slides: list[dict]          # carousel slides (empty for non-carousel)
    image_url: str              # local path for generated image
    pdf_bytes: bytes            # carousel PDF bytes

    # Meta
    post_id: str                # Supabase row id after save
    error: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

LENGTH_GUIDE = {
    "short":  "150 words maximum. Punchy and direct.",
    "medium": "250-350 words. Well-structured with clear sections.",
    "long":   "450-600 words. In-depth with examples and takeaways.",
}

HOOK_GUIDE = {
    "question":      "Start with a thought-provoking question that makes developers stop scrolling.",
    "bold_stat":     "Start with a surprising statistic or fact relevant to the topic.",
    "controversial": "Start with a counterintuitive or mildly controversial take on the topic.",
    "personal_story":"Start with a brief personal anecdote or experience related to the topic.",
}

TONE_GUIDE = {
    "educational":   "Teach something concrete. Use simple language, analogies, and examples.",
    "casual":        "Conversational and relaxed. Like texting a dev friend.",
    "motivational":  "Inspiring and energizing. Push the reader to take action.",
    "storytelling":  "Narrative-driven. Build tension and payoff.",
}


async def call_claude(system: str, user: str, max_tokens: int = 1500) -> str:
    """Call Claude and return the text response."""
    response = await anthropic.messages.create(
        model="claude-opus-4-5",
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return response.content[0].text.strip()


# ---------------------------------------------------------------------------
# Node 1 — Input
# ---------------------------------------------------------------------------

async def input_node(state: AgentState) -> AgentState:
    """Detect input type and extract clean content."""
    input_type = state["input_type"]
    raw = state["input_content"]

    try:
        if input_type == "youtube":
            result = await get_transcript(raw)
            if not result["success"]:
                return {**state, "error": result["error"]}
            state["extracted_content"] = result["transcript"]

        elif input_type == "article":
            result = await scrape_article(raw)
            if not result["success"]:
                return {**state, "error": result["error"]}
            state["extracted_content"] = f"Title: {result['title']}\n\n{result['content']}"

        else:
            # topic / notes / sheets — use raw input directly
            state["extracted_content"] = raw

    except Exception as e:
        state["error"] = str(e)

    return state


# ---------------------------------------------------------------------------
# Node 2 — Content generation
# ---------------------------------------------------------------------------

async def content_node(state: AgentState) -> AgentState:
    """Use Claude to generate the post content."""
    if state.get("error"):
        return state

    post_type = state["post_type"]
    tone      = state.get("tone", "educational")
    hook      = state.get("hook_style", "question")
    length    = state.get("length", "medium")
    content   = state["extracted_content"]

    brand_voice = get_brand_voice()

    try:
        if post_type == "carousel":
            system = f"""{brand_voice}

You are generating a LinkedIn carousel post (slide deck).
Tone: {TONE_GUIDE.get(tone, tone)}
Hook style: {HOOK_GUIDE.get(hook, hook)}

Return ONLY valid JSON — no markdown, no explanation, no backticks.
Format:
{{
  "title": "carousel title",
  "intro_text": "the LinkedIn post caption (100-150 words)",
  "slides": [
    {{"type": "cover", "headline": "...", "subtitle": "..."}},
    {{"type": "content", "headline": "...", "bullets": ["...", "...", "..."]}},
    {{"type": "content", "headline": "...", "body": "..."}},
    {{"type": "cta", "cta_text": "..."}}
  ]
}}

Rules:
- 5-8 slides total (cover + 3-5 content + cta)
- Each content slide: ONE clear point
- Bullets: 2-4 items max, short and scannable
- Cover headline: bold, curiosity-driving
- CTA slide: one actionable takeaway"""

            user = f"Create a LinkedIn carousel about:\n\n{content}"
            raw_json = await call_claude(system, user, max_tokens=2000)

            # Strip any accidental markdown fences
            raw_json = raw_json.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
            parsed = json.loads(raw_json)

            state["title"]   = parsed.get("title", "")
            state["content"] = parsed.get("intro_text", "")
            state["slides"]  = parsed.get("slides", [])

        elif post_type == "image":
            system = f"""{brand_voice}

You are writing a LinkedIn image post caption.
Tone: {TONE_GUIDE.get(tone, tone)}
Hook style: {HOOK_GUIDE.get(hook, hook)}
Length: {LENGTH_GUIDE.get(length, length)}

Write ONLY the post caption — no title, no explanation.
End with 3-5 relevant hashtags on a new line."""

            user = f"Write a LinkedIn image post caption about:\n\n{content}"
            caption = await call_claude(system, user)

            state["title"]   = content[:60]
            state["content"] = caption
            state["slides"]  = []

        else:  # text post
            system = f"""{brand_voice}

You are writing a LinkedIn text post.
Tone: {TONE_GUIDE.get(tone, tone)}
Hook style: {HOOK_GUIDE.get(hook, hook)}
Length: {LENGTH_GUIDE.get(length, length)}

Format rules:
- First line = the hook (stand-alone, no label)
- Use short paragraphs (1-3 lines max)
- Use line breaks generously — LinkedIn rewards whitespace
- End with a question or CTA to drive comments
- Add 3-5 hashtags on the last line

Write ONLY the post — no title, no explanation."""

            user = f"Write a LinkedIn post about:\n\n{content}"
            post_text = await call_claude(system, user)

            state["title"]   = content[:60]
            state["content"] = post_text
            state["slides"]  = []

    except json.JSONDecodeError as e:
        state["error"] = f"Failed to parse Claude response as JSON: {e}"
    except Exception as e:
        state["error"] = str(e)

    return state


# ---------------------------------------------------------------------------
# Node 3 — Format
# ---------------------------------------------------------------------------

async def format_node(state: AgentState) -> AgentState:
    """Generate PDF for carousel or image for image posts."""
    if state.get("error"):
        return state

    post_type = state["post_type"]

    try:
        if post_type == "carousel" and state.get("slides"):
            pdf_bytes = generate_carousel_pdf(state["slides"])
            state["pdf_bytes"] = pdf_bytes

        elif post_type == "image":
            result = await generate_image(
                topic=state["title"],
                post_content=state["content"],
            )
            if result["success"]:
                state["image_url"] = result["local_path"]
            else:
                state["error"] = f"Image generation failed: {result['error']}"

    except Exception as e:
        state["error"] = str(e)

    return state


# ---------------------------------------------------------------------------
# Node 4 — Save
# ---------------------------------------------------------------------------

async def save_node(state: AgentState) -> AgentState:
    """Persist the generated post as a draft in Supabase."""
    if state.get("error"):
        return state

    try:
        post_data = {
            "input_type":    state["input_type"],
            "input_content": state["input_content"],
            "post_type":     state["post_type"],
            "title":         state.get("title", ""),
            "content":       state.get("content", ""),
            "slides":        state.get("slides") or None,
            "tone":          state.get("tone", ""),
            "hook_style":    state.get("hook_style", ""),
            "image_url":     state.get("image_url", ""),
            "sheets_row_id": state.get("sheets_row_id", ""),
            "status":        "draft",
        }
        saved = await save_post(post_data)
        state["post_id"] = saved["id"]

    except Exception as e:
        state["error"] = str(e)

    return state


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------

def should_continue(state: AgentState) -> str:
    if state.get("error"):
        return END
    return "continue"


# ---------------------------------------------------------------------------
# Build graph
# ---------------------------------------------------------------------------

def build_agent() -> StateGraph:
    graph = StateGraph(AgentState)

    graph.add_node("input",   input_node)
    graph.add_node("content", content_node)
    graph.add_node("format",  format_node)
    graph.add_node("save",    save_node)

    graph.set_entry_point("input")

    graph.add_conditional_edges("input",   should_continue, {"continue": "content", END: END})
    graph.add_conditional_edges("content", should_continue, {"continue": "format",  END: END})
    graph.add_conditional_edges("format",  should_continue, {"continue": "save",    END: END})
    graph.add_edge("save", END)

    return graph.compile()


# Singleton — import and call this
agent = build_agent()


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def run_agent(
    input_type: str,
    input_content: str,
    post_type: str = "text",
    tone: str = "educational",
    hook_style: str = "question",
    length: str = "medium",
    sheets_row_id: str = "",
) -> AgentState:
    """Run the full agent pipeline and return final state."""
    initial_state: AgentState = {
        "input_type":        input_type,
        "input_content":     input_content,
        "post_type":         post_type,
        "tone":              tone,
        "hook_style":        hook_style,
        "length":            length,
        "sheets_row_id":     sheets_row_id,
        "extracted_content": "",
        "title":             "",
        "content":           "",
        "slides":            [],
        "image_url":         "",
        "pdf_bytes":         b"",
        "post_id":           "",
        "error":             "",
    }
    result = await agent.ainvoke(initial_state)
    return result