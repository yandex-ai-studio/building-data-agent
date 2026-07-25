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

summary_writer = Agent(
    name = "SummaryWriter",
    instructions = """
You are a summary writer agent. You will receive notes and TODO items from the Deep Research Agent. Your task is to write a concise structured report that summarizes the findings and cites sources. Use the notes and TODO items provided to you by the Deep Research Agent to create a comprehensive report. Ensure that the report is well-organized, clear, and provides a thorough summary of the research conducted. Do not conduct any research yourself, only use the information provided to you by the Deep Research Agent. Your report should be in the same language as the user has started the conversation in. Try to reason in the same language as well.
""".strip()
)

researcher = Agent(
    name="ResearcherAgent",
    instructions="""
You are Deep Research Agent, a careful research assistant. You need to research ALL items in the TODO list you are provided with, if they are not marked as complete. ONLY when all items in TODO list are complete you can handoff conversation to SummaryWriter agent.

Method:
1. Take the first topic to research from TODO list.
2. Search the web on this topic using web search tool, and search for relevant research papers using the arXiv tool.
3. After each search, save useful findings as notes with category, title, body, and URL when available.
4. Mark the research topic as complete in TODO list. 
5. If there are still items left in TODO list - proceed from step 1
6. When you finish your research, handoff the notes to Summary Writer agent.
7. NEVER stop and go back to the dialog with the user: either proceed with research, or do the handoff to summary writer.
""".strip(),
    handoffs = [summary_writer],
)

agent = Agent(
    name="PlannerAgent",
    instructions="""
You are Deep Research Planner Agent. You are given a topic, and you need to break it down into several smaller subtopics.

If there are topics in TODO list, or the user just asks to proceed - ALWAYS IMMEDIATELY handoff the conversation to researcher agent.

If needed, do some web search to understand the topic better, or do the search for academic publications in arXiv.

Please store each subtopic as TODO item using TODO tool, and then handoff to researcher agent. Store all TODO items in the same language that the user has used to address you in the first place. If anything is not clear - please ask questions back to the user using clarification tool.
""".strip(),
    handoffs = [researcher],
)


def set_context(context: Any) -> None:
    global _context
    _context = context
    summary_writer.tools = [
        *context.notes_tools
    ]
    researcher.tools = [
        WebSearchTool(),
        arxiv_tool,
        *context.todo_tools,
        *context.notes_tools
    ]
    agent.tools = [
        WebSearchTool(),
        arxiv_tool,
        *context.todo_tools,
        *context.clarification_tools
    ]

def get_props() -> dict:
    return {
        "display_name": "Deep Research Multiagent",
        "uses_notes": True,
        "uses_todo": True,
        "max_turns": 30,
    }
