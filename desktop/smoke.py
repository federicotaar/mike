"""Bounded GUI smoke: create widgets, exercise memory and pause, save a preview."""
import os
from pathlib import Path
import tempfile
import tkinter as tk
from desktop.__main__ import MikeWindow
from desktop.service import DesktopService


def main():
    root = tk.Tk()
    window = MikeWindow(root)
    window.service = DesktopService(Path(tempfile.mkdtemp()))
    window.toggle_pause()
    assert window.service.memory.is_paused()
    window.toggle_pause()
    assert not window.service.memory.is_paused()
    window.service.memory.remember("fact", "Smoke test fact")
    window.show_memory()
    root.update()
    root.after(800, root.quit)
    root.mainloop()
    if os.getenv("MIKE_SCREENSHOT"):
        from PIL import ImageGrab
        ImageGrab.grab().save(os.environ["MIKE_SCREENSHOT"])
    root.destroy()
    print("DESKTOP SMOKE PASS")


if __name__ == "__main__": main()
