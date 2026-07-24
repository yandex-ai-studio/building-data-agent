from __future__ import annotations

import json
import zipfile
from pathlib import Path

from PIL import Image
from pydantic import SecretStr

from vibedraw.artifacts import build_archive, cleanup_context
from vibedraw.config import AppConfig, find_env_file
from vibedraw.models import ConceptEvaluation, IterationRecord, RunContext
from vibedraw.ui import build_demo, render_trace, ui_payload


def config():
    return AppConfig(folder_id="folder", api_key=SecretStr("secret"))


def test_find_env_file_from_nested_app_directory(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text("folder_id=x\napi_key=y\n", encoding="utf-8")
    nested = tmp_path / "apps" / "vibedraw"
    nested.mkdir(parents=True)
    assert find_env_file(nested) == env_path


def test_archive_contains_manifest_images_and_best(tmp_path):
    image_path = tmp_path / "iteration_01.png"
    Image.new("RGB", (8, 8), "blue").save(image_path)
    context = RunContext(
        concept="quiet courage!",
        run_id="run",
        work_dir=str(tmp_path),
        stop_reason="threshold_met",
        best_iteration=1,
        iterations=[
            IterationRecord(
                iteration=1,
                prompt="a blue doorway",
                prompt_kind="initial",
                image_path=str(image_path),
                evaluation=ConceptEvaluation(
                    fit_percent=98,
                    strengths=["clear"],
                    recommendations=[],
                ),
            )
        ],
    )
    archive_path = Path(build_archive(context, config()))
    assert archive_path.name == "vibedraw-quiet-courage.zip"
    with zipfile.ZipFile(archive_path) as archive:
        assert set(archive.namelist()) == {"manifest.json", "iteration_01.png", "best.png"}
        manifest = json.loads(archive.read("manifest.json"))
    assert manifest["best_score"] == 98
    assert manifest["iterations"][0]["image_filename"] == "iteration_01.png"


def test_cleanup_removes_session_directory(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    context = RunContext(work_dir=str(run_dir))
    cleanup_context(context)
    assert not run_dir.exists()


def test_trace_escapes_user_and_model_text():
    context = RunContext(
        iterations=[
            IterationRecord(
                iteration=1,
                prompt="<script>alert('x')</script>",
                prompt_kind="initial",
                error="<b>bad</b>",
            )
        ]
    )
    rendered = render_trace(context)
    assert "<script>" not in rendered
    assert "&lt;script&gt;" in rendered
    assert "<b>bad</b>" not in rendered


def test_ui_payload_has_seven_outputs(tmp_path):
    image_path = tmp_path / "image.png"
    Image.new("RGB", (8, 8), "green").save(image_path)
    context = RunContext(
        concept="hope",
        work_dir=str(tmp_path),
        iterations=[
            IterationRecord(
                iteration=1,
                prompt="sunrise",
                prompt_kind="initial",
                image_path=str(image_path),
            )
        ],
    )
    assert len(ui_payload(context, config())) == 7


def test_gradio_app_builds_without_creating_api_client():
    demo = build_demo(config=config(), service_factory=lambda _: None)
    assert demo is not None

