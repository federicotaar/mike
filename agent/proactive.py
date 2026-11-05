"""Proactive jobs. Each one speaks only when it has something real to say.

Current job: tell the user when approvals are waiting for their decision.
It never acts on an approval, never sends anything except a push to the
user's own ntfy topic, stays silent while paused, and does not repeat itself
until the set of pending approvals changes.
"""
from __future__ import annotations
import hashlib
from typing import Awaitable, Callable

from .memory import Memory

Sender = Callable[[str, str], Awaitable[None]]
DIGEST_KEY = "digest_last_signature"


def pending_digest(memory: Memory) -> tuple[str, str] | None:
    """(signature, text) for the pending approvals, or None when nothing waits."""
    pending = memory.pending_approvals()
    if not pending:
        return None
    ids = ",".join(sorted(p["id"] for p in pending))
    signature = hashlib.sha256(ids.encode()).hexdigest()[:16]
    lines = [f"- {p['summary']}" for p in pending[:5]]
    more = len(pending) - len(lines)
    if more > 0:
        lines.append(f"...and {more} more")
    noun = "approval is" if len(pending) == 1 else "approvals are"
    return signature, f"{len(pending)} {noun} waiting for you:\n" + "\n".join(lines)


async def run_approval_digest(memory: Memory, send: Sender) -> bool:
    """Send one digest if something new is waiting. Returns True when it sent."""
    if memory.is_paused():
        return False
    digest = pending_digest(memory)
    if digest is None:
        memory.set_kv(DIGEST_KEY, "")
        return False
    signature, text = digest
    if memory.get_kv(DIGEST_KEY) == signature:
        return False
    await send("Mike needs a decision", text)
    memory.set_kv(DIGEST_KEY, signature)
    memory.log_activity("proactive", "sent approvals digest")
    return True
