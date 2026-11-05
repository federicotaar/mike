"""What the agent learns: preferences, facts, feedback. Plain SQLite on the PC.

This is the honest version of 'self-improving': every correction and approval
becomes a row the agent reads back next time. No magic weight updates.
Also stores the approval queue, the activity log and the paused flag, so the
iPhone app always reads real state, never a simulation.
"""
from __future__ import annotations
import sqlite3
from pathlib import Path
import time
import datetime
import threading
from functools import wraps

SCHEMA = """
CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,          -- preference | fact | feedback
    text TEXT NOT NULL,
    created_at REAL NOT NULL,
    superseded_by INTEGER        -- set when a newer memory replaces this one
);
CREATE TABLE IF NOT EXISTS approvals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    summary TEXT NOT NULL,       -- one-line what Mike wants to do
    detail TEXT NOT NULL,        -- full context the user reviews
    created_at REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'   -- pending | approved | denied
);
CREATE TABLE IF NOT EXISTS activity (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,          -- chat | approval | feedback | stop | selfedit | ...
    summary TEXT NOT NULL,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS kv (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


MEMORY_KINDS = {"preference", "fact", "feedback"}


def synchronized(method):
    """One connection serves API requests and worker threads; serialize transactions."""
    @wraps(method)
    def locked(self, *args, **kwargs):
        with self._lock:
            return method(self, *args, **kwargs)
    return locked


class Memory:
    def __init__(self, path: str):
        if path != ":memory:":
            path = str(Path(path).expanduser())
            parent = Path(path).parent
            if str(parent) not in ("", "."):
                parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.executescript(SCHEMA)

    # ---- memories: how it learns -------------------------------------
    @synchronized
    def remember(self, kind: str, text: str) -> int:
        if kind not in MEMORY_KINDS:
            raise ValueError(f"unknown memory kind: {kind!r} (expected one of {sorted(MEMORY_KINDS)})")
        if not text.strip():
            raise ValueError("memory text must not be blank")
        cur = self.db.execute(
            "INSERT INTO memories (kind, text, created_at) VALUES (?, ?, ?)",
            (kind, text, time.time()),
        )
        self.db.commit()
        return cur.lastrowid

    @synchronized
    def recall(self, limit: int = 50, kind: str | None = None) -> list[tuple[int, str, str]]:
        if kind is None:
            rows = self.db.execute(
                "SELECT id, kind, text FROM memories "
                "WHERE superseded_by IS NULL ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )
        else:
            rows = self.db.execute(
                "SELECT id, kind, text FROM memories "
                "WHERE superseded_by IS NULL AND kind=? ORDER BY created_at DESC LIMIT ?",
                (kind, limit),
            )
        return rows.fetchall()

    @synchronized
    def forget(self, memory_id: int) -> bool:
        """User deleted a memory for good. Returns False when no such memory."""
        cur = self.db.execute("DELETE FROM memories WHERE id=?", (memory_id,))
        self.db.commit()
        return cur.rowcount == 1

    @synchronized
    def correct(self, old_id: int, new_text: str) -> int:
        """User corrected something: keep history, point old at new."""
        row = self.db.execute(
            "SELECT kind FROM memories WHERE id=? AND superseded_by IS NULL", (old_id,)
        ).fetchone()
        if row is None:
            raise ValueError("no active memory with that id")
        if not new_text.strip():
            raise ValueError("memory text must not be blank")
        with self.db:
            cur = self.db.execute(
                "INSERT INTO memories (kind, text, created_at) VALUES (?, ?, ?)",
                (row[0], new_text, time.time()),
            )
            new_id = cur.lastrowid
            self.db.execute("UPDATE memories SET superseded_by=? WHERE id=?", (new_id, old_id))
        return new_id

    # ---- approval queue ----------------------------------------------
    @synchronized
    def request_approval(self, summary: str, detail: str) -> int:
        cur = self.db.execute(
            "INSERT INTO approvals (summary, detail, created_at) VALUES (?, ?, ?)",
            (summary, detail, time.time()),
        )
        self.db.commit()
        return cur.lastrowid

    @synchronized
    def pending_approvals(self) -> list[dict]:
        rows = self.db.execute(
            "SELECT id, summary, detail, created_at FROM approvals "
            "WHERE status='pending' ORDER BY created_at ASC"
        ).fetchall()
        return [
            {"id": str(r[0]), "summary": r[1], "detail": r[2],
             "createdAt": r[3], "status": "pending"}
            for r in rows
        ]

    @synchronized
    def approvals_history(self, limit: int = 100) -> list[dict]:
        """All approvals, newest first, any status - the full record, not just pending."""
        rows = self.db.execute(
            "SELECT id, summary, detail, created_at, status FROM approvals "
            "ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [
            {"id": str(r[0]), "summary": r[1], "detail": r[2],
             "createdAt": r[3], "status": r[4]}
            for r in rows
        ]

    @synchronized
    def decide_approval(self, approval_id: int, approved: bool) -> bool:
        """Returns False when no such pending approval exists."""
        cur = self.db.execute(
            "UPDATE approvals SET status=? WHERE id=? AND status='pending'",
            ("approved" if approved else "denied", approval_id),
        )
        self.db.commit()
        return cur.rowcount == 1

    # ---- activity log --------------------------------------------------
    @synchronized
    def log_activity(self, kind: str, summary: str) -> int:
        cur = self.db.execute(
            "INSERT INTO activity (kind, summary, created_at) VALUES (?, ?, ?)",
            (kind, summary, time.time()),
        )
        self.db.commit()
        return cur.lastrowid

    @synchronized
    def recent_activity(self, limit: int = 100) -> list[dict]:
        rows = self.db.execute(
            "SELECT id, kind, summary, created_at FROM activity "
            "ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [
            {"id": str(r[0]), "kind": r[1], "summary": r[2], "time": r[3]}
            for r in rows
        ]

    @synchronized
    def prune_activity(self, keep: int = 1000) -> int:
        """Bound the activity log: drop all but the newest `keep` rows.
        Returns how many rows were removed."""
        if keep < 0:
            raise ValueError("keep must not be negative")
        cur = self.db.execute(
            "DELETE FROM activity WHERE id NOT IN "
            "(SELECT id FROM activity ORDER BY created_at DESC LIMIT ?)",
            (keep,),
        )
        self.db.commit()
        return cur.rowcount

    # ---- paused flag ----------------------------------------------------
    @synchronized
    def set_paused(self, paused: bool) -> None:
        self.db.execute(
            "INSERT INTO kv (key, value) VALUES ('paused', ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            ("1" if paused else "0",),
        )
        self.db.commit()

    @synchronized
    def is_paused(self) -> bool:
        row = self.db.execute("SELECT value FROM kv WHERE key='paused'").fetchone()
        return bool(row and row[0] == "1")

    # ---- per-day request counter (quota tracking) ---------------------
    @synchronized
    def count_request(self, today: str | None = None) -> int:
        """Count one model request for today (local date). Returns today's total."""
        today = today or datetime.date.today().isoformat()
        row = self.db.execute("SELECT value FROM kv WHERE key='quota_day'").fetchone()
        if row is None or row[0] != today:
            self.db.execute(
                "INSERT INTO kv (key, value) VALUES ('quota_day', ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (today,))
            self.db.execute(
                "INSERT INTO kv (key, value) VALUES ('quota_used', '0') "
                "ON CONFLICT(key) DO UPDATE SET value='0'")
        self.db.execute("UPDATE kv SET value = CAST(value AS INTEGER) + 1 WHERE key='quota_used'")
        self.db.commit()
        return int(self.db.execute("SELECT value FROM kv WHERE key='quota_used'").fetchone()[0])

    @synchronized
    def requests_today(self, today: str | None = None) -> int:
        today = today or datetime.date.today().isoformat()
        day = self.db.execute("SELECT value FROM kv WHERE key='quota_day'").fetchone()
        if day is None or day[0] != today:
            return 0
        return int(self.db.execute("SELECT value FROM kv WHERE key='quota_used'").fetchone()[0])
