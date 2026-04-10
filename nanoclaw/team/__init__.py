#!/usr/bin/env python3
"""nanoclaw.team - Teammate orchestration and communication.

This layer provides:
- manager.py: Teammate lifecycle (spawn, idle/work phases, auto-claim)
- messaging.py: Message bus for inter-agent communication
- plans.py: Plan approval protocol
- shutdown.py: Graceful shutdown protocol
"""

from .manager import TeammateManager
from .messaging import MessageBus
from .plans import PlanApprovalProtocol
from .shutdown import ShutdownProtocol

__all__ = [
    "TeammateManager",
    "MessageBus",
    "PlanApprovalProtocol",
    "ShutdownProtocol",
]