from __future__ import annotations

from app.core.config import Settings, settings
from app.core.path_resolver import ArtifactPathResolver
from app.readers.common import now, public_value
from app.readers.execution_resolver import ExecutionResolver
from app.readers.manifest_reader import ManifestReader
from app.readers import part_a, part_b, part_c, part_d, inference, inference_results
from app.schemas.common import ReportEnvelope


class ReportService:
    def __init__(self, config: Settings = settings) -> None:
        self.resolver = ArtifactPathResolver(config)
        self.manifests = ManifestReader(self.resolver)
        self.executions = ExecutionResolver(self.resolver, self.manifests)

    def stage_report(self, run_id: str, attempt_id: str, stage: str) -> ReportEnvelope:
        resolved = self.executions.resolve(run_id, attempt_id, stage)
        # Readers only receive the resolver through this private attachment; all path access remains centralized.
        object.__setattr__(resolved, "_resolver", self.resolver)
        reader = {"part_a": part_a.read, "part_b": part_b.read, "part_c": part_c.read, "part_d": part_d.read}[resolved.stage]
        summary, details, warnings = reader(resolved)
        return ReportEnvelope(run_id=run_id, attempt_id=attempt_id, stage=resolved.stage, status="completed", execution_id=resolved.execution_id, generated_at=now(), summary=public_value(summary), artifacts=details.pop("artifacts", []) if "artifacts" in details else [], warnings=warnings, details=public_value(details))

    def attempt(self, run_id: str, attempt_id: str) -> dict:
        manifest, _ = self.manifests.load(run_id)
        attempt = self.manifests.attempt(manifest, self.resolver.identifier(attempt_id, "attempt_id"))
        return {"run_id": run_id, "attempt_id": attempt_id, "status": attempt.get("status"), "stages": {name: {"status": record.get("status"), "successful_execution_id": record.get("successful_execution_id")} for name, record in attempt.get("stages", {}).items() if isinstance(record, dict)}}

    def run(self, run_id: str) -> dict:
        manifest, _ = self.manifests.load(run_id)
        return {"run_id": run_id, "status": manifest.get("status"), "latest_attempt_id": manifest.get("latest_attempt_id"), "active_inference_attempt_id": manifest.get("active_inference_attempt_id"), "inference_ready": manifest.get("inference_ready"), "attempts": list(manifest.get("attempts", {}).keys()), "inference_invocation_count": len(inference.list_invocations(manifest))}

    def inference_list(self, run_id: str) -> dict:
        manifest, _ = self.manifests.load(run_id)
        return {"run_id": run_id, "invocations": [{key: value for key, value in item.items() if key in {"invocation_id", "training_attempt_id", "status", "started_at_utc", "completed_at_utc", "metrics"}} for item in inference.list_invocations(manifest)]}

    def inference_report(self, run_id: str, invocation_id: str) -> ReportEnvelope:
        manifest, root = self.manifests.load(run_id)
        record, summary, details, artifacts = inference.read(manifest, root, invocation_id, self.resolver)
        return ReportEnvelope(run_id=run_id, stage="inference", status="completed", invocation_id=invocation_id, training_attempt_id=record.get("training_attempt_id"), generated_at=now(), summary=public_value(summary), artifacts=artifacts, details=public_value(details))

    def inference_results(self, run_id: str, invocation_id: str, **params) -> dict:
        manifest, root = self.manifests.load(run_id)
        return inference_results.page(manifest, root, invocation_id, self.resolver, **params)

    def inference_filter_options(self, run_id: str, invocation_id: str) -> dict:
        manifest, root = self.manifests.load(run_id)
        return inference_results.options(manifest, root, invocation_id, self.resolver)
