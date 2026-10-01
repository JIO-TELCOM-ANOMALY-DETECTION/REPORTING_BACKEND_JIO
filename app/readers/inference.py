from __future__ import annotations
from pathlib import Path
from app.core.exceptions import ArtifactError, NotFoundError
from .common import artifact, pick, read_json
from .part_a import resolved_resolver

def list_invocations(manifest: dict) -> list[dict]:
    invocations = manifest.get("inference", {}).get("invocations", {}) if isinstance(manifest.get("inference"), dict) else {}
    return [dict(value, invocation_id=key) for key, value in invocations.items() if isinstance(value, dict)]

def read(manifest: dict, run_root: Path, invocation_id: str, resolver):
    invocation_id = resolver.identifier(invocation_id, "invocation_id")
    records = manifest.get("inference", {}).get("invocations", {}) if isinstance(manifest.get("inference"), dict) else {}
    invocation = records.get(invocation_id) if isinstance(records, dict) else None
    if not isinstance(invocation, dict): raise NotFoundError("Inference invocation not found.", error_code="INFERENCE_INVOCATION_NOT_FOUND")
    if invocation.get("status") != "completed": raise ArtifactError("Inference invocation is not completed.", error_code="INFERENCE_NOT_COMPLETED")
    result_path = invocation.get("result_file")
    if not isinstance(result_path, str): raise ArtifactError("Inference result snapshot is missing.", error_code="INFERENCE_RESULT_FILE_MISSING")
    result_file = resolver.file(result_path, run_root=run_root, recorded_run_directory=manifest.get("run_directory"))
    result = read_json(result_file, resolver.config.default_file_encoding)
    if result.get("invocation_id") != invocation_id: raise ArtifactError("Inference result identity is inconsistent.", error_code="INFERENCE_RESULT_ID_MISMATCH")
    artifacts = []
    for output in result.get("outputs", []):
        if isinstance(output, dict) and output.get("result_file"):
            artifacts.append(artifact(output["result_file"], kind="series_result", resolver=resolver, run_root=run_root, recorded_run_directory=manifest.get("run_directory"), config=resolver.config, preview=True))
    summary = pick(result, ("model_type", "inference_days", "inference_start", "inference_end_exclusive", "total_saved_series", "completed_series", "skipped_series_count", "unmodelled_part_c_series"))
    summary.update(pick(invocation, ("started_at_utc", "completed_at_utc", "metrics")))
    details = {"series": [pick(item, ("kpi_name", "series_key", "identity", "total_window_rows", "scorable_rows", "unscorable_rows", "anomaly_count", "anomaly_rate", "model_anomaly_count", "lower_anomaly_count", "upper_anomaly_count")) for item in result.get("outputs", []) if isinstance(item, dict)], "skipped_series": result.get("skipped_series", [])}
    return invocation, summary, details, artifacts
