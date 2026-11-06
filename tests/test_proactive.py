import asyncio

from agent.memory import Memory
from agent.proactive import run_approval_digest


def run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


class Recorder:
    def __init__(self):
        self.sent = []

    async def __call__(self, title, body):
        self.sent.append((title, body))


def test_silent_when_nothing_pending():
    m, r = Memory(":memory:"), Recorder()
    assert run(run_approval_digest(m, r)) is False
    assert r.sent == []


def test_sends_once_per_pending_set():
    m, r = Memory(":memory:"), Recorder()
    m.request_approval("Save memory: likes tea", "detail")
    assert run(run_approval_digest(m, r)) is True
    assert run(run_approval_digest(m, r)) is False
    assert len(r.sent) == 1 and "1 approval is waiting" in r.sent[0][1]
    m.request_approval("Set reminder", "detail")
    assert run(run_approval_digest(m, r)) is True
    assert "2 approvals are waiting" in r.sent[1][1]


def test_silent_while_paused():
    m, r = Memory(":memory:"), Recorder()
    m.request_approval("x", "y")
    m.set_paused(True)
    assert run(run_approval_digest(m, r)) is False
    assert r.sent == []


def test_resets_after_decision_so_next_one_notifies():
    m, r = Memory(":memory:"), Recorder()
    a = m.request_approval("one", "d")
    run(run_approval_digest(m, r))
    m.decide_approval(a, True)
    assert run(run_approval_digest(m, r)) is False
    m.request_approval("two", "d")
    assert run(run_approval_digest(m, r)) is True


def test_never_decides_approvals():
    m, r = Memory(":memory:"), Recorder()
    m.request_approval("one", "d")
    run(run_approval_digest(m, r))
    assert len(m.pending_approvals()) == 1


def test_scheduler_registers_only_the_digest_job():
    from agent import scheduler

    async def go():
        s = scheduler.start()
        try:
            return [j.id for j in s.get_jobs()]
        finally:
            s.shutdown(wait=False)

    assert run(go()) == ["approval-digest"]


def test_digest_clips_long_summaries():
    m, r = Memory(":memory:"), Recorder()
    long_summary = "Review this   very long\napproval request " + "x" * 200
    m.request_approval(long_summary, "detail")
    assert run(run_approval_digest(m, r)) is True
    line = r.sent[0][1].splitlines()[1]
    assert line.startswith("- ")
    assert len(line) <= 103  # "- " + 100 clipped chars
    assert line.endswith("\u2026")


def test_digest_flattens_newlines_in_summaries():
    m, r = Memory(":memory:"), Recorder()
    m.request_approval("first line\nsecond line", "detail")
    assert run(run_approval_digest(m, r)) is True
    assert "first line second line" in r.sent[0][1]


def test_digest_resends_after_pending_set_clears():
    m, r = Memory(":memory:"), Recorder()
    aid = m.request_approval("water the plants", "detail")
    assert run(run_approval_digest(m, r)) is True
    m.decide_approval(aid, True)
    assert run(run_approval_digest(m, r)) is False  # nothing pending: signature resets
    m.request_approval("water the plants", "detail")
    assert run(run_approval_digest(m, r)) is True  # a new pending set speaks again
    assert len(r.sent) == 2
