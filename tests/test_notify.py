"""ntfy push: without a configured topic, ping must be a silent no-op."""
import asyncio
import dataclasses

from agent import notify


def test_ping_without_topic_is_noop(monkeypatch):
    monkeypatch.setattr(notify, "settings", dataclasses.replace(notify.settings, ntfy_topic=""))
    # Must return without any network call.
    asyncio.run(notify.ping("hi", "there", priority=5, tags=["rocket"]))
