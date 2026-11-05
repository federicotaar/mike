from agent.memory import Memory


def test_counter_counts_and_resets_per_day():
    m = Memory(":memory:")
    assert m.requests_today("2026-11-05") == 0
    assert m.count_request("2026-11-05") == 1
    assert m.count_request("2026-11-05") == 2
    assert m.requests_today("2026-11-05") == 2
    assert m.requests_today("2026-11-06") == 0
    assert m.count_request("2026-11-06") == 1
