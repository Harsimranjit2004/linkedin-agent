from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # LinkedIn
    LINKEDIN_CLIENT_ID: str
    LINKEDIN_CLIENT_SECRET: str
    LINKEDIN_REDIRECT_URI: str = "http://localhost:8000/auth/linkedin/callback"

    # Anthropic
    ANTHROPIC_API_KEY: str

    # OpenAI (image generation)
    OPENAI_API_KEY: str

    # Supabase
    SUPABASE_URL: str
    SUPABASE_KEY: str

    # Google Sheets
    GOOGLE_SHEETS_ID: str = ""
    GOOGLE_SERVICE_ACCOUNT_JSON: str = "service_account.json"

    # App
    APP_SECRET_KEY: str = "change-me-in-production"
    FRONTEND_URL: str = "http://localhost:3000"

    # Brand voice — baked into every AI prompt
    BRAND_NAME: str = "Harsimranjit Singh"
    BRAND_ROLE: str = "Junior Software Developer"
    BRAND_AUDIENCE: str = "Junior developers, tech community"
    BRAND_STYLE: str = "Educational, practical, developer-focused"
    BRAND_SKILLS: str = "TypeScript, Node.js, Python, FastAPI, AWS, Docker, Kubernetes"
    BRAND_LINKEDIN: str = "https://www.linkedin.com/in/harsimranjits1/"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()


def get_brand_voice() -> str:
    """Returns brand voice block injected into every AI prompt."""
    return f"""
You are writing LinkedIn content on behalf of {settings.BRAND_NAME}.

ABOUT THE AUTHOR:
- Role: {settings.BRAND_ROLE}
- Skills: {settings.BRAND_SKILLS}
- Target audience: {settings.BRAND_AUDIENCE}
- Content style: {settings.BRAND_STYLE}

When given source material (video, article, notes), extract the TOPIC and teach it.
Never retell someone else's personal journey or story — teach the concept, the tool, the insight.
The post should make the reader smarter about the topic, not tell them what someone else experienced.
""".strip()