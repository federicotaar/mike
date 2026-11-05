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
