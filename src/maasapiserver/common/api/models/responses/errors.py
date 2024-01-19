from typing import Any, Optional

from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from starlette import status
from starlette.responses import JSONResponse


class ErrorBodyResponse(BaseModel):
    kind = "Error"
    code: int
    message: str
    details: Optional[Any] = None


class InternalServerErrorBodyResponse(ErrorBodyResponse):
    code = status.HTTP_500_INTERNAL_SERVER_ERROR
    message = "Unexpected internal server error. Please check the server logs for more details."


class InternalServerErrorResponse(JSONResponse):
    def __init__(self):
        super().__init__(
            content=jsonable_encoder(InternalServerErrorBodyResponse()),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


class ValidationErrorBodyResponse(ErrorBodyResponse):
    code = status.HTTP_422_UNPROCESSABLE_ENTITY
    message = "Failed to validate the request."


class ValidationErrorResponse(JSONResponse):
    def __init__(self, details: Optional[Any]):
        super().__init__(
            content=jsonable_encoder(
                ValidationErrorBodyResponse(details=details)
            ),
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )


class NotFoundBodyResponse(ErrorBodyResponse):
    code = status.HTTP_404_NOT_FOUND
    message = "Entity not found."


class NotFoundResponse(JSONResponse):
    def __init__(self):
        super().__init__(
            content=jsonable_encoder(NotFoundBodyResponse()),
            status_code=status.HTTP_404_NOT_FOUND,
        )
