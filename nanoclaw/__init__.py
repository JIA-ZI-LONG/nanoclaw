#!/usr/bin/env python3
"""nanoclaw - Modular Agent Framework

A clean, reusable agent framework.
Provides layered architecture for both production use and educational reference.

Layers:
- tools/: Tool implementations (bash, read, write, edit) + schemas
- memory/: Storage + compression
- coordination/: State management (todos, tasks, skills)
- execution/: Agent spawning and background work
- team/: Teammate orchestration + messaging + protocols
- agent.py: Main loop integration
"""

from pathlib import Path
from anthropic import Anthropic

from .agent import AgentConfig, AgentLoop
from .tools import run_bash, run_read, run_write, run_edit, safe_path, TOOL_SCHEMAS
from .coordination.todos import TodoManager
from .coordination.tasks import TaskManager
from .coordination.skills import SkillLoader
from .execution.subagent import run_subagent
from .execution.background import BackgroundManager
from .team import TeammateManager, MessageBus, ShutdownProtocol, PlanApprovalProtocol
from .memory import MemoryStore


def create_agent(
    workdir: Path = None,
    client: Anthropic = None,
    model: str = None
) -> AgentLoop:
    """Quick factory for AgentLoop with defaults."""
    from .cli import create_default_config
    config = create_default_config(workdir)
    if client:
        config.client = client
    if model:
        config.model = model
    return AgentLoop(config)


__all__ = [
    # Agent
    "AgentConfig", "AgentLoop", "create_agent",

    # Tools
    "safe_path", "run_bash", "run_read", "run_write", "run_edit", "TOOL_SCHEMAS",

    # Memory
    "MemoryStore",

    # Coordination
    "TodoManager", "TaskManager", "SkillLoader",

    # Execution
    "run_subagent", "BackgroundManager",

    # Team (includes messaging + protocols)
    "TeammateManager", "MessageBus", "ShutdownProtocol", "PlanApprovalProtocol",
]