#!/usr/bin/env python3
"""nanoclaw.execution.subagent - Spawn isolated agents for exploration/work.

Source: s_full.py lines 161-196

Provides two agent types:
- Explore: read-only (bash, read_file)
- general-purpose: read/write (bash, read, write, edit)
"""

from anthropic import Anthropic


def run_subagent(
    prompt: str,
    client: Anthropic,
    model: str,
    workdir_handler_bash: callable,
    workdir_handler_read: callable,
    agent_type: str = "Explore",
    workdir_handler_write: callable = None,
    workdir_handler_edit: callable = None,
) -> str:
    """Spawn subagent for isolated exploration or work.

    Args:
        prompt: Task prompt for subagent
        agent_type: "Explore" (read-only) or "general-purpose" (read/write)
        client: Anthropic client
        model: Model ID
        workdir_handler_bash: Bash handler (already bound to workdir)
        workdir_handler_read: Read handler (already bound to workdir)
        workdir_handler_write: Write handler (for general-purpose)
        workdir_handler_edit: Edit handler (for general-purpose)

    Returns:
        Summary text from subagent, or error message
    """
    # Build tool schemas based on agent_type
    sub_tools = [
        {
            "name": "bash",
            "description": "Run command.",
            "input_schema": {
                "type": "object",
                "properties": {"command": {"type": "string"}},
                "required": ["command"]
            }
        },
        {
            "name": "read_file",
            "description": "Read file.",
            "input_schema": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"]
            }
        },
    ]

    if agent_type != "Explore":
        sub_tools += [
            {
                "name": "write_file",
                "description": "Write file.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "content": {"type": "string"}
                    },
                    "required": ["path", "content"]
                }
            },
            {
                "name": "edit_file",
                "description": "Edit file.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "old_text": {"type": "string"},
                        "new_text": {"type": "string"}
                    },
                    "required": ["path", "old_text", "new_text"]
                }
            },
        ]

    # Build handlers
    sub_handlers = {
        "bash": workdir_handler_bash,
        "read_file": workdir_handler_read,
    }
    if agent_type != "Explore":
        sub_handlers["write_file"] = workdir_handler_write
        sub_handlers["edit_file"] = workdir_handler_edit

    # Run subagent loop
    sub_msgs = [{"role": "user", "content": prompt}]
    resp = None

    for _ in range(30):  # Max 30 iterations
        resp = client.messages.create(
            model=model,
            messages=sub_msgs,
            tools=sub_tools,
            max_tokens=8000
        )
        sub_msgs.append({"role": "assistant", "content": resp.content})

        if resp.stop_reason != "tool_use":
            break

        results = []
        for block in resp.content:
            if block.type == "tool_use":
                handler = sub_handlers.get(block.name, lambda **kw: "Unknown tool")
                output = handler(**block.input)
                results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": str(output)[:50000]
                })
        sub_msgs.append({"role": "user", "content": results})

    if resp:
        return "".join(
            b.text for b in resp.content if hasattr(b, "text")
        ) or "(no summary)"
    return "(subagent failed)"