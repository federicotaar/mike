"""Provider rules: fail closed with no approved key; the model stays free-tier."""
import asyncio
import dataclasses

import pytest

from agent import brain


def test_no_approved_key_fails_closed(monkeypatch):
    monkeypatch.setattr(brain, "settings", dataclasses.replace(brain.settings, groq_api_key=""))
    with pytest.raises(brain.ProviderNotConfigured):
        asyncio.run(brain.think([{"role": "user", "content": "hi"}]))


def test_model_defaults_to_free_tier(monkeypatch):
    monkeypatch.delenv("GROQ_MODEL", raising=False)
    # The constant is read at import time, so recompute the same way the module does.
    import os
    assert os.getenv("GROQ_MODEL", "openai/gpt-oss-120b") == brain.GROQ_MODEL
