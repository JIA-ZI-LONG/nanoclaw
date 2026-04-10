#!/usr/bin/env python3
"""nanoclaw.communication.plans - Plan approval workflow.

Source: s_full.py lines 396, 568-574

Protocol for plan submission and review:
- Teammate submits plan (stores request)
- Lead reviews and sends plan_approval_response
- Teammate receives approval/rejection with feedback
"""

import uuid


class PlanApprovalProtocol:
    """Plan submission and approval workflow.

    Attributes:
        bus: MessageBus for sending responses
        requests: Dict tracking pending requests {request_id: {from, status, content}}
    """

    def __init__(self, bus):
        """Initialize with message bus.

        Args:
            bus: MessageBus instance for communication
        """
        self.bus = bus
        self.requests: dict = {}

    def submit(self, from_agent: str, plan_content: str) -> str:
        """Submit plan for approval.

        Args:
            from_agent: Agent submitting plan
            plan_content: Plan description

        Returns:
            Request ID and confirmation
        """
        request_id = str(uuid.uuid4())[:8]
        self.requests[request_id] = {
            "from": from_agent,
            "status": "pending",
            "content": plan_content
        }
        return f"Plan submitted with request_id {request_id}"

    def review(
        self,
        request_id: str,
        approve: bool,
        feedback: str = "",
        reviewer: str = "lead"
    ) -> str:
        """Review plan and send response.

        Args:
            request_id: Request ID to review
            approve: True to approve, False to reject
            feedback: Optional feedback message
            reviewer: Reviewer name (usually "lead")

        Returns:
            Status message
        """
        req = self.requests.get(request_id)
        if not req:
            return f"Error: Unknown request_id '{request_id}'"

        req["status"] = "approved" if approve else "rejected"

        self.bus.send(
            reviewer, req["from"],
            feedback,
            "plan_approval_response",
            {"request_id": request_id, "approve": approve, "feedback": feedback}
        )

        return f"Plan {req['status']} for '{req['from']}'"

    def get_pending(self) -> list:
        """Get list of pending plan requests.

        Returns:
            List of pending request dicts
        """
        return [
            {"request_id": rid, **data}
            for rid, data in self.requests.items()
            if data["status"] == "pending"
        ]