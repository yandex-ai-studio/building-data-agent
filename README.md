# Building Your Own Data Exploration Agent

This is a repository for my talk on Building Data Exploration Agent using Yandex AI Studio, Responses API and OpenAI Agents SDK.

The talk consists of three parts:

1. Learning how to work with LLM from Code using Responses API and OpenAI Agents SDK - open [AIStudio_Demo](notebooks/AIStudio_Demo.ipynb) and explore it.
[![Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/shwars/building-data-agent/blob/main/notebooks/AIStudio_Demo.ipynb)
2. Understanding Agentic Loop using the Concept Drawing Example - explore [VibeDraw](apps/vibedraw/README.md) Application to see how the loop helps to get the job done.
3. Switch to building text-based console coding agents using [ma](https://github.com/shwars/ma) shell. It allows you to talk to any agents created using OpenAI Agents SDK through pre-built text interface resembling Codex/Claude Code. A number of agents exploring different concepts is available in `agents` directory, and can be directly used from within `ma` environment.

> Source code of text-based interface is not included into this repository, but you can always find it [on GitHub](https://github.com/shwars/ma).

As a result, we would build an agent for data exploration, that will be able to:

1. Take any data files (XLSX/CSV) from current directory, explore them and upload into code interpreter for processing
2. Analyze those file using code interpreter, building derived artifacts, including graphs and simple ML models.
3. Download those artifacts back to the user's computer.

## Setting up MA

You would need to do the first-time setup of the `ma` console agent shell. The easiest way to do it is using [uv](https://docs.astral.sh/uv/) package manager:

1. Install `uv` ([instruction](https://docs.astral.sh/uv/getting-started/installation/)):
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```
2. Install `ma` ([instruction](https://github.com/shwars/ma#run-from-github)):
```bash
uv tool install git+https://github.com/shwars/ma
```
3. Clone this repository into some working directory:
```bash
git clone https://github.com/shwars/building-data-agent
cd ma-agent
```
`ma` will be able to work with agents located in `agents` subdirectory.
4. Set `folder_id` and `api_key` environment variables, or place `.env` file into the current directory that looks like this:
```
folder_id=...
api_key=...
```
5. Start `ma`:
```bash
ma
```
6. Use commands to select LLM and agent:
```
/model Deepseek V4 Flash
/agent
```
7. Start the dialog and enjoy!

## About the Talk

The talk based on this repository has been delivered at:

* [SMILES-2026](https://smiles.skoltech.ru/) Summer Workshop at Suzhou, China
