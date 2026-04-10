#!/usr/bin/env python3
"""nanoclaw.communication - Messaging and protocol mechanisms.

This layer provides communication mechanisms:
- messaging.py: Inter-agent messaging via JSONL files
- shutdown.py: Shutdown request/response handshake
- plans.py: Plan approval workflow
"""

from .messaging import MessageBus
from .shutdown import ShutdownProtocol
from .plans import PlanApprovalProtocol

__all__ = ["MessageBus", "ShutdownProtocol", "PlanApprovalProtocol"]