"""Click-through test on real Tk widgets (run under a display, e.g. xvfb in CI).

It presses the real buttons through Tk's invoke(), so the same callbacks the
user triggers run. Nothing here sends anything outside the machine.
"""
from pathlib import Path
import tempfile
import tkinter as tk
from tkinter import ttk

from desktop.__main__ import MikeWindow
from desktop.service import DesktopService


def walk(widget):
    for child in widget.winfo_children():
        yield child
        yield from walk(child)


def button(parent, text):
    for w in walk(parent):
        if isinstance(w, ttk.Button) and str(w.cget("text")) == text:
            return w
    raise AssertionError(f"no button {text!r}")


def popups(root):
    return [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)]


def main():
    root = tk.Tk()
    win = MikeWindow(root)
    win.service = DesktopService(Path(tempfile.mkdtemp()))
    mem = win.service.memory

    # Pause toggles through the real button and persists.
    button(root, "Pause").invoke()
    assert mem.is_paused()
    button(root, "Resume").invoke()
    assert not mem.is_paused()

    # Approvals: select a row, press Deny then Approve. Only status changes.
    a = mem.request_approval("[TEST] first", "x")
    b = mem.request_approval("[TEST] second", "y")
    button(root, "Approvals").invoke()
    root.update()
    (pop,) = popups(root)
    box = next(w for w in walk(pop) if isinstance(w, tk.Listbox))
    assert box.size() == 2
    box.selection_set(0)
    button(pop, "Deny").invoke()
    assert box.size() == 1
    box.selection_set(0)
    button(pop, "Approve").invoke()
    assert box.size() == 0 and mem.pending_approvals() == []
    statuses = {r["id"]: r["status"] for r in mem.approvals_history()}
    assert statuses[str(a)] == "denied" and statuses[str(b)] == "approved", statuses
    pop.destroy()

    # Approve/Deny with nothing selected must do nothing.
    c = mem.request_approval("[TEST] third", "z")
    button(root, "Approvals").invoke()
    root.update()
    (pop,) = popups(root)
    button(pop, "Approve").invoke()
    assert len(mem.pending_approvals()) == 1
    pop.destroy()

    # Memory window lists facts; New chat clears history but keeps facts.
    mem.remember("fact", "click-test fact")
    button(root, "Memory").invoke()
    root.update()
    (pop,) = popups(root)
    box = next(w for w in walk(pop) if isinstance(w, tk.Listbox))
    assert box.get(0) == "click-test fact"
    pop.destroy()
    win.service.history = [{"role": "user", "content": "hi"}]
    button(root, "New chat").invoke()
    assert win.service.history == [] and len(mem.recall()) == 1

    # Activity window shows what happened above.
    button(root, "Activity").invoke()
    root.update()
    (pop,) = popups(root)
    box = next(w for w in walk(pop) if isinstance(w, tk.Listbox))
    assert box.size() >= 3
    pop.destroy()
    root.destroy()
    print("DESKTOP CLICK TEST PASS")


if __name__ == "__main__":
    main()
