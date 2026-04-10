#!/usr/bin/env python3
"""nanoclaw.team.manager - Teammate lifecycle management.

Source: s_full.py lines 400-543

Teammate lifecycle:
- Spawn: create teammate, start thread
- Work phase: process inbox, run LLM, execute tools
- Idle phase: poll for messages, auto-claim unclaimed tasks
- Shutdown: when no resume signal or shutdown_request received

All dependencies injected via constructor.
"""

import json
import threading
import time
from pathlib import Path


class TeammateManager:
    """Teammate lifecycle: spawn, work/idle phases, auto-claim.

    Attributes:
        bus: MessageBus for communication
        task_mgr: TaskManager for task claiming
        team_dir: Directory for team config
        client: Anthropic client
        model: Model ID
        workdir: Working directory
        poll_interval: Seconds between idle polls
        idle_timeout: Seconds before shutdown if no work
        config: Team config dict
        threads: Dict of active threads {name: Thread}
    """

    def __init__(
        self,
        bus,
        task_mgr,
        team_dir: Path,
        client,
        model: str,
        workdir: Path,
        core_handlers: dict,
        poll_interval: int = 5,
        idle_timeout: int = 60
    ):
        """Initialize teammate manager.

        Args:
            bus: MessageBus instance
            task_mgr: TaskManager instance
            team_dir: Directory for team config.json
            client: Anthropic client
            model: Model ID
            workdir: Working directory for operations
            core_handlers: Dict of core tool handlers {bash, read, write, edit}
            poll_interval: Seconds between idle phase polls
            idle_timeout: Seconds before auto-shutdown
        """
        team_dir.mkdir(exist_ok=True)

        self.bus = bus
        self.task_mgr = task_mgr
        self.team_dir = team_dir
        self.client = client
        self.model = model
        self.workdir = workdir
        self.core_handlers = core_handlers
        self.poll_interval = poll_interval
        self.idle_timeout = idle_timeout

        self.config_path = team_dir / "config.json"
        self.config = self._load_config()
        self.threads: dict = {}

    def _load_config(self) -> dict:
        """Load team config from file.

        Returns:
            Config dict with team_name and members list
        """
        if self.config_path.exists():
            return json.loads(self.config_path.read_text(encoding='utf-8'))
        return {"team_name": "default", "members": []}

    def _save_config(self):
        """Save team config to file."""
        self.config_path.write_text(json.dumps(self.config, indent=2, ensure_ascii=False), encoding='utf-8')

    def _find_member(self, name: str) -> dict:
        """Find member by name in config.

        Args:
            name: Member name

        Returns:
            Member dict or None
        """
        for member in self.config["members"]:
            if member["name"] == name:
                return member
        return None

    def _set_status(self, name: str, status: str):
        """Update member status in config.

        Args:
            name: Member name
            status: New status (working, idle, shutdown)
        """
        member = self._find_member(name)
        if member:
            member["status"] = status
            self._save_config()

    def spawn(self, name: str, role: str, prompt: str) -> str:
        """Spawn teammate with name, role, initial prompt.

        Args:
            name: Teammate name
            role: Role description
            prompt: Initial task prompt

        Returns:
            Spawn confirmation message
        """
        member = self._find_member(name)

        if member:
            if member["status"] not in ("idle", "shutdown"):
                return f"Error: '{name}' is currently {member['status']}"
            member["status"] = "working"
            member["role"] = role
        else:
            member = {"name": name, "role": role, "status": "working"}
            self.config["members"].append(member)

        self._save_config()

        thread = threading.Thread(
            target=self._loop,
            args=(name, role, prompt),
            daemon=True
        )
        self.threads[name] = thread
        thread.start()

        return f"Spawned '{name}' (role: {role})"

    def _loop(self, name: str, role: str, prompt: str):
        """Teammate loop: work phase -> idle phase -> repeat.

        Args:
            name: Teammate name
            role: Role description
            prompt: Initial prompt
        """
        team_name = self.config["team_name"]
        sys_prompt = (
            f"You are '{name}', role: {role}, team: {team_name}, at {self.workdir}. "
            f"Use idle when done with current work. You may auto-claim tasks."
        )

        messages = [{"role": "user", "content": prompt}]

        # Build teammate tools
        tools = self._build_teammate_tools()

        while True:
            # === WORK PHASE ===
            for _ in range(50):
                # Process inbox
                inbox = self.bus.read_inbox(name)
                for msg in inbox:
                    if msg.get("type") == "shutdown_request":
                        self._set_status(name, "shutdown")
                        return
                    messages.append({"role": "user", "content": json.dumps(msg)})

                # LLM call
                try:
                    response = self.client.messages.create(
                        model=self.model,
                        system=sys_prompt,
                        messages=messages,
                        tools=tools,
                        max_tokens=8000
                    )
                except Exception:
                    self._set_status(name, "shutdown")
                    return

                messages.append({"role": "assistant", "content": response.content})

                if response.stop_reason != "tool_use":
                    break

                results = []
                idle_requested = False

                for block in response.content:
                    if block.type == "tool_use":
                        output = self._handle_tool(name, block)
                        if block.name == "idle":
                            idle_requested = True
                            output = "Entering idle phase."
                        print(f"  [{name}] {block.name}: {str(output)[:120]}")
                        results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": str(output)
                        })

                messages.append({"role": "user", "content": results})

                if idle_requested:
                    break

            # === IDLE PHASE ===
            self._set_status(name, "idle")
            resume = False

            for _ in range(self.idle_timeout // max(self.poll_interval, 1)):
                time.sleep(self.poll_interval)

                # Check inbox
                inbox = self.bus.read_inbox(name)
                if inbox:
                    for msg in inbox:
                        if msg.get("type") == "shutdown_request":
                            self._set_status(name, "shutdown")
                            return
                        messages.append({"role": "user", "content": json.dumps(msg)})
                    resume = True
                    break

                # Auto-claim unclaimed tasks
                unclaimed = self._find_unclaimed_tasks()
                if unclaimed:
                    task = unclaimed[0]
                    self.task_mgr.claim(task["id"], name)

                    # Identity re-injection for compressed contexts
                    if len(messages) <= 3:
                        messages.insert(0, {
                            "role": "user",
                            "content": f"<identity>You are '{name}', role: {role}, team: {team_name}.</identity>"
                        })
                        messages.insert(1, {
                            "role": "assistant",
                            "content": f"I am {name}. Continuing."
                        })

                    messages.append({
                        "role": "user",
                        "content": f"<auto-claimed>Task #{task['id']}: {task['subject']}\n{task.get('description', '')}</auto-claimed>"
                    })
                    messages.append({
                        "role": "assistant",
                        "content": f"Claimed task #{task['id']}. Working on it."
                    })
                    resume = True
                    break

            if not resume:
                self._set_status(name, "shutdown")
                return

            self._set_status(name, "working")

    def _build_teammate_tools(self) -> list:
        """Build tool schemas for teammate.

        Returns:
            List of tool schema dicts
        """
        return [
            {"name": "bash", "description": "Run command.",
             "input_schema": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}},
            {"name": "read_file", "description": "Read file.",
             "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
            {"name": "write_file", "description": "Write file.",
             "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}},
            {"name": "edit_file", "description": "Edit file.",
             "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "old_text": {"type": "string"}, "new_text": {"type": "string"}}, "required": ["path", "old_text", "new_text"]}},
            {"name": "send_message", "description": "Send message.",
             "input_schema": {"type": "object", "properties": {"to": {"type": "string"}, "content": {"type": "string"}}, "required": ["to", "content"]}},
            {"name": "idle", "description": "Signal no more work.",
             "input_schema": {"type": "object", "properties": {}}},
            {"name": "claim_task", "description": "Claim task by ID.",
             "input_schema": {"type": "object", "properties": {"task_id": {"type": "integer"}}, "required": ["task_id"]}},
        ]

    def _handle_tool(self, name: str, block) -> str:
        """Handle tool call for teammate.

        Args:
            name: Teammate name
            block: Tool use block

        Returns:
            Tool output string
        """
        if block.name == "claim_task":
            return self.task_mgr.claim(block.input["task_id"], name)
        elif block.name == "send_message":
            return self.bus.send(name, block.input["to"], block.input["content"])
        else:
            handler = self.core_handlers.get(block.name)
            if handler:
                return handler(**block.input)
            return f"Unknown tool: {block.name}"

    def _find_unclaimed_tasks(self) -> list:
        """Find unclaimed, unblocked pending tasks.

        Returns:
            List of task dicts
        """
        unclaimed = []
        for f in sorted(self.task_mgr.tasks_dir.glob("task_*.json")):
            task = json.loads(f.read_text(encoding='utf-8'))
            if task.get("status") == "pending" and not task.get("owner") and not task.get("blockedBy"):
                unclaimed.append(task)
        return unclaimed

    def list_all(self) -> str:
        """List all teammates with status.

        Returns:
            Formatted team list string
        """
        if not self.config["members"]:
            return "No teammates."

        lines = [f"Team: {self.config['team_name']}"]
        for member in self.config["members"]:
            lines.append(f"  {member['name']} ({member['role']}): {member['status']}")
        return "\n".join(lines)

    def member_names(self) -> list:
        """Return list of member names.

        Returns:
            List of name strings
        """
        return [member["name"] for member in self.config["members"]]