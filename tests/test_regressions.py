"""Storage and startup regressions found during the November audit."""
import asyncio
import pytest
from agent.memory import Memory
from agent import api


def test_tilde_database_path(tmp_path, monkeypatch):
    monkeypatch.setenv('HOME', str(tmp_path))
    monkeypatch.setenv('USERPROFILE', str(tmp_path))  # Windows expanduser uses this, not HOME.
    m = Memory('~/data/mike.db')
    assert (tmp_path / 'data/mike.db').exists()
    m.db.close()


def test_correction_preserves_kind_and_is_atomic(tmp_path):
    m = Memory(str(tmp_path / 'm.db'))
    mid = m.remember('fact', 'old')
    new = m.correct(mid, 'new')
    assert m.recall() == [(new, 'fact', 'new')]
    with pytest.raises(ValueError):
        m.correct(mid, 'another')
    assert len(m.recall()) == 1


def test_missing_correction_creates_nothing(tmp_path):
    m = Memory(str(tmp_path / 'm.db'))
    with pytest.raises(ValueError):
        m.correct(987, 'not stored')
    assert m.recall() == []


def test_whitespace_and_negative_pruning_rejected(tmp_path):
    m = Memory(str(tmp_path / 'm.db'))
    with pytest.raises(ValueError):
        m.remember('fact', '  \n')
    m.log_activity('chat', 'keep me')
    with pytest.raises(ValueError):
        m.prune_activity(-1)
    assert len(m.recent_activity()) == 1


def test_application_lifespan_starts_in_event_loop():
    async def run():
        async with api.lifespan(api.app):
            assert asyncio.get_running_loop().is_running()
    asyncio.run(run())
