#!/usr/bin/env python3
"""nanoclaw.cli - REPL entry script.

Provides interactive REPL for manual agent interaction.
"""

import os
import json
from pathlib import Path
from anthropic import Anthropic
from dotenv import load_dotenv

from .agent import AgentConfig, AgentLoop


def create_default_config(workdir: Path = None) -> AgentConfig:
    """Create config from environment variables."""
    load_dotenv(override=True)
    workdir = workdir or Path.cwd()

    client = Anthropic(
        base_url=os.getenv("ANTHROPIC_BASE_URL"),
        api_key=os.getenv("ANTHROPIC_AUTH_TOKEN")
    )
    model = os.environ["MODEL_ID"]

    return AgentConfig(workdir=workdir, client=client, model=model)


def run_repl() -> None:
    """Interactive REPL loop."""
    config = create_default_config()
    agent = AgentLoop(config)
    history = []

    print("nanoclaw REPL - type 'q' or 'exit' to quit")
    print("Commands: /tasks, /compact, /team, /inbox, /heartbeat")

    while True:
        try:
            query = input("\033[36mnanoclaw >> \033[0m")
        except (EOFError, KeyboardInterrupt):
            break

        if query.strip().lower() in ("q", "exit", ""):
            break

        # REPL commands
        if query.strip() == "/tasks":
            print(agent.tasks.list_all())
            continue

        if query.strip() == "/compact":
            if history:
                print("[manual compact]")
                history[:] = agent.memory.compact(
                    history,
                    config.client,
                    config.model
                )
            continue

        if query.strip() == "/team":
            print(agent.team.list_all())
            continue

        if query.strip() == "/inbox":
            print(json.dumps(agent.bus.read_inbox("lead"), indent=2, ensure_ascii=False))
            continue

        if query.strip() == "/heartbeat":
            result = agent.heartbeat.trigger_now()
            print(result or "No tasks (HEARTBEAT.md missing or skip)")
            continue

        # Run agent
        history.append({"role": "user", "content": query})
        should_compress = agent.run(history)

        if should_compress:
            print("[compress triggered - compacting]")
            history[:] = agent.memory.compact(
                history,
                config.client,
                config.model
            )

        # Print response
        last = history[-1]
        if isinstance(last.get("content"), list):
            for block in last["content"]:
                if hasattr(block, "text"):
                    print(block.text)


if __name__ == "__main__":
    run_repl()