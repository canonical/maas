from pydantic import BaseModel


class BaseExceptionDetail(BaseModel):
    type: str
    message: str


class BaseException(Exception):
    def __init__(self, message: str, details: list[BaseExceptionDetail]):
        super().__init__(message)
        self.details = details


class AlreadyExistsException(BaseException):
    def __init__(self, details: list[BaseExceptionDetail]):
        super().__init__(
            "An instance with the same unique attributes already exists.",
            details,
        )


class BadRequestException(BaseException):
    def __init__(self, details: list[BaseExceptionDetail]):
        super().__init__(
            "Invalid request. Please check the provided data.", details
        )


class PreconditionFailedException(BaseException):
    def __init__(self, details: list[BaseExceptionDetail]):
        super().__init__("A precondition has failed.", details)
