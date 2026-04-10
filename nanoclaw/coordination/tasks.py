#!/usr/bin/env python3
"""nanoclaw.coordination.tasks - File-based persistent task management.

Source: s_full.py lines 263-326

tasks_dir injected via constructor. Each task stored as task_{id}.json.
Supports dependency tracking (blockedBy).
"""

import json
from pathlib import Path
from typing import Optional, List


class TaskManager:
    """File-based persistent task management.

    Attributes:
        tasks_dir: Directory for task JSON files

    Task file format (task_{id}.json):
        - id: Auto-incremented integer
        - subject: Task title
        - description: Detailed description
        - status: pending, in_progress, completed, deleted
        - owner: Claimed owner name (or None)
        - blockedBy: List of task IDs blocking this task
    """

    def __init__(self, tasks_dir: Path):
        """Initialize with storage directory.

        Args:
            tasks_dir: Directory to store task JSON files
        """
        self.tasks_dir = tasks_dir
        tasks_dir.mkdir(exist_ok=True)

    def _next_id(self) -> int:
        """Get next available task ID.

        Returns:
            Max existing ID + 1, or 1 if no tasks
        """
        ids = [
            int(f.stem.split("_")[1])
            for f in self.tasks_dir.glob("task_*.json")
        ]
        return max(ids, default=0) + 1

    def _load(self, tid: int) -> dict:
        """Load task from file.

        Args:
            tid: Task ID

        Returns:
            Task dict

        Raises:
            ValueError: If task not found
        """
        path = self.tasks_dir / f"task_{tid}.json"
        if not path.exists():
            raise ValueError(f"Task {tid} not found")
        return json.loads(path.read_text(encoding='utf-8'))

    def _save(self, task: dict) -> None:
        """Save task to file.

        Args:
            task: Task dict to save
        """
        path = self.tasks_dir / f"task_{task['id']}.json"
        path.write_text(json.dumps(task, indent=2, ensure_ascii=False), encoding='utf-8')

    def create(self, subject: str, description: str = "") -> str:
        """Create new task.

        Args:
            subject: Task title
            description: Detailed description

        Returns:
            JSON representation of created task
        """
        task = {
            "id": self._next_id(),
            "subject": subject,
            "description": description,
            "status": "pending",
            "owner": None,
            "blockedBy": []
        }
        self._save(task)
        return json.dumps(task, indent=2, ensure_ascii=False)

    def get(self, tid: int) -> str:
        """Get task details by ID.

        Args:
            tid: Task ID

        Returns:
            JSON representation of task
        """
        return json.dumps(self._load(tid), indent=2)

    def update(
        self,
        tid: int,
        status: Optional[str] = None,
        add_blocked_by: Optional[List[int]] = None,
        remove_blocked_by: Optional[List[int]] = None,
        owner: Optional[str] = None
    ) -> str:
        """Update task status and dependencies.

        Args:
            tid: Task ID
            status: New status (pending, in_progress, completed, deleted)
            add_blocked_by: Task IDs to add as blockers
            remove_blocked_by: Task IDs to remove from blockers
            owner: New owner name

        Returns:
            JSON representation or deletion message
        """
        task = self._load(tid)

        if status:
            task["status"] = status

            # completed: remove from other tasks' blockedBy
            if status == "completed":
                for f in self.tasks_dir.glob("task_*.json"):
                    t = json.loads(f.read_text(encoding='utf-8'))
                    if tid in t.get("blockedBy", []):
                        t["blockedBy"].remove(tid)
                        self._save(t)

            # deleted: remove file
            if status == "deleted":
                (self.tasks_dir / f"task_{tid}.json").unlink(missing_ok=True)
                return f"Task {tid} deleted"

        if add_blocked_by:
            task["blockedBy"] = list(set(task["blockedBy"] + add_blocked_by))

        if remove_blocked_by:
            task["blockedBy"] = [
                x for x in task["blockedBy"]
                if x not in remove_blocked_by
            ]

        if owner:
            task["owner"] = owner

        self._save(task)
        return json.dumps(task, indent=2, ensure_ascii=False)

    def list_all(self) -> str:
        """List all tasks with status markers.

        Returns:
            Formatted task list string
        """
        tasks = [
            json.loads(f.read_text(encoding='utf-8'))
            for f in sorted(self.tasks_dir.glob("task_*.json"))
        ]

        if not tasks:
            return "No tasks."

        lines = []
        status_markers = {
            "pending": "[ ]",
            "in_progress": "[>]",
            "completed": "[x]"
        }

        for t in tasks:
            marker = status_markers.get(t["status"], "[?]")
            owner = f" @{t['owner']}" if t.get("owner") else ""
            blocked = ""
            if t.get("blockedBy"):
                blocked = f" (blocked by: {t['blockedBy']})"
            lines.append(f"{marker} #{t['id']}: {t['subject']}{owner}{blocked}")

        return "\n".join(lines)

    def claim(self, tid: int, owner: str) -> str:
        """Claim task for specific owner.

        Args:
            tid: Task ID
            owner: Owner name

        Returns:
            Claim confirmation message
        """
        task = self._load(tid)
        task["owner"] = owner
        task["status"] = "in_progress"
        self._save(task)
        return f"Claimed task #{tid} for {owner}"