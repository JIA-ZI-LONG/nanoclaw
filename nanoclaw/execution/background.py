#!/usr/bin/env python3
"""nanoclaw.execution.background - Background task threads with notifications.

Source: s_full.py lines 329-362

Thread-based execution with daemon threads and notification queue.
workdir injected per run() call.
"""

import subprocess
import threading
import uuid
from queue import Queue
from pathlib import Path


class BackgroundManager:
    """Background task execution with notification queue.

    Attributes:
        tasks: Dict of {task_id: {status, command, result}}
        notifications: Queue for async status updates
    """

    def __init__(self):
        self.tasks: dict = {}
        self.notifications: Queue = Queue()

    def run(self, command: str, workdir: Path, timeout: int = 120) -> str:
        """Start background task.

        Args:
            command: Shell command to execute
            workdir: Working directory for execution
            timeout: Maximum execution time (seconds)

        Returns:
            Task ID and status message
        """
        task_id = str(uuid.uuid4())[:8]
        self.tasks[task_id] = {
            "status": "running",
            "command": command,
            "result": None
        }

        thread = threading.Thread(
            target=self._exec,
            args=(task_id, command, workdir, timeout),
            daemon=True
        )
        thread.start()

        return f"Background task {task_id} started: {command[:80]}"

    def _exec(self, task_id: str, command: str, workdir: Path, timeout: int):
        """Execute command in thread, push notification on completion."""
        try:
            r = subprocess.run(
                command, shell=True, cwd=workdir,
                capture_output=True, text=True, timeout=timeout
            )
            output = (r.stdout + r.stderr).strip()[:50000]
            self.tasks[task_id].update({
                "status": "completed",
                "result": output or "(no output)"
            })
        except Exception as e:
            self.tasks[task_id].update({
                "status": "error",
                "result": str(e)
            })

        # Push notification
        self.notifications.put({
            "task_id": task_id,
            "status": self.tasks[task_id]["status"],
            "result": self.tasks[task_id]["result"][:500]
        })

    def check(self, task_id: str = None) -> str:
        """Check task status or list all tasks.

        Args:
            task_id: Specific task ID, or None for all

        Returns:
            Task status string or list of all tasks
        """
        if task_id:
            task = self.tasks.get(task_id)
            if task:
                return f"[{task['status']}] {task.get('result') or '(running)'}"
            return f"Unknown: {task_id}"

        if not self.tasks:
            return "No background tasks."

        lines = [
            f"{tid}: [{t['status']}] {t['command'][:60]}"
            for tid, t in self.tasks.items()
        ]
        return "\n".join(lines)

    def drain(self) -> list:
        """Drain all pending notifications.

        Returns:
            List of notification dicts {task_id, status, result}
        """
        notifications = []
        while not self.notifications.empty():
            notifications.append(self.notifications.get_nowait())
        return notifications