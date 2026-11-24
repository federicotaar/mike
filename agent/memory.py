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
import math
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
        if len(text) > 4000:
            raise ValueError("memory text must be at most 4000 characters")
        cur = self.db.execute(
            "INSERT INTO memories (kind, text, created_at) VALUES (?, ?, ?)",
            (kind, text, time.time()),
        )
        self.db.commit()
        return cur.lastrowid

    @synchronized
    def recall(self, limit: int = 50, kind: str | None = None) -> list[tuple[int, str, str]]:
        if kind is not None and kind not in MEMORY_KINDS:
            raise ValueError(f"unknown memory kind: {kind!r} (expected one of {sorted(MEMORY_KINDS)})")
        if limit < 1:
            raise ValueError("limit must be at least 1")
        if kind is None:
            rows = self.db.execute(
                "SELECT id, kind, text FROM memories "
                "WHERE superseded_by IS NULL ORDER BY created_at DESC, id DESC LIMIT ?",
                (limit,),
            )
        else:
            rows = self.db.execute(
                "SELECT id, kind, text FROM memories "
                "WHERE superseded_by IS NULL AND kind=? ORDER BY created_at DESC, id DESC LIMIT ?",
                (kind, limit),
            )
        return rows.fetchall()

    @synchronized
    def search_memories(self, query: str, limit: int = 50, kind: str | None = None) -> list[tuple[int, str, str]]:
        """Case-insensitive substring search over active memories, newest first.

        instr() instead of LIKE so % and _ in the query stay literal text.
        Optionally restrict the search to one memory kind.
        """
        if not query.strip():
            raise ValueError("search query must not be blank")
        if limit < 1:
            raise ValueError("limit must be at least 1")
        if kind is not None and kind not in MEMORY_KINDS:
            raise ValueError(f"unknown memory kind: {kind!r} (expected one of {sorted(MEMORY_KINDS)})")
        if kind is None:
            rows = self.db.execute(
                "SELECT id, kind, text FROM memories "
                "WHERE superseded_by IS NULL AND instr(lower(text), lower(?)) > 0 "
                "ORDER BY created_at DESC, id DESC LIMIT ?",
                (query, limit),
            )
        else:
            rows = self.db.execute(
                "SELECT id, kind, text FROM memories "
                "WHERE superseded_by IS NULL AND kind=? AND instr(lower(text), lower(?)) > 0 "
                "ORDER BY created_at DESC, id DESC LIMIT ?",
                (kind, query, limit),
            )
        return rows.fetchall()

    @synchronized
    def latest_memory(self, kind: str | None = None) -> dict | None:
        """Newest active memory, optionally of one kind, or None."""
        rows = self.recall(limit=1, kind=kind)
        return {"id": rows[0][0], "kind": rows[0][1], "text": rows[0][2]} if rows else None

    @synchronized
    def count_memories(self, kind: str | None = None) -> int:
        """How many active memories exist, optionally only one kind."""
        if kind is not None and kind not in MEMORY_KINDS:
            raise ValueError(f"unknown memory kind: {kind!r} (expected one of {sorted(MEMORY_KINDS)})")
        if kind is None:
            row = self.db.execute(
                "SELECT COUNT(*) FROM memories WHERE superseded_by IS NULL"
            ).fetchone()
        else:
            row = self.db.execute(
                "SELECT COUNT(*) FROM memories WHERE superseded_by IS NULL AND kind=?",
                (kind,),
            ).fetchone()
        return int(row[0])

    @synchronized
    def forget(self, memory_id: int) -> bool:
        """User deleted a memory for good. Returns False when no such memory."""
        cur = self.db.execute("DELETE FROM memories WHERE id=?", (memory_id,))
        self.db.commit()
        return cur.rowcount == 1

    @synchronized
    def export_memories(self) -> list[dict]:
        """Every active memory with its creation time - a portable backup the
        user owns, newest first."""
        rows = self.db.execute(
            "SELECT id, kind, text, created_at FROM memories "
            "WHERE superseded_by IS NULL ORDER BY created_at DESC, id DESC"
        ).fetchall()
        return [
            {"id": r[0], "kind": r[1], "text": r[2], "createdAt": r[3]}
            for r in rows
        ]

    @synchronized
    def memory_by_id(self, memory_id: int) -> dict | None:
        """One active memory as a dict, or None - edit screens read this before correcting."""
        row = self.db.execute(
            "SELECT id, kind, text, created_at FROM memories "
            "WHERE id=? AND superseded_by IS NULL",
            (memory_id,),
        ).fetchone()
        if row is None:
            return None
        return {"id": row[0], "kind": row[1], "text": row[2], "createdAt": row[3]}

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

    @synchronized
    def find_duplicate_memories(self) -> list[list[dict]]:
        """Groups of active memories whose normalized text is identical
        (case and surrounding/inner whitespace collapsed). Duplicates creep
        in when the same fact is re-learned; this lists them so they can be
        reviewed and forgotten, never auto-deleted."""
        rows = self.db.execute(
            "SELECT id, kind, text, created_at FROM memories WHERE superseded_by IS NULL ORDER BY created_at, id"
        ).fetchall()
        groups: dict[str, list[dict]] = {}
        for r in rows:
            norm = " ".join(str(r[2]).split()).lower()
            if not norm:
                continue
            groups.setdefault(norm, []).append(
                {"id": r[0], "kind": r[1], "text": r[2], "created_at": r[3]}
            )
        return [g for g in groups.values() if len(g) > 1]

    @synchronized
    def import_memories(self, records: list[dict]) -> dict:
        """Restore an exported backup atomically without duplicating active facts.

        IDs in backups are deliberately ignored. Creation times are preserved;
        absent times use the import time. Validation precedes every database write.
        No approval, activity or execution state can be imported through this path.
        """
        if not isinstance(records, list) or len(records) > 1000:
            raise ValueError("backup must be a list of at most 1000 memories")
        now = time.time()
        validated = []
        for record in records:
            if not isinstance(record, dict):
                raise ValueError("every memory must be an object")
            kind, text = record.get("kind"), record.get("text")
            if not isinstance(kind, str) or kind not in MEMORY_KINDS:
                raise ValueError("unknown memory kind in backup")
            if not isinstance(text, str) or not text.strip() or len(text) > 4000:
                raise ValueError("memory text must contain 1 to 4000 characters")
            created = record.get("createdAt", now)
            if type(created) not in (float, int) or not 0 <= created <= 253402300799 or not math.isfinite(created):
                raise ValueError("invalid memory creation time")
            validated.append((kind, text, created))
        existing = set(self.db.execute(
            "SELECT kind, text FROM memories WHERE superseded_by IS NULL"
        ).fetchall())
        imported = 0
        with self.db:
            for kind, text, created in validated:
                if (kind, text) in existing:
                    continue
                self.db.execute(
                    "INSERT INTO memories(kind, text, created_at) VALUES (?, ?, ?)",
                    (kind, text, created),
                )
                existing.add((kind, text))
                imported += 1
        return {"imported": imported, "skipped": len(records) - imported}

    @synchronized
    def memory_counts(self) -> dict[str, int]:
        """Active memory totals by kind, including zero-count categories."""
        counts = dict.fromkeys(sorted(MEMORY_KINDS), 0)
        counts.update(self.db.execute(
            "SELECT kind, COUNT(*) FROM memories WHERE superseded_by IS NULL GROUP BY kind"
        ).fetchall())
        return counts

    # ---- approval queue ----------------------------------------------
    @synchronized
    def request_approval(self, summary: str, detail: str) -> int:
        if not summary.strip():
            raise ValueError("approval summary must not be blank")
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
            "WHERE status='pending' ORDER BY created_at ASC, id ASC"
        ).fetchall()
        return [
            {"id": str(r[0]), "summary": r[1], "detail": r[2],
             "createdAt": r[3], "status": "pending"}
            for r in rows
        ]

    @synchronized
    def approvals_history(self, limit: int = 100, status: str | None = None) -> list[dict]:
        """All approvals, newest first, any status - the full record, not just pending."""
        if limit < 1:
            raise ValueError("limit must be at least 1")
        if status is not None and status not in {"pending", "approved", "denied"}:
            raise ValueError("unknown approval status")
        where = " WHERE status=?" if status is not None else ""
        params = (status, limit) if status is not None else (limit,)
        rows = self.db.execute(
            "SELECT id, summary, detail, created_at, status FROM approvals" + where +
            " ORDER BY created_at DESC, id DESC LIMIT ?", params,
        ).fetchall()
        return [
            {"id": str(r[0]), "summary": r[1], "detail": r[2],
             "createdAt": r[3], "status": r[4]}
            for r in rows
        ]

    @synchronized
    def search_approvals(self, query: str, limit: int = 50, status: str | None = None) -> list[dict]:
        """Literal, case-insensitive search over approval summary and detail, newest first."""
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must not be blank")
        if type(limit) is not int or not 1 <= limit <= 500:
            raise ValueError("limit must be between 1 and 500")
        if status is not None and status not in {"pending", "approved", "denied"}:
            raise ValueError("unknown approval status")
        where = "(instr(lower(summary), lower(?)) > 0 OR instr(lower(detail), lower(?)) > 0)"
        params = [query, query]
        if status is not None:
            where += " AND status=?"
            params.append(status)
        rows = self.db.execute(
            "SELECT id, summary, detail, created_at, status FROM approvals WHERE " + where +
            " ORDER BY id DESC LIMIT ?", (*params, limit),
        ).fetchall()
        return [{"id": str(x[0]), "summary": x[1], "detail": x[2], "createdAt": x[3], "status": x[4]} for x in rows]

    @synchronized
    def stale_approvals(self, days: float) -> list[dict]:
        """Pending approvals older than `days`, oldest first. Lists only; never decides anything."""
        if isinstance(days, bool) or not isinstance(days, (int, float)) or not math.isfinite(days) or days <= 0:
            raise ValueError("days must be a positive number")
        cutoff = time.time() - days * 86400
        rows = self.db.execute(
            "SELECT id, summary, detail, created_at FROM approvals "
            "WHERE status='pending' AND created_at<? ORDER BY created_at ASC, id ASC", (cutoff,),
        ).fetchall()
        return [{"id": str(x[0]), "summary": x[1], "detail": x[2], "createdAt": x[3], "status": "pending"} for x in rows]

    @synchronized
    def approval_by_id(self, approval_id: int) -> dict | None:
        """One approval in any status, or None - direct lookup, no history scan."""
        row = self.db.execute(
            "SELECT id, summary, detail, created_at, status FROM approvals WHERE id=?",
            (approval_id,),
        ).fetchone()
        if row is None:
            return None
        return {"id": str(row[0]), "summary": row[1], "detail": row[2],
                "createdAt": row[3], "status": row[4]}

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
        if not kind.strip():
            raise ValueError("activity kind must not be blank")
        if not summary.strip():
            raise ValueError("activity summary must not be blank")
        cur = self.db.execute(
            "INSERT INTO activity (kind, summary, created_at) VALUES (?, ?, ?)",
            (kind, summary, time.time()),
        )
        self.db.commit()
        return cur.lastrowid

    @synchronized
    def recent_activity(self, limit: int = 100, kind: str | None = None, before_id: int | None = None) -> list[dict]:
        if type(limit) is not int or limit<1:
            raise ValueError("limit must be a positive integer")
        if before_id is not None and (type(before_id) is not int or before_id < 1):
            raise ValueError("before_id must be a positive integer")
        clauses, params = [], []
        if kind is not None:
            clauses.append("kind=?")
            params.append(kind)
        if before_id is not None:
            clauses.append("id<?")
            params.append(before_id)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        params.append(limit)
        rows = self.db.execute(
            "SELECT id, kind, summary, created_at FROM activity" + where +
            " ORDER BY id DESC LIMIT ?", params,
        ).fetchall()
        return [
            {"id": str(r[0]), "kind": r[1], "summary": r[2], "time": r[3]}
            for r in rows
        ]

    @synchronized
    def activity_counts(self) -> dict[str, int]:
        """How many activity rows exist per kind, most frequent first.
        Feeds status/debug views without shipping the whole log."""
        rows = self.db.execute(
            "SELECT kind, COUNT(*) FROM activity GROUP BY kind ORDER BY COUNT(*) DESC, kind"
        ).fetchall()
        return {r[0]: r[1] for r in rows}

    @synchronized
    def activity_kinds(self) -> list[str]:
        """Distinct activity kinds in alphabetical order, for filter menus."""
        return [x[0] for x in self.db.execute("SELECT DISTINCT kind FROM activity ORDER BY kind").fetchall()]

    @synchronized
    def count_activity(self, kind: str | None = None) -> int:
        """Total activity rows (optionally one kind): recent_activity() pages
        through the log with before_id, callers need the total to show
        progress and to know when another page exists."""
        if kind is None:
            return self.db.execute("SELECT COUNT(*) FROM activity").fetchone()[0]
        return self.db.execute("SELECT COUNT(*) FROM activity WHERE kind=?", (kind,)).fetchone()[0]

    @synchronized
    def prune_activity(self, keep: int = 1000) -> int:
        """Bound the activity log: drop all but the newest `keep` rows.
        Returns how many rows were removed."""
        if keep < 0:
            raise ValueError("keep must not be negative")
        cur = self.db.execute(
            "DELETE FROM activity WHERE id NOT IN "
            "(SELECT id FROM activity ORDER BY created_at DESC, id DESC LIMIT ?)",
            (keep,),
        )
        self.db.commit()
        return cur.rowcount

    # ---- paused flag ----------------------------------------------------
    @synchronized
    def prune_activity_older_than(self, days: float) -> int:
        """Drop activity rows older than `days` days. prune_activity() bounds
        the log by row count; this bounds it by age, which is what a weekly
        cleanup job actually wants. Returns how many rows were removed."""
        if not isinstance(days, (int, float)) or isinstance(days, bool) or not math.isfinite(days) or days < 0:
            raise ValueError("days must be a non-negative number")
        cutoff = time.time() - days * 86400
        cur = self.db.execute("DELETE FROM activity WHERE created_at < ?", (cutoff,))
        self.db.commit()
        return cur.rowcount

    @synchronized
    def export_activity(self, limit: int | None = None) -> list[dict]:
        """Export the activity log (newest first) for backups, mirroring
        export_memories(). With limit=None the whole log is exported."""
        if limit is not None and (type(limit) is not int or limit < 1):
            raise ValueError("limit must be a positive integer or None")
        if limit is None:
            rows = self.db.execute(
                "SELECT id, kind, summary, created_at FROM activity ORDER BY id DESC"
            ).fetchall()
        else:
            rows = self.db.execute(
                "SELECT id, kind, summary, created_at FROM activity ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {"id": r[0], "kind": r[1], "summary": r[2], "created_at": r[3]}
            for r in rows
        ]

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

    # ---- small key/value store -------------------------------------------
    @synchronized
    def get_kv(self, key: str, default: str | None = None) -> str | None:
        row = self.db.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
        return row[0] if row else default

    @synchronized
    def set_kv(self, key: str, value: str) -> None:
        self.db.execute(
            "INSERT INTO kv (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))
        self.db.commit()

    @synchronized
    def delete_kv(self, key: str) -> bool:
        """Remove a key; False when it did not exist."""
        cur = self.db.execute("DELETE FROM kv WHERE key=?", (key,))
        self.db.commit()
        return cur.rowcount == 1

    @synchronized
    def kv_keys(self, prefix: str = "") -> list[str]:
        """Stored keys in alphabetical order, optionally only those starting with `prefix`."""
        rows = self.db.execute("SELECT key FROM kv ORDER BY key").fetchall()
        return [x[0] for x in rows if x[0].startswith(prefix)]

    @synchronized
    def search_activity(self, query: str, limit: int = 100, kind: str | None = None) -> list[dict]:
        """Search literal activity text without treating % and _ as wildcards."""
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must not be blank")
        if type(limit) is not int or not 1 <= limit <= 500:
            raise ValueError("limit must be between 1 and 500")
        where, params = "instr(lower(summary), lower(?)) > 0", [query]
        if kind is not None:
            where += " AND kind=?"
            params.append(kind)
        rows = self.db.execute(
            "SELECT id, kind, summary, created_at FROM activity WHERE " + where +
            " ORDER BY id DESC LIMIT ?", (*params, limit),
        ).fetchall()
        return [{"id": str(r[0]), "kind": r[1], "summary": r[2], "time": r[3]} for r in rows]

    @synchronized
    def memory_history(self, memory_id: int) -> list[dict]:
        """Available correction chain in chronological order, from any member.

        UNION rather than UNION ALL also terminates on malformed cyclic data.
        Deleted memories cannot be recovered through this read-only view.
        """
        rows = self.db.execute("""
            WITH RECURSIVE chain(id) AS (
                SELECT id FROM memories WHERE id=?
                UNION
                SELECT m.id FROM memories m JOIN chain c
                ON m.superseded_by=c.id OR m.id=(
                    SELECT superseded_by FROM memories WHERE id=c.id
                )
            )
            SELECT id, kind, text, created_at, superseded_by FROM memories
            WHERE id IN (SELECT id FROM chain) ORDER BY created_at, id
        """, (memory_id,)).fetchall()
        return [{"id": r[0], "kind": r[1], "text": r[2], "createdAt": r[3],
                 "supersededBy": r[4]} for r in rows]

    @synchronized
    def approval_counts(self) -> dict[str, int]:
        """Counts by decision state, including states with no rows."""
        counts = dict.fromkeys(("pending", "approved", "denied"), 0)
        counts.update(self.db.execute(
            "SELECT status, COUNT(*) FROM approvals GROUP BY status"
        ).fetchall())
        return counts

    @synchronized
    def memory_page(self, limit: int = 50, before_id: int | None = None,
                    kind: str | None = None) -> dict:
        """Cursor-paged active memories, ordered by insertion ID rather than backup date."""
        if type(limit) is not int or not 1 <= limit <= 500:
            raise ValueError("limit must be between 1 and 500")
        if before_id is not None and (type(before_id) is not int or before_id < 1):
            raise ValueError("before_id must be a positive integer")
        if kind is not None and kind not in MEMORY_KINDS:
            raise ValueError("unknown memory kind")
        clauses, params = ["superseded_by IS NULL"], []
        if before_id is not None:
            clauses.append("id<?"); params.append(before_id)
        if kind is not None:
            clauses.append("kind=?"); params.append(kind)
        rows = self.db.execute(
            "SELECT id, kind, text, created_at FROM memories WHERE " + " AND ".join(clauses) +
            " ORDER BY id DESC LIMIT ?", (*params, limit+1),
        ).fetchall()
        more=len(rows)>limit
        rows=rows[:limit]
        return {"items": [{"id":str(r[0]),"kind":r[1],"text":r[2],"createdAt":r[3]} for r in rows],
                "nextBeforeId": str(rows[-1][0]) if more else None}

    @synchronized
    def activity_by_id(self, activity_id: int) -> dict | None:
        row=self.db.execute("SELECT id,kind,summary,created_at FROM activity WHERE id=?",(activity_id,)).fetchone()
        return {"id":str(row[0]),"kind":row[1],"summary":row[2],"time":row[3]} if row else None

    @synchronized
    def activity_page(self, limit: int = 50, before_id: int | None = None,
                      kind: str | None = None) -> dict:
        """Cursor-paged activity, newest first, same shape as memory_page."""
        if type(limit) is not int or not 1 <= limit <= 500:
            raise ValueError("limit must be between 1 and 500")
        if before_id is not None and (type(before_id) is not int or before_id < 1):
            raise ValueError("before_id must be a positive integer")
        clauses, params = [], []
        if before_id is not None:
            clauses.append("id<?"); params.append(before_id)
        if kind is not None:
            clauses.append("kind=?"); params.append(kind)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        rows = self.db.execute(
            "SELECT id, kind, summary, created_at FROM activity" + where +
            " ORDER BY id DESC LIMIT ?", (*params, limit + 1),
        ).fetchall()
        more = len(rows) > limit
        rows = rows[:limit]
        return {"items": [{"id": str(x[0]), "kind": x[1], "summary": x[2], "time": x[3]} for x in rows],
                "nextBeforeId": str(rows[-1][0]) if more else None}

    @synchronized
    def approval_page(self, limit: int = 50, before_id: int | None = None,
                      status: str | None = None) -> dict:
        if type(limit) is not int or not 1 <= limit <= 500:
            raise ValueError("limit must be between 1 and 500")
        if before_id is not None and (type(before_id) is not int or before_id < 1):
            raise ValueError("before_id must be a positive integer")
        if status is not None and status not in {"pending","approved","denied"}:
            raise ValueError("unknown approval status")
        clauses,params=[],[]
        if before_id is not None:clauses.append("id<?");params.append(before_id)
        if status is not None:clauses.append("status=?");params.append(status)
        where=" WHERE "+" AND ".join(clauses) if clauses else ""
        rows=self.db.execute("SELECT id,summary,detail,created_at,status FROM approvals"+where+
                             " ORDER BY id DESC LIMIT ?",(*params,limit+1)).fetchall()
        more=len(rows)>limit;rows=rows[:limit]
        return {"items":[{"id":str(r[0]),"summary":r[1],"detail":r[2],"createdAt":r[3],"status":r[4]} for r in rows],
                "nextBeforeId":str(rows[-1][0]) if more else None}
