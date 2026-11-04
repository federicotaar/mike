"""Provider rules: fail closed with no approved key; the model stays free-tier."""
import asyncio
import dataclasses

import pytest

from agent import brain


def test_no_approved_key_fails_closed(monkeypatch):
    monkeypatch.setattr(brain, "settings", dataclasses.replace(brain.settings, groq_api_key=""))
    with pytest.raises(brain.ProviderNotConfigured):
        asyncio.run(brain.think([{"role": "user", "content": "hi"}]))


def test_configured_model_and_quota_fail_closed(monkeypatch):
    import httpx
    monkeypatch.setattr(brain, "settings", dataclasses.replace(brain.settings, groq_api_key="test-only"))
    seen = []
    class Client:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def post(self, url, **kwargs):
            seen.append((url, kwargs))
            return httpx.Response(429, request=httpx.Request("POST", url))
    monkeypatch.setattr(brain.httpx, "AsyncClient", Client)
    with pytest.raises(brain.QuotaSpent):
        asyncio.run(brain.think([{"role": "user", "content": "hello"}]))
    assert len(seen) == 1  # No retry or fallback provider.
    assert seen[0][0] == brain.GROQ_URL
    assert seen[0][1]["json"]["model"] == brain.GROQ_MODEL
