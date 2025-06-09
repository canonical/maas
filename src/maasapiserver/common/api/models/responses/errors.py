import json
from typing import Optional

from fastapi.encoders import jsonable_encoder
from macaroonbakery import httpbakery
from macaroonbakery.bakery import Macaroon
from pydantic import BaseModel
from starlette import status
from starlette.responses import JSONResponse

from maasservicelayer.exceptions.catalog import BaseExceptionDetail


class ErrorBodyResponse(BaseModel):
    kind = "Error"
    code: int
    message: str
    details: Optional[list[BaseExceptionDetail]] = None


class BadRequestBodyResponse(ErrorBodyResponse):
    code: int = status.HTTP_400_BAD_REQUEST
    message: str = "Bad request."


class BadRequestResponse(JSONResponse):
    def __init__(self, details: Optional[list[BaseExceptionDetail]]):
        super().__init__(
            content=jsonable_encoder(BadRequestBodyResponse(details=details)),
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class UnauthorizedBodyResponse(ErrorBodyResponse):
    code: int = status.HTTP_401_UNAUTHORIZED
    message: str = "Unauthorized."


class UnauthorizedResponse(JSONResponse):
    def __init__(self, details: Optional[list[BaseExceptionDetail]]):
        super().__init__(
            content=jsonable_encoder(
                UnauthorizedBodyResponse(details=details)
            ),
            status_code=status.HTTP_401_UNAUTHORIZED,
        )


class ForbiddenBodyResponse(ErrorBodyResponse):
    code: int = status.HTTP_403_FORBIDDEN
    message: str = "Forbidden."


class ForbiddenResponse(JSONResponse):
    def __init__(self, details: Optional[list[BaseExceptionDetail]]):
        super().__init__(
            content=jsonable_encoder(ForbiddenBodyResponse(details=details)),
            status_code=status.HTTP_403_FORBIDDEN,
        )


class NotFoundBodyResponse(ErrorBodyResponse):
    code: int = status.HTTP_404_NOT_FOUND
    message: str = "Entity not found."


class NotFoundResponse(JSONResponse):
    def __init__(self):
        super().__init__(
            content=jsonable_encoder(NotFoundBodyResponse()),
            status_code=status.HTTP_404_NOT_FOUND,
        )


class ConflictBodyResponse(ErrorBodyResponse):
    code: int = status.HTTP_409_CONFLICT
    message: str = "The request could not be completed due to a conflict with an existing resource."


class ConflictResponse(JSONResponse):
    def __init__(self, details: Optional[list[BaseExceptionDetail]]):
        super().__init__(
            content=jsonable_encoder(ConflictBodyResponse(details=details)),
            status_code=status.HTTP_409_CONFLICT,
        )


class PreconditionFailedBodyResponse(ErrorBodyResponse):
    code: int = status.HTTP_412_PRECONDITION_FAILED
    message: str = "A precondition has failed."


class PreconditionFailedResponse(JSONResponse):
    def __init__(self, details: Optional[list[BaseExceptionDetail]]):
        super().__init__(
            content=jsonable_encoder(
                PreconditionFailedBodyResponse(details=details)
            ),
            status_code=status.HTTP_412_PRECONDITION_FAILED,
        )


class ValidationErrorBodyResponse(ErrorBodyResponse):
    code: int = status.HTTP_422_UNPROCESSABLE_ENTITY
    message: str = "Failed to validate the request."


class ValidationErrorResponse(JSONResponse):
    def __init__(self, details: Optional[list[BaseExceptionDetail]]):
        super().__init__(
            content=jsonable_encoder(
                ValidationErrorBodyResponse(details=details)
            ),
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )


class InternalServerErrorBodyResponse(ErrorBodyResponse):
    code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    message: str = "Unexpected internal server error. Please check the server logs for more details."


class InternalServerErrorResponse(JSONResponse):
    def __init__(self):
        super().__init__(
            content=jsonable_encoder(InternalServerErrorBodyResponse()),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


class ServiceUnavailableErrorBodyResponse(ErrorBodyResponse):
    code: int = status.HTTP_503_SERVICE_UNAVAILABLE
    message: str = "The service is not available. Please check the server logs for more details."


class ServiceUnavailableErrorResponse(JSONResponse):
    def __init__(self, details: Optional[list[BaseExceptionDetail]]):
        super().__init__(
            content=jsonable_encoder(
                ServiceUnavailableErrorBodyResponse(details=details)
            ),
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


class DischargeRequiredErrorResponse(JSONResponse):
    def __init__(self, macaroon: Macaroon):
        content, headers = httpbakery.discharge_required_response(
            macaroon=macaroon, path="/", cookie_suffix_name="maas"
        )
        super().__init__(
            content=json.loads(content.decode("utf-8")),
            status_code=status.HTTP_401_UNAUTHORIZED,
            headers=headers,
        )
