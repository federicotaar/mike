"""Proactivity: jobs that run on their own and ping the user when something matters.

One real job is registered: the approvals digest (see proactive.py). It checks
every few minutes but only speaks when the set of pending approvals changed.
"""
from __future__ import annotations
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .notify import ping
from .proactive import run_approval_digest


def _digest_minutes() -> int:
    """Digest cadence in minutes: MIKE_DIGEST_MINUTES, default 15, minimum 1."""
    import os
    raw = os.getenv("MIKE_DIGEST_MINUTES", "15")
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return 15
    return value if value >= 1 else 15


async def _digest_job() -> None:
    from .api import mem
    try:
        await run_approval_digest(mem(), lambda title, body: ping(title, body))
    except Exception as exc:  # a failed push must never take the core down
        mem().log_activity("proactive", f"digest failed: {type(exc).__name__}")


def start() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(_digest_job, "interval", minutes=_digest_minutes(),
                      id="approval-digest", max_instances=1, coalesce=True)
    scheduler.start()
    return scheduler
