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


@pytest.mark.parametrize("payload", [{}, {"choices": []}, {"choices": [{"message": {"content": None}}]}, {"choices": [{"message": {"content": " "}}]}])
def test_malformed_provider_response_fails_cleanly(monkeypatch, payload):
    import httpx
    monkeypatch.setattr(brain, "settings", dataclasses.replace(brain.settings, groq_api_key="test-only"))
    class Client:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def post(self, url, **kwargs):
            return httpx.Response(200, json=payload, request=httpx.Request("POST", url))
    monkeypatch.setattr(brain.httpx, "AsyncClient", Client)
    with pytest.raises(brain.InvalidProviderResponse):
        asyncio.run(brain.think([]))


@pytest.mark.parametrize("status", [401, 403])
def test_rejected_key_raises_distinct_error(monkeypatch, status):
    import httpx
    monkeypatch.setattr(brain, "settings", dataclasses.replace(brain.settings, groq_api_key="bad-key"))
    class Client:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def post(self, url, **kwargs):
            return httpx.Response(status, request=httpx.Request("POST", url))
    monkeypatch.setattr(brain.httpx, "AsyncClient", Client)
    with pytest.raises(brain.ProviderAuthRejected):
        asyncio.run(brain.think([{"role": "user", "content": "hi"}]))


def test_request_timeout_env_override(monkeypatch):
    monkeypatch.setenv("MIKE_GROQ_TIMEOUT", "5")
    assert brain._request_timeout() == 5.0
    monkeypatch.setenv("MIKE_GROQ_TIMEOUT", "2.5")
    assert brain._request_timeout() == 2.5
    monkeypatch.setenv("MIKE_GROQ_TIMEOUT", "garbage")
    assert brain._request_timeout() == 60.0
    monkeypatch.setenv("MIKE_GROQ_TIMEOUT", "-3")
    assert brain._request_timeout() == 60.0
    monkeypatch.delenv("MIKE_GROQ_TIMEOUT")
    assert brain._request_timeout() == 60.0
