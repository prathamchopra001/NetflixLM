"""The error envelope of docs/api-contracts.md: {"error": {"code", "message", "details"}}."""

from collections.abc import Mapping
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

_CODES = {401: "UNAUTHORIZED", 403: "FORBIDDEN", 404: "NOT_FOUND"}


class ApiError(Exception):
    def __init__(
        self,
        status: int,
        code: str,
        message: str,
        details: Any = None,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        self.status, self.code, self.message = status, code, message
        self.details, self.headers = details, headers


def _envelope(
    status: int, code: str, message: str, details: Any, headers: Mapping[str, str] | None
) -> JSONResponse:
    body = {"error": {"code": code, "message": message, "details": details}}
    return JSONResponse(jsonable_encoder(body), status_code=status, headers=headers)


def install(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_: Request, e: ApiError) -> JSONResponse:
        return _envelope(e.status, e.code, e.message, e.details, e.headers)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, e: StarletteHTTPException) -> JSONResponse:
        code = _CODES.get(e.status_code, f"HTTP_{e.status_code}")
        return _envelope(e.status_code, code, str(e.detail), None, e.headers)

    @app.exception_handler(RequestValidationError)
    async def _invalid(_: Request, e: RequestValidationError) -> JSONResponse:
        return _envelope(400, "VALIDATION_FAILED", "Request invalid", e.errors(), None)
