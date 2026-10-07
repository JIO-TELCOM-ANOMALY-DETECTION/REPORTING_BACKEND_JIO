from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.exceptions import ArtifactError, ValidationError
from .common import read_json

FILTERS = ("composite_id", "circle", "cluster", "site_name", "kpi", "status", "start_time", "end_time")
ALIASES = {"composite_id": "series_key", "kpi": "kpi_name"}
TRUE_VALUES = {"true", "1", "yes"}
MAX_PAGE_SIZE = 100


def source(manifest: dict, run_root: Path, invocation_id: str, resolver):
    invocation_id = resolver.identifier(invocation_id, "invocation_id")
    inference = manifest.get("inference")
    records = inference.get("invocations") if isinstance(inference, dict) else None
    record = records.get(invocation_id) if isinstance(records, dict) else None
    if not isinstance(record, dict):
        from app.core.exceptions import NotFoundError
        raise NotFoundError("Inference invocation not found.", error_code="INFERENCE_INVOCATION_NOT_FOUND")
    if record.get("status") != "completed":
        raise ArtifactError("Inference invocation is not completed.", error_code="INFERENCE_NOT_COMPLETED")
    if not isinstance(record.get("result_file"), str):
        raise ArtifactError("Inference result snapshot is missing.", error_code="INFERENCE_RESULT_FILE_MISSING")
    path = resolver.file(record["result_file"], run_root=run_root, recorded_run_directory=manifest.get("run_directory"))
    result = read_json(path, resolver.config.default_file_encoding)
    if result.get("invocation_id") != invocation_id:
        raise ArtifactError("Inference result identity is inconsistent.", error_code="INFERENCE_RESULT_ID_MISMATCH")
    outputs = result.get("outputs")
    if not isinstance(outputs, list) or any(not isinstance(item, dict) or not isinstance(item.get("result_file"), str) for item in outputs):
        raise ArtifactError("Inference result has malformed output references.", error_code="MALFORMED_INFERENCE_OUTPUTS")
    paths = [(item, resolver.file(item["result_file"], run_root=run_root, recorded_run_directory=manifest.get("run_directory"))) for item in outputs]
    return record, result, paths


def _timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError as error:
        raise ValidationError("Invalid timestamp filter.", error_code="INVALID_TIME_FILTER") from error


def _rows(paths, encoding: str):
    for output, path in paths:
        if path.suffix.lower() != ".csv":
            raise ArtifactError("Inference output must be a CSV file.", error_code="INVALID_RESULT_FORMAT")
        try:
            with path.open("r", encoding=encoding, newline="") as handle:
                reader = csv.DictReader(handle)
                if not reader.fieldnames or "is_anomaly" not in reader.fieldnames:
                    raise ArtifactError("Inference CSV has no anomaly column.", error_code="MALFORMED_RESULT_CSV")
                for row in reader:
                    if None in row or any(value is None for value in row.values()):
                        raise ArtifactError("Inference CSV has malformed rows.", error_code="MALFORMED_RESULT_CSV")
                    yield {**{key: value for key, value in row.items() if key}, "series_key": row.get("series_key") or output.get("series_key", ""), "kpi_name": row.get("kpi_name") or output.get("kpi_name", "")}
        except (OSError, UnicodeError, csv.Error) as error:
            raise ArtifactError("Unable to read inference CSV.", error_code="MALFORMED_RESULT_CSV") from error


