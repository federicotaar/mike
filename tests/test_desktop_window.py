"""Exercise the window code paths with a stubbed tkinter (no display needed)."""
import sys
import types
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def window(tmp_path, monkeypatch):
    tk = MagicMock(name="tkinter")
    ttk = MagicMock(name="ttk")
    tk.ttk, tk.messagebox, tk.simpledialog = ttk, MagicMock(), MagicMock()
    monkeypatch.setitem(sys.modules, "tkinter", tk)
    monkeypatch.setitem(sys.modules, "tkinter.ttk", ttk)
    monkeypatch.setitem(sys.modules, "tkinter.messagebox", tk.messagebox)
    monkeypatch.setitem(sys.modules, "tkinter.simpledialog", tk.simpledialog)
    sys.modules.pop("desktop.__main__", None)
    import desktop.__main__ as main
    monkeypatch.setattr(main, "DesktopService", lambda: __import__("desktop.service", fromlist=["x"]).DesktopService(tmp_path))
    win = main.MikeWindow(MagicMock())
    yield win
    sys.modules.pop("desktop.__main__", None)


def test_new_chat_clears_history_and_keeps_facts(window):
    window.service.memory.remember("fact", "keep")
    window.service.history = [{"role": "user", "content": "hi"}]
    window.new_chat()
    assert window.service.history == []
    assert len(window.service.memory.recall()) == 1


def test_new_chat_is_refused_while_a_reply_is_pending(window):
    window.busy = True
    window.service.history = [{"role": "user", "content": "hi"}]
    window.new_chat()
    assert window.service.history != []


def test_show_activity_runs(window):
    window.service.memory.log_activity("chat", "something")
    window.show_activity()
