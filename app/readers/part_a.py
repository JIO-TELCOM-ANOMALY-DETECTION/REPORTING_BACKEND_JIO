from __future__ import annotations
from typing import Any
from app.core.exceptions import ArtifactError
from .common import artifact, pick
from .execution_resolver import ResolvedExecution


def read(resolved: ResolvedExecution) -> tuple[dict[str, Any], list, list[str]]:
    payload = resolved.result.get("payload")
    if resolved.result.get("handoff_schema_version") != "1.0" or not isinstance(payload, dict):
        raise ArtifactError("Unsupported Part A result schema.", error_code="UNSUPPORTED_RESULT_SCHEMA")
    eda = payload.get("eda_result")
    if not isinstance(eda, dict):
        raise ArtifactError("Part A result is incomplete.", error_code="INVALID_PART_A_RESULT")
    artifacts, reports = [], []
    for item in eda.get("kpi_results", []):
        if not isinstance(item, dict): continue
        kpi = item.get("prepared_dataset", {}).get("kpi_name", "unknown") if isinstance(item.get("prepared_dataset"), dict) else "unknown"
        artifacts_for_kpi = []
        for source, kind in ((item.get("site_analysis"), "site_summary"), (item.get("data_integrity"), "integrity")):
            if isinstance(source, dict):
                for key in ("summary_file", "series_summary_file", "gap_details_file", "global_missing_file", "duplicate_details_file"):
                    if source.get(key): artifacts_for_kpi.append(artifact(source[key], kind=f"{kind}:{key}", resolver=resolved_resolver(resolved), run_root=resolved.run_root, recorded_run_directory=resolved.manifest.get("run_directory"), config=resolved_resolver(resolved).config, preview=key.endswith("summary_file")))
        artifacts.extend(artifacts_for_kpi)
        reports.append({"kpi_name": kpi, "site_analysis": pick(item.get("site_analysis", {}), ("total_rows", "total_unique_sites", "rows_with_missing_site_identity")), "server_validation": pick(item.get("server_validation", {}), ("check_skipped", "total_sites", "consistent_site_count", "inconsistent_site_count", "unresolved_site_count", "rows_with_missing_server")), "integrity": pick(item.get("data_integrity", {}), ("total_sites", "expected_timestamps_per_site", "total_missing_timestamps", "total_gap_events", "rows_with_invalid_timestamp", "rows_outside_expected_timeline"))})
    return {"kpi_count": len(reports), "prepared_dataset_count": len(eda.get("kpi_results", []))}, {"kpis": reports, "artifacts": artifacts}, []


def resolved_resolver(resolved: ResolvedExecution):
    # Attached by ReportService, keeping individual readers free of global settings.
    return resolved._resolver  # type: ignore[attr-defined]
