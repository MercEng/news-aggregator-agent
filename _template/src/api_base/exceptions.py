"""Domain exceptions and the handlers that turn them into HTTP responses.

Services raise these. Routers and repositories never do: repositories return
`None`, and routers let the handlers registered here do the translation. That is
what keeps `HTTPException` out of the service layer.

Every error response has the same shape:

    {"error": {"code": "not_found", "message": "...", "details": {...}}}
"""

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class DomainError(Exception):
    """Base class for errors that carry a meaning, not a status code."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    code: str = "internal_error"

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class NotFoundError(DomainError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"


class ConflictError(DomainError):
    status_code = status.HTTP_409_CONFLICT
    code = "conflict"


class ValidationError(DomainError):
    """A business rule rejected the input; not a schema/shape problem."""

    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    code = "validation_error"


def error_body(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details or {}}}


def register_exception_handlers(app: FastAPI) -> None:
    """Attach handlers so every error leaves the app in the same envelope."""

    @app.exception_handler(DomainError)
    async def _domain_error(_: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(exc.code, exc.message, exc.details),
        )

    @app.exception_handler(RequestValidationError)
    async def _request_validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=error_body(
                "validation_error",
                "Request validation failed.",
                {"errors": jsonable_errors(exc)},
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_exception(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(
                _CODES_BY_STATUS.get(exc.status_code, "http_error"), str(exc.detail)
            ),
            headers=getattr(exc, "headers", None),
        )


def jsonable_errors(exc: RequestValidationError) -> list[dict[str, Any]]:
    """Drop the non-serialisable `ctx` payload pydantic attaches to some errors."""
    return [{k: v for k, v in error.items() if k != "ctx"} for error in exc.errors()]


_CODES_BY_STATUS = {
    status.HTTP_400_BAD_REQUEST: "bad_request",
    status.HTTP_401_UNAUTHORIZED: "unauthorized",
    status.HTTP_403_FORBIDDEN: "forbidden",
    status.HTTP_404_NOT_FOUND: "not_found",
    status.HTTP_405_METHOD_NOT_ALLOWED: "method_not_allowed",
    status.HTTP_409_CONFLICT: "conflict",
    status.HTTP_500_INTERNAL_SERVER_ERROR: "internal_error",
    status.HTTP_503_SERVICE_UNAVAILABLE: "service_unavailable",
}
