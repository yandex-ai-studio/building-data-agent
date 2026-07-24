from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from agents import function_tool

_root = Path.cwd()
_agent_dir = Path(__file__).resolve().parent
_SAFE_SKILL_ID = re.compile(r"^[A-Za-z0-9_.-]+$")


def configure(root: Path | str | None = None, agent_dir: Path | str | None = None) -> None:
    global _root, _agent_dir
    if root is not None:
        _root = Path(root).resolve()
    if agent_dir is not None:
        _agent_dir = Path(agent_dir).resolve()


def _check_skill_id(skill_id: str) -> None:
    if not _SAFE_SKILL_ID.match(skill_id):
        raise ValueError(f"Unsafe skill id: {skill_id}")


def _parse_scalar(value: str) -> Any:
    value = value.strip()
    if value.startswith("[") and value.endswith("]"):
        items = value[1:-1].strip()
        if not items:
            return []
        return [item.strip().strip("'\"") for item in items.split(",")]
    return value.strip("'\"")


def _parse_skill_file(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    metadata: dict[str, Any] = {}
    body = text
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) == 3:
            _, frontmatter, body = parts
            for line in frontmatter.splitlines():
                if not line.strip() or line.lstrip().startswith("#") or ":" not in line:
                    continue
                key, value = line.split(":", 1)
                metadata[key.strip()] = _parse_scalar(value)

    skill_id = str(metadata.get("id") or path.parent.name)
    _check_skill_id(skill_id)
    metadata.setdefault("id", skill_id)
    metadata.setdefault("name", skill_id.replace("_", " ").replace("-", " ").title())
    metadata.setdefault("description", "")
    metadata.setdefault("tags", [])
    return {"metadata": metadata, "instructions": body.strip(), "path": path}


def _candidate_files(base: Path) -> list[Path]:
    candidates: list[Path] = []
    skills_dir = base / "skills"
    if skills_dir.is_dir():
        candidates.extend(sorted(skills_dir.glob("*/skill.md")))
    candidates.extend(sorted(path for path in base.glob("*/skill.md") if path.parent.name != "skills"))
    return candidates


def _discover() -> dict[str, dict[str, Any]]:
    skills: dict[str, dict[str, Any]] = {}
    for base, location in [(_agent_dir, "agent"), (_root, "current")]:
        for path in _candidate_files(base):
            parsed = _parse_skill_file(path)
            metadata = dict(parsed["metadata"])
            metadata["location"] = location
            metadata["path"] = str(path)
            skills[str(metadata["id"])] = {
                "metadata": metadata,
                "instructions": parsed["instructions"],
            }
    return skills


def list_skill_metadata() -> str:
    skills = _discover()
    items = [
        {
            "id": skill["metadata"]["id"],
            "name": skill["metadata"]["name"],
            "description": skill["metadata"].get("description", ""),
            "tags": skill["metadata"].get("tags", []),
            "location": skill["metadata"].get("location", ""),
        }
        for skill in skills.values()
    ]
    items.sort(key=lambda item: item["id"])
    return json.dumps({"skills": items}, ensure_ascii=False)


def load_skill_instructions(skill_id: str) -> str:
    _check_skill_id(skill_id)
    skills = _discover()
    if skill_id not in skills:
        return f"No skill found: {skill_id}"
    skill = skills[skill_id]
    return json.dumps(
        {
            "metadata": skill["metadata"],
            "instructions": skill["instructions"],
        },
        ensure_ascii=False,
    )


@function_tool
def list_skills() -> str:
    """List available skills from the current directory and the Pro Analyst agent folder."""
    return list_skill_metadata()


@function_tool
def load_skill(skill_id: str) -> str:
    """Load full instructions for one skill by skill id."""
    return load_skill_instructions(skill_id)
