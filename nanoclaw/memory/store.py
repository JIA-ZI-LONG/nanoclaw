"""Memory store - history.jsonl and MEMORY.md management."""

import json
from datetime import datetime
from pathlib import Path


class MemoryStore:
    """Memory file I/O: history.jsonl + MEMORY.md.

    history.jsonl: append-only LLM summaries
    MEMORY.md: long-term knowledge
    """

    def __init__(self, workdir: Path, max_history: int = 500):
        self.workdir = workdir
        self.max_history = max_history
        self.memory_dir = workdir / "memory"
        self.memory_dir.mkdir(exist_ok=True)
        self.history_file = self.memory_dir / "history.jsonl"
        self.memory_file = self.memory_dir / "MEMORY.md"
        self._cursor_file = self.memory_dir / ".cursor"

    # -- history.jsonl --

    def append_history(self, content: str) -> int:
        """Append summary to history.jsonl, return cursor."""
        cursor = self._next_cursor()
        record = {
            "cursor": cursor,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "content": content.strip()
        }
        with open(self.history_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        self._cursor_file.write_text(str(cursor), encoding="utf-8")
        return cursor

    def read_history(self, since: int = 0) -> list[dict]:
        """Read history entries with cursor > since."""
        entries = []
        try:
            with open(self.history_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            e = json.loads(line)
                            if e.get("cursor", 0) > since:
                                entries.append(e)
                        except json.JSONDecodeError:
                            continue
        except FileNotFoundError:
            pass
        return entries

    def compact_history(self) -> None:
        """Drop oldest entries if exceeds max_history."""
        if self.max_history <= 0:
            return
        entries = self._read_all_entries()
        if len(entries) <= self.max_history:
            return
        kept = entries[-self.max_history:]
        self._write_entries(kept)

    def _next_cursor(self) -> int:
        if self._cursor_file.exists():
            try:
                return int(self._cursor_file.read_text(encoding="utf-8").strip()) + 1
            except (ValueError, OSError):
                pass
        entries = self._read_all_entries()
        return (entries[-1]["cursor"] + 1) if entries else 1

    def _read_all_entries(self) -> list[dict]:
        entries = []
        try:
            with open(self.history_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            entries.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
        except FileNotFoundError:
            pass
        return entries

    def _write_entries(self, entries: list[dict]) -> None:
        with open(self.history_file, "w", encoding="utf-8") as f:
            for e in entries:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")

    # -- MEMORY.md --

    def read_memory(self) -> str:
        try:
            return self.memory_file.read_text(encoding="utf-8")
        except FileNotFoundError:
            return ""

    def write_memory(self, content: str) -> None:
        self.memory_file.write_text(content, encoding="utf-8")

    # -- context injection --

    def get_context(self) -> str:
        """Get memory context for system prompt."""
        memory = self.read_memory()
        return f"# Memory\n\n{memory}" if memory else ""

    def get_recent_history(self, limit: int = 10) -> str:
        """Get recent history for context."""
        entries = self._read_all_entries()[-limit:]
        if not entries:
            return ""
        lines = [f"- [{e['timestamp']}] {e['content'][:100]}" for e in entries]
        return "# Recent History\n\n" + "\n".join(lines)