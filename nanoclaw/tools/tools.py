#!/usr/bin/env python3
"""nanoclaw.core.tools - File and shell operations with safety checks.

Source: s_full.py lines 75-121

All functions receive workdir as parameter (dependency injection pattern).
No global WORKDIR variable - enables reusable, testable operations.
"""

import subprocess
from pathlib import Path


def safe_path(p: str, workdir: Path) -> Path:
    """Validate path doesn't escape workspace.

    Args:
        p: Relative or absolute path string
        workdir: Base workspace directory

    Returns:
        Resolved absolute path within workdir

    Raises:
        ValueError: If path attempts to escape workspace
    """
    workdir = workdir.resolve()  # Ensure absolute
    path = (workdir / p).resolve()
    if not path.is_relative_to(workdir):
        raise ValueError(f"Path escapes workspace: {p}")
    return path


def run_bash(command: str, workdir: Path) -> str:
    """Execute shell command with safety checks.

    Blocks dangerous commands: rm -rf /, sudo, shutdown, reboot.
    Timeout: 120s, output truncated to 50000 chars.

    Args:
        command: Shell command to execute
        workdir: Working directory for execution

    Returns:
        Command output (stdout + stderr) or error message
    """
    dangerous = ["rm -rf /", "sudo", "shutdown", "reboot", "> /dev/"]
    if any(d in command for d in dangerous):
        return "Error: Dangerous command blocked"
    try:
        r = subprocess.run(
            command, shell=True, cwd=workdir,
            capture_output=True, text=True, timeout=120,
            encoding='utf-8', errors='replace'
        )
        out = (r.stdout + r.stderr).strip()
        return out[:50000] if out else "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: Timeout (120s)"


def run_read(path: str, workdir: Path, limit: int = None) -> str:
    """Read file contents with optional line limit.

    Args:
        path: File path (relative to workdir)
        workdir: Base workspace directory
        limit: Maximum lines to read (None = all)

    Returns:
        File contents (truncated to 50000 chars) or error message
    """
    try:
        lines = safe_path(path, workdir).read_text(encoding='utf-8').splitlines()
        if limit and limit < len(lines):
            lines = lines[:limit] + [f"... ({len(lines) - limit} more)"]
        return "\n".join(lines)[:50000]
    except Exception as e:
        return f"Error: {e}"


def run_write(path: str, content: str, workdir: Path) -> str:
    """Write content to file, creating parent dirs if needed.

    Args:
        path: File path (relative to workdir)
        content: Content to write
        workdir: Base workspace directory

    Returns:
        Success message with bytes written, or error message
    """
    try:
        fp = safe_path(path, workdir)
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content, encoding='utf-8')
        return f"Wrote {len(content)} bytes to {path}"
    except Exception as e:
        return f"Error: {e}"


def run_edit(path: str, old_text: str, new_text: str, workdir: Path) -> str:
    """Replace exact text in file (single replacement).

    Args:
        path: File path (relative to workdir)
        old_text: Text to find and replace
        new_text: Replacement text
        workdir: Base workspace directory

    Returns:
        Success message or error message
    """
    try:
        fp = safe_path(path, workdir)
        content = fp.read_text(encoding='utf-8')
        if old_text not in content:
            return f"Error: Text not found in {path}"
        fp.write_text(content.replace(old_text, new_text, 1), encoding='utf-8')
        return f"Edited {path}"
    except Exception as e:
        return f"Error: {e}"