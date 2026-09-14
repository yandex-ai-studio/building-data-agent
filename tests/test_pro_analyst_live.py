from __future__ import annotations

import asyncio
import importlib.util
import os
from pathlib import Path
from types import ModuleType
from uuid import uuid4

import pytest
from agents import Agent, Runner, ShellTool, set_tracing_disabled
from agents.models.openai_responses import OpenAIResponsesModel
from dotenv import load_dotenv
from openai import AsyncOpenAI, OpenAI
from openai.types.responses import ResponseFunctionShellToolCall


REPO_ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = REPO_ROOT / "agents" / "pro_analyst"
BASE_URL = "https://ai.api.cloud.yandex.net/v1"


def load_skill_tools() -> ModuleType:
    path = AGENT_DIR / "skill_tools.py"
    spec = importlib.util.spec_from_file_location(
        f"test_live_skill_tools_{uuid4().hex}", path
    )
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def credentials() -> tuple[str, str]:
    load_dotenv(REPO_ROOT / ".env")
    folder_id = os.getenv("folder_id", "")
    api_key = os.getenv("api_key", "")
    if not folder_id or not api_key:
        pytest.skip("Yandex folder_id and api_key are not configured.")
    return folder_id, api_key


async def run_probe(
    folder_id: str,
    api_key: str,
    skill_reference: dict[str, str],
    skill_name: str,
) -> object:
    async_client = AsyncOpenAI(
        base_url=BASE_URL,
        api_key=api_key,
        project=folder_id,
    )
    try:
        qwen3_model = f"gpt://{folder_id}/qwen3-235b-a22b-fp8"
        model = OpenAIResponsesModel(
            model=qwen3_model,
            openai_client=async_client,
        )
        probe_agent = Agent(
            name="ProAnalystSkillProbe",
            model=model,
            instructions=(
                "Use the requested attached skill. Read its SKILL.md with Shell before answering. "
                "Use the exact skill path exposed in the Shell tool context instead of guessing it. "
                "If that read fails, locate the attached SKILL.md with find and try again."
            ),
            tools=[
                ShellTool(
                    environment={
                        "type": "container_auto",
                        "skills": [skill_reference],
                    }
                )
            ],
        )
        return await Runner.run(
            probe_agent,
            f"Use the {skill_name} skill and return its verification token exactly.",
            max_turns=6,
        )
    finally:
        await async_client.close()


def test_yandex_agent_reads_uploaded_skill(tmp_path: Path) -> None:
    folder_id, api_key = credentials()
    skill_tools = load_skill_tools()
    token = f"PRO_ANALYST_SKILL_{uuid4().hex}"
    skill_name = f"pro-analyst-integration-{uuid4().hex}"
    source = (AGENT_DIR / "skills" / "data_exploration" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    body = source.split("---", 2)[2].strip()
    skill_dir = tmp_path / "skills" / "probe"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        (
            f"---\nname: {skill_name}\n"
            "description: Return a private verification token when explicitly requested.\n"
            f"---\n\n{body}\n\n"
            "## Integration verification\n\n"
            f"When explicitly asked for the verification token, return `{token}` exactly.\n"
        ),
        encoding="utf-8",
    )

    set_tracing_disabled(True)
    client = OpenAI(base_url=BASE_URL, api_key=api_key, project=folder_id)
    skill_id: str | None = None
    try:
        references = skill_tools.sync_skills(client, skill_dir.parent)
        assert len(references) == 1
        skill_id = references[0]["skill_id"]

        results = []
        for _attempt in range(2):
            result = asyncio.run(
                run_probe(folder_id, api_key, references[0], skill_name)
            )
            results.append(result)
            if token in str(result.final_output):
                break

        outputs = "\n".join(str(result.final_output) for result in results)
        assert token in outputs
        assert any(
            isinstance(item, ResponseFunctionShellToolCall)
            for result in results
            for response in result.raw_responses
            for item in response.output
        )
    finally:
        if skill_id is not None:
            client.skills.delete(skill_id)
        client.close()
