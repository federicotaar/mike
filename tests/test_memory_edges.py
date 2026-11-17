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
