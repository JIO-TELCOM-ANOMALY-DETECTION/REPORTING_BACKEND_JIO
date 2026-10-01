from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from app.core.config import Settings
from app.core.exceptions import ArtifactError, ConflictError, NotFoundError
from app.main import health
from app.services.report_service import ReportService


class ReportingFixtureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "runs"
        self.run = self.root / "run_valid"
        self.attempt = "attempt_0001"
        self.run.mkdir(parents=True)
        self.config = Settings(ml_runs_root=self.root, max_csv_preview_rows=2)
        self.service = ReportService(self.config)
        self._fixture()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write(self, relative: str, content: str = "{}") -> Path:
        path = self.run / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def _stage(self, name: str, result: dict, status: str = "completed", success: str | None = "execution_0001") -> dict:
        base = f"attempts/{self.attempt}/stages/{name}/execution_0001"
        result_path = self.write(f"{base}/result.json", json.dumps(result))
        return {"status": status, "active_execution_id": None, "successful_execution_id": success,
                "executions": {"execution_0001": {"status": status, "result_file": str(result_path)}}}

    def _fixture(self) -> None:
        a_csv = self.write("a/site.csv", "site,rows\na,1\n")
        text = self.write("a/summary.txt", "integrity ok\n")
        b_csv = self.write("b/outliers.csv", "site,count\na,0\n")
        c_csv = self.write("c/sites.csv", "site,status\na,valid\n")
        d_json = self.write("d/training/training_summary.json", '{"training_summary":{"mae":1.0}}')
        series = self.write("inference/attempt_0001/inference_results/inv_1/series.csv", "time,anomaly\nt1,false\n")
        request_result = self.write("inference/attempt_0001/requests/request_000001/result.json", json.dumps({
            "run_id": "run_valid", "invocation_id": "inv_1", "model_type": "xgboost", "inference_days": 1,
            "inference_start": "2026-01-01T00:00:00+00:00", "inference_end_exclusive": "2026-01-02T00:00:00+00:00",
            "total_saved_series": 1, "completed_series": 1, "skipped_series_count": 0, "unmodelled_part_c_series": 0,
            "outputs": [{"kpi_name": "KPI", "series_key": "site", "result_file": str(series), "anomaly_count": 0, "anomaly_rate": 0.0}], "skipped_series": []
        }))
        stages = {
            "part_a": self._stage("part_a", {"handoff_schema_version": "1.0", "stage": "part_a", "payload": {"eda_result": {"kpi_results": [{"prepared_dataset": {"kpi_name": "KPI"}, "site_analysis": {"summary_file": str(a_csv), "total_rows": 1, "total_unique_sites": 1}, "server_validation": {"total_sites": 1}, "data_integrity": {"summary_file": str(text), "series_summary_file": str(a_csv), "gap_details_file": str(a_csv), "global_missing_file": str(a_csv), "duplicate_details_file": str(a_csv), "total_sites": 1}}]}}}),
            "part_b": self._stage("part_b", {"handoff_schema_version": "1.0", "stage": "part_b", "payload": {"preprocessing_results": [{"kpi_name": "KPI", "outlier_summary_file": str(b_csv), "gap_summary_file": str(b_csv), "phase_1_summary_file": str(b_csv), "phase_2_summary_file": str(b_csv), "phase_3_summary_file": str(b_csv), "phase_4_summary_file": None, "final_rows": 1}]}}),
            "part_c": self._stage("part_c", {"handoff_schema_version": "1.0", "stage": "part_c", "payload": {"feature_engineering_results": [{"kpi_name": "KPI", "site_summary_file": str(c_csv), "corrected_history_audit_file": None, "feature_columns": ["lag_1"], "total_rows": 1}]}}),
            "part_d": self._stage("part_d", {"part_d_snapshot_version": "1.0", "stage": "part_d", "training_config": {"model_type": "xgboost"}, "training_records": [{"kpi_name": "KPI", "status": "completed", "model_type": "xgboost", "training_directory": str(d_json.parent), "trained_series": 1}]})
        }
        self.manifest = {"manifest_version": "2.0", "run_id": "run_valid", "run_directory": str(self.run), "status": "completed", "attempts": {self.attempt: {"status": "completed", "stages": stages}}, "inference": {"invocations": {"inv_1": {"invocation_id": "inv_1", "training_attempt_id": self.attempt, "status": "completed", "result_file": str(request_result), "metrics": {"completed_series": 1}}}}}
        self.write("manifest.json", json.dumps(self.manifest))

    def test_valid_stage_reports_and_repeated_reads_are_read_only(self) -> None:
        before = hashlib.sha256((self.run / "manifest.json").read_bytes()).hexdigest()
        for stage in ("part-a", "part-b", "part-c", "part-d"):
            report = self.service.stage_report("run_valid", self.attempt, stage)
            self.assertEqual(report.status, "completed")
            self.assertGreaterEqual(len(report.artifacts), 1)
        self.assertEqual(self.service.stage_report("run_valid", self.attempt, "part-b").execution_id, "execution_0001")
        self.assertEqual(before, hashlib.sha256((self.run / "manifest.json").read_bytes()).hexdigest())

    def test_valid_inference_report(self) -> None:
        report = self.service.inference_report("run_valid", "inv_1")
        self.assertEqual(report.training_attempt_id, self.attempt)
        self.assertEqual(report.summary["completed_series"], 1)
        self.assertEqual(len(report.artifacts), 1)

    def test_unknown_run_attempt_stage_and_invocation(self) -> None:
        with self.assertRaises(NotFoundError): self.service.run("run_missing")
        with self.assertRaises(NotFoundError): self.service.attempt("run_valid", "attempt_missing")
        with self.assertRaises(NotFoundError): self.service.inference_report("run_valid", "inv_missing")
        self.manifest["attempts"][self.attempt]["stages"]["part_a"]["status"] = "failed"
        self.write("manifest.json", json.dumps(self.manifest))
        with self.assertRaises(ConflictError): self.service.stage_report("run_valid", self.attempt, "part-a")

    def test_missing_result_and_unsafe_paths_are_rejected(self) -> None:
        self.manifest["attempts"][self.attempt]["stages"]["part_a"]["executions"]["execution_0001"]["result_file"] = str(self.run / "missing.json")
        self.write("manifest.json", json.dumps(self.manifest))
        with self.assertRaises(ArtifactError): self.service.stage_report("run_valid", self.attempt, "part-a")
        self.manifest["attempts"][self.attempt]["stages"]["part_a"]["executions"]["execution_0001"]["result_file"] = str(Path(self.temp.name) / "outside.json")
        self.write("manifest.json", json.dumps(self.manifest))
        with self.assertRaises(ArtifactError): self.service.stage_report("run_valid", self.attempt, "part-a")
        with self.assertRaises(Exception): self.service.stage_report("../run_valid", self.attempt, "part-a")

    def test_relocated_stored_path_remaps(self) -> None:
        old_root = Path(self.temp.name) / "old" / "run_valid"
        result = self.run / f"attempts/{self.attempt}/stages/part_b/execution_0001/result.json"
        self.manifest["run_directory"] = str(old_root)
        self.manifest["attempts"][self.attempt]["stages"]["part_b"]["executions"]["execution_0001"]["result_file"] = str(old_root / result.relative_to(self.run))
        self.write("manifest.json", json.dumps(self.manifest))
        self.assertEqual(self.service.stage_report("run_valid", self.attempt, "part-b").stage, "part_b")

    def test_missing_referenced_artifact_is_rejected(self) -> None:
        (self.run / "b/outliers.csv").unlink()
        with self.assertRaises(ArtifactError):
            self.service.stage_report("run_valid", self.attempt, "part-b")
    def test_health_endpoint(self) -> None:
        self.assertEqual(health()["status"], "ok")


if __name__ == "__main__":
    unittest.main()
