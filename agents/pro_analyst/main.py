from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any

from agents import Agent, CodeInterpreterTool

_context: Any = None
_container_id: str | None = None
_container_client: Any = None
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

configure_skills = _skill_tools.configure
list_skill_metadata = _skill_tools.list_skill_metadata
list_skills = _skill_tools.list_skills
load_skill = _skill_tools.load_skill


BASE_INSTRUCTIONS = """
You are Pro Analyst, an advanced local-data analyst and report-building agent.

You can work with local files, reusable markdown skills, safe command execution, and Code Interpreter.

Local data workflow:
1. Before exploring data, first review the Available skills snapshot already included in these instructions.
2. Use ls to discover relevant files in the current working directory.
3. Use inspect for CSV/XLS/XLSX files before analysis.
4. Use read_file when a text file, markdown file, script, or config matters.
5. Use write_file and edit_file only for files the user asked you to create or change.

Planning workflow:
1. For multi-step analysis, reporting, or deliverable work, create TODO items for the plan.
2. Mark TODO items done as steps are completed.
3. Use TODOs to keep long-running analysis visible to the user.

Skills workflow:
1. Skill metadata is loaded into the Available skills snapshot before each run/context update.
2. At the very start of every non-trivial analytical, reporting, document-generation, presentation, PDF, or data exploration request, review that snapshot before using ls, inspect, read_file, upload, or Code Interpreter.
3. Do not reload skill metadata during execution. Do not call list_skills unless the user explicitly asks to inspect available skills.
4. If a skill from the snapshot is relevant, call load_skill(skill_id) before following it.
5. If no skill applies, briefly proceed without one.
6. Treat skills as instructions, not executable plugins.
7. Current-directory skills override bundled skills at context-build time.

Code Interpreter workflow:
1. Always upload every local data file needed for analysis before running any Code Interpreter code that reads data.
2. Never analyze local data in Code Interpreter until the required files have been uploaded to the active container.
3. After upload, use the exact container_path returned by the upload tool in Code Interpreter Python code.
4. If a file is not found, list the Code Interpreter working directory before retrying instead of guessing paths.
5. Do computation, plotting, report generation, and rich file creation in Code Interpreter.
6. For PPTX/DOCX or other deliverables needing third-party packages, generate them in Code Interpreter and return the files.
7. Save useful outputs as files: charts, cleaned datasets, summaries, notebooks, PDFs, presentations, documents, or reports.
8. In your final answer, explicitly list every produced file so ma can download it.

Command workflow:
1. execute_command is available only for cmd, bash, and ssh.
2. Prefer Code Interpreter for analysis code.
3. Use local command execution only for existing utilities, lightweight checks, or workflows requested by a loaded skill.

Be careful, explain assumptions and data quality issues, and ask clarifying questions when the requested deliverable is underspecified.
""".strip()


def skill_metadata_snapshot() -> str:
    return f"""

Available skills snapshot:
{list_skill_metadata()}

Review this snapshot at the start of substantive analytical/reporting work before exploring data. Do not refresh skill metadata during execution. Call load_skill(skill_id) before applying a skill from the snapshot.
""".rstrip()


agent = Agent(
    name="ProAnalyst",
    instructions=BASE_INSTRUCTIONS,
    tools=[ls, inspect, read_file, list_skills, load_skill],
)


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
    configure_skills(root=Path.cwd(), agent_dir=_agent_dir)
    agent.instructions = BASE_INSTRUCTIONS + skill_metadata_snapshot()

    base_tools = [
        ls,
        inspect,
        read_file,
        write_file,
        edit_file,
        execute_command,
        list_skills,
        load_skill,
        *context.todo_tools,
        *context.clarification_tools,
    ]

    if context.client is None:
        configure_filesystem(root=Path.cwd(), client=None, container_id=None)
        agent.tools = base_tools
        context.log("Pro Analyst needs Yandex folder_id/api_key to use Code Interpreter.")
        return

    container_id = ensure_container(context)
    configure_filesystem(root=Path.cwd(), client=context.client, container_id=container_id)

    if context.model is not None:
        agent.model = context.model

    agent.tools = [
        *base_tools,
        upload,
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
