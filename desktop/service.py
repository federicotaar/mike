"""Desktop chat without a background server or a paid fallback."""
from __future__ import annotations
from pathlib import Path
import os
import httpx
from agent.memory import Memory
from agent.brain import GROQ_URL, GROQ_MODEL, InvalidProviderResponse


def data_directory() -> Path:
    import sys
    if sys.platform == "win32":
        root = Path(os.getenv("LOCALAPPDATA", str(Path.home() / "AppData/Local")))
    elif sys.platform == "darwin":
        root = Path.home() / "Library/Application Support"
    else:
        root = Path(os.getenv("XDG_DATA_HOME", str(Path.home() / ".local/share")))
    return root / "Mike"


class DesktopService:
    def __init__(self, directory: Path | None = None):
        self.directory = directory or data_directory()
        self.memory = Memory(str(self.directory / "mike.db"))
        # Keys stay in process memory; never persisted in chat, logs or settings.
        self.key = ""
        self.history: list[dict[str, str]] = []

    def chat(self, text: str) -> str:
        if not text.strip() or len(text) > 32000:
            raise ValueError("Enter a message of 1 to 32000 characters.")
        if self.memory.is_paused():
            return "Mike is paused. Press Resume before sending another message."
        if not self.key.strip():
            return "Enter your own Groq key above. It stays in this session only."
        facts = "\n".join(t for _, _, t in self.memory.recall())
        system = "You are Mike. Be concise and honest. You cannot execute actions or set reminders in this desktop preview. Saved facts:\n" + facts
        with httpx.Client(timeout=60, follow_redirects=False) as client:
            response = client.post(GROQ_URL, headers={"Authorization": f"Bearer {self.key.strip()}"},
                json={"model": GROQ_MODEL, "messages": [{"role": "system", "content": system}] + self.history[-20:] + [{"role": "user", "content": text}]})
            if response.status_code in (402, 429):
                return "Groq refused this request because of an account or quota limit. No fallback was used."
            if response.status_code in (401, 403):
                return "Groq rejected this key. Check it and try again."
            response.raise_for_status()
            try:
                reply = response.json()["choices"][0]["message"]["content"]
            except (ValueError, KeyError, IndexError, TypeError) as exc:
                raise InvalidProviderResponse("Groq returned no usable reply.") from exc
            if not isinstance(reply, str) or not reply.strip():
                raise InvalidProviderResponse("Groq returned no usable reply.")
        self.history.extend([{"role": "user", "content": text}, {"role": "assistant", "content": reply}])
        self.history = self.history[-20:]
        self.memory.log_activity("chat", "Desktop chat completed")
        return reply

    def clear_conversation(self) -> None:
        """Forget this session's chat history (saved facts are kept)."""
        self.history = []
        self.memory.log_activity("chat", "Desktop conversation cleared")

    def activity(self, limit: int = 100) -> list[dict]:
        """What Mike did, newest first - the same log the iPhone Activity tab reads."""
        return self.memory.recent_activity(limit)

    def search_facts(self, query: str) -> list[str]:
        """Saved facts containing the query text, case-insensitive."""
        return [t for _, _, t in self.memory.search_memories(query)]

    def edit_fact(self, memory_id: int, new_text: str) -> int:
        """Correct a saved fact. The old text stays as history, the new one is used."""
        new_id = self.memory.correct(memory_id, new_text.strip())
        self.memory.log_activity("memory", f"corrected memory #{memory_id}")
        return new_id

    def pending_approvals(self) -> list[dict]:
        """Actions Mike is waiting on. Only the user decides these."""
        return self.memory.pending_approvals()

    def decide(self, approval_id: int, approved: bool) -> bool:
        """The user's own decision from the Approvals window."""
        done = self.memory.decide_approval(approval_id, approved)
        if done:
            self.memory.log_activity("approval", f"{'approved' if approved else 'denied'} #{approval_id} (desktop)")
        return done
