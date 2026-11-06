"""ntfy push: without a configured topic, ping must be a silent no-op."""
import asyncio
import dataclasses

from agent import notify


def test_ping_without_topic_is_noop(monkeypatch):
    monkeypatch.setattr(notify, "settings", dataclasses.replace(notify.settings, ntfy_topic=""))
    # Must return without any network call.
    asyncio.run(notify.ping("hi", "there", priority=5, tags=["rocket"]))


def test_failed_push_is_not_silent(monkeypatch):
    import httpx
    import pytest
    monkeypatch.setattr(notify, "settings", dataclasses.replace(notify.settings, ntfy_topic="test-only"))
    class Client:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def post(self, url, **kwargs):
            return httpx.Response(503, request=httpx.Request("POST", url))
    monkeypatch.setattr(notify.httpx, "AsyncClient", Client)
    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(notify.ping("test", "not delivered"))


def test_ping_rejects_out_of_range_priority():
    import pytest
    for bad in (0, 6, -1):
        with pytest.raises(ValueError):
            asyncio.run(notify.ping("t", "b", priority=bad))


def test_ping_rejects_malformed_tags():
    import pytest
    for bad in (["a,b"], ["has space"], [""]):
        with pytest.raises(ValueError):
            asyncio.run(notify.ping("t", "b", tags=bad))
