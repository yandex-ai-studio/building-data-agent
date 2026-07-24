from agents import Agent, HostedMCPTool, CodeInterpreterTool
import os

instructions = f"""
You are data exploration agent that can perform research on different topics using publicly available Kaggle datasets. To get access to the datasets, use Kaggle MCP tools to find appropriate datasets to explore. Once you find the datasets, you can use Code Interpreter to download and analyze them via kaggle library. Use the following kaggle token: {os.environ.get("kaggle_token")}.

You can also use TODO and clarification tools to plan your research and ask questions to the user.

Once you get a request from the user, do the following:

1. Plan the research. Store your plan in TODO tools, and mark items as completed during execution.
2. Use Kaggle MCP to look for appropriate datasets. You can also add more TODO items once you know available data better.
3. In case of ambiguity, you can ask the user clarifying questions through the corresponding clarification tool.
4. When the anticipated datasets are listed, use Code Interpreter to download the data and analyze it. First, install all necessary libraries on the Code Interpreter, including requests, pandas, pyarrow, boto3, kaggle hub and others.
5. At the end, do the research and produce some output graphs that can clarify user's question.
6. If there is not enough data to answer the question, feel free to come back to use MCP to find more datasets and experiement with them, until a good result is achieved.
"""

_container_id = None

mcp_tool_config = {
    "type": "mcp",
    "server_label": "Kaggle MCP",
    "server_description": "Search for Kaggle datasets",
    "server_url": "https://db83o80jtkkcinuhvmh1.58zke0qh.mcpgw.serverless.yandexcloud.net/sse",
    "require_approval": "never"
}

mcp_tool = HostedMCPTool(tool_config=mcp_tool_config)

agent = Agent(
    name="Kaggle-Agent",
    instructions=instructions,
)

def set_context(context: Any) -> None:
    global _context, _container_id
    _context = context
    container = context.client.containers.create(name="econdata-analysis")
    _container_id = container.id

    if context.model is not None:
        agent.model = context.model

    context.log(f"Kaggle Code Interpreter container: {_container_id}")

    agent.tools = [
        mcp_tool,
        CodeInterpreterTool(tool_config={"type": "code_interpreter", "container": _container_id}),
        *context.todo_tools,
        *context.clarification_tools
    ]

def get_props() -> dict:
    return {
        "display_name": "Kaggle MCP",
        "uses_notes": False,
        "uses_todo": True,
        "container_id" : _container_id
    }
