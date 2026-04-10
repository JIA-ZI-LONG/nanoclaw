#!/usr/bin/env python3
"""nanoclaw - Modular Agent Framework

A clean, reusable agent framework.
Provides layered architecture for both production use and educational reference.

Layers:
- core/: Foundation (tools, schemas)
- memory/: Storage + compression
- coordination/: State management (todos, tasks, skills)
- execution/: Agent spawning and background work
- communication/: Messaging and protocols
- team/: Teammate orchestration
- agent.py: Main loop integration
"""

from pathlib import Path
from anthropic import Anthropic

from .agent import AgentConfig, AgentLoop
from .core.tools import run_bash, run_read, run_write, run_edit, safe_path
from .coordination.todos import TodoManager
from .coordination.tasks import TaskManager
from .coordination.skills import SkillLoader
from .execution.subagent import run_subagent
from .execution.background import BackgroundManager
from .communication.messaging import MessageBus
from .communication.shutdown import ShutdownProtocol
from .communication.plans import PlanApprovalProtocol
from .team.manager import TeammateManager
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

    # Core
    "safe_path", "run_bash", "run_read", "run_write", "run_edit",

    # Memory
    "MemoryStore",

    # Coordination
    "TodoManager", "TaskManager", "SkillLoader",

    # Execution
    "run_subagent", "BackgroundManager",

    # Communication
    "MessageBus", "ShutdownProtocol", "PlanApprovalProtocol",

    # Team
    "TeammateManager",
]