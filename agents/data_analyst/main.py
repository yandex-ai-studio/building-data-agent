from __future__ import annotations

from typing import Any

from agents import Agent, CodeInterpreterTool

from filesystem_tools import configure, inspect, ls, upload

_context: Any = None
_container_id: str | None = None


agent = Agent(
    name="DataAnalyst",
    instructions="""
You are a careful data analyst.

Local files are available through filesystem tools:
- Use ls to discover files in the current working directory.
- Use inspect to understand CSV/XLS/XLSX files before analysis.
- Use upload to copy needed files into the Code Interpreter container.

Rules:
1. Always list and inspect relevant local files before doing analysis.
2. Upload all needed data files before data analysis or Code Interpreter use.
3. Do all computation, plotting, table generation, and file creation in Code Interpreter using the uploaded files.
4. Save useful outputs as files: charts, cleaned datasets, summaries, notebooks, or reports.
5. In your final answer, explicitly list every file you produced and return/link those files so ma can download them.
6. Explain assumptions, data quality issues, and limitations clearly.
""".strip(),
    tools=[ls, inspect],
)


def set_context(context: Any) -> None:
    global _context, _container_id
    _context = context

    if context.client is None:
        configure(root=None, client=None, container_id=None)
        agent.tools = [ls, inspect, *context.clarification_tools]
        context.log("Data Analyst needs Yandex folder_id/api_key to use Code Interpreter.")
        return

    container = context.client.containers.create(name="ma-data-analysis")
    _container_id = container.id
    configure(root=None, client=context.client, container_id=_container_id)

    if context.model is not None:
        agent.model = context.model

    agent.tools = [
        ls,
        inspect,
        upload,
        CodeInterpreterTool(tool_config={"type": "code_interpreter", "container": _container_id}),
        *context.clarification_tools,
    ]
    context.log(f"Data Analyst Code Interpreter container: {_container_id}")


def get_props() -> dict:
    props = {
        "display_name": "Data Analyst",
        "uses_notes": False,
        "uses_todo": False,
    }
    if _container_id:
        props["container_id"] = _container_id
    return props
