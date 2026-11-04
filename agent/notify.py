"""ntfy push to the user's phone, same pattern NOVA already uses. Free."""
from __future__ import annotations
import httpx

from .config import settings


async def ping(title: str, body: str, priority: int = 3, tags: list[str] | None = None) -> None:
    if not settings.ntfy_topic:
        return
    headers = {"Title": title, "Priority": str(priority)}
    if tags:
        headers["Tags"] = ",".join(tags)
    async with httpx.AsyncClient(timeout=15) as client:
        await client.post(
            f"https://ntfy.sh/{settings.ntfy_topic}",
            content=body,
            headers=headers,
        )
