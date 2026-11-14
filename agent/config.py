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


def _as_cap(value: str, default: int) -> int:
    """Parse a daily cap: like an int, but a negative cap means no cap (0)."""
    return max(0, _as_int(value, default))


def _as_port(value: str, default: int) -> int:
    """Parse a TCP port; anything outside 1-65535 would only fail later inside
    uvicorn, so fall back to the default while the message is still clear."""
    port = _as_int(value, default)
    return port if 1 <= port <= 65535 else default


@dataclass(frozen=True)
class Settings:
    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    ntfy_topic: str = os.getenv("NTFY_TOPIC", "")
    api_token: str = os.getenv("MIKE_TOKEN", "")
    agent_name: str = os.getenv("AGENT_NAME", "agent")
    approval_required: bool = _as_bool(os.getenv("APPROVAL_REQUIRED", "true"), True)
    db_path: str = os.getenv("DB_PATH", "mike.db")  # repo-local by default; docker sets DB_PATH=/data/agent.db
    host: str = os.getenv("HOST", "127.0.0.1")
    # Optional local safety cap on model requests per day. 0 = no cap. This is the
    # user's own limit, NOT the provider's quota, which Mike cannot read.
    local_daily_cap: int = _as_cap(os.getenv("MIKE_LOCAL_DAILY_CAP", "0"), 0)
    port: int = _as_port(os.getenv("PORT", "8787"), 8787)


settings = Settings()
