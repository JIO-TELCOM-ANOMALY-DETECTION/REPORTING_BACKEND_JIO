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
