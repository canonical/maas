#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from macaroonbakery.bakery import Macaroon
from pydantic import BaseModel


class BaseExceptionDetail(BaseModel):
    type: str
    message: str


class BaseException(Exception):
    def __init__(
        self, message: str, details: list[BaseExceptionDetail] | None = None
    ):
        super().__init__(message)
        self.details = details


class AlreadyExistsException(BaseException):
    def __init__(self, details: list[BaseExceptionDetail] | None = None):
        super().__init__(
            "An instance with the same unique attributes already exists.",
            details,
        )


class BadRequestException(BaseException):
    def __init__(self, details: list[BaseExceptionDetail] | None = None):
        super().__init__(
            "Invalid request. Please check the provided data.", details
        )


class NotFoundException(BaseException):
    def __init__(self, details: list[BaseExceptionDetail] | None = None):
        super().__init__("The requested resource was not found.", details)


class UnauthorizedException(BaseException):
    def __init__(self, details: list[BaseExceptionDetail] | None = None):
        super().__init__("Not authenticated.", details)


class ForbiddenException(BaseException):
    def __init__(self, details: list[BaseExceptionDetail] | None = None):
        super().__init__("Forbidden.", details)


class PreconditionFailedException(BaseException):
    def __init__(self, details: list[BaseExceptionDetail] | None = None):
        super().__init__("A precondition has failed.", details)


class ServiceUnavailableException(BaseException):
    def __init__(self, details: list[BaseExceptionDetail] | None = None):
        super().__init__("The service is not available.", details)


class DischargeRequiredException(BaseException):
    def __init__(
        self,
        macaroon: Macaroon,
        details: list[BaseExceptionDetail] | None = None,
    ):
        super().__init__("Macaroon discharge required.", details)
        self.macaroon = macaroon
