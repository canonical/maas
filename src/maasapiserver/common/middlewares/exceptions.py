import logging
from typing import Awaitable, Callable

from fastapi import Request, Response
from fastapi.exceptions import RequestValidationError
from starlette.middleware.base import BaseHTTPMiddleware

from maasapiserver.common.api.models.responses.errors import (
    InternalServerErrorResponse,
    ValidationErrorResponse,
)

logger = logging.getLogger(__name__)


class ExceptionHandlers:
    @classmethod
    async def validation_exception_handler(
        cls, request: Request, exc: RequestValidationError
    ):
        return ValidationErrorResponse(details=exc.errors())


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
            return InternalServerErrorResponse()
