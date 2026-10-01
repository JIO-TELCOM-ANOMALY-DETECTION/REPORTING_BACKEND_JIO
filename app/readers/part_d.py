from __future__ import annotations

from pathlib import Path

from app.core.exceptions import ArtifactError

from .common import artifact, pick, read_json
from .execution_resolver import ResolvedExecution
from .part_a import resolved_resolver

JSON_FILES = (
    "metadata_file",
    "decision_settings_file",
    "split_plan_file",
    "training_config_file",
    "feature_contract_file",
    "final_hyperparameters_file",
    "training_summary_file",
    "usable_row_counts_file",
)
FALLBACK_TRAINING_FILES = {
    "training_summary_file": "training_summary.json",
}


def read(resolved: ResolvedExecution):
    if resolved.result.get("part_d_snapshot_version") != "1.0":
        raise ArtifactError("Unsupported Part D result schema.", error_code="UNSUPPORTED_RESULT_SCHEMA")

    resolver, artifacts, reports = resolved_resolver(resolved), [], []
    for record in resolved.result.get("training_records", []):
        if not isinstance(record, dict):
            continue

        report = pick(record, (
            "kpi_name", "status", "model_type", "minimum_history_points",
            "total_series", "valid_series", "trained_series", "skipped_invalid_series",
            "model_feature_columns", "target_column",
        ))
        training_dir = record.get("training_directory")

        for key in JSON_FILES:
            value = record.get(key)
            if value is None and isinstance(training_dir, str) and key in FALLBACK_TRAINING_FILES:
                value = str(Path(training_dir) / FALLBACK_TRAINING_FILES[key])
            if not value:
                continue

            artifacts.append(artifact(
                value,
                kind=key.removesuffix("_file"),
                resolver=resolver,
                run_root=resolved.run_root,
                recorded_run_directory=resolved.manifest.get("run_directory"),
                config=resolver.config,
            ))
            if key in {"training_summary_file", "metadata_file", "decision_settings_file"}:
                report[key.removesuffix("_file")] = read_json(
                    resolver.file(
                        value,
                        run_root=resolved.run_root,
                        recorded_run_directory=resolved.manifest.get("run_directory"),
                    ),
                    resolver.config.default_file_encoding,
                )

        reports.append(report)

    return (
        {
            "model_type": resolved.result.get("training_config", {}).get("model_type"),
            "kpi_count": len(reports),
        },
        {"training_records": reports, "artifacts": artifacts},
        [],
    )
