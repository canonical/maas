# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Any, Awaitable, Callable

from fastapi.exceptions import RequestValidationError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
import structlog

from maasapiserver.common.api.models.responses.errors import (
    BadGatewayErrorResponse,
    BadRequestResponse,
    ConflictResponse,
    DischargeRequiredErrorResponse,
    ForbiddenResponse,
    InsufficientStorageErrorResponse,
    InternalServerErrorResponse,
    NotFoundResponse,
    PreconditionFailedResponse,
    ServiceUnavailableErrorResponse,
    UnauthorizedResponse,
    ValidationErrorResponse,
)
from maascommon.logging.security import AUTHN_AUTH_FAILED, AUTHZ_FAIL, SECURITY
from maasservicelayer.exceptions.catalog import (
    AlreadyExistsException,
    BadGatewayException,
    BadRequestException,
    BaseExceptionDetail,
    ConflictException,
    DischargeRequiredException,
    ForbiddenException,
    InsufficientStorageException,
    NotFoundException,
    PreconditionFailedException,
    ServiceUnavailableException,
    UnauthorizedException,
    ValidationException,
)

logger = structlog.getLogger(__name__)


def _build_json_path(loc: list[Any]) -> str:
    elements: list[str] = []
    for elem in loc:
        if isinstance(elem, int) and elements:
            elements.append(f"{elements.pop()}[{elem}]")
        else:
            elements.append(str(elem))
    return ".".join(elements)


class ExceptionHandlers:
    @classmethod
    async def validation_exception_handler(
        cls, request: Request, exc: RequestValidationError
    ):
        """
        FastAPI raises a RequestValidationError for any validation error that
        occurs during the request processing, from JSON decoder errors to pydantic
        field/model validation issues.

        Each error in the `exc.errors()` is an instance of `pydantic_core.ErrorDetails`
        that has the following attributes:
            type: the name of the error
            msg: the description of the error
            loc: a tuple explaining where the failure happened. The first item
              could be one of: path, query, header, cookie, body. The next items
              specify the path of the wrong field. E.g. if the passed json is in
              the form `{"foo": {"bar": [0, "wrong-field"]}}` the loc parameter
              would be something like `(<location>, "foo", "bar", 1)`.
            ctx: additional context regarding the input data.
        """
        details: list[BaseExceptionDetail] = []
        for err in exc.errors():
            d = BaseExceptionDetail(
                type=err["type"],
                message=err["msg"],
                location=err["loc"][0],
                field=_build_json_path(err["loc"][1:]),
            )
            if ctx := err.get("ctx", None):
                if loc := ctx.get("loc", None):
                    d.field = loc
                if msg := ctx.get("reason", None):
                    d.message = msg

            details.append(d)

        return ValidationErrorResponse(details=details)


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
        except BadGatewayException as e:
            logger.error(e)
            return BadGatewayErrorResponse(details=e.details)
        except ConflictException as e:
            logger.debug(e)
            return ConflictResponse(details=e.details)
        except BadRequestException as e:
            logger.debug(e)
            return BadRequestResponse(e.details)
        except UnauthorizedException as e:
            logger.debug(e)
            logger.info(
                AUTHN_AUTH_FAILED,
                type=SECURITY,
            )
            return UnauthorizedResponse(e.details)
        except DischargeRequiredException as e:
            logger.debug(e)
            return DischargeRequiredErrorResponse(e.macaroon)
        except ForbiddenException as e:
            logger.debug(e)
            logger.warn(AUTHZ_FAIL, type=SECURITY)
            return ForbiddenResponse(e.details)
        except ValidationException as e:
            logger.debug(e)
            return ValidationErrorResponse(e.details)
        except NotFoundException as e:
            logger.debug(e)
            return NotFoundResponse(e.details)
        except PreconditionFailedException as e:
            logger.debug(e)
            return PreconditionFailedResponse(e.details)
        except InsufficientStorageException as e:
            logger.error(e)
            return InsufficientStorageErrorResponse(e.details)
        except ServiceUnavailableException as e:
            logger.error(e)
            return ServiceUnavailableErrorResponse(e.details)
        except Exception as e:
            logger.exception(e)
            return InternalServerErrorResponse()
