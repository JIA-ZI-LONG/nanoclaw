#!/usr/bin/env python3
"""nanoclaw.team - Teammate orchestration.

This layer provides team mechanisms:
- manager.py: Teammate lifecycle (spawn, idle/work phases, auto-claim)
"""

from .manager import TeammateManager

__all__ = ["TeammateManager"]