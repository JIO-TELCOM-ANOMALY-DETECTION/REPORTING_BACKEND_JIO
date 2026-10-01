from __future__ import annotations


class ReportingError(Exception):
    status_code = 500
    error_code = "REPORTING_INTERNAL_ERROR"

    def __init__(self, message: str, *, error_code: str | None = None) -> None:
        super().__init__(message)
        if error_code:
            self.error_code = error_code


class NotFoundError(ReportingError):
    status_code = 404


class ValidationError(ReportingError):
    status_code = 422


class ConflictError(ReportingError):
    status_code = 409


class ArtifactError(ReportingError):
    status_code = 422
