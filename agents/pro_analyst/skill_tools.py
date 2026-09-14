from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile


class SkillBundle:
    def __init__(self, directory: Path, name: str, archive: bytes) -> None:
        self.directory = directory
        self.name = name
        self.archive = archive

    def upload_files(self) -> list[tuple[str, BytesIO, str]]:
        return [
            (
                f"{self.directory.name}.zip",
                BytesIO(self.archive),
                "application/zip",
            )
        ]


def _manifest_path(skill_dir: Path) -> Path:
    manifests = [
        path
        for path in skill_dir.rglob("*")
        if path.is_file() and path.name.lower() == "skill.md"
    ]
    if len(manifests) != 1 or manifests[0].parent != skill_dir:
        raise ValueError(
            f"{skill_dir} must contain exactly one top-level SKILL.md; "
            f"found {len(manifests)}."
        )
    return manifests[0]


def _skill_name(manifest: Path) -> str:
    text = manifest.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise ValueError(f"{manifest} must start with YAML frontmatter.")

    parts = text.split("---", 2)
    if len(parts) != 3:
        raise ValueError(f"{manifest} has incomplete YAML frontmatter.")

    metadata: dict[str, str] = {}
    for line in parts[1].splitlines():
        if not line.strip() or line.lstrip().startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip().strip("'\"")

    name = metadata.get("name", "")
    description = metadata.get("description", "")
    if not name or not description:
        raise ValueError(f"{manifest} must define non-empty name and description fields.")
    return name


def _build_archive(skill_dir: Path) -> bytes:
    files = sorted(
        (path for path in skill_dir.rglob("*") if path.is_file()),
        key=lambda path: path.relative_to(skill_dir).as_posix(),
    )
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        for path in files:
            relative = path.relative_to(skill_dir)
            archive.write(path, (Path(skill_dir.name) / relative).as_posix())
    return buffer.getvalue()


def discover_skills(skills_dir: Path | str) -> list[SkillBundle]:
    root = Path(skills_dir).resolve()
    if not root.is_dir():
        raise ValueError(f"Skills directory does not exist: {root}")

    skill_dirs = sorted(
        (path for path in root.iterdir() if path.is_dir()),
        key=lambda path: path.name,
    )
    if not skill_dirs:
        raise ValueError(f"No skill directories found in {root}")

    bundles = [
        SkillBundle(
            directory=skill_dir,
            name=_skill_name(_manifest_path(skill_dir)),
            archive=_build_archive(skill_dir),
        )
        for skill_dir in skill_dirs
    ]

    names = [bundle.name for bundle in bundles]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        raise ValueError(f"Duplicate local skill names: {', '.join(duplicates)}")
    return bundles


def sync_skills(client: Any, skills_dir: Path | str) -> list[dict[str, str]]:
    bundles = discover_skills(skills_dir)
    existing_by_name: dict[str, Any] = {}
    for skill in client.skills.list(order="desc", limit=100):
        existing_by_name.setdefault(str(skill.name), skill)

    references: list[dict[str, str]] = []
    for bundle in bundles:
        existing = existing_by_name.get(bundle.name)
        try:
            if existing is None:
                uploaded = client.skills.create(files=bundle.upload_files())
                skill_id = str(uploaded.id)
                version = str(uploaded.default_version)
            else:
                uploaded = client.skills.versions.create(
                    str(existing.id),
                    default=True,
                    files=bundle.upload_files(),
                )
                skill_id = str(existing.id)
                version = str(uploaded.version)
        except Exception as error:
            raise RuntimeError(
                f"Failed to upload cloud skill {bundle.name}: {error}"
            ) from error

        references.append(
            {
                "type": "skill_reference",
                "skill_id": skill_id,
                "version": version,
            }
        )
    return references
