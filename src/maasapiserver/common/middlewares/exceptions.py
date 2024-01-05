import logging
from typing import Awaitable, Callable

from fastapi import Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from starlette import status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from ..api.models.responses.errors import (
    InternalServerErrorResponse,
    ValidationErrorResponse,
)

logger = logging.getLogger(__name__)


class ExceptionHandlers:
    @classmethod
    async def validation_exception_handler(
        cls, request: Request, exc: RequestValidationError
    ):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=jsonable_encoder(
                ValidationErrorResponse(details=exc.errors())
            ),
        )


class ExceptionMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        try:
            return await call_next(request)
        except Exception as e:
            logger.exception(e)
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content=jsonable_encoder(InternalServerErrorResponse()),
            )
