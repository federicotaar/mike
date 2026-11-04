"""Native desktop chat window. Start with python -m desktop."""
from __future__ import annotations
import queue
import threading
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from desktop.service import DesktopService


class MikeWindow:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.service = DesktopService()
        self.results: queue.Queue = queue.Queue()
        self.busy = False
        root.title("Mike - Desktop Preview")
        root.geometry("860x700")
        root.minsize(580, 480)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(2, weight=1)
        header = ttk.Frame(root, padding=18)
        header.grid(row=0, column=0, sticky="ew")
        ttk.Label(header, text="Mike", font=("Arial", 24, "bold")).pack(side="left")
        ttk.Label(header, text="Desktop preview | Your key. Your control.").pack(side="left", padx=18)
        setup = ttk.Frame(root, padding=(18, 0, 18, 12))
        setup.grid(row=1, column=0, sticky="ew")
        setup.columnconfigure(1, weight=1)
        ttk.Label(setup, text="Groq key (session only)").grid(row=0, column=0, padx=(0, 10))
        self.key = ttk.Entry(setup, show="*")
        self.key.grid(row=0, column=1, sticky="ew")
        self.pause = ttk.Button(setup, text="Resume" if self.service.memory.is_paused() else "Pause", command=self.toggle_pause)
        self.pause.grid(row=0, column=2, padx=8)
        ttk.Button(setup, text="Memory", command=self.show_memory).grid(row=0, column=3)
        self.transcript = tk.Text(root, wrap="word", state="disabled", padx=18, pady=16, font=("Arial", 12))
        self.transcript.grid(row=2, column=0, sticky="nsew", padx=18)
        self.append("Mike", "Welcome. Enter your own Groq API key and send a message. Keys are not saved. This preview supports chat, manually saved memory and pause. It does not run tools, reminders or an always-on agent.")
        controls = ttk.Frame(root, padding=18)
        controls.grid(row=3, column=0, sticky="ew")
        controls.columnconfigure(0, weight=1)
        self.input = ttk.Entry(controls, font=("Arial", 12))
        self.input.grid(row=0, column=0, sticky="ew")
        self.input.bind("<Return>", lambda _: self.send())
        self.send_button = ttk.Button(controls, text="Send", command=self.send)
        self.send_button.grid(row=0, column=1, padx=(10, 0))
        self.status = ttk.Label(root, text="Ready. No request is sent until you press Send.", padding=(18, 0, 18, 12))
        self.status.grid(row=4, column=0, sticky="w")
        root.after(100, self.poll)

    def append(self, speaker, text):
        self.transcript.configure(state="normal")
        self.transcript.insert("end", f"{speaker}\n{text}\n\n")
        self.transcript.configure(state="disabled")
        self.transcript.see("end")

    def toggle_pause(self):
        paused = not self.service.memory.is_paused()
        self.service.memory.set_paused(paused)
        self.pause.configure(text="Resume" if paused else "Pause")
        self.status.configure(text="Paused. An already sent request may still finish." if paused else "Ready.")

    def send(self):
        if self.busy or not self.input.get().strip(): return
        text = self.input.get()
        self.service.key = self.key.get()
        self.input.delete(0, "end")
        self.append("You", text)
        self.busy = True
        self.send_button.configure(state="disabled")
        self.status.configure(text="Waiting for Groq. No fallback provider will be used.")
        def work():
            try: result = self.service.chat(text)
            except Exception:
                result = "The request failed. Check your key and connection, then try again. No fallback was used."
            self.results.put(result)
        threading.Thread(target=work, daemon=True).start()

    def poll(self):
        try:
            result = self.results.get_nowait()
            self.append("Mike", result)
            self.busy = False
            self.send_button.configure(state="normal")
            self.status.configure(text="Paused." if self.service.memory.is_paused() else "Ready.")
        except queue.Empty: pass
        self.root.after(100, self.poll)

    def show_memory(self):
        window = tk.Toplevel(self.root)
        window.title("Mike - Saved memory")
        window.geometry("600x380")
        items = tk.Listbox(window)
        items.pack(fill="both", expand=True, padx=12, pady=12)
        rows = []
        def refresh():
            nonlocal rows
            rows = self.service.memory.recall(limit=200)
            items.delete(0, "end")
            for _, kind, text in rows: items.insert("end", text)
        def add():
            text = simpledialog.askstring("Remember", "Fact to save on this computer:", parent=window)
            if text and text.strip(): self.service.memory.remember("fact", text.strip()); refresh()
        def delete():
            selected = items.curselection()
            if selected and messagebox.askyesno("Delete memory", "Permanently delete the selected fact?", parent=window):
                self.service.memory.forget(rows[selected[0]][0]); refresh()
        ttk.Button(window, text="Add fact", command=add).pack(side="left", padx=12, pady=12)
        ttk.Button(window, text="Delete selected", command=delete).pack(side="left", padx=12)
        refresh()


def main():
    root = tk.Tk()
    MikeWindow(root)
    root.mainloop()


if __name__ == "__main__": main()
