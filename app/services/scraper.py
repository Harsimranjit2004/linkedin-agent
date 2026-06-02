"""
Article scraper — extracts clean text from any article or blog URL.
Uses BeautifulSoup4 + httpx.
"""

import httpx
from bs4 import BeautifulSoup

# Tags that usually contain the main article body
CONTENT_TAGS = ["article", "main", "section"]

# Tags to strip — noise, not content
STRIP_TAGS = [
    "script", "style", "nav", "header", "footer",
    "aside", "form", "button", "iframe", "noscript",
    "advertisement", "figure",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def clean_soup(soup: BeautifulSoup) -> BeautifulSoup:
    """Remove all noise tags from the soup in-place."""
    for tag in soup(STRIP_TAGS):
        tag.decompose()
    return soup


def extract_title(soup: BeautifulSoup) -> str:
    """Extract the page title."""
    og_title = soup.find("meta", property="og:title")
    if og_title and og_title.get("content"):
        return og_title["content"].strip()
    if soup.title:
        return soup.title.get_text().strip()
    h1 = soup.find("h1")
    if h1:
        return h1.get_text().strip()
    return ""


def extract_body(soup: BeautifulSoup) -> str:
    """
    Try to find the main article content.
    Falls back to <body> if no semantic content tag is found.
    """
    for tag in CONTENT_TAGS:
        element = soup.find(tag)
        if element:
            return element.get_text(separator=" ", strip=True)

    # Fallback: grab everything in body
    body = soup.find("body")
    if body:
        return body.get_text(separator=" ", strip=True)

    return soup.get_text(separator=" ", strip=True)


def truncate(text: str, max_chars: int = 8000) -> str:
    """Truncate to keep within reasonable token limits for the AI."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "... [truncated]"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def scrape_article(url: str) -> dict:
    """
    Scrape an article URL and return clean title + body text.

    Returns:
        {
            "success": bool,
            "url": str,
            "title": str,
            "content": str,
            "error": str | None
        }
    """
    try:
        async with httpx.AsyncClient(
            headers=HEADERS,
            follow_redirects=True,
            timeout=15.0,
        ) as client:
            response = await client.get(url)
            response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        soup = clean_soup(soup)

        title = extract_title(soup)
        body = extract_body(soup)
        body = truncate(body)

        if not body or len(body) < 100:
            return {
                "success": False,
                "url": url,
                "title": title,
                "content": "",
                "error": "Could not extract meaningful content from this URL.",
            }

        return {
            "success": True,
            "url": url,
            "title": title,
            "content": body,
            "error": None,
        }

    except httpx.HTTPStatusError as e:
        return {
            "success": False,
            "url": url,
            "title": "",
            "content": "",
            "error": f"HTTP {e.response.status_code}: Could not fetch the page.",
        }
    except httpx.TimeoutException:
        return {
            "success": False,
            "url": url,
            "title": "",
            "content": "",
            "error": "Request timed out. The site may be slow or blocking scrapers.",
        }
    except Exception as e:
        return {
            "success": False,
            "url": url,
            "title": "",
            "content": "",
            "error": str(e),
        }