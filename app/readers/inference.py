from __future__ import annotations
from pathlib import Path
from datetime import datetime
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
    outputs = result.get("outputs")
    if not isinstance(outputs, list) or any(not isinstance(item, dict) or not isinstance(item.get("result_file"), str) for item in outputs): raise ArtifactError("Inference result has malformed outputs.", error_code="MALFORMED_INFERENCE_OUTPUTS")
    artifacts = []
    for output in outputs:
        if isinstance(output, dict) and output.get("result_file"):
            artifacts.append(artifact(output["result_file"], kind="series_result", resolver=resolver, run_root=run_root, recorded_run_directory=manifest.get("run_directory"), config=resolver.config, preview=True))
    summary = pick(result, ("model_type", "inference_days", "inference_start", "inference_end_exclusive", "total_saved_series", "completed_series", "skipped_series_count", "unmodelled_part_c_series"))
    summary.update(pick(invocation, ("started_at_utc", "completed_at_utc", "metrics")))
    if all(isinstance(item.get("total_window_rows"), int) for item in outputs):
        summary["total_processed_rows"] = sum(item["total_window_rows"] for item in outputs)
    if all(isinstance(item.get("anomaly_count"), int) for item in outputs):
        summary["total_anomalies"] = sum(item["anomaly_count"] for item in outputs)
    if "total_anomalies" in summary and all(isinstance(item.get("scorable_rows"), int) for item in outputs):
        scorable = sum(item["scorable_rows"] for item in outputs)
        summary["normal_row_count"] = max(0, scorable - summary["total_anomalies"])
        summary["anomaly_percentage"] = round(100 * summary["total_anomalies"] / scorable, 2) if scorable else 0
    summary["composite_ids"] = sorted({item["series_key"] for item in outputs if isinstance(item, dict) and isinstance(item.get("series_key"), str)})
    summary["kpis"] = sorted({item["kpi_name"] for item in outputs if isinstance(item, dict) and isinstance(item.get("kpi_name"), str)})
    summary["output_artifact_count"] = len(artifacts)
    summary["output_artifact_references"] = [item.relative_path for item in artifacts]
    started, completed = invocation.get("started_at_utc"), invocation.get("completed_at_utc")
    if isinstance(started, str) and isinstance(completed, str):
        try: summary["execution_duration_seconds"] = round((datetime.fromisoformat(completed.replace("Z", "+00:00")) - datetime.fromisoformat(started.replace("Z", "+00:00"))).total_seconds(), 3)
        except (ValueError, TypeError): pass
    details = {"series": [pick(item, ("kpi_name", "series_key", "identity", "total_window_rows", "scorable_rows", "unscorable_rows", "anomaly_count", "anomaly_rate", "model_anomaly_count", "lower_anomaly_count", "upper_anomaly_count")) for item in outputs if isinstance(item, dict)], "skipped_series": result.get("skipped_series", [])}
    return invocation, summary, details, artifacts
