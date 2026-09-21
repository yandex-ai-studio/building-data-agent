from __future__ import annotations

import asyncio
import importlib.util
import json
import os
from pathlib import Path
from types import ModuleType, SimpleNamespace
from uuid import uuid4

import pytest
from agents import ModelSettings, RunConfig, Runner, set_tracing_disabled
from agents.models.openai_responses import OpenAIResponsesModel
from dotenv import load_dotenv
from openai import AsyncOpenAI, OpenAI


REPO_ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = REPO_ROOT / "agents" / "pro_analyst_manual_skills"
GDP_DIR = REPO_ROOT / "outputs" / "gdp"
BASE_URL = "https://ai.api.cloud.yandex.net/v1"


def load_module(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        f"test_pro_analyst_manual_{path.stem}_{uuid4().hex}",
        path,
    )
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeContainerFiles:
    def create(self, *, container_id: str, file: object) -> SimpleNamespace:
        assert container_id == "container-test"
        assert file.readline() == b"Country Name,Country Code,Year,Value\n"
        return SimpleNamespace(
            id="file-test",
            container_id=container_id,
            path="./mounted.csv",
            bytes=562767,
        )


def credentials() -> tuple[str, str]:
    load_dotenv(REPO_ROOT / ".env")
    folder_id = os.getenv("folder_id", "")
    api_key = os.getenv("api_key", "")
    if not folder_id or not api_key:
        pytest.skip("Yandex folder_id and api_key are not configured.")
    return folder_id, api_key


def test_upload_reports_server_container_path() -> None:
    filesystem_tools = load_module(AGENT_DIR / "filesystem_tools.py")
    client = SimpleNamespace(
        containers=SimpleNamespace(files=FakeContainerFiles()),
    )
    filesystem_tools.configure(
        root=GDP_DIR,
        client=client,
        container_id="container-test",
    )

    result = json.loads(filesystem_tools.upload_files(["gdp.csv"]))

    assert result == {
        "files": [
            {
                "name": "gdp.csv",
                "id": "file-test",
                "container_id": "container-test",
                "container_path": "./mounted.csv",
                "bytes": 562767,
            }
        ],
        "code_interpreter_note": (
            "Use each file's container_path exactly in Code Interpreter Python code. "
            "Do not assume the local filename is the container path."
        ),
    }


def test_agent_reads_file_uploaded_after_empty_container(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    folder_id, api_key = credentials()
    monkeypatch.chdir(GDP_DIR)
    main = load_module(AGENT_DIR / "main.py")
    set_tracing_disabled(True)

    async def run_probe() -> None:
        client = OpenAI(
            base_url=BASE_URL,
            api_key=api_key,
            project=folder_id,
        )
        async_client = AsyncOpenAI(
            base_url=BASE_URL,
            api_key=api_key,
            project=folder_id,
        )
        qwen3_model = f"gpt://{folder_id}/qwen3-235b-a22b-fp8"
        model = OpenAIResponsesModel(
            model=qwen3_model,
            openai_client=async_client,
        )
        container_id: str | None = None

        try:
            main.set_context(
                SimpleNamespace(
                    client=client,
                    model=model,
                    todo_tools=[],
                    clarification_tools=[],
                    log=lambda _message: None,
                )
            )
            container_id = main.get_container_id()
            assert container_id is not None
            initial_files = client.containers.files.list(
                container_id=container_id,
                limit=100,
            )
            assert list(initial_files.data) == []

            result = await Runner.run(
                main.agent,
                (
                    "This is a focused file-visibility test. Review the skills snapshot and "
                    "load the relevant data exploration skill. Then list and inspect gdp.csv, "
                    "upload it exactly once, and use Code Interpreter to read the exact "
                    "container_path returned by upload. Print exactly "
                    "FILE_VISIBLE rows=<row count> columns=<comma-separated column names>."
                ),
                max_turns=12,
                run_config=RunConfig(
                    model=model,
                    model_settings=ModelSettings(reasoning={"effort": "low"}),
                ),
            )

            upload_payloads: list[dict[str, object]] = []
            interpreter_calls: list[object] = []
            for item in result.new_items:
                raw_item = getattr(item, "raw_item", None)
                if (
                    isinstance(raw_item, dict)
                    and raw_item.get("type") == "function_call_output"
                    and "container_path" in str(raw_item.get("output", ""))
                ):
                    upload_payloads.append(json.loads(str(raw_item["output"])))
                elif getattr(raw_item, "type", None) == "code_interpreter_call":
                    interpreter_calls.append(raw_item)

            assert len(upload_payloads) == 1
            uploaded_file = upload_payloads[0]["files"][0]
            assert uploaded_file["container_id"] == container_id
            container_path = str(uploaded_file["container_path"])
            assert container_path

            assert interpreter_calls
            assert all(
                getattr(call, "container_id", None) == container_id
                for call in interpreter_calls
            )
            assert any(
                container_path in str(getattr(call, "code", ""))
                for call in interpreter_calls
            )
            logs = "\n".join(
                str(getattr(output, "logs", ""))
                for call in interpreter_calls
                for output in (getattr(call, "outputs", None) or [])
            )
            assert "FILE_VISIBLE rows=13979" in logs
            assert "Country Name,Country Code,Year,Value" in logs
        finally:
            await async_client.close()
            if container_id is not None:
                client.containers.delete(container_id=container_id)
            client.close()

    asyncio.run(run_probe())
