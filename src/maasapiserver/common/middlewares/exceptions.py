from typing import Awaitable, Callable

from fastapi.exceptions import RequestValidationError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
import structlog

from maasapiserver.common.api.models.responses.errors import (
    BadRequestResponse,
    ConflictResponse,
    DischargeRequiredErrorResponse,
    ForbiddenResponse,
    InternalServerErrorResponse,
    NotFoundResponse,
    PreconditionFailedResponse,
    ServiceUnavailableErrorResponse,
    UnauthorizedResponse,
    ValidationErrorResponse,
)
from maasservicelayer.exceptions.catalog import (
    AlreadyExistsException,
    BadRequestException,
    BaseExceptionDetail,
    DischargeRequiredException,
    ForbiddenException,
    NotFoundException,
    PreconditionFailedException,
    ServiceUnavailableException,
    UnauthorizedException,
)

logger = structlog.getLogger(__name__)


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
        except UnauthorizedException as e:
            logger.debug(e)
            return UnauthorizedResponse(e.details)
        except DischargeRequiredException as e:
            logger.debug(e)
            return DischargeRequiredErrorResponse(e.macaroon)
        except ForbiddenException as e:
            logger.debug(e)
            return ForbiddenResponse(e.details)
        except NotFoundException as e:
            logger.debug(e)
            return NotFoundResponse()
        except PreconditionFailedException as e:
            logger.debug(e)
            return PreconditionFailedResponse(e.details)
        except ServiceUnavailableException as e:
            logger.error(e)
            return ServiceUnavailableErrorResponse(e.details)
        except Exception as e:
            logger.exception(e)
            return InternalServerErrorResponse()
