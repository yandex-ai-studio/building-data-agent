from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any

from agents import Agent, CodeInterpreterTool, ShellTool

_context: Any = None
_container_id: str | None = None
_container_client: Any = None
_skill_cache: dict[int, tuple[Any, list[dict[str, str]]]] = {}
_agent_dir = Path(__file__).resolve().parent


def _load_local_module(name: str) -> ModuleType:
    path = _agent_dir / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"pro_analyst_{name}", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_filesystem_tools = _load_local_module("filesystem_tools")
_skill_tools = _load_local_module("skill_tools")

configure_filesystem = _filesystem_tools.configure
ls = _filesystem_tools.ls
inspect = _filesystem_tools.inspect
upload = _filesystem_tools.upload
read_file = _filesystem_tools.read_file
write_file = _filesystem_tools.write_file
edit_file = _filesystem_tools.edit_file
execute_command = _filesystem_tools.execute_command

sync_skills = _skill_tools.sync_skills


BASE_INSTRUCTIONS = """
You are Pro Analyst, an advanced local-data analyst and report-building agent.
In your response, use the same language that the user has used in his original query.

You can work with local files, cloud-hosted reusable skills, safe command execution, and Code Interpreter.

Local data workflow:
1. Before substantive work, review the skill names and descriptions exposed by the hosted Shell tool when it is available.
2. Use ls to discover relevant files in the current working directory.
3. Use inspect for CSV/XLS/XLSX files before analysis.
4. Use read_file when a text file, markdown file, script, or config matters.
5. Use write_file and edit_file only for files the user asked you to create or change.

Planning workflow:
1. For multi-step analysis, reporting, or deliverable work, create TODO items for the plan.
2. Mark TODO items done as steps are completed.
3. Use TODOs to keep long-running analysis visible to the user.

Skills workflow:
1. Skills are attached to the hosted Shell tool by Yandex AI Studio.
2. At the start of analytical, reporting, document-generation, presentation, PDF, or data exploration work, review the available skill metadata.
3. If a skill applies, use Shell to open its SKILL.md before following its workflow.
4. Treat SKILL.md as instructions. Use skill-provided scripts and resources inside the Shell container when needed.
5. The Shell container is separate from the local working directory and the Code Interpreter container. Use local tools for current-directory files and Code Interpreter for uploaded data and generated artifacts.
6. If no skill applies or Shell is unavailable, proceed with the other available tools.

Code Interpreter workflow:
1. Always upload every local data file needed for analysis before running any Code Interpreter code that reads data using upload tool.
2. Never analyze local data in Code Interpreter until the required files have been uploaded to the active container.
3. After upload, use the exact container_path returned by the upload tool in Code Interpreter Python code.
4. If a file is not found, list the Code Interpreter working directory before retrying instead of guessing paths.
5. Do computation, plotting, report generation, and rich file creation in Code Interpreter.
6. For PPTX/DOCX or other deliverables needing third-party packages, generate them in Code Interpreter and return the files.
7. Save useful outputs as files: charts, cleaned datasets, summaries, notebooks, PDFs, presentations, documents, or reports.
8. In your final answer, explicitly list every produced file so we can download it as part of the result.

Command workflow:
1. execute_command is available only for cmd, bash, and ssh.
2. Use Code Interpreter for analysis code.
3. Use local command execution only for existing utilities, lightweight checks, or workflows requested by a cloud skill.

Be careful, explain assumptions and data quality issues, and ask clarifying questions when the requested deliverable is underspecified.
""".strip()


agent = Agent(
    name="ProAnalyst",
    instructions=BASE_INSTRUCTIONS,
    tools=[ls, inspect, read_file],
)


def ensure_skill_references(context: Any) -> list[dict[str, str]]:
    if context.client is None:
        return []

    cache_key = id(context.client)
    cached = _skill_cache.get(cache_key)
    if cached is not None and cached[0] is context.client:
        return list(cached[1])

    references = sync_skills(context.client, _agent_dir / "skills")
    _skill_cache[cache_key] = (context.client, references)
    context.log(f"Pro Analyst synced {len(references)} cloud skills.")
    return list(references)


def ensure_container(context: Any) -> str | None:
    global _container_id, _container_client
    if context.client is None:
        _container_id = None
        _container_client = None
        return None
    if _container_id is None or _container_client is not context.client:
        container = context.client.containers.create(name="ma-pro-analysis")
        _container_id = container.id
        _container_client = context.client
        context.log(f"Pro Analyst Code Interpreter container: {_container_id}")
    return _container_id


def set_context(context: Any) -> None:
    global _context
    _context = context
    context.log("Calling set_context")
    agent.instructions = BASE_INSTRUCTIONS

    base_tools = [
        ls,
        inspect,
        read_file,
        write_file,
        edit_file,
        execute_command,
        *context.todo_tools,
        *context.clarification_tools,
    ]

    if context.client is None:
        ensure_skill_references(context)
        ensure_container(context)
        configure_filesystem(root=Path.cwd(), client=None, container_id=None)
        agent.tools = base_tools
        context.log(
            "Pro Analyst needs Yandex folder_id/api_key to use cloud Skills, Shell, and Code Interpreter."
        )
        return

    skill_references = ensure_skill_references(context)
    container_id = ensure_container(context)
    configure_filesystem(root=Path.cwd(), client=context.client, container_id=container_id)

    agent.tools = [
        *base_tools,
        upload,
        ShellTool(
            environment={
                "type": "container_auto",
                "skills": skill_references,
            }
        ),
        CodeInterpreterTool(tool_config={"type": "code_interpreter", "container": container_id}),
    ]


def get_props() -> dict:
    props = {
        "display_name": "Pro Analyst",
        "uses_notes": False,
        "uses_todo": True,
    }
    if _container_id:
        props["container_id"] = _container_id
    return props


def get_container_id() -> str | None:
    return _container_id
