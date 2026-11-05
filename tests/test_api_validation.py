"""Input validation and auth on the HTTP API."""
import dataclasses

import pytest
from fastapi.testclient import TestClient

from agent import api


@pytest.fixture()
def open_client(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "settings", dataclasses.replace(api.settings, api_token=""))
    monkeypatch.setattr(api, "memory", api.Memory(str(tmp_path / "t.db")))
    return TestClient(api.app)


@pytest.fixture()
def locked_client(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "settings", dataclasses.replace(api.settings, api_token="s3cret"))
    monkeypatch.setattr(api, "memory", api.Memory(str(tmp_path / "t.db")))
    return TestClient(api.app)


def test_chat_rejects_blank_and_oversized(open_client):
    assert open_client.post("/chat", json={"message": "   "}).status_code == 422
    assert open_client.post("/chat", json={"message": ""}).status_code == 422
    assert open_client.post("/chat", json={"message": "x" * 32001}).status_code == 422


def test_chat_requires_message_field(open_client):
    assert open_client.post("/chat", json={}).status_code == 422


def test_token_required_when_configured(locked_client):
    assert locked_client.get("/status").status_code == 401
    assert locked_client.get("/status", headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert locked_client.get("/status", headers={"Authorization": "Bearer s3cret"}).status_code == 200


def test_token_check_covers_write_endpoints(locked_client):
    assert locked_client.post("/chat", json={"message": "hi"}).status_code == 401


def test_paused_chat_never_calls_the_model(open_client, monkeypatch):
    async def boom(*a, **k):
        raise AssertionError("model must not be called while paused")
    monkeypatch.setattr(api, "think", boom)
    api.memory.set_paused(True)
    reply = open_client.post("/chat", json={"message": "hello"}).json()["reply"]
    assert "paused" in reply.lower()
    assert api.memory.requests_today() == 0
