"""Memory store - storage + compression for long conversations."""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from anthropic import Anthropic


class MemoryStore:
    """Memory management: storage + compression.

    Files:
        memory/history.jsonl  - append-only LLM summaries
        memory/MEMORY.md      - long-term knowledge
        memory/.cursor        - write position counter
        .transcripts/         - full conversation archives
    """

    def __init__(self, workdir: Path, max_history: int = 500):
        self.workdir = workdir
        self.max_history = max_history
        self.memory_dir = workdir / "memory"
        self.memory_dir.mkdir(exist_ok=True)
        self.transcript_dir = workdir / ".transcripts"
        self.transcript_dir.mkdir(exist_ok=True)
        self.history_file = self.memory_dir / "history.jsonl"
        self.memory_file = self.memory_dir / "MEMORY.md"
        self._cursor_file = self.memory_dir / ".cursor"

    # =========================================================================
    # Token estimation
    # =========================================================================

    @staticmethod
    def estimate_tokens(messages: list) -> int:
        """Estimate token count (JSON length / 4)."""
        return len(json.dumps(messages, default=str)) // 4

    # =========================================================================
    # Compression
    # =========================================================================

    def _microcompact(self, messages: list) -> None:
        """Clear old tool_results (>100 chars, keep last 3). Mutates in-place."""
        tool_results = []
        for msg in messages:
            if msg["role"] == "user" and isinstance(msg.get("content"), list):
                for part in msg["content"]:
                    if isinstance(part, dict) and part.get("type") == "tool_result":
                        tool_results.append(part)

        if len(tool_results) <= 3:
            return
        for part in tool_results[:-3]:
            if isinstance(part.get("content"), str) and len(part["content"]) > 100:
                part["content"] = "[cleared]"

    def compact(self, messages: list, client: "Anthropic", model: str) -> list:
        """Compress messages via LLM summary.

        - Saves full transcript to .transcripts/
        - Writes summary to history.jsonl
        - Returns condensed message list

        Args:
            messages: Conversation history
            client: Anthropic client
            model: Model ID

        Returns:
            Condensed message list with summary
        """
        # Save full transcript
        path = self.transcript_dir / f"transcript_{int(time.time())}.jsonl"
        with open(path, "w", encoding="utf-8") as f:
            for msg in messages:
                f.write(json.dumps(msg, default=str, ensure_ascii=False) + "\n")

        # LLM summary
        conv_text = json.dumps(messages, default=str)[-80000:]
        resp = client.messages.create(
            model=model,
            messages=[{"role": "user", "content": f"Summarize for continuity:\n{conv_text}"}],
            max_tokens=2000,
        )
        summary = ""
        for block in resp.content:
            if hasattr(block, "text"):
                print(f"\033[33m[Compressed]\033[0m {block.text[:100]}...")
                summary = block.text

        # Save to history.jsonl
        if summary:
            self.append_history(summary)

        return [
            {"role": "user", "content": f"[Compressed. Transcript: {path}]\n{summary}"},
        ]

    # =========================================================================
    # history.jsonl
    # =========================================================================

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
        return [e for e in self._read_all_entries() if e.get("cursor", 0) > since]

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

    def compact_history(self) -> None:
        """Drop oldest entries if exceeds max_history."""
        if self.max_history <= 0:
            return
        entries = self._read_all_entries()
        if len(entries) <= self.max_history:
            return
        self._write_entries(entries[-self.max_history:])

    # =========================================================================
    # MEMORY.md
    # =========================================================================

    def read_memory(self) -> str:
        try:
            return self.memory_file.read_text(encoding="utf-8")
        except FileNotFoundError:
            return ""

    def write_memory(self, content: str) -> None:
        self.memory_file.write_text(content, encoding="utf-8")

    # =========================================================================
    # Context injection
    # =========================================================================

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