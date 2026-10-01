from __future__ import annotations
from app.core.exceptions import ArtifactError
from .common import artifact, pick
from .part_a import resolved_resolver
from .execution_resolver import ResolvedExecution

SUMMARY_KEYS = ("outlier_summary_file", "gap_summary_file", "phase_1_summary_file", "phase_2_summary_file", "phase_3_summary_file", "phase_4_summary_file")

def read(resolved: ResolvedExecution):
    payload = resolved.result.get("payload")
    if resolved.result.get("handoff_schema_version") != "1.0" or not isinstance(payload, dict): raise ArtifactError("Unsupported Part B result schema.", error_code="UNSUPPORTED_RESULT_SCHEMA")
    resolver, artifacts, reports = resolved_resolver(resolved), [], []
    for item in payload.get("preprocessing_results", []):
        if not isinstance(item, dict): continue
        for key in SUMMARY_KEYS:
            if item.get(key): artifacts.append(artifact(item[key], kind=key.removesuffix("_file"), resolver=resolver, run_root=resolved.run_root, recorded_run_directory=resolved.manifest.get("run_directory"), config=resolver.config, preview=True))
        reports.append(pick(item, ("kpi_name", "prophet_enabled", "total_input_rows", "final_rows", "duplicate_rows_removed", "inserted_timestamp_rows", "invalid_rows_converted", "valid_series", "invalid_series", "outliers_flagged", "original_gaps", "original_missing_points", "phase_1_filled_points", "phase_2_filled_points", "phase_3_filled_points", "phase_4_safe_filled_points", "unresolved_points")))
    return {"kpi_count": len(reports)}, {"kpis": reports, "artifacts": artifacts}, []
