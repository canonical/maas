# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import MagicMock, Mock, patch

from macaroonbakery.bakery import Macaroon
import pytest
from starlette.requests import Request
from starlette.types import ASGIApp

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
from maasapiserver.common.middlewares.exceptions import ExceptionMiddleware
from maascommon.logging.security import AUTHN_AUTH_FAILED, AUTHZ_FAIL, SECURITY
from maasservicelayer.exceptions.catalog import (
    AlreadyExistsException,
    BadRequestException,
    BaseExceptionDetail,
    ConflictException,
    DischargeRequiredException,
    ForbiddenException,
    NotFoundException,
    PreconditionFailedException,
    ServiceUnavailableException,
    UnauthorizedException,
    ValidationException,
)


class TestExceptionMiddleware:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "exception_to_raise, expected_response",
        [
            (
                AlreadyExistsException(
                    details=[BaseExceptionDetail(type="type", message="msg")]
                ),
                ConflictResponse,
            ),
            (
                ConflictException(
                    details=[BaseExceptionDetail(type="type", message="msg")]
                ),
                ConflictResponse,
            ),
            (
                BadRequestException(
                    details=[BaseExceptionDetail(type="type", message="msg")]
                ),
                BadRequestResponse,
            ),
            (
                UnauthorizedException(
                    details=[BaseExceptionDetail(type="type", message="msg")]
                ),
                UnauthorizedResponse,
            ),
            (
                DischargeRequiredException(
                    macaroon=Macaroon(root_key="key", id="id"),
                    details=[BaseExceptionDetail(type="type", message="msg")],
                ),
                DischargeRequiredErrorResponse,
            ),
            (
                ForbiddenException(
                    details=[BaseExceptionDetail(type="type", message="msg")]
                ),
                ForbiddenResponse,
            ),
            (
                ValidationException(
                    details=[BaseExceptionDetail(type="type", message="msg")]
                ),
                ValidationErrorResponse,
            ),
            (
                NotFoundException(
                    details=[BaseExceptionDetail(type="type", message="msg")]
                ),
                NotFoundResponse,
            ),
            (
                PreconditionFailedException(
                    details=[BaseExceptionDetail(type="type", message="msg")]
                ),
                PreconditionFailedResponse,
            ),
            (
                ServiceUnavailableException(
                    details=[BaseExceptionDetail(type="type", message="msg")]
                ),
                ServiceUnavailableErrorResponse,
            ),
            (Exception("Unexpected error"), InternalServerErrorResponse),
        ],
    )
    async def test_exception_middleware(
        self, exception_to_raise, expected_response
    ):
        async def mock_call_next(request):
            raise exception_to_raise

        middleware = ExceptionMiddleware(app=Mock(ASGIApp))
        request = MagicMock(spec=Request)

        response = await middleware.dispatch(request, mock_call_next)
        assert isinstance(response, expected_response)


class TestExceptionLogging:
    @pytest.mark.asyncio
    async def test_unauthorized_exception(self):
        async def mock_call_next(request):
            raise UnauthorizedException(
                details=[BaseExceptionDetail(type="type", message="msg")]
            )

        middleware = ExceptionMiddleware(app=Mock(ASGIApp))
        request = MagicMock(spec=Request)
        with patch(
            "maasapiserver.common.middlewares.exceptions.logger"
        ) as mock_logger:
            await middleware.dispatch(request, mock_call_next)

        logging_call = mock_logger.info.call_args_list[0]

        assert logging_call.kwargs["type"] == SECURITY
        assert AUTHN_AUTH_FAILED in logging_call.args[0]

    async def test_forbidden_exception(self):
        async def mock_call_next(request):
            raise ForbiddenException(
                details=[BaseExceptionDetail(type="type", message="msg")]
            )

        middleware = ExceptionMiddleware(app=Mock(ASGIApp))
        request = MagicMock(spec=Request)
        with patch(
            "maasapiserver.common.middlewares.exceptions.logger"
        ) as mock_logger:
            await middleware.dispatch(request, mock_call_next)

        mock_logger.warn.assert_called_once_with(AUTHZ_FAIL, type=SECURITY)
