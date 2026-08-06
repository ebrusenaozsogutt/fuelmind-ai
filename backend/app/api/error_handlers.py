"""Central HTTP exception mappings for domain errors."""

import logging

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from sqlalchemy.exc import IntegrityError

from app.exceptions import (
    AuthenticationError,
    AuthorizationError,
    BusinessRuleError,
    ConflictError,
    NotFoundError,
)

logger = logging.getLogger(__name__)


def error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    details: object = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """Return the stable, client-safe API error envelope."""

    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder(
            {
                "error": {
                    "code": code,
                    "message": message,
                    "details": details,
                }
            }
        ),
        headers=headers,
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register stable, client-safe exception responses."""

    def domain_handler(status_code: int, code: str):
        async def handler(_: Request, exc: Exception) -> JSONResponse:
            return error_response(
                status_code=status_code,
                code=code,
                message=str(exc),
            )

        return handler

    app.add_exception_handler(
        NotFoundError,
        domain_handler(status.HTTP_404_NOT_FOUND, "RESOURCE_NOT_FOUND"),
    )
    app.add_exception_handler(
        ConflictError,
        domain_handler(status.HTTP_409_CONFLICT, "RESOURCE_CONFLICT"),
    )
    app.add_exception_handler(
        BusinessRuleError,
        domain_handler(status.HTTP_400_BAD_REQUEST, "BUSINESS_RULE_VIOLATION"),
    )
    app.add_exception_handler(
        AuthenticationError,
        domain_handler(status.HTTP_401_UNAUTHORIZED, "AUTHENTICATION_FAILED"),
    )
    app.add_exception_handler(
        AuthorizationError,
        domain_handler(status.HTTP_403_FORBIDDEN, "AUTHORIZATION_FAILED"),
    )

    @app.exception_handler(IntegrityError)
    async def integrity_error_handler(_: Request, exc: IntegrityError) -> JSONResponse:
        logger.warning("Database integrity constraint violated: %s", exc.__class__.__name__)
        return error_response(
            status_code=status.HTTP_409_CONFLICT,
            code="RESOURCE_CONFLICT",
            message="A conflicting record already exists.",
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
        code_by_status = {
            status.HTTP_400_BAD_REQUEST: "BAD_REQUEST",
            status.HTTP_401_UNAUTHORIZED: "UNAUTHORIZED",
            status.HTTP_403_FORBIDDEN: "FORBIDDEN",
            status.HTTP_404_NOT_FOUND: "RESOURCE_NOT_FOUND",
            status.HTTP_409_CONFLICT: "RESOURCE_CONFLICT",
        }
        return error_response(
            status_code=exc.status_code,
            code=code_by_status.get(exc.status_code, "HTTP_ERROR"),
            message=str(exc.detail),
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        _: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return error_response(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code="VALIDATION_ERROR",
            message="Request validation failed.",
            details=exc.errors(),
        )

    @app.exception_handler(Exception)
    async def unexpected_error_handler(request: Request, _: Exception) -> JSONResponse:
        logger.exception("Unhandled API error for %s", request.url.path)
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="INTERNAL_SERVER_ERROR",
            message="Internal server error.",
        )