def page(manifest: dict, run_root: Path, invocation_id: str, resolver, *, mode: str = "anomalies", page: int = 1, page_size: int = 50, sort_by: str = "timestamp", sort_order: str = "asc", **filters: str | None) -> dict[str, Any]:
    if mode not in {"anomalies", "all"}:
        raise ValidationError("Mode must be anomalies or all.", error_code="INVALID_RESULT_MODE")
    if page < 1 or page_size < 1 or page_size > MAX_PAGE_SIZE:
        raise ValidationError(f"Page must be at least 1 and page size must be between 1 and {MAX_PAGE_SIZE}.", error_code="INVALID_PAGINATION")
    if sort_order not in {"asc", "desc"}:
        raise ValidationError("Sort order must be asc or desc.", error_code="INVALID_SORT_ORDER")
    if sort_by not in {"timestamp", "series_key", "composite_id", "circle", "cluster", "site_name", "kpi", "kpi_name", "actual", "is_anomaly", "status"}:
        raise ValidationError("Unsupported sort column.", error_code="INVALID_SORT_COLUMN")
    record, result, paths = source(manifest, run_root, invocation_id, resolver)
    applied = {key: value for key, value in filters.items() if key in FILTERS and value not in (None, "")}
    start = _timestamp(applied["start_time"]) if "start_time" in applied else None
    end = _timestamp(applied["end_time"]) if "end_time" in applied else None
    if start and end and start > end:
        raise ValidationError("Start time must not be after end time.", error_code="INVALID_TIME_RANGE")
    matches = []
    for row in _rows(paths, resolver.config.default_file_encoding):
        anomaly = row.get("is_anomaly", "").lower() in TRUE_VALUES
        if mode == "anomalies" and not anomaly:
            continue
        if any(str(row.get(ALIASES.get(key, key), "")).casefold() != str(value).casefold() for key, value in applied.items() if key not in {"start_time", "end_time", "status"}):
            continue
        if "status" in applied and str(row.get("status") or row.get("anomaly_type") or row.get("is_anomaly", "")).casefold() != applied["status"].casefold():
            continue
        if start or end:
            raw_time = row.get("timestamp", "")
            try:
                timestamp = _timestamp(raw_time)
                if (start and timestamp < start) or (end and timestamp > end):
                    continue
            except (ValidationError, TypeError) as error:
                raise ArtifactError("Inference CSV contains an invalid timestamp.", error_code="MALFORMED_RESULT_CSV") from error
        matches.append(row)
    sort_key = ALIASES.get(sort_by, sort_by)
    def key(row):
        value = (row.get("status") or row.get("anomaly_type") or row.get("is_anomaly", "")) if sort_key == "status" else row.get(sort_key, "")
        if sort_key == "actual":
            try: return (0, float(value))
            except (ValueError, TypeError): return (1, 0.0)
        return (0, value.casefold())
    matches.sort(key=key, reverse=sort_order == "desc")
    total = len(matches)
    offset = (page - 1) * page_size
    return {"items": matches[offset:offset + page_size], "pagination": {"page": page, "page_size": page_size, "total_items": total, "total_pages": (total + page_size - 1) // page_size, "has_previous": page > 1, "has_next": offset + page_size < total}, "filters_applied": applied, "source": {"run_id": manifest.get("run_id"), "invocation_id": invocation_id, "training_attempt_id": record.get("training_attempt_id"), "output_count": len(paths), "result_file": resolver.relative_name(resolver.file(record["result_file"], run_root=run_root, recorded_run_directory=manifest.get("run_directory")), run_root)}}


def options(manifest: dict, run_root: Path, invocation_id: str, resolver) -> dict[str, list[str]]:
    _, _, paths = source(manifest, run_root, invocation_id, resolver)
    values = {key: set() for key in ("composite_id", "circle", "cluster", "site_name", "kpi", "status")}
    for output, path in paths:
        if path.suffix.lower() != ".csv":
            raise ArtifactError("Inference output must be a CSV file.", error_code="INVALID_RESULT_FORMAT")
        for key, index in (("composite_id", None), ("circle", 0), ("cluster", 1), ("site_name", 2), ("kpi", None)):
            value = output.get("series_key") if key == "composite_id" else output.get("kpi_name") if key == "kpi" else (output.get("identity") or [])[index] if isinstance(output.get("identity"), list) and len(output["identity"]) > index else None
            if isinstance(value, str) and value: values[key].add(value)
    # Status is often only present in rows, so discover it while keeping output bounded.
    for row in _rows(paths, resolver.config.default_file_encoding):
        for key in ("composite_id", "circle", "cluster", "site_name", "kpi"):
            value = row.get(ALIASES.get(key, key))
            if value: values[key].add(value)
        value = row.get("status") or row.get("anomaly_type") or row.get("is_anomaly")
        if value: values["status"].add(value)
    return {key: sorted(items) for key, items in values.items()}
