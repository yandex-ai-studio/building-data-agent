from __future__ import annotations

import json
import re
import shutil
import zipfile
from pathlib import Path

from .config import AppConfig
from .models import RunContext


def safe_slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return (slug or "concept")[:60]


def manifest_data(context: RunContext, config: AppConfig) -> dict:
    return {
        "concept": context.concept,
        "run_id": context.run_id,
        "threshold": config.threshold,
        "max_iterations": config.max_iterations,
        "models": {
            "text": config.text_model,
            "vision": config.vision_model,
            "image": config.image_model,
        },
        "stop_reason": context.stop_reason,
        "status": context.status,
        "best_iteration": context.best_iteration,
        "best_score": context.best_score,
        "iterations": [item.manifest() for item in context.iterations],
    }


def build_archive(context: RunContext, config: AppConfig) -> str | None:
    if not context.work_dir or not context.iterations:
        return None
    work_dir = Path(context.work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = work_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest_data(context, config), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    best = context.best
    best_path = work_dir / "best.png"
    if best and best.image_path:
        shutil.copy2(best.image_path, best_path)

    archive_path = work_dir / f"vibedraw-{safe_slug(context.concept)}.zip"
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(manifest_path, manifest_path.name)
        for item in context.iterations:
            if item.image_path and Path(item.image_path).is_file():
                archive.write(item.image_path, Path(item.image_path).name)
        if best_path.is_file():
            archive.write(best_path, best_path.name)
    return str(archive_path)


def cleanup_context(context: RunContext | None) -> None:
    if context and context.work_dir:
        shutil.rmtree(context.work_dir, ignore_errors=True)

