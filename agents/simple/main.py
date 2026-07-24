from agents import Agent, WebSearchTool


agent = Agent(
    name="Simple",
    instructions=(
        "You are a concise helpful assistant. Use web search when the user asks "
        "for current facts, links, or information that may have changed. Answer in the "
        "same language as the user has started the conversation in. Try to reason in "
        "the same language as well."
    ),
    tools=[WebSearchTool()],
)


def get_props() -> dict:
    return {
        "display_name": "Simple",
        "uses_notes": False,
        "uses_todo": False,
    }
