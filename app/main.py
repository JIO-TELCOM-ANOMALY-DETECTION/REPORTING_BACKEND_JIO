from __future__ import annotations
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.api import router
from app.core.config import settings
from app.core.exceptions import ReportingError

app = FastAPI(title=settings.reporting_app_name, debug=settings.reporting_debug)
app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_allowed_origins), allow_credentials=False, allow_methods=["GET"], allow_headers=["*"])

@app.exception_handler(ReportingError)
async def reporting_error(_: Request, error: ReportingError) -> JSONResponse:
    return JSONResponse(status_code=error.status_code, content={"error": {"code": error.error_code, "message": str(error)}})

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "reporting_backend"}

app.include_router(router, prefix=settings.reporting_api_prefix)
