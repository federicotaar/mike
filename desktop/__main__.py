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
        root.geometry("900x720")
        root.configure(bg="#101114")
        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure(".", background="#101114", foreground="#f3f4f6", font=("Arial", 11))
        style.configure("TFrame", background="#101114")
        style.configure("TEntry", fieldbackground="#22252b", foreground="#f3f4f6", padding=8)
        style.configure("TButton", background="#303640", foreground="#ffffff", padding=(14, 8))
        style.map("TButton", background=[("active", "#414b5a"), ("disabled", "#23262c")])
        style.configure("Send.TButton", background="#2563eb", foreground="white")
        style.configure("Muted.TLabel", foreground="#a1a8b3")
        root.minsize(580, 480)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(2, weight=1)
        header = ttk.Frame(root, padding=18)
        header.grid(row=0, column=0, sticky="ew")
        ttk.Label(header, text="Mike", font=("Arial", 24, "bold")).pack(side="left")
        ttk.Label(header, text="DESKTOP PREVIEW", style="Muted.TLabel").pack(side="left", padx=18)
        setup = ttk.Frame(root, padding=(18, 0, 18, 12))
        setup.grid(row=1, column=0, sticky="ew")
        setup.columnconfigure(1, weight=1)
        ttk.Label(setup, text="Groq key (session only)").grid(row=0, column=0, padx=(0, 10))
        self.key = ttk.Entry(setup, show="*")
        self.key.grid(row=0, column=1, sticky="ew")
        self.pause = ttk.Button(setup, text="Resume" if self.service.memory.is_paused() else "Pause", command=self.toggle_pause)
        self.pause.grid(row=0, column=2, padx=8)
        ttk.Button(setup, text="Memory", command=self.show_memory).grid(row=0, column=3)
        ttk.Button(setup, text="New chat", command=self.new_chat).grid(row=0, column=4, padx=(8, 0))
        ttk.Button(setup, text="Activity", command=self.show_activity).grid(row=0, column=5, padx=(8, 0))
        self.transcript = tk.Text(root, wrap="word", state="disabled", padx=22, pady=20,
                                  font=("Arial", 12), bg="#191c21", fg="#e5e7eb", relief="flat", spacing3=10,
                                  insertbackground="white", selectbackground="#2563eb")
        self.transcript.tag_configure("speaker", foreground="#79aaff", font=("Arial", 11, "bold"))
        self.transcript.grid(row=2, column=0, sticky="nsew", padx=18)
        self.append("Mike", "Your assistant, on your computer.\n\nEnter your own Groq key above to start a conversation. Your key stays in this session and is never saved.\n\nAvailable in this preview: chat, saved facts and pause controls.\nNot available yet: reminder tools, a local model or an always-on agent.")
        controls = ttk.Frame(root, padding=18)
        controls.grid(row=3, column=0, sticky="ew")
        controls.columnconfigure(0, weight=1)
        self.input = ttk.Entry(controls, font=("Arial", 12))
        self.input.grid(row=0, column=0, sticky="ew")
        self.input.bind("<Return>", lambda _: self.send())
        self.send_button = ttk.Button(controls, text="Send", style="Send.TButton", command=self.send)
        self.send_button.grid(row=0, column=1, padx=(10, 0))
        self.status = ttk.Label(root, text="Ready. No request is sent until you press Send.", padding=(18, 0, 18, 12))
        self.status.grid(row=4, column=0, sticky="w")
        root.after(100, self.poll)

    def append(self, speaker, text):
        self.transcript.configure(state="normal")
        self.transcript.insert("end", f"{speaker}\n", "speaker")
        self.transcript.insert("end", f"{text}\n\n")
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

    def new_chat(self):
        if self.busy:
            self.status.configure(text="Wait for the current reply before starting a new chat.")
            return
        self.service.clear_conversation()
        self.transcript.configure(state="normal")
        self.transcript.delete("1.0", "end")
        self.transcript.configure(state="disabled")
        self.append("Mike", "New chat. Saved facts are kept; the earlier conversation is forgotten.")
        self.status.configure(text="Ready.")

    def show_activity(self):
        import time
        window = tk.Toplevel(self.root)
        window.title("Mike - Activity")
        window.geometry("640x420")
        items = tk.Listbox(window)
        items.pack(fill="both", expand=True, padx=12, pady=12)
        for event in self.service.activity(limit=200):
            stamp = time.strftime("%Y-%m-%d %H:%M", time.localtime(event["time"]))
            items.insert("end", f"{stamp}  [{event['kind']}]  {event['summary']}")

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
