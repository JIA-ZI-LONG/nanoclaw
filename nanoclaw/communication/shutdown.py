#!/usr/bin/env python3
"""nanoclaw.communication.shutdown - Shutdown request/response handshake.

Source: s_full.py lines 395, 561-565

Protocol for graceful teammate shutdown:
- Lead sends shutdown_request with request_id
- Teammate responds with shutdown_response (approve=True)
- Lead tracks pending requests
"""

import uuid


class ShutdownProtocol:
    """Shutdown request/response handshake.

    Attributes:
        bus: MessageBus for sending requests
        requests: Dict tracking pending requests {request_id: {target, status}}
    """

    def __init__(self, bus):
        """Initialize with message bus.

        Args:
            bus: MessageBus instance for communication
        """
        self.bus = bus
        self.requests: dict = {}

    def request(self, sender: str, target: str) -> str:
        """Send shutdown request to target.

        Args:
            sender: Requester name (usually "lead")
            target: Target teammate name

        Returns:
            Request ID and confirmation
        """
        request_id = str(uuid.uuid4())[:8]
        self.requests[request_id] = {
            "target": target,
            "status": "pending"
        }

        self.bus.send(
            sender, target,
            "Please shut down.",
            "shutdown_request",
            {"request_id": request_id}
        )

        return f"Shutdown request {request_id} sent to '{target}'"

    def handle_response(self, request_id: str, approve: bool) -> str:
        """Process shutdown response.

        Args:
            request_id: Request ID from response
            approve: Whether shutdown was approved

        Returns:
            Status message
        """
        req = self.requests.get(request_id)
        if not req:
            return f"Error: Unknown request_id '{request_id}'"

        req["status"] = "approved" if approve else "rejected"
        return f"Shutdown {req['status']} for '{req['target']}'"

    def get_pending(self) -> list:
        """Get list of pending shutdown requests.

        Returns:
            List of pending request dicts
        """
        return [
            {"request_id": rid, **data}
            for rid, data in self.requests.items()
            if data["status"] == "pending"
        ]