#!/usr/bin/env python3
"""nanoclaw.agent - Main agent loop orchestrating all components.

Source: Assembled from multiple s_full.py sections

Classes:
- AgentConfig: Configuration container for dependency injection
- AgentLoop: Main agent loop, orchestrates all components
"""

import json
from pathlib import Path
from anthropic import Anthropic

from .tools import run_bash, run_read, run_write, run_edit, TOOL_SCHEMAS
from .coordination.todos import TodoManager
from .coordination.tasks import TaskManager
from .coordination.skills import SkillLoader
from .execution.subagent import run_subagent
from .execution.background import BackgroundManager
from .team import TeammateManager, MessageBus, ShutdownProtocol, PlanApprovalProtocol
from .heartbeat import HeartbeatService
from .memory import MemoryStore


class AgentConfig:
    """Configuration container for dependency injection.

    All dependencies flow through this container, enabling:
    - Custom configurations for different environments
    - Easy testing with mock clients
    - No hidden global state

    Attributes:
        workdir: Working directory for file operations
        client: Anthropic client for LLM calls
        model: Model ID for LLM
        token_threshold: Token count threshold for auto-compact
        poll_interval: Seconds between idle phase polls
        idle_timeout: Seconds before auto-shutdown
        skills_dir: Directory for SKILL.md files
        tasks_dir: Directory for task JSON files
        transcript_dir: Directory for compression transcripts
        inbox_dir: Directory for message inboxes
        team_dir: Directory for team config
    """

    def __init__(
        self,
        workdir: Path,
        client: Anthropic,
        model: str,
        token_threshold: int = 100000,
        poll_interval: int = 5,
        idle_timeout: int = 60,
        heartbeat_interval: int = 1800,
        skills_dir: Path = None,
        tasks_dir: Path = None,
        transcript_dir: Path = None,
        inbox_dir: Path = None,
        team_dir: Path = None,
    ):
        self.workdir = workdir
        self.client = client
        self.model = model
        self.token_threshold = token_threshold
        self.poll_interval = poll_interval
        self.idle_timeout = idle_timeout
        self.heartbeat_interval = heartbeat_interval

        # Default paths (can override)
        self.skills_dir = skills_dir or workdir / "skills"
        self.tasks_dir = tasks_dir or workdir / ".tasks"
        self.transcript_dir = transcript_dir or workdir / ".transcripts"
        self.inbox_dir = inbox_dir or workdir / ".team" / "inbox"
        self.team_dir = team_dir or workdir / ".team"


