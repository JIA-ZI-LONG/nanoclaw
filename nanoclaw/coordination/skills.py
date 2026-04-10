#!/usr/bin/env python3
"""nanoclaw.coordination.skills - SKILL.md loading and management.

Source: s_full.py lines 199-225

skills_dir injected via constructor. Supports hierarchical skill directories.
SKILL.md format: YAML frontmatter + markdown body.
"""

import re
from pathlib import Path


class SkillLoader:
    """Load and manage skill definitions from SKILL.md files.

    Attributes:
        skills_dir: Root directory for skill files
        skills: Dict of {name: {meta: dict, body: str}}

    SKILL.md format:
        ---
        name: skill-name
        description: Brief description
        ---
        Skill content in markdown...
    """

    def __init__(self, skills_dir: Path):
        """Initialize with skills directory.

        Args:
            skills_dir: Directory to search for SKILL.md files
        """
        self.skills_dir = skills_dir
        self.skills: dict = {}

        if skills_dir.exists():
            self._load_all()

    def _load_all(self) -> None:
        """Recursively find and parse all SKILL.md files."""
        for f in sorted(self.skills_dir.rglob("SKILL.md")):
            text = f.read_text(encoding='utf-8')

            # Parse YAML frontmatter
            match = re.match(r"^---\n(.*?)\n---\n(.*)", text, re.DOTALL)
            meta, body = {}, text

            if match:
                for line in match.group(1).strip().splitlines():
                    if ":" in line:
                        key, value = line.split(":", 1)
                        meta[key.strip()] = value.strip()
                body = match.group(2).strip()

            # Use meta name or parent directory name
            name = meta.get("name", f.parent.name)
            self.skills[name] = {"meta": meta, "body": body}

    def descriptions(self) -> str:
        """Return formatted list of skill descriptions.

        Returns:
            Multi-line string of skill names and descriptions
        """
        if not self.skills:
            return "(no skills)"

        lines = [
            f"  - {name}: {skill['meta'].get('description', '-')}"
            for name, skill in self.skills.items()
        ]
        return "\n".join(lines)

    def load(self, name: str) -> str:
        """Load specific skill content.

        Args:
            name: Skill name to load

        Returns:
            XML-wrapped skill content, or error message
        """
        skill = self.skills.get(name)
        if not skill:
            available = ", ".join(self.skills.keys())
            return f"Error: Unknown skill '{name}'. Available: {available}"

        return f'<skill name="{name}">\n{skill["body"]}\n</skill>'