"""Edge cases for Memory that the main tests do not cover."""
import pytest

from agent.memory import Memory


@pytest.fixture
def mem(tmp_path):
    return Memory(str(tmp_path / "m.db"))


def test_recall_filters_by_kind_and_limit(mem):
    mem.remember("fact", "a")
    mem.remember("preference", "b")
    mem.remember("fact", "c")
    assert {t for _, _, t in mem.recall(kind="fact")} == {"a", "c"}
    assert len(mem.recall(limit=1)) == 1


def test_correct_chain_only_latest_is_active(mem):
    first = mem.remember("fact", "v1")
    second = mem.correct(first, "v2")
    third = mem.correct(second, "v3")
    assert [t for _, _, t in mem.recall()] == ["v3"]
    with pytest.raises(ValueError):
        mem.correct(first, "late edit of a superseded memory")
    assert third > second > first


def test_correct_keeps_kind(mem):
    old = mem.remember("preference", "likes tea")
    mem.correct(old, "likes coffee")
    assert [(k, t) for _, k, t in mem.recall()] == [("preference", "likes coffee")]


def test_forget_unknown_returns_false(mem):
    assert mem.forget(12345) is False


def test_blank_memory_rejected_everywhere(mem):
    with pytest.raises(ValueError):
        mem.remember("fact", "  \n")
    old = mem.remember("fact", "ok")
    with pytest.raises(ValueError):
        mem.correct(old, "")
    assert [t for _, _, t in mem.recall()] == ["ok"]


def test_approval_can_only_be_decided_once(mem):
    aid = mem.request_approval("send mail", "details")
    assert mem.decide_approval(aid, True) is True
    assert mem.decide_approval(aid, False) is False
    assert mem.pending_approvals() == []


def test_prune_activity_keeps_newest(mem):
    for i in range(6):
        mem.log_activity("chat", f"e{i}")
    assert mem.prune_activity(keep=2) == 4
    assert [a["summary"] for a in mem.recent_activity()] == ["e5", "e4"]
    with pytest.raises(ValueError):
        mem.prune_activity(keep=-1)


def test_pause_flag_round_trip(mem):
    assert mem.is_paused() is False
    mem.set_paused(True)
    assert mem.is_paused() is True
    mem.set_paused(False)
    assert mem.is_paused() is False


def test_request_counter_resets_on_new_day(mem):
    assert mem.count_request("2026-11-05") == 1
    assert mem.count_request("2026-11-05") == 2
    assert mem.requests_today("2026-11-06") == 0
    assert mem.count_request("2026-11-06") == 1


def test_recall_rejects_unknown_kind_and_bad_limit(mem):
    with pytest.raises(ValueError):
        mem.recall(kind="secret")
    with pytest.raises(ValueError):
        mem.recall(limit=0)
    with pytest.raises(ValueError):
        mem.recall(limit=-5)


def test_request_approval_rejects_blank_summary(mem):
    with pytest.raises(ValueError):
        mem.request_approval("   ", "detail")
    assert mem.pending_approvals() == []


def test_log_activity_rejects_blank_fields(mem):
    with pytest.raises(ValueError):
        mem.log_activity("", "something happened")
    with pytest.raises(ValueError):
        mem.log_activity("chat", "  ")
    assert mem.recent_activity() == []


def test_approvals_history_rejects_bad_limit(mem):
    mem.request_approval("x", "y")
    with pytest.raises(ValueError):
        mem.approvals_history(limit=0)
    assert len(mem.approvals_history(limit=1)) == 1


def test_approval_by_id_hit_and_miss(mem):
    aid = mem.request_approval("call Marco", "context")
    row = mem.approval_by_id(aid)
    assert row["summary"] == "call Marco"
    assert row["status"] == "pending"
    mem.decide_approval(aid, True)
    assert mem.approval_by_id(aid)["status"] == "approved"
    assert mem.approval_by_id(999999) is None


def test_recall_breaks_created_at_ties_newest_id_first(tmp_path):
    m = Memory(str(tmp_path / "t.db"))
    m.remember("fact", "remembered first")
    m.remember("fact", "remembered second")
    m.db.execute("UPDATE memories SET created_at=?", (1700000000.0,))
    m.db.commit()
    texts = [t for _, _, t in m.recall()]
    assert texts == ["remembered second", "remembered first"]


def test_search_treats_like_metacharacters_as_literal(mem):
    # instr() search: % and _ must match themselves, not act as wildcards
    mem.remember("fact", "coverage is 100% on weekdays")
    mem.remember("fact", "totally unrelated note")
    hits = mem.search_memories("100%")
    assert len(hits) == 1 and "100%" in hits[0][2]
    mem.remember("fact", "file a_b.py")
    hits = mem.search_memories("a_b")
    assert len(hits) == 1 and "a_b" in hits[0][2]


