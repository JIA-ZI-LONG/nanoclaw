#!/usr/bin/env python3
"""nanoclaw.coordination - State management with core dependencies.

This layer manages coordination mechanisms:
- todos.py: In-memory task tracking (TodoManager)
- tasks.py: File-based persistent tasks (TaskManager)
- skills.py: SKILL.md loading and management (SkillLoader)
"""

from .todos import TodoManager
from .tasks import TaskManager
from .skills import SkillLoader

__all__ = ["TodoManager", "TaskManager", "SkillLoader"]