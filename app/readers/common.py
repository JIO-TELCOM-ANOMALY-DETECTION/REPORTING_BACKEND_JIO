from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from app.core.config import Settings
from app.core.path_resolver import ArtifactPathResolver
from app.schemas.common import Artifact


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path, encoding: str) -> dict[str, Any]:
    try:
        with path.open("r", encoding=encoding) as handle:
            value = json.load(handle)
    except (OSError, json.JSONDecodeError) as error:
        from app.core.exceptions import ArtifactError
        raise ArtifactError("Unable to read JSON artifact.", error_code="MALFORMED_JSON") from error
    if not isinstance(value, dict):
        from app.core.exceptions import ArtifactError
        raise ArtifactError("JSON artifact must contain an object.", error_code="INVALID_JSON_OBJECT")
    return value


def artifact(path_value: str | Path, *, kind: str, resolver: ArtifactPathResolver, run_root: Path,
             recorded_run_directory: str | None, config: Settings, preview: bool = False) -> Artifact:
    path = resolver.file(path_value, run_root=run_root, recorded_run_directory=recorded_run_directory)
    suffix = path.suffix.lower().lstrip(".") or "file"
    rows = csv_preview(path, config.max_csv_preview_rows, config.default_file_encoding) if preview and suffix == "csv" else None
    return Artifact(name=path.name, kind=kind, format=suffix, relative_path=resolver.relative_name(path, run_root),
                    size_bytes=path.stat().st_size, preview=rows)


def csv_preview(path: Path, limit: int, encoding: str) -> list[dict[str, str]]:
    if limit == 0:
        return []
    try:
        with path.open("r", encoding=encoding, newline="") as handle:
            return list(__import__("itertools").islice(csv.DictReader(handle), limit))
    except (OSError, UnicodeError, csv.Error):
        return []


def pick(mapping: dict[str, Any], keys: Iterable[str]) -> dict[str, Any]:
    return {key: mapping[key] for key in keys if key in mapping and mapping[key] is not None}


def public_value(value: Any) -> Any:
    """Remove internal absolute paths from values copied out of saved summaries."""
    if isinstance(value, dict):
        return {str(key): public_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [public_value(item) for item in value]
    if isinstance(value, str) and (value.startswith(("/", "\\")) or (len(value) > 2 and value[1] == ":" and value[2] in "\\/")):
        return "[internal path]"
    return value