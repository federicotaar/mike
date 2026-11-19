from agent.memory import Memory


def test_export_activity_newest_first_with_optional_limit():
    m = Memory(":memory:")
    for i in range(3):
        m.log_activity("note", f"entry {i}")
    all_rows = m.export_activity()
    assert [r["summary"] for r in all_rows] == ["entry 2", "entry 1", "entry 0"]
    assert all(set(r) == {"id", "kind", "summary", "created_at"} for r in all_rows)
    assert len(m.export_activity(limit=2)) == 2
    for bad in (0, -1, 1.5, "2"):
        try:
            m.export_activity(limit=bad)
            raise AssertionError(f"accepted {bad!r}")
        except ValueError:
            pass


def test_prune_activity_older_than_removes_only_old_rows():
    import time
    m = Memory(":memory:")
    old_id = m.log_activity("note", "ancient")
    new_id = m.log_activity("note", "fresh")
    m.db.execute("UPDATE activity SET created_at=? WHERE id=?", (time.time() - 10 * 86400, old_id))
    m.db.commit()
    assert m.prune_activity_older_than(7) == 1
    kinds = [r["id"] for r in m.recent_activity()]
    assert str(new_id) in kinds and str(old_id) not in kinds
    # nothing old left: second run removes zero
    assert m.prune_activity_older_than(7) == 0
    for bad in (-1, True, "7"):
        try:
            m.prune_activity_older_than(bad)
            raise AssertionError(f"accepted {bad!r}")
        except ValueError:
            pass


def test_find_duplicate_memories_groups_normalized_text():
    m = Memory(":memory:")
    a = m.remember("fact", "Likes  coffee")
    m.remember("fact", "likes coffee")
    m.remember("preference", "different thing entirely")
    groups = m.find_duplicate_memories()
    assert len(groups) == 1
    assert len(groups[0]) == 2
    assert groups[0][0]["id"] == a
    # a superseded memory no longer counts as a duplicate
    m.correct(a, "likes tea")
    assert m.find_duplicate_memories() == []


def test_count_activity_total_and_per_kind():
    m = Memory(":memory:")
    assert m.count_activity() == 0
    for i in range(5):
        m.log_activity("note", f"n{i}")
    m.log_activity("sync", "s0")
    assert m.count_activity() == 6
    assert m.count_activity("note") == 5
    assert m.count_activity("sync") == 1
    assert m.count_activity("missing-kind") == 0


def test_activity_counts_group_per_kind():
    m = Memory(":memory:")
    assert m.activity_counts() == {}
    m.log_activity("note", "one")
    m.log_activity("note", "two")
    m.log_activity("sync", "three")
    assert m.activity_counts() == {"note": 2, "sync": 1}


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


def test_export_memories_returns_everything_active(tmp_path):
    m = Memory(str(tmp_path / "t.db"))
    old = m.remember("fact", "v1")
    m.correct(old, "v2")
    m.remember("preference", "short answers")
    rows = m.export_memories()
    assert [r["text"] for r in rows] == ["short answers", "v2"]
    assert all("createdAt" in r for r in rows)


def test_search_memories_kind_filter(tmp_path):
    m = Memory(str(tmp_path / "t.db"))
    m.remember("fact", "lives in Mirandola")
    m.remember("preference", "Mirandola coffee bar on Saturdays")
    all_hits = m.search_memories("mirandola")
    assert len(all_hits) == 2
    fact_hits = m.search_memories("mirandola", kind="fact")
    assert fact_hits == [(all_hits[1][0], "fact", "lives in Mirandola")]


def test_search_memories_rejects_unknown_kind(tmp_path):
    import pytest
    m = Memory(str(tmp_path / "t.db"))
    with pytest.raises(ValueError):
        m.search_memories("anything", kind="bogus")


def test_synchronized_holds_the_instance_lock_during_the_call():
    """The decorator must serialize on self._lock: a method that observes the
    lock mid-call proves concurrent calls cannot interleave."""
    import threading
    from agent.memory import synchronized

    class Dummy:
        def __init__(self):
            self._lock = threading.Lock()

        @synchronized
        def probe(self):
            # locked by the decorator already: a non-blocking acquire fails
            return self._lock.acquire(blocking=False)

    assert Dummy().probe() is False
