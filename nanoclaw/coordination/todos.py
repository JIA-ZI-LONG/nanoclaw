#!/usr/bin/env python3
"""nanoclaw.coordination.todos - In-memory task tracking for short-term checklists.

Source: s_full.py lines 124-158

State stored in instance (self.items). No file dependencies.
Validation errors raise ValueError.
"""

from typing import List, Dict


class TodoManager:
    """In-memory task tracking for short-term checklists.

    Attributes:
        items: List of todo item dicts

    Validation rules:
        - Each item requires: content, status, activeForm
        - status must be: pending, in_progress, completed
        - Max 20 items
        - Only one in_progress allowed
    """

    def __init__(self):
        self.items: List[Dict] = []

    def update(self, items: list) -> str:
        """Validate and update todo list.

        Args:
            items: List of todo item dicts

        Returns:
            Rendered todo list string

        Raises:
            ValueError: If validation fails
        """
        validated, in_progress_count = [], 0

        for i, item in enumerate(items):
            content = str(item.get("content", "")).strip()
            status = str(item.get("status", "pending")).lower()
            active_form = str(item.get("activeForm", "")).strip()

            if not content:
                raise ValueError(f"Item {i}: content required")
            if status not in ("pending", "in_progress", "completed"):
                raise ValueError(f"Item {i}: invalid status '{status}'")
            if not active_form:
                raise ValueError(f"Item {i}: activeForm required")

            if status == "in_progress":
                in_progress_count += 1

            validated.append({
                "content": content,
                "status": status,
                "activeForm": active_form
            })

        if len(validated) > 20:
            raise ValueError("Max 20 todos")
        if in_progress_count > 1:
            raise ValueError("Only one in_progress allowed")

        self.items = validated
        return self.render()

    def render(self) -> str:
        """Render as readable format: [x] [>] [ ] with counts.

        Returns:
            Formatted todo list string
        """
        if not self.items:
            return "No todos."

        lines = []
        status_markers = {
            "completed": "[x]",
            "in_progress": "[>]",
            "pending": "[ ]"
        }

        for item in self.items:
            marker = status_markers.get(item["status"], "[?]")
            suffix = ""
            if item["status"] == "in_progress":
                suffix = f" <- {item['activeForm']}"
            lines.append(f"{marker} {item['content']}{suffix}")

        done = sum(1 for t in self.items if t["status"] == "completed")
        lines.append(f"\n({done}/{len(self.items)} completed)")

        return "\n".join(lines)

    def has_open_items(self) -> bool:
        """Check if any non-completed items exist.

        Returns:
            True if any pending or in_progress items
        """
        return any(item.get("status") != "completed" for item in self.items)