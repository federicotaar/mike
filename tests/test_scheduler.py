"""Digest cadence configuration: env override, default, and garbage fallback."""
from agent import scheduler


def test_digest_minutes_default(monkeypatch):
    monkeypatch.delenv("MIKE_DIGEST_MINUTES", raising=False)
    assert scheduler._digest_minutes() == 15


def test_digest_minutes_override_and_fallbacks(monkeypatch):
    monkeypatch.setenv("MIKE_DIGEST_MINUTES", "5")
    assert scheduler._digest_minutes() == 5
    monkeypatch.setenv("MIKE_DIGEST_MINUTES", "0")
    assert scheduler._digest_minutes() == 15
    monkeypatch.setenv("MIKE_DIGEST_MINUTES", "garbage")
    assert scheduler._digest_minutes() == 15
