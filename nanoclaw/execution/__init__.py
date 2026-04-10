#!/usr/bin/env python3
"""nanoclaw.execution - Agent spawning and background work.

This layer provides execution mechanisms:
- subagent.py: Spawn isolated agents for exploration or work
- background.py: Background task threads with notifications
"""

from .subagent import run_subagent
from .background import BackgroundManager

__all__ = ["run_subagent", "BackgroundManager"]