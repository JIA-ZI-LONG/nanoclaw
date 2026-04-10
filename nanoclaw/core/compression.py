#!/usr/bin/env python3
"""nanoclaw.core.compression - Context management for long conversations.

Source: s_full.py lines 227-260

Functions:
- estimate_tokens: Pure function, no dependencies
- microcompact: Direct mutation of messages list
- auto_compact: Receives client/model/transcript_dir as parameters (DI)
"""

import json
import time
from pathlib import Path
from anthropic import Anthropic


def estimate_tokens(messages: list) -> int:
    """Estimate token count from message JSON length.

    Simple heuristic: JSON length / 4 (approximates token count).

    Args:
        messages: List of message dicts

    Returns:
        Estimated token count
    """
    return len(json.dumps(messages, default=str)) // 4


def microcompact(messages: list) -> None:
    """Clear old tool_result content (>100 chars, keep last 3).

    Mutates messages list in-place. Reduces context size without
    losing recent tool results that may be referenced.

    Args:
        messages: List of message dicts to mutate

    Note:
        No return value - modifies messages directly
    """
    # Collect all tool_result parts from user messages
    tool_results = []
    for msg in messages:
        if msg["role"] == "user" and isinstance(msg.get("content"), list):
            for part in msg["content"]:
                if isinstance(part, dict) and part.get("type") == "tool_result":
                    tool_results.append(part)

    # Keep only last 3, clear older ones with >100 chars
    if len(tool_results) <= 3:
        return
    for part in tool_results[:-3]:
        if isinstance(part.get("content"), str) and len(part["content"]) > 100:
            part["content"] = "[cleared]"


def auto_compact(
    messages: list,
    client: Anthropic,
    model: str,
    transcript_dir: Path,
    memory=None,
) -> list:
    """Compress via LLM summary, save transcript, return condensed messages.

    Args:
        messages: Current conversation history
        client: Anthropic client for summary call
        model: Model ID for summary
        transcript_dir: Directory to save transcripts
        memory: Optional MemoryStore to save summary to history.jsonl

    Returns:
        New condensed message list with summary
    """
    transcript_dir.mkdir(exist_ok=True)
    path = transcript_dir / f"transcript_{int(time.time())}.jsonl"

    # Save full transcript
    with open(path, "w", encoding='utf-8') as f:
        for msg in messages:
            f.write(json.dumps(msg, default=str, ensure_ascii=False) + "\n")

    # Extract recent context for summary
    conv_text = json.dumps(messages, default=str)[-80000:]

    # Request LLM summary
    resp = client.messages.create(
        model=model,
        messages=[{"role": "user", "content": f"Summarize for continuity:\n{conv_text}"}],
        max_tokens=2000,
    )
    summary = ""
    for block in resp.content:
        if hasattr(block, "text"):
            print(f"\033[33m[Compression Summary Block]\033[0m {block.text}")
            summary = block.text

    # Save to history.jsonl if memory provided
    if memory and summary:
        memory.append_history(summary)

    # Return condensed message
    return [
        {"role": "user", "content": f"[Compressed. Transcript: {path}]\n{summary}"},
    ]