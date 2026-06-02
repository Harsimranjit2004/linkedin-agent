"""
YouTube transcript extractor.
Compatible with youtube-transcript-api >= 1.0.0
"""

import re
from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound, TranscriptsDisabled


def extract_video_id(url: str) -> str | None:
    patterns = [
        r"(?:v=)([a-zA-Z0-9_-]{11})",
        r"(?:youtu\.be/)([a-zA-Z0-9_-]{11})",
        r"(?:embed/)([a-zA-Z0-9_-]{11})",
        r"(?:shorts/)([a-zA-Z0-9_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def format_transcript(transcript) -> str:
    """Join transcript snippets into clean text."""
    return " ".join(snippet.text.strip() for snippet in transcript)


async def get_transcript(url: str) -> dict:
    video_id = extract_video_id(url)

    if not video_id:
        return {
            "success": False,
            "video_id": None,
            "transcript": "",
            "error": "Could not extract video ID from URL.",
        }

    try:
        ytt_api = YouTubeTranscriptApi()

        try:
            transcript = ytt_api.fetch(video_id, languages=["en"])
        except NoTranscriptFound:
            transcript_list = ytt_api.list(video_id)
            transcript = transcript_list.find_generated_transcript(["en"]).fetch()

        text = format_transcript(transcript)

        return {
            "success": True,
            "video_id": video_id,
            "transcript": text,
            "error": None,
        }

    except TranscriptsDisabled:
        return {
            "success": False,
            "video_id": video_id,
            "transcript": "",
            "error": "Transcripts are disabled for this video.",
        }
    except Exception as e:
        return {
            "success": False,
            "video_id": video_id,
            "transcript": "",
            "error": str(e),
        }