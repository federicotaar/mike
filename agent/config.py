"""Environment-driven configuration. Secrets come from .env, never from the repo."""
from __future__ import annotations
import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()  # reads .env in the working directory when present


def _as_bool(value: str, default: bool) -> bool:
    """Parse common truthy/falsy spellings; fall back to the default."""
    v = value.strip().lower()
    if v in ("1", "true", "yes", "on"):
        return True
    if v in ("0", "false", "no", "off"):
        return False
    return default


def _as_int(value: str, default: int) -> int:
    """Parse an int env value; fall back to the default on garbage."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class Settings:
    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    ntfy_topic: str = os.getenv("NTFY_TOPIC", "")
    api_token: str = os.getenv("MIKE_TOKEN", "")
    agent_name: str = os.getenv("AGENT_NAME", "agent")
    approval_required: bool = _as_bool(os.getenv("APPROVAL_REQUIRED", "true"), True)
    db_path: str = os.getenv("DB_PATH", "mike.db")  # repo-local by default; docker sets DB_PATH=/data/agent.db
    host: str = os.getenv("HOST", "127.0.0.1")
    daily_request_limit: int = _as_int(os.getenv("DAILY_REQUEST_LIMIT", "1000"), 1000)
    port: int = _as_int(os.getenv("PORT", "8787"), 8787)


settings = Settings()
