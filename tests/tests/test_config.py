"""Config parsing must survive messy .env values, not crash the core."""
from agent.config import _as_bool, _as_int


def test_bool_spellings():
    for v in ("1", "true", "TRUE", " yes ", "on"):
        assert _as_bool(v, False) is True
    for v in ("0", "false", "no", "off"):
        assert _as_bool(v, True) is False


def test_bool_garbage_falls_back():
    assert _as_bool("banana", True) is True
    assert _as_bool("banana", False) is False


def test_int_parsing():
    assert _as_int("8787", 1) == 8787
    assert _as_int("not-a-port", 8787) == 8787
    assert _as_int("", 8787) == 8787
