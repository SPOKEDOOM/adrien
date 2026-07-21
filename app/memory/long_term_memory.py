from __future__ import annotations

import os
import re
import sqlite3
import time
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import QStandardPaths

CATEGORIES = ("identity", "preference", "project", "goal", "routine", "tool", "note")
STOP_WORDS = {"a", "an", "and", "are", "about", "do", "i", "is", "it", "me", "my", "of", "the",
              "to", "user", "what", "you", "your", "continue", "please"}
SENSITIVE = re.compile(
    r"(?i)(api[_ -]?key|password|passwd|access[_ -]?token|auth(?:entication)?[_ -]?code|"
    r"credit[_ -]?card|card number|cvv|bank(?:ing)? credential|sk-[A-Za-z0-9_-]{12,}|"
    r"gsk_[A-Za-z0-9_-]{12,})"
)


def _now(): return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True, slots=True)
class LongTermMemory:
    id: str; category: str; title: str; content: str; source: str
    created_at: str; updated_at: str; last_used_at: str | None
    importance: int; enabled: bool; user_confirmed: bool


@dataclass(frozen=True, slots=True)
class MemoryCandidate:
    id: str; category: str; title: str; content: str; source: str; created_at: str


class LongTermMemoryManager:
    SCHEMA_VERSION = 1

    def __init__(self, path: str | Path | None = None, *, enabled=True, maximum_memories=500):
        if path is None:
            root = Path(QStandardPaths.writableLocation(QStandardPaths.AppDataLocation) or Path.home() / ".adrien")
            path = os.getenv("ADRIEN_MEMORY_DB") or root / "memory.sqlite3"
        self.path = str(path); self.enabled = bool(enabled); self.maximum_memories = max(1, int(maximum_memories))
        self.suggestions_enabled = True; self.ask_before_saving = True; self.disabled_categories = set()
        self.pending_candidates: dict[str, MemoryCandidate] = {}; self.storage_available = False
        self.last_saved = "—"; self.last_retrieval_count = 0; self.last_retrieval_latency = 0.0
        self.last_retrieval_time = "—"; self._connect_and_migrate()

    def _connect(self):
        if self.path != ":memory:": Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=3); connection.row_factory = sqlite3.Row; return connection

    def _connect_and_migrate(self):
        try:
            with closing(self._connect()) as db, db:
                db.execute("CREATE TABLE IF NOT EXISTS schema_info (version INTEGER NOT NULL)")
                if not db.execute("SELECT 1 FROM schema_info").fetchone(): db.execute("INSERT INTO schema_info VALUES (?)", (self.SCHEMA_VERSION,))
                db.execute("""CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY, category TEXT NOT NULL, title TEXT NOT NULL, content TEXT NOT NULL,
                    source TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    last_used_at TEXT, importance INTEGER NOT NULL, enabled INTEGER NOT NULL,
                    user_confirmed INTEGER NOT NULL)""")
                db.execute("CREATE INDEX IF NOT EXISTS idx_memories_category ON memories(category)")
            self.storage_available = True
        except sqlite3.Error: self.storage_available = False

    @staticmethod
    def contains_sensitive_content(*values): return bool(SENSITIVE.search(" ".join(str(v) for v in values)))
    @staticmethod
    def _tokens(text):
        aliases = {"preference": "prefer", "preferences": "prefer", "prefers": "prefer",
                   "preferred": "prefer", "likes": "prefer", "liked": "prefer"}
        return {aliases.get(token, token) for token in re.findall(r"[a-z0-9]+", text.casefold())
                if token not in STOP_WORDS}

    def create(self, category, title, content, *, source="user", importance=3,
               enabled=True, user_confirmed=True):
        category = category if category in CATEGORIES else "note"; title = title.strip(); content = content.strip()
        if not self.enabled or not title or not content: raise ValueError("Memory is disabled or incomplete.")
        if self.contains_sensitive_content(title, content): raise ValueError("Sensitive information cannot be stored in memory.")
        duplicate = self._find_duplicate(category, title, content)
        if duplicate: return self.update(duplicate.id, category=category, title=title, content=content,
                                         source=source, importance=importance, enabled=enabled,
                                         user_confirmed=user_confirmed)
        if len(self.list()) >= self.maximum_memories: raise ValueError("Maximum memory count reached.")
        now = _now(); identifier = str(uuid4())
        with closing(self._connect()) as db, db:
            db.execute("INSERT INTO memories VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                       (identifier, category, title, content, source, now, now, None,
                        max(1, min(5, int(importance))), int(enabled), int(user_confirmed)))
        self.last_saved = now; return self.get(identifier)

    def get(self, identifier):
        with closing(self._connect()) as db, db: row = db.execute("SELECT * FROM memories WHERE id=?", (identifier,)).fetchone()
        return self._from_row(row) if row else None

    def update(self, identifier, **changes):
        current = self.get(identifier)
        if not current: raise KeyError(identifier)
        allowed = {"category", "title", "content", "source", "importance", "enabled", "user_confirmed"}
        values = {key: changes.get(key, getattr(current, key)) for key in allowed}
        if values["category"] not in CATEGORIES: raise ValueError("Invalid memory category.")
        if self.contains_sensitive_content(values["title"], values["content"]): raise ValueError("Sensitive information cannot be stored in memory.")
        values["importance"] = max(1, min(5, int(values["importance"])))
        with closing(self._connect()) as db, db:
            db.execute("""UPDATE memories SET category=?,title=?,content=?,source=?,updated_at=?,
                       importance=?,enabled=?,user_confirmed=? WHERE id=?""",
                       (values["category"], str(values["title"]).strip(), str(values["content"]).strip(),
                        values["source"], _now(), values["importance"], int(values["enabled"]),
                        int(values["user_confirmed"]), identifier))
        self.last_saved = _now(); return self.get(identifier)

    def delete(self, identifier):
        with closing(self._connect()) as db, db: result = db.execute("DELETE FROM memories WHERE id=?", (identifier,))
        return bool(result.rowcount)

    def clear(self):
        with closing(self._connect()) as db, db: db.execute("DELETE FROM memories")

    def list(self, *, category=None, search="", sort="recent"):
        clauses, parameters = [], []
        if category and category in CATEGORIES: clauses.append("category=?"); parameters.append(category)
        if search.strip(): clauses.append("(title LIKE ? OR content LIKE ?)"); parameters += [f"%{search.strip()}%"] * 2
        order = {"oldest": "created_at ASC", "importance": "importance DESC, updated_at DESC",
                 "last_used": "COALESCE(last_used_at,'') DESC", "recent": "updated_at DESC"}.get(sort, "updated_at DESC")
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        with closing(self._connect()) as db, db: rows = db.execute(f"SELECT * FROM memories{where} ORDER BY {order}", parameters).fetchall()
        return tuple(self._from_row(row) for row in rows)

    def search_relevant(self, query, limit=5, exclude_text=""):
        started = time.monotonic(); query_tokens = self._tokens(query); excluded = exclude_text.casefold(); scored = []
        if self.enabled and query_tokens:
            for memory in self.list():
                if not memory.enabled or memory.content.casefold() in excluded: continue
                tokens = self._tokens(f"{memory.category} {memory.title} {memory.content}")
                overlap = len(query_tokens & tokens)
                if not overlap: continue
                category_bonus = 2 if memory.category in ("identity", "project", "goal") else 1
                scored.append((overlap * 10 + memory.importance * 2 + category_bonus, memory))
        selected = tuple(item for _, item in sorted(scored, key=lambda pair: pair[0], reverse=True)[:limit])
        now = _now()
        if selected:
            with closing(self._connect()) as db, db: db.executemany("UPDATE memories SET last_used_at=? WHERE id=?", ((now, item.id) for item in selected))
        self.last_retrieval_count = len(selected); self.last_retrieval_latency = time.monotonic() - started
        self.last_retrieval_time = now; return selected

    def create_candidate(self, category, title, content, source="inferred"):
        if not self.suggestions_enabled or category in self.disabled_categories or self.contains_sensitive_content(title, content): return None
        candidate = MemoryCandidate(str(uuid4()), category if category in CATEGORIES else "note",
                                    title.strip(), content.strip(), source, _now())
        self.pending_candidates[candidate.id] = candidate; return candidate

    def approve_candidate(self, identifier):
        candidate = self.pending_candidates.pop(identifier)
        return self.create(candidate.category, candidate.title, candidate.content,
                           source=candidate.source, user_confirmed=True)

    def dismiss_candidate(self, identifier): return self.pending_candidates.pop(identifier, None) is not None
    def disable_candidate_category(self, identifier):
        candidate = self.pending_candidates.pop(identifier, None)
        if candidate: self.disabled_categories.add(candidate.category)
        return bool(candidate)
    def clear_candidates(self): self.pending_candidates.clear()
    def rebuild_index(self):
        with closing(self._connect()) as db, db: db.execute("REINDEX")

    def diagnostics(self):
        memories = self.list(); categories = {}
        for item in memories: categories[item.category] = categories.get(item.category, 0) + 1
        return {"enabled": self.enabled, "storage_available": self.storage_available,
                "total": len(memories), "enabled_count": sum(item.enabled for item in memories),
                "pending": len(self.pending_candidates), "last_saved": self.last_saved,
                "last_retrieval_count": self.last_retrieval_count,
                "last_retrieval_latency": self.last_retrieval_latency,
                "last_retrieval_time": self.last_retrieval_time, "category_counts": categories,
                "storage_path": self.path}

    def _find_duplicate(self, category, title, content):
        incoming = self._tokens(f"{title} {content}")
        for memory in self.list(category=category):
            existing = self._tokens(f"{memory.title} {memory.content}")
            if incoming and len(incoming & existing) / max(1, len(incoming | existing)) >= .55: return memory
        return None

    @staticmethod
    def _from_row(row):
        return LongTermMemory(row["id"], row["category"], row["title"], row["content"], row["source"],
                              row["created_at"], row["updated_at"], row["last_used_at"], row["importance"],
                              bool(row["enabled"]), bool(row["user_confirmed"]))
