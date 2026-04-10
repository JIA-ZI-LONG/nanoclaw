"""Heartbeat service - periodic task check via LLM decision."""

import threading
import time
from pathlib import Path
from queue import Queue
from typing import Callable, Optional

_HEARTBEAT_TOOL = [{
    "name": "heartbeat",
    "input_schema": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["skip", "run"]},
            "tasks": {"type": "string"}
        },
        "required": ["action"]
    }
}]


class HeartbeatService:
    """周期性心跳服务，线程实现。

    Phase 1: LLM 读取 HEARTBEAT.md，决策 skip/run
    Phase 2: 若 run，调用 on_execute 执行任务
    """

    def __init__(
        self,
        workdir: Path,
        client,  # Anthropic client
        model: str,
        interval_s: int = 1800,
        on_execute: Optional[Callable[[str], str]] = None,
    ):
        self.workdir = workdir
        self.client = client
        self.model = model
        self.interval_s = interval_s
        self.on_execute = on_execute
        self._running = False
        self._thread = None
        self._notifications = Queue()

    def _decide(self, content: str) -> tuple[str, str]:
        """LLM 决策阶段，返回 (action, tasks)"""
        try:
            r = self.client.messages.create(
                model=self.model,
                system="Call heartbeat tool with skip/run decision.",
                messages=[{"role": "user", "content": f"Review:\n{content}"}],
                tools=_HEARTBEAT_TOOL,
                max_tokens=256,
            )
            for b in r.content:
                if b.type == "tool_use" and b.name == "heartbeat":
                    return b.input.get("action", "skip"), b.input.get("tasks", "")
        except Exception:
            pass
        return "skip", ""

    def _tick(self):
        """执行一次心跳检查"""
        f = self.workdir / "prompts" / "HEARTBEAT.md"
        if not f.exists():
            return
        action, tasks = self._decide(f.read_text(encoding="utf-8"))
        if action == "run" and self.on_execute:
            result = self.on_execute(tasks)
            self._notifications.put({"tasks": tasks, "result": result})

    def _loop(self):
        """心跳主循环"""
        while self._running:
            time.sleep(self.interval_s)
            if self._running:
                self._tick()

    def start(self):
        """启动心跳服务"""
        if not self._running:
            self._running = True
            self._thread = threading.Thread(target=self._loop, daemon=True)
            self._thread.start()

    def stop(self):
        """停止心跳服务"""
        self._running = False

    def trigger_now(self) -> Optional[str]:
        """手动触发一次心跳"""
        f = self.workdir / "prompts" / "HEARTBEAT.md"
        if not f.exists():
            return None
        action, tasks = self._decide(f.read_text(encoding="utf-8"))
        return self.on_execute(tasks) if action == "run" and self.on_execute else None

    def drain(self) -> list:
        """取出所有待处理的心跳通知"""
        n = []
        while not self._notifications.empty():
            n.append(self._notifications.get_nowait())
        return n