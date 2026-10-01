from __future__ import annotations
from app.core.exceptions import ArtifactError
from .common import artifact, pick
from .part_a import resolved_resolver
from .execution_resolver import ResolvedExecution

def read(resolved: ResolvedExecution):
    payload = resolved.result.get("payload")
    if resolved.result.get("handoff_schema_version") != "1.0" or not isinstance(payload, dict): raise ArtifactError("Unsupported Part C result schema.", error_code="UNSUPPORTED_RESULT_SCHEMA")
    resolver, artifacts, reports = resolved_resolver(resolved), [], []
    for item in payload.get("feature_engineering_results", []):
        if not isinstance(item, dict): continue
        for key in ("site_summary_file", "corrected_history_audit_file"):
            if item.get(key): artifacts.append(artifact(item[key], kind=key.removesuffix("_file"), resolver=resolver, run_root=resolved.run_root, recorded_run_directory=resolved.manifest.get("run_directory"), config=resolver.config, preview=True))
        report = pick(item, ("kpi_name", "feature_columns", "total_rows", "total_sites", "processed_sites", "skipped_invalid_sites", "insufficient_history_sites", "populated_feature_cells", "missing_feature_cells"))
        report["resolved_config"] = item.get("resolved_config", {})
        reports.append(report)
    return {"kpi_count": len(reports)}, {"kpis": reports, "artifacts": artifacts}, []
