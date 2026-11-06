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


def test_search_memories_finds_substring_case_insensitive(tmp_path):
    m = Memory(str(tmp_path / "t.db"))
    m.remember("fact", "Lives in Ferrara")
    m.remember("preference", "short answers")
    hits = m.search_memories("ferrara")
    assert [t for _, _, t in hits] == ["Lives in Ferrara"]


def test_search_memories_skips_superseded_and_validates_input(tmp_path):
    m = Memory(str(tmp_path / "t.db"))
    old = m.remember("fact", "wakes at 8")
    m.correct(old, "wakes at 6:10")
    assert m.search_memories("wakes at 8") == []
    assert [t for _, _, t in m.search_memories("6:10")] == ["wakes at 6:10"]
    import pytest
    with pytest.raises(ValueError):
        m.search_memories("   ")
    with pytest.raises(ValueError):
        m.search_memories("x", limit=0)


def test_count_memories_total_and_per_kind(tmp_path):
    m = Memory(str(tmp_path / "t.db"))
    m.remember("fact", "a")
    m.remember("preference", "b")
    m.remember("fact", "c")
    assert m.count_memories() == 3
    assert m.count_memories("fact") == 2
    import pytest
    with pytest.raises(ValueError):
        m.count_memories("secret")


def test_count_memories_excludes_superseded_and_deleted(tmp_path):
    m = Memory(str(tmp_path / "t.db"))
    old = m.remember("fact", "v1")
    m.correct(old, "v2")
    gone = m.remember("fact", "gone")
    m.forget(gone)
    assert m.count_memories() == 1


def test_recent_activity_filters_by_kind(tmp_path):
    m = Memory(str(tmp_path / "t.db"))
    m.log_activity("chat", "hello")
    m.log_activity("stop", "paused")
    assert len(m.recent_activity()) == 2
    chats = m.recent_activity(kind="chat")
    assert [r["summary"] for r in chats] == ["hello"]


def test_memory_by_id_returns_active_memory_or_none(tmp_path):
    m = Memory(str(tmp_path / "t.db"))
    mid = m.remember("fact", "lives in Ferrara")
    row = m.memory_by_id(mid)
    assert row["kind"] == "fact"
    assert row["text"] == "lives in Ferrara"
    assert "createdAt" in row
    assert m.memory_by_id(999999) is None
    m.forget(mid)
    assert m.memory_by_id(mid) is None
