from agent.memory import Memory


def test_counter_counts_and_resets_per_day():
    m = Memory(":memory:")
    assert m.requests_today("2026-11-05") == 0
    assert m.count_request("2026-11-05") == 1
    assert m.count_request("2026-11-05") == 2
    assert m.requests_today("2026-11-05") == 2
    assert m.requests_today("2026-11-06") == 0
    assert m.count_request("2026-11-06") == 1


def test_status_reports_counts_but_not_fake_provider_quota(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    from agent import api
    monkeypatch.setattr(api, "memory", Memory(":memory:"))
    r = TestClient(api.app).get("/status").json()
    assert r["quotaRemainingToday"] is None
    assert r["requestsSentToday"] == 0
    assert r["localDailyCap"] == 0


def test_local_cap_stops_chat_with_honest_message(monkeypatch):
    from dataclasses import replace
    from fastapi.testclient import TestClient
    from agent import api
    monkeypatch.setattr(api, "memory", Memory(":memory:"))
    monkeypatch.setattr(api, "settings", replace(api.settings, local_daily_cap=1))
    api.memory.count_request()
    reply = TestClient(api.app).post("/chat", json={"message": "hi"}).json()["reply"]
    assert "limit of 1 requests you set" in reply
    assert "free" not in reply
