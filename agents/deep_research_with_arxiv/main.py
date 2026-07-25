from __future__ import annotations

from typing import Any

from agents import Agent, WebSearchTool, HostedMCPTool


_context: Any = None

arxiv_tool = HostedMCPTool(
    tool_config={
        "type": "mcp",
        "server_label" : "arXiv-Research",
        "server_url" : "https://db8smk1bt9b3didu862a.zfnhylrb.mcpgw.serverless.yandexcloud.net/sse",
        "server_description": "Search and retrieve research papers from arXiv.org",
        "require_approval": "never",
    }
)

agent = Agent(
    name="DeepResearchArxiv",
    instructions="""
You are Deep Research Agent, a careful research assistant. Do all your thinking, research, note-keeping etc. in the same language, in which the user has started the dialog.

Method:
1. Given the topic, first plan the research as 3-5 concrete questions.
2. Create TODO items for the plan using the tool.
3. Search the web for each important question using web search tool, and search for relevant research papers using the arXiv tool.
4. After each search, save useful findings as notes with category, title, body, and URL when available.
5. Mark TODO items done as you complete them.
6. Using the notes you have collected, write a concise structured report that summarizes your findings and cites sources.

Prefer clear summaries over long quotations.
""".strip(),
    tools=[WebSearchTool(), arxiv_tool],
)


def set_context(context: Any) -> None:
    global _context
    _context = context
    agent.tools = [
        WebSearchTool(),
        arxiv_tool,
        *context.notes_tools,
        *context.todo_tools,
    ]


def get_props() -> dict:
    return {
        "display_name": "Deep Research arXiv",
        "uses_notes": True,
        "uses_todo": True,
    }
