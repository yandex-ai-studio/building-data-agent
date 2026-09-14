from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

from agents import function_tool

_root = Path.cwd()
_client: Any = None
_container_id: str | None = None
_ALLOWED_COMMANDS = {"cmd", "cmd.exe", "bash", "ssh"}


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
        uploaded.append(
            {
                "name": path.relative_to(_root).as_posix(),
                "id": result.id,
                "container_id": getattr(result, "container_id", _container_id),
                "container_path": getattr(result, "path", path.name),
                "bytes": getattr(result, "bytes", path.stat().st_size),
            }
        )
    return json.dumps(
        {
            "files": uploaded,
            "code_interpreter_note": (
                "Use each file's container_path exactly in Code Interpreter Python code. "
                "Do not assume the local filename is the container path."
            ),
        },
        ensure_ascii=False,
    )


def read_local_file(filename: str, max_bytes: int = 200000) -> str:
    path = _safe_path(filename)
    if not path.is_file():
        raise FileNotFoundError(filename)
    limit = max(1, min(int(max_bytes), 1_000_000))
    data = path.read_bytes()[:limit]
    return data.decode("utf-8", errors="replace")


def write_local_file(filename: str, content: str, overwrite: bool = False) -> str:
    path = _safe_path(filename)
    if path.exists() and not overwrite:
        return f"File already exists: {filename}. Pass overwrite=True to replace it."
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return f"Wrote {path.relative_to(_root).as_posix()} ({path.stat().st_size} bytes)."


def _parse_hunk_header(header: str) -> int:
    match = re.match(r"@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@", header)
    if not match:
        raise ValueError(f"Bad unified diff hunk header: {header}")
    return int(match.group(1))


def apply_unified_diff(original: str, unified_diff: str) -> str:
    source = original.splitlines(keepends=True)
    diff_lines = unified_diff.splitlines(keepends=True)
    result: list[str] = []
    source_index = 0
    index = 0

    while index < len(diff_lines):
        line = diff_lines[index]
        if line.startswith("---") or line.startswith("+++"):
            index += 1
            continue
        if not line.startswith("@@"):
            index += 1
            continue

        old_start = _parse_hunk_header(line)
        target_index = old_start - 1
        result.extend(source[source_index:target_index])
        source_index = target_index
        index += 1

        while index < len(diff_lines) and not diff_lines[index].startswith("@@"):
            change = diff_lines[index]
            marker = change[:1]
            payload = change[1:]
            if marker == " ":
                if source_index >= len(source) or source[source_index].rstrip("\n\r") != payload.rstrip("\n\r"):
                    raise ValueError("Unified diff context does not match file.")
                result.append(source[source_index])
                source_index += 1
            elif marker == "-":
                if source_index >= len(source) or source[source_index].rstrip("\n\r") != payload.rstrip("\n\r"):
                    raise ValueError("Unified diff removal does not match file.")
                source_index += 1
            elif marker == "+":
                result.append(payload)
            elif change.startswith("\\ No newline at end of file"):
                pass
            else:
                raise ValueError(f"Unsupported unified diff line: {change.rstrip()}")
            index += 1

    result.extend(source[source_index:])
    return "".join(result)


def edit_local_file(filename: str, unified_diff: str) -> str:
    path = _safe_path(filename)
    original = path.read_text(encoding="utf-8")
    updated = apply_unified_diff(original, unified_diff)
    path.write_text(updated, encoding="utf-8")
    return f"Edited {path.relative_to(_root).as_posix()}."


def run_command(command: str, args: list[str] | None = None, timeout_seconds: int = 60) -> str:
    entrypoint = Path(command).name.lower()
    if entrypoint not in _ALLOWED_COMMANDS:
        raise ValueError("Allowed commands are: cmd, bash, ssh.")
    timeout = max(1, min(int(timeout_seconds), 300))
    argv = [command, *(args or [])]
    completed = subprocess.run(
        argv,
        cwd=_root,
        text=True,
        capture_output=True,
        timeout=timeout,
        shell=False,
    )
    return json.dumps(
        {
            "command": argv,
            "exit_code": completed.returncode,
            "stdout": completed.stdout[-20000:],
            "stderr": completed.stderr[-20000:],
        },
        ensure_ascii=False,
    )


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
    """Upload local files into Code Interpreter and return exact container_path values to use in code."""
    return upload_files(filenames)


@function_tool
def read_file(filename: str, max_bytes: int = 200000) -> str:
    """Read a UTF-8 text file from the current directory, capped by max_bytes."""
    return read_local_file(filename, max_bytes)


@function_tool
def write_file(filename: str, content: str, overwrite: bool = False) -> str:
    """Write a UTF-8 text file in the current directory."""
    return write_local_file(filename, content, overwrite)


@function_tool
def edit_file(filename: str, unified_diff: str) -> str:
    """Edit a UTF-8 text file by applying a unified diff."""
    return edit_local_file(filename, unified_diff)


@function_tool
def execute_command(command: str, args: list[str] | None = None, timeout_seconds: int = 60) -> str:
    """Execute an allowlisted local command: cmd, bash, or ssh."""
    return run_command(command, args, timeout_seconds)
