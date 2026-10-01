from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from app.core.exceptions import ArtifactError, ConflictError, NotFoundError
from app.core.path_resolver import ArtifactPathResolver
from .common import read_json
from .manifest_reader import ManifestReader


@dataclass(frozen=True)
class ResolvedExecution:
    manifest: dict[str, Any]
    run_root: Path
    attempt_id: str
    stage: str
    execution_id: str
    record: dict[str, Any]
    result_file: Path
    result: dict[str, Any]


class ExecutionResolver:
    def __init__(self, resolver: ArtifactPathResolver, manifests: ManifestReader) -> None:
        self.resolver, self.manifests = resolver, manifests

    def resolve(self, run_id: str, attempt_id: str, stage: str) -> ResolvedExecution:
        attempt_id = self.resolver.identifier(attempt_id, "attempt_id")
        stage = self.resolver.stage(stage)
        manifest, run_root = self.manifests.load(run_id)
        attempt = self.manifests.attempt(manifest, attempt_id)
        stages = attempt.get("stages") if isinstance(attempt.get("stages"), dict) else {}
        record = stages.get(stage)
        if not isinstance(record, dict):
            raise NotFoundError("Stage not found.", error_code="STAGE_NOT_FOUND")
        if record.get("status") != "completed":
            raise ConflictError("Stage is not completed.", error_code="STAGE_NOT_COMPLETED")
        execution_id = record.get("successful_execution_id")
        if not isinstance(execution_id, str):
            raise ConflictError("Stage has no successful execution.", error_code="NO_SUCCESSFUL_EXECUTION")
        executions = record.get("executions") if isinstance(record.get("executions"), dict) else {}
        execution = executions.get(execution_id)
        if not isinstance(execution, dict):
            raise ArtifactError("Successful execution record is missing.", error_code="EXECUTION_RECORD_MISSING")
        result_value = execution.get("result_file")
        if not isinstance(result_value, str):
            raise ArtifactError("Successful result file is missing.", error_code="RESULT_FILE_MISSING")
        result_file = self.resolver.file(result_value, run_root=run_root, recorded_run_directory=manifest.get("run_directory"))
        result = read_json(result_file, self.resolver.config.default_file_encoding)
        return ResolvedExecution(manifest, run_root, attempt_id, stage, execution_id, execution, result_file, result)