class AgentLoop:
    """Main agent loop, orchestrates all components.

    The loop:
    1. Compression pipeline (microcompact + auto_compact)
    2. Drain background notifications
    3. Check inbox for messages
    4. LLM call with tools
    5. Tool execution and results
    6. Nag reminder (if todos active)

    Attributes:
        config: AgentConfig instance
        todos: TodoManager for short-term checklists
        tasks: TaskManager for persistent tasks
        skills: SkillLoader for skill definitions
        background: BackgroundManager for background tasks
        bus: MessageBus for inter-agent messaging
        shutdown: ShutdownProtocol for graceful shutdown
        plans: PlanApprovalProtocol for plan approval
        team: TeammateManager for teammate orchestration
        tool_handlers: Dict mapping tool names to handlers
        system_prompt: Generated system prompt with skill descriptions
    """

    def __init__(self, config: AgentConfig):
        self.config = config

        # Create core handlers (bound to workdir)
        self._core_handlers = {
            "bash": lambda **kw: run_bash(kw["command"], config.workdir),
            "read_file": lambda **kw: run_read(kw["path"], config.workdir, kw.get("limit")),
            "write_file": lambda **kw: run_write(kw["path"], kw["content"], config.workdir),
            "edit_file": lambda **kw: run_edit(kw["path"], kw["old_text"], kw["new_text"], config.workdir),
        }

        # Create coordination instances
        self.todos = TodoManager()
        self.tasks = TaskManager(config.tasks_dir)
        self.skills = SkillLoader(config.skills_dir)

        # Create execution instances
        self.background = BackgroundManager()

        # Create communication instances
        self.bus = MessageBus(config.inbox_dir)
        self.shutdown = ShutdownProtocol(self.bus)
        self.plans = PlanApprovalProtocol(self.bus)

        # Create team instance
        self.team = TeammateManager(
            bus=self.bus,
            task_mgr=self.tasks,
            team_dir=config.team_dir,
            client=config.client,
            model=config.model,
            workdir=config.workdir,
            core_handlers=self._core_handlers,
            poll_interval=config.poll_interval,
            idle_timeout=config.idle_timeout
        )

        # Create heartbeat service
        self.heartbeat = HeartbeatService(
            workdir=config.workdir,
            client=config.client,
            model=config.model,
            interval_s=config.heartbeat_interval,
            on_execute=lambda t: f"Heartbeat tasks: {t}",
        )
        self.heartbeat.start()

        # Create memory store
        self.memory = MemoryStore(config.workdir)

        # Build handlers and system prompt
        self.tool_handlers = self._build_handlers()
        self.system_prompt = self._build_system_prompt()

    def _build_handlers(self) -> dict:
        """Map tool names to handler functions.

        Returns:
            Dict of {tool_name: lambda handler}
        """
        handlers = {}

        # Core tools
        handlers.update(self._core_handlers)

        # Todo
        handlers["TodoWrite"] = lambda **kw: self.todos.update(kw["items"])

        # Tasks
        handlers["task_create"] = lambda **kw: self.tasks.create(kw["subject"], kw.get("description", ""))
        handlers["task_get"] = lambda **kw: self.tasks.get(kw["task_id"])
        handlers["task_update"] = lambda **kw: self.tasks.update(
            kw["task_id"],
            kw.get("status"),
            kw.get("add_blocked_by"),
            kw.get("remove_blocked_by"),
            kw.get("owner")
        )
        handlers["task_list"] = lambda **kw: self.tasks.list_all()

        # Subagent
        handlers["task"] = lambda **kw: run_subagent(
            prompt=kw["prompt"],
            client=self.config.client,
            model=self.config.model,
            workdir_handler_bash=self._core_handlers["bash"],
            workdir_handler_read=self._core_handlers["read_file"],
            agent_type=kw.get("agent_type", "Explore"),
            workdir_handler_write=self._core_handlers["write_file"],
            workdir_handler_edit=self._core_handlers["edit_file"],
        )

        # Skills
        handlers["load_skill"] = lambda **kw: self.skills.load(kw["name"])

        # Compression
        handlers["compress"] = lambda **kw: "Compressing..."

        # Background
        handlers["background_run"] = lambda **kw: self.background.run(
            kw["command"], self.config.workdir, kw.get("timeout", 120)
        )
        handlers["check_background"] = lambda **kw: self.background.check(kw.get("task_id"))

        # Team
        handlers["spawn_teammate"] = lambda **kw: self.team.spawn(
            kw["name"], kw["role"], kw["prompt"]
        )
        handlers["list_teammates"] = lambda **kw: self.team.list_all()

        # Messaging
        handlers["send_message"] = lambda **kw: self.bus.send(
            "lead", kw["to"], kw["content"], kw.get("msg_type", "message")
        )
        handlers["read_inbox"] = lambda **kw: json.dumps(
            self.bus.read_inbox("lead"), indent=2
        )
        handlers["broadcast"] = lambda **kw: self.bus.broadcast(
            "lead", kw["content"], self.team.member_names()
        )

        # Shutdown
        handlers["shutdown_request"] = lambda **kw: self.shutdown.request(
            "lead", kw["teammate"]
        )

        # Plan approval
        handlers["plan_approval"] = lambda **kw: self.plans.review(
            kw["request_id"], kw["approve"], kw.get("feedback", "")
        )

        # Idle & Claim (lead doesn't idle)
        handlers["idle"] = lambda **kw: "Lead does not idle."
        handlers["claim_task"] = lambda **kw: self.tasks.claim(kw["task_id"], "lead")

        return handlers

    def _build_system_prompt(self) -> str:
        """Generate system prompt with soul, agents, user, and skill descriptions.

        Returns:
            System prompt string
        """
        parts = []

        # Load SOUL.md (identity)
        soul_path = self.config.workdir / "prompts" / "SOUL.md"
        if soul_path.exists():
            parts.append(soul_path.read_text(encoding="utf-8"))

        # Load AGENTS.md (instructions)
        agents_path = self.config.workdir / "prompts" / "AGENTS.md"
        if agents_path.exists():
            parts.append(agents_path.read_text(encoding="utf-8"))

        # Load USER.md (user profile)
        user_path = self.config.workdir / "prompts" / "USER.md"
        if user_path.exists():
            parts.append(user_path.read_text(encoding="utf-8"))

        # Memory context
        memory_ctx = self.memory.get_context()
        if memory_ctx:
            parts.append(memory_ctx)

        # Recent history
        history_ctx = self.memory.get_recent_history(limit=5)
        if history_ctx:
            parts.append(history_ctx)

        # Default context
        parts.append(
            f"Workspace: {self.config.workdir}\n"
            f"Skills: {self.skills.descriptions()}"
        )

        return "\n\n---\n\n".join(parts)

    def run(self, messages: list) -> bool:
        """Execute agent loop until stop or manual compress.

        Args:
            messages: Conversation history (mutated in-place)

        Returns:
            True if manual compress triggered (caller should compact)
        """
        rounds_without_todo = 0

        while True:
            # 1. Compression pipeline
            self.memory._microcompact(messages)

            if self.memory.estimate_tokens(messages) > self.config.token_threshold:
                messages[:] = self.memory.compact(
                    messages,
                    self.config.client,
                    self.config.model
                )

            # 2. Drain background notifications
            notifs = self.background.drain()
            if notifs:
                txt = "\n".join(
                    f"[bg:{n['task_id']}] {n['status']}: {n['result']}"
                    for n in notifs
                )
                messages.append({
                    "role": "user",
                    "content": f"<background-results>\n{txt}\n</background-results>"
                })

            # 2b. Drain heartbeat notifications
            hb_notifs = self.heartbeat.drain()
            if hb_notifs:
                hb_txt = "\n".join(
                    f"[heartbeat] {n['tasks']}: {n['result']}"
                    for n in hb_notifs
                )
                messages.append({
                    "role": "user",
                    "content": f"<heartbeat-results>\n{hb_txt}\n</heartbeat-results>"
                })

            # 3. Check inbox
            inbox = self.bus.read_inbox("lead")
            if inbox:
                messages.append({
                    "role": "user",
                    "content": f"<inbox>{json.dumps(inbox, indent=2)}</inbox>"
                })

            # 4. LLM call
            response = self.config.client.messages.create(
                model=self.config.model,
                system=self.system_prompt,
                messages=messages,
                tools=TOOL_SCHEMAS,
                max_tokens=8000,
            )
            messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason != "tool_use":
                return False

            # 5. Tool execution
            results, manual_compress, used_todo = self._execute_tools(response.content)
            messages.append({"role": "user", "content": results})

            # 6. Nag reminder
            rounds_without_todo = 0 if used_todo else rounds_without_todo + 1
            if self.todos.has_open_items() and rounds_without_todo >= 3:
                results.append({
                    "type": "text",
                    "text": "<reminder>Update your todos.</reminder>"
                })

            # Manual compress triggers return
            if manual_compress:
                return True

    def _execute_tools(self, content) -> tuple:
        """Execute tool calls, return tool_result list.

        Args:
            content: Response content blocks

        Returns:
            Tuple of (results list, manual_compress bool, used_todo bool)
        """
        results = []
        manual_compress = False
        used_todo = False

        for block in content:
            if block.type == "tool_use":
                if block.name == "compress":
                    manual_compress = True
                if block.name == "TodoWrite":
                    used_todo = True

                handler = self.tool_handlers.get(block.name)

                try:
                    output = handler(**block.input) if handler else f"Unknown tool: {block.name}"
                except Exception as e:
                    output = f"Error: {e}"

                print(f"> {block.name}:")
                print(str(output)[:200])

                results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": str(output)[:50000]
                })

        return results, manual_compress, used_todo