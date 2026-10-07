from __future__ import annotations
from fastapi import APIRouter, Depends
from app.services import ReportService

router = APIRouter(prefix="/reports", tags=["reports"])
_service = ReportService()

def service() -> ReportService:
    return _service

@router.get("/runs/{run_id}")
def run(run_id: str, reports: ReportService = Depends(service)):
    return reports.run(run_id)

@router.get("/runs/{run_id}/attempts/{attempt_id}")
def attempt(run_id: str, attempt_id: str, reports: ReportService = Depends(service)):
    return reports.attempt(run_id, attempt_id)

@router.get("/runs/{run_id}/attempts/{attempt_id}/stages/{stage}")
def stage(run_id: str, attempt_id: str, stage: str, reports: ReportService = Depends(service)):
    return reports.stage_report(run_id, attempt_id, stage)

@router.get("/runs/{run_id}/inference")
def inference_list(run_id: str, reports: ReportService = Depends(service)):
    return reports.inference_list(run_id)

@router.get("/runs/{run_id}/inference/{invocation_id}")
def inference_report(run_id: str, invocation_id: str, reports: ReportService = Depends(service)):
    return reports.inference_report(run_id, invocation_id)

@router.get("/runs/{run_id}/inference/{invocation_id}/results")
def inference_results(run_id: str, invocation_id: str, mode: str = "anomalies", page: int = 1, page_size: int = 50,
                      composite_id: str | None = None, circle: str | None = None, cluster: str | None = None,
                      site_name: str | None = None, kpi: str | None = None, status: str | None = None,
                      start_time: str | None = None, end_time: str | None = None, sort_by: str = "timestamp",
                      sort_order: str = "asc", reports: ReportService = Depends(service)):
    return reports.inference_results(run_id, invocation_id, mode=mode, page=page, page_size=page_size,
        composite_id=composite_id, circle=circle, cluster=cluster, site_name=site_name, kpi=kpi,
        status=status, start_time=start_time, end_time=end_time, sort_by=sort_by, sort_order=sort_order)

@router.get("/runs/{run_id}/inference/{invocation_id}/filter-options")
def inference_filter_options(run_id: str, invocation_id: str, reports: ReportService = Depends(service)):
    return reports.inference_filter_options(run_id, invocation_id)