def test_kv_round_trip_overwrite_and_default(mem):
    assert mem.get_kv("missing") is None
    assert mem.get_kv("missing", "fallback") == "fallback"
    mem.set_kv("theme", "dark")
    assert mem.get_kv("theme") == "dark"
    mem.set_kv("theme", "light")
    assert mem.get_kv("theme") == "light"


def test_correct_unknown_memory_rejected(mem):
    # correcting an id that does not exist fails loudly, no phantom memory
    import pytest

    before = mem.count_memories()
    with pytest.raises(ValueError):
        mem.correct(9999, "fixed text")
    assert mem.count_memories() == before

def test_export_ties_use_descending_ids(mem):
    mem.remember('fact','first');mem.remember('fact','second')
    mem.db.execute('UPDATE memories SET created_at=1');mem.db.commit()
    assert [x['text'] for x in mem.export_memories()]==['second','first']

def test_approval_queue_ties_are_fifo(mem):
    a=mem.request_approval('first','detail');b=mem.request_approval('second','detail')
    mem.db.execute('UPDATE approvals SET created_at=1');mem.db.commit()
    assert [x['id'] for x in mem.pending_approvals()]==[str(a),str(b)]
    assert [x['id'] for x in mem.approvals_history()]==[str(b),str(a)]

def test_activity_ties_and_pruning_keep_newest(mem):
    for i in range(4):mem.log_activity('test',str(i))
    mem.db.execute('UPDATE activity SET created_at=1');mem.db.commit()
    assert [x['summary'] for x in mem.recent_activity()]==['3','2','1','0']
    assert [x['summary'] for x in mem.recent_activity(kind='test')]==['3','2','1','0']
    assert mem.prune_activity(2)==2
    assert [x['summary'] for x in mem.recent_activity()]==['3','2']

def test_activity_rejects_invalid_limit_types(mem):
    for value in (0,-1,True,1.5,'1'):
        with pytest.raises(ValueError):mem.recent_activity(limit=value)

def test_denied_approval_cannot_be_reapproved(mem):
    aid=mem.request_approval('test','detail')
    assert mem.decide_approval(aid,False)
    assert not mem.decide_approval(aid,True)
    assert mem.approval_by_id(aid)['status']=='denied' 

def test_backup_restore_is_atomic_deduplicated_and_portable(tmp_path):
    from agent.memory import Memory
    m = Memory(str(tmp_path / "restore.db"))
    original = m.remember("fact", "A")
    assert m.import_memories([{"id": 999, "kind": "fact", "text": "A"},
                             {"kind": "fact", "text": "B", "createdAt": 42},
                             {"kind": "fact", "text": "B"}]) == {"imported": 1, "skipped": 2}
    restored = next(x for x in m.export_memories() if x["text"] == "B")
    assert restored["createdAt"] == 42
    assert restored["id"] != 999
    m.correct(original, "corrected A")
    backup = m.export_memories()
    fresh = Memory(str(tmp_path / "fresh.db"))
    assert fresh.import_memories(backup)["imported"] == 2
    assert sorted((x["kind"], x["text"], x["createdAt"]) for x in fresh.export_memories()) == sorted((x["kind"], x["text"], x["createdAt"]) for x in backup)
    assert fresh.import_memories(backup) == {"imported": 0, "skipped": 2}


def test_backup_restore_rejects_invalid_batch_without_partial_writes(tmp_path):
    import pytest
    from agent.memory import Memory
    m = Memory(str(tmp_path / "atomic.db"))
    valid = {"kind": "fact", "text": "valid"}
    invalid = [None, [], {"kind": "unknown", "text": "x"}, {"kind": [], "text": "x"},
               {"kind": "fact", "text": " "}, {"kind": "fact", "text": 5},
               {**valid, "createdAt": float("nan")}, {**valid, "createdAt": True},
               {**valid, "createdAt": -1}, {**valid, "text": "x" * 4001}]
    for bad in invalid:
        with pytest.raises(ValueError):
            m.import_memories([valid, bad])
        assert m.count_memories() == 0
    with pytest.raises(ValueError):
        m.import_memories([valid] * 1001)
    assert m.import_memories([]) == {"imported": 0, "skipped": 0}


def test_memory_category_counts_exclude_superseded_and_deleted(tmp_path):
    from agent.memory import Memory
    m = Memory(str(tmp_path / "counts.db"))
    assert m.memory_counts() == {"fact": 0, "feedback": 0, "preference": 0}
    old = m.remember("fact", "old")
    new = m.correct(old, "new")
    m.remember("preference", "short")
    assert m.memory_counts() == {"fact": 1, "feedback": 0, "preference": 1}
    m.forget(new)
    assert m.memory_counts()["fact"] == 0
