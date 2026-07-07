"""Global exception handlers for the API.

Provides consistent error responses across all endpoints
with proper HTTP status codes and structured error payloads.
"""

from typing import Any, Optional

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError as PydanticValidationError

from regulaforge.common.exceptions import (
    AuthenticationError,
    AuthorizationError,
    DuplicateEntityError,
    EntityNotFoundError,
    RateLimitError,
    RepositoryError,
    ValidationError as AppValidationError,
)
from regulaforge.config.logging import get_logger

logger = get_logger(__name__)


class ErrorResponse:
    """Standard error response structure."""

    def __init__(
        self,
        code: str,
        message: str,
        details: Optional[Any] = None,
        status_code: int = 500,
    ) -> None:
        self.code = code
        self.message = message
        self.details = details
        self.status_code = status_code

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "error": {
                "code": self.code,
                "message": self.message,
            }
        }
        if self.details:
            result["error"]["details"] = self.details
        return result


def register_error_handlers(app: FastAPI) -> None:
    """Register global exception handlers on the FastAPI app."""

    @app.exception_handler(EntityNotFoundError)
    async def entity_not_found_handler(
        request: Request, exc: EntityNotFoundError
    ) -> JSONResponse:
        logger.warning(
            "Entity not found: %s %s at %s",
            exc.entity_type, exc.entity_id, request.url.path,
        )
        error = ErrorResponse(
            code="NOT_FOUND",
            message=str(exc),
            status_code=404,
        )
        return JSONResponse(
            status_code=404,
            content=error.to_dict(),
        )

    @app.exception_handler(DuplicateEntityError)
    async def duplicate_entity_handler(
        request: Request, exc: DuplicateEntityError
    ) -> JSONResponse:
        logger.warning(
            "Duplicate entity: %s %s=%s at %s",
            exc.entity_type, exc.field, exc.value, request.url.path,
        )
        error = ErrorResponse(
            code="DUPLICATE_ENTITY",
            message=str(exc),
            status_code=409,
        )
        return JSONResponse(
            status_code=409,
            content=error.to_dict(),
        )

    @app.exception_handler(RepositoryError)
    async def repository_error_handler(
        request: Request, exc: RepositoryError
    ) -> JSONResponse:
        logger.error(
            "Repository error at %s: %s",
            request.url.path, exc, exc_info=True,
        )
        error = ErrorResponse(
            code="DATABASE_ERROR",
            message="An internal database error occurred. Please try again later.",
            status_code=500,
        )
        return JSONResponse(
            status_code=500,
            content=error.to_dict(),
        )

    @app.exception_handler(AuthenticationError)
    async def authentication_error_handler(
        request: Request, exc: AuthenticationError
    ) -> JSONResponse:
        logger.warning(
            "Authentication failed at %s: %s",
            request.url.path, exc,
        )
        error = ErrorResponse(
            code=exc.code,
            message=str(exc),
            status_code=401,
        )
        return JSONResponse(
            status_code=401,
            content=error.to_dict(),
            headers={"WWW-Authenticate": "Bearer"},
        )

    @app.exception_handler(AuthorizationError)
    async def authorization_error_handler(
        request: Request, exc: AuthorizationError
    ) -> JSONResponse:
        logger.warning(
            "Authorization denied at %s: %s",
            request.url.path, exc,
        )
        error = ErrorResponse(
            code=exc.code,
            message=str(exc),
            status_code=403,
        )
        return JSONResponse(
            status_code=403,
            content=error.to_dict(),
        )

    @app.exception_handler(RateLimitError)
    async def rate_limit_error_handler(
        request: Request, exc: RateLimitError
    ) -> JSONResponse:
        logger.warning(
            "Rate limit exceeded at %s: %s",
            request.url.path, exc,
        )
        error = ErrorResponse(
            code=exc.code,
            message=str(exc),
            status_code=429,
        )
        return JSONResponse(
            status_code=429,
            content=error.to_dict(),
            headers={"Retry-After": str(exc.retry_after)},
        )

    @app.exception_handler(AppValidationError)
    async def app_validation_error_handler(
        request: Request, exc: AppValidationError
    ) -> JSONResponse:
        logger.warning(
            "Validation error at %s: %s",
            request.url.path, exc,
        )
        error = ErrorResponse(
            code=exc.code,
            message=str(exc),
            details=exc.details,
            status_code=422,
        )
        return JSONResponse(
            status_code=422,
            content=error.to_dict(),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        errors = []
        for err in exc.errors():
            errors.append({
                "field": " -> ".join(str(part) for part in err.get("loc", [])),
                "message": err.get("msg", ""),
                "type": err.get("type", ""),
            })

        logger.warning(
            "Validation error at %s: %s",
            request.url.path, errors,
        )
        error = ErrorResponse(
            code="VALIDATION_ERROR",
            message="Request validation failed",
            details=errors,
            status_code=422,
        )
        return JSONResponse(
            status_code=422,
            content=error.to_dict(),
        )

    @app.exception_handler(PydanticValidationError)
    async def pydantic_validation_handler(
        _request: Request, exc: PydanticValidationError
    ) -> JSONResponse:
        error = ErrorResponse(
            code="VALIDATION_ERROR",
            message="Data validation failed",
            details=exc.errors(),
            status_code=422,
        )
        return JSONResponse(
            status_code=422,
            content=error.to_dict(),
        )

    @app.exception_handler(ValueError)
    async def value_error_handler(
        request: Request, exc: ValueError
    ) -> JSONResponse:
        logger.warning(
            "Value error at %s: %s",
            request.url.path, exc,
        )
        error = ErrorResponse(
            code="BAD_REQUEST",
            message=str(exc),
            status_code=400,
        )
        return JSONResponse(
            status_code=400,
            content=error.to_dict(),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        logger.error(
            "Unhandled exception at %s: %s",
            request.url.path, exc, exc_info=True,
        )
        error = ErrorResponse(
            code="INTERNAL_ERROR",
            message="An unexpected internal error occurred. Please contact support.",
            status_code=500,
        )
        return JSONResponse(
            status_code=500,
            content=error.to_dict(),
        )
