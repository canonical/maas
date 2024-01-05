from typing import Any, Optional

from pydantic import BaseModel
from starlette import status


class ErrorResponse(BaseModel):
    code: int
    message: str
    details: Optional[Any] = None


class InternalServerErrorResponse(ErrorResponse):
    code = status.HTTP_500_INTERNAL_SERVER_ERROR
    message = "Unexpected internal server error. Please check the server logs for more details."


class ValidationErrorResponse(ErrorResponse):
    code = status.HTTP_422_UNPROCESSABLE_ENTITY
    message = "Failed to validate the request."
