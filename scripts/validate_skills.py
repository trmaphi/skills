"""Validate public skill metadata and local Markdown links without executing tools."""

import ast
from pathlib import Path
import re
import sys

import yaml


def validate(root):
    errors = []
    skills = sorted(root.glob("*/SKILL.md"))
    if not skills:
        errors.append("No top-level skills found")
    for document in skills:
        try:
            text = document.read_text(encoding="utf-8")
            match = re.match(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|$)", text, re.S)
            if not match:
                raise ValueError("Missing YAML frontmatter")
            data = yaml.safe_load(match[1])
            name = data["name"]
            if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name) or len(name) > 64:
                raise ValueError("Invalid skill name")
            if name != document.parent.name:
                raise ValueError("Skill name must match its directory")
            description = data["description"]
            if not isinstance(description, str) or not 1 <= len(description) <= 1024:
                raise ValueError("Description must contain 1–1024 characters")
            metadata = yaml.safe_load((document.parent / "agents/openai.yaml").read_text(encoding="utf-8"))
            interface = metadata["interface"]
            if not isinstance(interface["display_name"], str) or not interface["display_name"].strip():
                raise ValueError("Missing display name")
            short = interface["short_description"]
            if not isinstance(short, str) or not 25 <= len(short) <= 64:
                raise ValueError("Short description must contain 25–64 characters")
            if not re.search(r"\$" + re.escape(name) + r"(?![\w-])", interface["default_prompt"]):
                raise ValueError("Default prompt must mention $skill-name")
        except (OSError, ValueError, TypeError, KeyError, yaml.YAMLError) as exc:
            errors.append(f"{document.relative_to(root)}: {exc}")
    for document in root.rglob("*.md"):
        if any(part.startswith(".") for part in document.relative_to(root).parts):
            continue
        for target in re.findall(r"\[[^\]]*\]\(([^\s)]+)\)", document.read_text(encoding="utf-8")):
            if re.match(r"[a-z]+:|#", target):
                continue
            if not (document.parent / target.split("#")[0]).exists():
                errors.append(f"{document.relative_to(root)}: broken link {target}")
    for script in root.rglob("*.py"):
        if any(part.startswith(".") for part in script.relative_to(root).parts):
            continue
        try:
            ast.parse(script.read_text(encoding="utf-8"), filename=str(script))
        except SyntaxError as exc:
            errors.append(str(exc))
    return skills, errors


if __name__ == "__main__":
    skills, errors = validate(Path(__file__).resolve().parents[1])
    if errors:
        print("\n".join(errors), file=sys.stderr)
        sys.exit(1)
    print(f"Validated {len(skills)} skill(s), metadata, local links and Python syntax")
