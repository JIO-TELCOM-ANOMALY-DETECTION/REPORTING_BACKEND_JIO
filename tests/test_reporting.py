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
        series = self.write("inference/attempt_0001/inference_results/inv_1/series.csv", "kpi_name,series_key,circle,cluster,site_name,timestamp,actual,is_anomaly\nKPI,site,West,C1,Site A,2026-01-01T00:00:00+00:00,10,False\nKPI,site,West,C1,Site A,2026-01-01T00:15:00+00:00,11,True\nKPI,site,West,C1,Site A,2026-01-01T00:30:00+00:00,12,True\n")
        request_result = self.write("inference/attempt_0001/requests/request_000001/result.json", json.dumps({
            "run_id": "run_valid", "invocation_id": "inv_1", "model_type": "xgboost", "inference_days": 1,
            "inference_start": "2026-01-01T00:00:00+00:00", "inference_end_exclusive": "2026-01-02T00:00:00+00:00",
            "total_saved_series": 1, "completed_series": 1, "skipped_series_count": 0, "unmodelled_part_c_series": 0,
            "outputs": [{"kpi_name": "KPI", "series_key": "site", "identity": ["West", "C1", "Site A"], "result_file": str(series), "total_window_rows": 3, "scorable_rows": 3, "anomaly_count": 2, "anomaly_rate": 2/3}], "skipped_series": []
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
        self.assertEqual(report.summary["total_processed_rows"], 3)
        self.assertEqual(report.summary["total_anomalies"], 2)
        self.assertEqual(report.summary["normal_row_count"], 1)

    def test_inference_result_modes_pagination_sort_and_filters(self) -> None:
        result = self.service.inference_results("run_valid", "inv_1")
        self.assertEqual(result["pagination"]["total_items"], 2)
        self.assertTrue(all(row["is_anomaly"] == "True" for row in result["items"]))
        first = self.service.inference_results("run_valid", "inv_1", mode="all", page_size=2)
        self.assertEqual(first["pagination"]["total_items"], 3)
        self.assertTrue(first["pagination"]["has_next"])
        last = self.service.inference_results("run_valid", "inv_1", mode="all", page=2, page_size=2)
        self.assertEqual(len(last["items"]), 1)
        self.assertFalse(last["pagination"]["has_next"])
        empty = self.service.inference_results("run_valid", "inv_1", mode="all", page=3, page_size=2)
        self.assertEqual(empty["items"], [])
        filtered = self.service.inference_results("run_valid", "inv_1", mode="all", circle="west", site_name="Site A", kpi="KPI", start_time="2026-01-01T00:15:00+00:00", status="True", sort_by="actual", sort_order="desc")
        self.assertEqual([row["actual"] for row in filtered["items"]], ["12", "11"])
        self.assertEqual(self.service.inference_results("run_valid", "inv_1", start_time="2026-01-01T00:15")["pagination"]["total_items"], 2)
        self.assertEqual(self.service.inference_filter_options("run_valid", "inv_1")["circle"], ["West"])

    def test_inference_results_reject_invalid_inputs_and_artifacts(self) -> None:
        from app.core.exceptions import ValidationError
        for params in ({"page": 0}, {"page_size": 101}, {"mode": "wrong"}, {"sort_by": "../../secret"}, {"start_time": "bad"}):
            with self.assertRaises(ValidationError): self.service.inference_results("run_valid", "inv_1", **params)
        with self.assertRaises(NotFoundError): self.service.inference_results("run_valid", "missing")
        with self.assertRaises(NotFoundError): self.service.inference_results("missing_run", "inv_1")
        before = hashlib.sha256((self.run / "manifest.json").read_bytes()).hexdigest()
        self.service.inference_results("run_valid", "inv_1", mode="all")
        self.assertEqual(before, hashlib.sha256((self.run / "manifest.json").read_bytes()).hexdigest())
        csv_path = self.run / "inference/attempt_0001/inference_results/inv_1/series.csv"
        csv_path.write_text("", encoding="utf-8")
        with self.assertRaises(ArtifactError): self.service.inference_results("run_valid", "inv_1")
        csv_path.unlink()
        with self.assertRaises(ArtifactError): self.service.inference_results("run_valid", "inv_1")
        self.manifest["inference"]["invocations"]["inv_1"]["result_file"] = str(Path(self.temp.name) / "outside.json")
        self.write("manifest.json", json.dumps(self.manifest))
        with self.assertRaises(ArtifactError): self.service.inference_results("run_valid", "inv_1")

    def test_inference_results_reject_unfinished_invocations_and_output_traversal(self) -> None:
        self.manifest["inference"]["invocations"]["inv_1"]["status"] = "failed"
        self.write("manifest.json", json.dumps(self.manifest))
        with self.assertRaises(ArtifactError) as unfinished:
            self.service.inference_results("run_valid", "inv_1")
        self.assertEqual(unfinished.exception.error_code, "INFERENCE_NOT_COMPLETED")
        self.manifest["inference"]["invocations"]["inv_1"]["status"] = "completed"
        self.write("manifest.json", json.dumps(self.manifest))
        path = self.run / "inference/attempt_0001/requests/request_000001/result.json"
        snapshot = json.loads(path.read_text(encoding="utf-8"))
        snapshot["outputs"][0]["result_file"] = str(Path(self.temp.name) / "outside.csv")
        path.write_text(json.dumps(snapshot), encoding="utf-8")
        with self.assertRaises(ArtifactError) as unsafe:
            self.service.inference_results("run_valid", "inv_1")
        self.assertEqual(unsafe.exception.error_code, "UNSAFE_ARTIFACT_PATH")

    def test_malformed_outputs_return_artifact_error_instead_of_type_error(self) -> None:
        result_path = self.run / "inference/attempt_0001/requests/request_000001/result.json"
        payload = json.loads(result_path.read_text(encoding="utf-8"))
        payload["outputs"] = None
        result_path.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaises(ArtifactError) as report_error:
            self.service.inference_report("run_valid", "inv_1")
        self.assertEqual(report_error.exception.error_code, "MALFORMED_INFERENCE_OUTPUTS")
        with self.assertRaises(ArtifactError) as page_error:
            self.service.inference_results("run_valid", "inv_1")
        self.assertEqual(page_error.exception.error_code, "MALFORMED_INFERENCE_OUTPUTS")
        result_path.write_text("{", encoding="utf-8")
        with self.assertRaises(ArtifactError) as malformed_json:
            self.service.inference_results("run_valid", "inv_1")
        self.assertEqual(malformed_json.exception.error_code, "MALFORMED_JSON")

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
