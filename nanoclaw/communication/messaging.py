#!/usr/bin/env python3
"""nanoclaw.communication.messaging - Inter-agent messaging via JSONL files.

Source: s_full.py lines 365-392

inbox_dir injected via constructor. JSONL format for append-only writes.
Message types: message, broadcast, shutdown_request, shutdown_response, plan_approval_response
"""

import json
import time
from pathlib import Path


class MessageBus:
    """Inter-agent messaging via JSONL files.

    Attributes:
        inbox_dir: Directory for inbox JSONL files

    Inbox format: {name}.jsonl - one JSON message per line
    Message format: {type, from, content, timestamp, ...extra}
    """

    VALID_MSG_TYPES = {
        "message",
        "broadcast",
        "shutdown_request",
        "shutdown_response",
        "plan_approval_response"
    }

    def __init__(self, inbox_dir: Path):
        """Initialize with inbox directory.

        Args:
            inbox_dir: Directory to store inbox files
        """
        self.inbox_dir = inbox_dir
        inbox_dir.mkdir(parents=True, exist_ok=True)

    def send(
        self,
        sender: str,
        to: str,
        content: str,
        msg_type: str = "message",
        extra: dict = None
    ) -> str:
        """Send message to recipient's inbox.

        Args:
            sender: Sender name
            to: Recipient name
            content: Message content
            msg_type: Message type (message, broadcast, etc.)
            extra: Additional fields to include

        Returns:
            Confirmation message
        """
        if msg_type not in self.VALID_MSG_TYPES:
            return f"Error: Invalid msg_type '{msg_type}'"

        msg = {
            "type": msg_type,
            "from": sender,
            "content": content,
            "timestamp": time.time()
        }
        if extra:
            msg.update(extra)

        inbox_path = self.inbox_dir / f"{to}.jsonl"
        with open(inbox_path, "a", encoding='utf-8') as f:
            f.write(json.dumps(msg) + "\n")

        return f"Sent {msg_type} to {to}"

    def read_inbox(self, name: str) -> list:
        """Read and drain inbox for name.

        Args:
            name: Agent name to read inbox for

        Returns:
            List of message dicts
        """
        path = self.inbox_dir / f"{name}.jsonl"
        if not path.exists():
            return []

        content = path.read_text(encoding='utf-8').strip()
        if not content:
            return []

        messages = [json.loads(line) for line in content.splitlines() if line]
        path.write_text("", encoding='utf-8')  # Clear inbox

        return messages

    def broadcast(self, sender: str, content: str, names: list) -> str:
        """Broadcast message to all names except sender.

        Args:
            sender: Sender name
            content: Message content
            names: List of recipient names

        Returns:
            Count of messages sent
        """
        count = 0
        for name in names:
            if name != sender:
                self.send(sender, name, content, "broadcast")
                count += 1
        return f"Broadcast to {count} teammates"