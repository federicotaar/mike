from agent.memory import Memory


def test_remember_and_recall(tmp_path):
    m = Memory(str(tmp_path / "t.db"))
    m.remember("preference", "likes short answers")
    rows = m.recall()
    assert len(rows) == 1
    assert rows[0][2] == "likes short answers"


def test_correction_supersedes(tmp_path):
    m = Memory(str(tmp_path / "t.db"))
    old = m.remember("fact", " wakes at 8")
    m.correct(old, "wakes at 6:10")
    texts = [t for _, _, t in m.recall()]
    assert "wakes at 6:10" in texts
    assert all("8" not in t for t in texts)


def test_forget_deletes_for_good(tmp_path):
    m = Memory(str(tmp_path / "t.db"))
    mid = m.remember("fact", "lives in Ferrara")
    assert m.forget(mid) is True
    assert all(t != "lives in Ferrara" for _, _, t in m.recall())
    # deleting twice is a real False, not a fake ok
    assert m.forget(mid) is False


def test_recall_filters_by_kind(tmp_path):
    m = Memory(str(tmp_path / "t.db"))
    m.remember("preference", "short answers")
    m.remember("fact", "has an iPhone 13")
    prefs = m.recall(kind="preference")
    assert [t for _, _, t in prefs] == ["short answers"]
    assert len(m.recall()) == 2


def test_approvals_history_includes_decided(tmp_path):
    m = Memory(str(tmp_path / "t.db"))
    aid = m.request_approval("text Marco", "reply to Marco")
    m.decide_approval(aid, True)
    history = m.approvals_history()
    assert len(history) == 1
    assert history[0]["status"] == "approved"
    assert history[0]["summary"] == "text Marco"


def test_prune_activity_keeps_newest(tmp_path):
    m = Memory(str(tmp_path / "t.db"))
    for i in range(10):
        m.log_activity("chat", f"msg {i}")
    removed = m.prune_activity(keep=3)
    assert removed == 7
    remaining = m.recent_activity(limit=100)
    assert len(remaining) == 3
    assert remaining[0]["summary"] == "msg 9"


def test_remember_rejects_unknown_kind(tmp_path):
    import pytest
    m = Memory(str(tmp_path / "t.db"))
    with pytest.raises(ValueError):
        m.remember("secret", "should not store")


def test_shared_connection_serializes_concurrent_writes(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    m = Memory(str(tmp_path / "threads.db"))
    def write(i):
        mid = m.remember("fact", f"fact {i}")
        m.log_activity("test", f"event {i}")
        return mid
    with ThreadPoolExecutor(max_workers=8) as pool:
        ids = list(pool.map(write, range(100)))
    assert len(set(ids)) == 100
    assert len(m.recall(limit=200)) == 100
    assert len(m.recent_activity(limit=200)) == 100


def test_concurrent_correction_has_single_winner(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    m = Memory(str(tmp_path / "correction.db"))
    old = m.remember("fact", "old")
    def correct(i):
        try: return m.correct(old, f"new {i}")
        except ValueError: return None
    with ThreadPoolExecutor(max_workers=8) as pool:
        outcomes = list(pool.map(correct, range(20)))
    assert sum(v is not None for v in outcomes) == 1
    assert len(m.recall()) == 1
