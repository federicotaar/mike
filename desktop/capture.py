"""Open every desktop window with sample data and save a real screenshot of each.

Used by CI (xvfb) so UI changes can be reviewed as images before any release.
Usage: python -m desktop.capture OUTPUT_DIR
"""
from pathlib import Path
import sys
import tempfile
import tkinter as tk

from PIL import ImageGrab

from desktop.__main__ import MikeWindow
from desktop.service import DesktopService


def _shot(root, out: Path, name: str) -> None:
    root.update_idletasks()
    root.update()
    root.after(400, root.quit)
    root.mainloop()
    ImageGrab.grab().save(out / f"{name}.png")


def main(out_dir: str) -> None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    root = tk.Tk()
    root.geometry("+40+40")
    window = MikeWindow(root)
    window.service = DesktopService(Path(tempfile.mkdtemp()))
    memory = window.service.memory
    fact = memory.remember("fact", "Lives in Modena")
    memory.remember("preference", "Likes short answers")
    memory.request_approval("[TEST FIXTURE] Example approval A", "Sample row for the screenshot")
    memory.request_approval("[TEST FIXTURE] Example approval B", "Sample row for the screenshot")
    memory.log_activity("chat", "Asked about tomorrow's schedule")
    window.service.edit_fact(fact, "Lives in Modena, Italy")
    window.append("You", "What is waiting for me?")
    window.append("Mike", "This is a screenshot fixture, not a real conversation.")
    _shot(root, out, "01-main")
    for name, opener in (("02-memory", window.show_memory),
                         ("03-activity", window.show_activity),
                         ("04-approvals", window.show_approvals)):
        before = set(root.winfo_children())
        opener()
        new = [w for w in root.winfo_children() if w not in before]
        _shot(root, out, name)
        for w in new:
            w.destroy()
    root.destroy()
    print("CAPTURED", sorted(p.name for p in out.glob("*.png")))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "captures")
