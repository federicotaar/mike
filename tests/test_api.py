"""The iPhone app's contract: these endpoints and shapes must stay real."""
import pytest
from fastapi.testclient import TestClient

from agent import api


@pytest.fixture()
def client(tmp_path, monkeypatch):
    import dataclasses
    # Tests must not depend on the developer's own .env: no token required here.
    monkeypatch.setattr(api, "settings", dataclasses.replace(api.settings, api_token=""))
    monkeypatch.setattr(api, "memory", api.Memory(str(tmp_path / "t.db")))
    return TestClient(api.app)


def test_status_shape(client):
    s = client.get("/status").json()
    assert set(s) == {"providerConfigured", "quotaRemainingToday", "requestsSentToday",
                  "localDailyCap", "paused", "version", "uptimeSeconds"}
    assert s["paused"] is False
    assert s["version"] and s["version"] != "unknown"
    assert isinstance(s["uptimeSeconds"], int) and s["uptimeSeconds"] >= 0


def test_approval_lifecycle(client):
    api.memory.request_approval("text Marco", "Mike wants to reply to Marco's message")
    pending = client.get("/approvals/pending").json()
    assert len(pending) == 1
    a = pending[0]
    assert set(a) == {"id", "summary", "detail", "createdAt", "status"}
    assert a["status"] == "pending"
    assert client.post(f"/approvals/{a['id']}", json={"approve": True}).json() == {"ok": True}
    assert client.get("/approvals/pending").json() == []
    # deciding twice is a real 404, not a fake ok
    assert client.post(f"/approvals/{a['id']}", json={"approve": True}).status_code == 404


def test_activity_records_real_events(client):
    api.memory.request_approval("spend 5 EUR", "buy a coffee")
    aid = client.get("/approvals/pending").json()[0]["id"]
    client.post(f"/approvals/{aid}", json={"approve": False})
    entries = client.get("/activity").json()
    assert any(e["kind"] == "approval" and "denied" in e["summary"] for e in entries)
    assert all(set(e) == {"id", "kind", "summary", "time"} for e in entries)


def test_stop_pauses_chat(client):
    client.post("/stop")
    assert client.get("/status").json()["paused"] is True
    reply = client.post("/chat", json={"message": "hi"}).json()["reply"]
    assert "paused" in reply.lower()
    client.post("/start")
    assert client.get("/status").json()["paused"] is False


def test_token_required_when_configured(client, monkeypatch):
    import dataclasses
    monkeypatch.setattr(api, "settings", dataclasses.replace(api.settings, api_token="secret"))
    assert client.get("/status").status_code == 401
    assert client.get("/status", headers={"Authorization": "Bearer secret"}).status_code == 200


def test_chat_without_key_fails_closed(client, monkeypatch):
    import dataclasses
    monkeypatch.setattr(api, "settings", dataclasses.replace(api.settings, groq_api_key=""))
    reply = client.post("/chat", json={"message": "hello"}).json()["reply"]
    assert "model key" in reply.lower()


def test_delete_memory(client):
    mid = api.memory.remember("fact", "temporary fact")
    assert client.delete(f"/memories/{mid}").json() == {"deleted": True}
    assert client.delete(f"/memories/{mid}").status_code == 404
    entries = client.get("/activity").json()
    assert any(e["kind"] == "memory" for e in entries)


def test_chat_network_error_answers_honestly(client, monkeypatch):
    import httpx

    async def boom(messages):
        raise httpx.ConnectError("no route")

    monkeypatch.setattr(api, "think", boom)
    reply = client.post("/chat", json={"message": "hello"}).json()["reply"]
    assert "reach the model" in reply.lower()


def test_approvals_history_endpoint(client):
    api.memory.request_approval("post publicly", "post a status update")
    pending = client.get("/approvals/pending").json()
    client.post(f"/approvals/{pending[0]['id']}", json={"approve": False})
    history = client.get("/approvals").json()
    assert len(history) == 1
    assert history[0]["status"] == "denied"


def test_empty_feedback_rejected(client):
    assert client.post("/feedback", json={"text": ""}).status_code == 422


def test_empty_chat_message_rejected(client):
    assert client.post("/chat", json={"message": ""}).status_code == 422


def test_blank_and_oversized_inputs_rejected(client):
    assert client.post("/chat", json={"message": " \n"}).status_code == 422
    assert client.post("/chat", json={"message": "x" * 32001}).status_code == 422
    assert client.post("/feedback", json={"text": "  "}).status_code == 422
    assert client.post("/feedback", json={"text": "x" * 4001}).status_code == 422


def test_owner_mutations_require_token(client, monkeypatch):
    import dataclasses
    monkeypatch.setattr(api, "settings", dataclasses.replace(api.settings, api_token="secret"))
    assert client.post("/stop").status_code == 401
    assert client.post("/start").status_code == 401
    assert client.delete("/memories/1").status_code == 401
    assert client.post("/approvals/1", json={"approve": True}).status_code == 401


def test_invalid_provider_reply_is_honest(client, monkeypatch):
    async def broken(messages):
        raise api.InvalidProviderResponse("bad schema")
    monkeypatch.setattr(api, "think", broken)
    response = client.post("/chat", json={"message": "hello"})
    assert response.status_code == 200
    assert "no usable reply" in response.json()["reply"]


def test_memory_search_endpoint(client):
    api.memory.remember("fact", "lives in Ferrara")
    api.memory.remember("preference", "short answers")
    hits = client.get("/memories/search", params={"q": "ferrara"}).json()
    assert [h["text"] for h in hits] == ["lives in Ferrara"]
    assert hits[0]["kind"] == "fact"
    assert client.get("/memories/search", params={"q": " "}).status_code == 400


def test_chat_says_when_provider_rejects_key(client, monkeypatch):
    import dataclasses
    import httpx
    from agent import brain
    monkeypatch.setattr(api, "settings", dataclasses.replace(api.settings, groq_api_key="bad-key"))
    monkeypatch.setattr(brain, "settings", api.settings)
    class Client:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def post(self, url, **kwargs):
            return httpx.Response(401, request=httpx.Request("POST", url))
    monkeypatch.setattr(brain.httpx, "AsyncClient", Client)
    reply = client.post("/chat", json={"message": "hi"}).json()["reply"]
    assert "rejected" in reply.lower()


def test_activity_endpoint_filters_by_kind(client):
    api.memory.log_activity("chat", "hello")
    api.memory.log_activity("stop", "paused")
    rows = client.get("/activity", params={"kind": "chat"}).json()
    assert [r["summary"] for r in rows] == ["hello"]
    assert len(client.get("/activity").json()) == 2
