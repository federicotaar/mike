from agent.config import _as_bool, _as_int


def test_as_bool_spellings_and_default():
    assert [_as_bool(v, False) for v in ("1", "TRUE", " yes ", "On")] == [True] * 4
    assert [_as_bool(v, True) for v in ("0", "False", "no", "OFF")] == [False] * 4
    assert _as_bool("maybe", True) is True
    assert _as_bool("", False) is False


def test_as_int_garbage_falls_back():
    assert _as_int("42", 1) == 42
    assert _as_int("abc", 7) == 7
    assert _as_int("", 7) == 7
    assert _as_int(None, 7) == 7
