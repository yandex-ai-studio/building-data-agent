from __future__ import annotations

import importlib.util
from io import BytesIO
from pathlib import Path
from types import ModuleType, SimpleNamespace
from uuid import uuid4
from zipfile import ZipFile

import pytest
from agents import CodeInterpreterTool, ShellTool


REPO_ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = REPO_ROOT / "agents" / "pro_analyst"


def load_module(path: Path) -> ModuleType:
    name = f"test_{path.stem}_{uuid4().hex}"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_skill(skill_dir: Path, name: str, body: str = "Follow these instructions.") -> None:
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: Test skill {name}.\n---\n\n{body}\n",
        encoding="utf-8",
    )


def uploaded_archive(
    files: list[tuple[str, BytesIO, str]],
) -> tuple[str, bytes, str]:
    assert len(files) == 1
    filename, stream, content_type = files[0]
    return filename, stream.getvalue(), content_type


class FakeVersions:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def create(
        self,
        skill_id: str,
        *,
        default: bool,
        files: list[tuple[str, BytesIO, str]],
    ) -> SimpleNamespace:
        self.calls.append(
            {
                "skill_id": skill_id,
                "default": default,
                "archive": uploaded_archive(files),
            }
        )
        return SimpleNamespace(version="7")


class FakeSkills:
    def __init__(self, existing: list[SimpleNamespace] | None = None) -> None:
        self.existing = existing or []
        self.list_kwargs: dict[str, object] | None = None
        self.create_calls: list[tuple[str, bytes, str]] = []
        self.versions = FakeVersions()

    def list(self, **kwargs: object) -> list[SimpleNamespace]:
        self.list_kwargs = kwargs
        return self.existing

    def create(self, *, files: list[tuple[str, BytesIO, str]]) -> SimpleNamespace:
        self.create_calls.append(uploaded_archive(files))
        return SimpleNamespace(
            id=f"created-{len(self.create_calls)}",
            default_version="1",
        )


def test_discover_skills_builds_ordered_archives(tmp_path: Path) -> None:
    skill_tools = load_module(AGENT_DIR / "skill_tools.py")
    skills_dir = tmp_path / "skills"
    write_skill(skills_dir / "zeta", "pro-analyst-zeta")
    write_skill(skills_dir / "alpha", "pro-analyst-alpha")
    nested = skills_dir / "alpha" / "references"
    nested.mkdir()
    (nested / "guide.txt").write_text("guide", encoding="utf-8")

    bundles = skill_tools.discover_skills(skills_dir)

    assert [bundle.directory.name for bundle in bundles] == ["alpha", "zeta"]
    assert [bundle.name for bundle in bundles] == [
        "pro-analyst-alpha",
        "pro-analyst-zeta",
    ]
    with ZipFile(BytesIO(bundles[0].archive)) as archive:
        assert archive.namelist() == [
            "alpha/SKILL.md",
            "alpha/references/guide.txt",
        ]


def test_discover_skills_validates_manifests_and_names(tmp_path: Path) -> None:
    skill_tools = load_module(AGENT_DIR / "skill_tools.py")
    missing_manifest = tmp_path / "missing" / "empty"
    missing_manifest.mkdir(parents=True)

    with pytest.raises(ValueError, match="exactly one top-level SKILL.md"):
        skill_tools.discover_skills(missing_manifest.parent)

    multiple_root = tmp_path / "multiple"
    write_skill(multiple_root / "skill", "pro-analyst-multiple")
    nested = multiple_root / "skill" / "references"
    nested.mkdir()
    (nested / "skill.md").write_text("extra", encoding="utf-8")
    with pytest.raises(ValueError, match="found 2"):
        skill_tools.discover_skills(multiple_root)

    duplicate_root = tmp_path / "duplicates"
    write_skill(duplicate_root / "first", "pro-analyst-duplicate")
    write_skill(duplicate_root / "second", "pro-analyst-duplicate")
    with pytest.raises(ValueError, match="Duplicate local skill names"):
        skill_tools.discover_skills(duplicate_root)


