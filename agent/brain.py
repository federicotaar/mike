"""Model calls: one user-approved provider, fail closed.

Design contract: Mike may use exactly one inference provider, and only after
the user explicitly chooses and approves it. Until that approval and its key
exist, no provider is configured and every call raises ProviderNotConfigured.
When a free daily quota is spent, Mike says so and stops - it must never move
the user's data to a different provider on its own, and never falls back to
anything paid.

Reference numbers, checked 25 Oct 2026, Groq free tier: ~1,000 requests/day,
30/min, 200K tokens/day (console.groq.com/docs/rate-limits). Other providers
can be added later, each only after the user's explicit yes.
"""
from __future__ import annotations
import os

import httpx

from .config import settings

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")  # free-tier model, overridable


def _request_timeout() -> float:
    """Seconds before a model call gives up. MIKE_GROQ_TIMEOUT overrides the
    60s default; garbage or non-positive values fall back to the default."""
    raw = os.getenv("MIKE_GROQ_TIMEOUT", "60")
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return 60.0
    return value if value > 0 else 60.0


class QuotaSpent(RuntimeError):
    """Today's free quota is gone. Say so, try again tomorrow."""


class InvalidProviderResponse(RuntimeError):
    """The provider answered without a usable text reply."""


class ProviderNotConfigured(RuntimeError):
    """No approved key yet."""


class ProviderAuthRejected(RuntimeError):
    """The provider rejected the configured key (401/403)."""


async def think(messages: list[dict]) -> str:
    key = settings.groq_api_key.strip()
    if not key:
        raise ProviderNotConfigured("no approved Groq key configured")
    async with httpx.AsyncClient(timeout=_request_timeout()) as client:
        r = await client.post(
            GROQ_URL,
            headers={"Authorization": f"Bearer {key}"},
            json={"model": GROQ_MODEL, "messages": messages},
        )
        if r.status_code in (402, 429):
            raise QuotaSpent("groq free tier limit reached")
        if r.status_code in (401, 403):
            raise ProviderAuthRejected("groq rejected the configured key")
        r.raise_for_status()
        try:
            content = r.json()["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise InvalidProviderResponse("provider returned an invalid chat response") from exc
        if not isinstance(content, str) or not content.strip():
            raise InvalidProviderResponse("provider returned no text reply")
        return content
