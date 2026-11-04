"""Desktop service never saves keys or silently changes providers."""
from desktop.service import DesktopService
from agent.brain import InvalidProviderResponse
import httpx
import pytest


def test_desktop_no_key_and_pause_do_not_call_network(tmp_path, monkeypatch):
    service = DesktopService(tmp_path)
    def forbidden(*args, **kwargs): raise AssertionError("unexpected network")
    monkeypatch.setattr(httpx.Client, "post", forbidden)
    assert "Enter your own" in service.chat("hi")
    service.memory.set_paused(True)
    assert "paused" in service.chat("hi")


def mock_reply(monkeypatch, status, payload):
    seen = []
    class Client:
        def __init__(self, **kwargs): assert kwargs['follow_redirects'] is False
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def post(self, url, **kwargs):
            seen.append((url, kwargs))
            return httpx.Response(status, json=payload, request=httpx.Request("POST", url))
    monkeypatch.setattr('desktop.service.httpx.Client', Client)
    return seen


def test_desktop_chat_uses_saved_facts_without_persisting_key(tmp_path, monkeypatch):
    service = DesktopService(tmp_path)
    service.key = "test-secret"
    service.memory.remember("fact", "likes short answers")
    seen = mock_reply(monkeypatch, 200, {"choices": [{"message": {"content": "Hello"}}]})
    assert service.chat("hi") == "Hello"
    assert len(seen) == 1
    assert "likes short answers" in seen[0][1]['json']['messages'][0]['content']
    service.memory.db.close()
    assert b"test-secret" not in (tmp_path / "mike.db").read_bytes()


@pytest.mark.parametrize('status', [402, 429])
def test_desktop_quota_never_falls_back(tmp_path, monkeypatch, status):
    service = DesktopService(tmp_path); service.key = "test"
    seen = mock_reply(monkeypatch, status, {})
    assert "No fallback" in service.chat("hello")
    assert len(seen) == 1


def test_desktop_malformed_response(tmp_path, monkeypatch):
    service = DesktopService(tmp_path); service.key = "test"
    mock_reply(monkeypatch, 200, {})
    with pytest.raises(InvalidProviderResponse): service.chat("hello")


def test_desktop_remembers_between_launches(tmp_path):
    service = DesktopService(tmp_path)
    service.memory.remember("fact", "a fact")
    service.memory.set_paused(True)
    again = DesktopService(tmp_path)
    assert again.memory.recall()[0][2] == "a fact"
    assert again.memory.is_paused()
    assert again.key == ""


def test_desktop_history_is_session_only_and_bounded(tmp_path, monkeypatch):
    service = DesktopService(tmp_path); service.key = "test"
    seen = mock_reply(monkeypatch, 200, {"choices": [{"message": {"content": "ok"}}]})
    for i in range(12): service.chat(f"message {i}")
    assert len(service.history) == 20
    assert len(seen[-1][1]["json"]["messages"]) == 22
    assert service.history[0]["content"] == "message 2"
    assert DesktopService(tmp_path).history == []
