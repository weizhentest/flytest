from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.responses import error_response


class AppError(Exception):
    def __init__(self, message: str, status_code: int = 400, errors: Any = None) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.errors = errors


async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response(message=exc.message, code=exc.status_code, errors=exc.errors),
    )
