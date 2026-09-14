# Agentic TUI

We need to design and build educational reference implementation of text interactive shell (TUI) for learning how coding agents are built based on OpenAI Agents SDK in Yandex Cloud. This console application is similar to OpenCode, Codex, Claude Code, etc., and it allows to chat with different agents.

Agents are implemented as Python packages inside `agents` directory. Each agent has his own directory, and exposes one main OpenAI Agents SDK `Agent` implementation which is used for chatting. Agents should be dynamically loaded by the shell, eg. if new agent is added or code is modified - it should be easily re-loaded by using /reload command.

The application should allow main text-based streaming chat with current agent. Streaming should ideally support main markdown formatting, including bold, italic, headers, tables formatting "on the fly". It should also support displaying main events: reasoning, tool calls, internal tool calls (eg. web search, file search, etc.), MCP calls, etc. All those categories should be nicely color-coded.

The following main commands should be supported:
/agent - select agent (separate dropdown displaying agents should be provided)
/model - select model (from a section in config.json)
/reload - reload agents from disk

config.json sets the overall configuration:
- folder_id
- api_key
- list of available models

Also, the shell provides two tools that agents can use if they want:
- `notes` tool that supports creating notes with the fields `cateogory`, `title`, `body`. The tool exposes list of function tools: create_note, clear_notes, list_notes (by category, by title search, or all). Ideally notes should also support additional user-defined fields such as url, etc.
- `todo` tool that supports creating TODO lists. It provides functions to create todo item (in arbitrary position), mark item as done, get next item.

Each agent implemented inside `agents` directory receives context object from TUI application, which includes those tools (each one is a list of tool functions), selected model, folder_id and api_key. It should also indicate if it uses todo or notes tools or not. Please look into `agents` directory to see how agents are using this functionality.

If the current agent uses todo or notes tools or both, those tools should be displayed on the right pane during chat dialog, and should be updated in realtime to reflect agent's state.

## Implementation Details

- This implementation is educational, so the code should always prefer simplicity over complexity. It should not check for all possible cases of errors, rather preferring simple logic and some possible run-time errors than checking for all cases and avoiding problems.
- Everything should be implemented in Python
- Look for some nice UI library to build text-based UI with colors and tables
