from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agents import function_tool

_root = Path.cwd()
_client: Any = None
_container_id: str | None = None


def configure(root: Path | str | None = None, client: Any = None, container_id: str | None = None) -> None:
    global _root, _client, _container_id
    if root is not None:
        _root = Path(root).resolve()
    _client = client
    _container_id = container_id


def _safe_path(filename: str) -> Path:
    path = Path(filename)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"Unsafe path: {filename}")
    resolved = (_root / path).resolve()
    if resolved != _root and _root not in resolved.parents:
        raise ValueError(f"Unsafe path: {filename}")
    return resolved


def _safe_mask(mask: str | None) -> str:
    if not mask:
        return "*"
    path = Path(mask)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"Unsafe mask: {mask}")
    return mask


def list_files(mask: str | None = None) -> str:
    pattern = _safe_mask(mask)
    files = sorted(path for path in _root.glob(pattern) if path.is_file())
    if not files:
        return "No files found."
    return "\n".join(f"{path.relative_to(_root).as_posix()} - {path.stat().st_size} bytes" for path in files)


def inspect_file(filename: str) -> str:
    path = _safe_path(filename)
    if not path.is_file():
        return f"No file: {filename}"

    import pandas as pd

    suffix = path.suffix.lower()
    if suffix == ".csv":
        sheets = None
        frame = pd.read_csv(path)
    elif suffix in {".xlsx", ".xls"}:
        book = pd.ExcelFile(path)
        sheets = book.sheet_names
        frame = pd.read_excel(path, sheet_name=sheets[0])
    else:
        return "Supported formats: CSV, XLSX, XLS."

    return json.dumps(
        {
            "file": path.relative_to(_root).as_posix(),
            "sheets": sheets,
            "shape": list(frame.shape),
            "columns": [str(column) for column in frame.columns],
            "dtypes": {str(column): str(dtype) for column, dtype in frame.dtypes.items()},
            "head": frame.head(8).to_dict(orient="records"),
        },
        ensure_ascii=False,
        default=str,
    )


def upload_files(filenames: list[str]) -> str:
    if _client is None or _container_id is None:
        return "Code Interpreter container is not configured."

    uploaded: list[dict[str, str]] = []
    for filename in filenames:
        path = _safe_path(filename)
        if not path.is_file():
            raise FileNotFoundError(filename)
        with path.open("rb") as handle:
            result = _client.containers.files.create(container_id=_container_id, file=handle)
        uploaded.append({"name": path.relative_to(_root).as_posix(), "id": result.id})
    return json.dumps({"files": uploaded}, ensure_ascii=False)


@function_tool
def ls(mask: str | None = None) -> str:
    """List local files in the current directory that match an optional glob mask."""
    return list_files(mask)


@function_tool
def inspect(filename: str) -> str:
    """Inspect a local CSV/XLS/XLSX file: sheets, shape, dtypes, columns, and first rows."""
    return inspect_file(filename)


@function_tool
def upload(filenames: list[str]) -> str:
    """Upload local files into the active Code Interpreter container."""
    return upload_files(filenames)