def test_production_skills_use_stable_cloud_names() -> None:
    skill_tools = load_module(AGENT_DIR / "skill_tools.py")

    bundles = skill_tools.discover_skills(AGENT_DIR / "skills")

    assert [bundle.name for bundle in bundles] == [
        "pro-analyst-data-exploration",
        "pro-analyst-docx-document",
        "pro-analyst-markdown-to-pdf",
        "pro-analyst-pptx-presentation",
    ]
    assert all((bundle.directory / "SKILL.md").is_file() for bundle in bundles)


def test_sync_skills_creates_and_versions_cloud_resources(tmp_path: Path) -> None:
    skill_tools = load_module(AGENT_DIR / "skill_tools.py")
    skills_dir = tmp_path / "skills"
    write_skill(skills_dir / "existing", "pro-analyst-existing")
    write_skill(skills_dir / "new", "pro-analyst-new")
    cloud_skills = FakeSkills(
        [SimpleNamespace(name="pro-analyst-existing", id="existing-id")]
    )
    client = SimpleNamespace(skills=cloud_skills)

    references = skill_tools.sync_skills(client, skills_dir)

    assert cloud_skills.list_kwargs == {"order": "desc", "limit": 100}
    assert references == [
        {
            "type": "skill_reference",
            "skill_id": "existing-id",
            "version": "7",
        },
        {
            "type": "skill_reference",
            "skill_id": "created-1",
            "version": "1",
        },
    ]
    assert len(cloud_skills.create_calls) == 1
    assert cloud_skills.create_calls[0][0] == "new.zip"
    assert cloud_skills.create_calls[0][2] == "application/zip"
    assert cloud_skills.versions.calls[0]["skill_id"] == "existing-id"
    assert cloud_skills.versions.calls[0]["default"] is True


class FakeContainers:
    def __init__(self) -> None:
        self.create_calls = 0

    def create(self, *, name: str) -> SimpleNamespace:
        assert name == "ma-pro-analysis"
        self.create_calls += 1
        return SimpleNamespace(id="container-test")


def context(client: object | None, logs: list[str]) -> SimpleNamespace:
    return SimpleNamespace(
        client=client,
        todo_tools=[],
        clarification_tools=[],
        log=logs.append,
    )


def test_set_context_caches_skills_and_attaches_shell() -> None:
    main = load_module(AGENT_DIR / "main.py")
    references = [
        {
            "type": "skill_reference",
            "skill_id": "skill-test",
            "version": "3",
        }
    ]
    sync_calls: list[tuple[object, Path]] = []

    def fake_sync(client: object, skills_dir: Path) -> list[dict[str, str]]:
        sync_calls.append((client, skills_dir))
        return references

    main.sync_skills = fake_sync
    containers = FakeContainers()
    client = SimpleNamespace(containers=containers)
    logs: list[str] = []
    agent_context = context(client, logs)

    main.set_context(agent_context)
    main.set_context(agent_context)

    other_containers = FakeContainers()
    other_client = SimpleNamespace(containers=other_containers)
    main.set_context(context(other_client, logs))
    main.set_context(agent_context)

    assert [call[0] for call in sync_calls] == [client, other_client]
    assert containers.create_calls == 2
    assert other_containers.create_calls == 1
    shell_tools = [tool for tool in main.agent.tools if isinstance(tool, ShellTool)]
    assert len(shell_tools) == 1
    assert shell_tools[0].environment == {
        "type": "container_auto",
        "skills": references,
    }
    assert sum(isinstance(tool, CodeInterpreterTool) for tool in main.agent.tools) == 1
    tool_names = {getattr(tool, "name", "") for tool in main.agent.tools}
    assert "list_skills" not in tool_names
    assert "load_skill" not in tool_names
    assert "Available skills snapshot" not in main.agent.instructions
    assert "Pro Analyst synced 1 cloud skills." in logs


def test_set_context_without_credentials_uses_only_local_tools() -> None:
    main = load_module(AGENT_DIR / "main.py")
    logs: list[str] = []

    main.set_context(context(None, logs))

    assert not any(isinstance(tool, ShellTool) for tool in main.agent.tools)
    assert not any(isinstance(tool, CodeInterpreterTool) for tool in main.agent.tools)
    assert main.get_container_id() is None
    assert any("cloud Skills, Shell, and Code Interpreter" in message for message in logs)
