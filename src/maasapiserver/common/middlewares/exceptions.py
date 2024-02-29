import logging
from typing import Awaitable, Callable

from fastapi import Request, Response
from fastapi.exceptions import RequestValidationError
from starlette.middleware.base import BaseHTTPMiddleware

from maasapiserver.common.api.models.responses.errors import (
    BadRequestResponse,
    ConflictResponse,
    InternalServerErrorResponse,
    PreconditionFailedResponse,
    ValidationErrorResponse,
)
from maasapiserver.common.models.exceptions import (
    AlreadyExistsException,
    BadRequestException,
    BaseExceptionDetail,
    PreconditionFailedException,
)

logger = logging.getLogger(__name__)


class ExceptionHandlers:
    @classmethod
    async def validation_exception_handler(
        cls, request: Request, exc: RequestValidationError
    ):
        return ValidationErrorResponse(
            details=[
                BaseExceptionDetail(type=error["type"], message=error["msg"])
                for error in exc.errors()
            ]
        )


class ExceptionMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        try:
            return await call_next(request)
        except AlreadyExistsException as e:
            logger.debug(e)
            return ConflictResponse(details=e.details)
        except BadRequestException as e:
            logger.debug(e)
            return BadRequestResponse(e.details)
        except PreconditionFailedException as e:
            logger.debug(e)
            return PreconditionFailedResponse(e.details)
        except Exception as e:
            logger.exception(e)
            return InternalServerErrorResponse()
