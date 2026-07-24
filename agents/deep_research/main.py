from __future__ import annotations

from typing import Any

from agents import Agent, WebSearchTool


_context: Any = None


agent = Agent(
    name="DeepResearch",
    instructions="""
You are Deep Research Agent, a careful research assistant. Do all your thinking, research, note-keeping etc. in the same language, in which the user has started the dialog.

Method:
1. Given the topic, first plan the research as 3-5 concrete questions.
2. Create TODO items for the plan using the tool.
3. Search the web for each important question.
4. Save useful findings as notes with category, title, body, and URL when available.
5. Mark TODO items done as you complete them.
6. Finish with a concise structured report and cite sources.

Prefer clear summaries over long quotations.
""".strip(),
    tools=[WebSearchTool()],
)


def set_context(context: Any) -> None:
    global _context
    _context = context
    agent.tools = [
        WebSearchTool(),
        *context.notes_tools,
        *context.todo_tools,
    ]


def get_props() -> dict:
    return {
        "display_name": "Deep Research",
        "uses_notes": True,
        "uses_todo": True,
    }
