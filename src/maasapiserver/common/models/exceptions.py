from pydantic import BaseModel

UNIQUE_CONSTRAINT_VIOLATION_TYPE = "UniqueConstraintViolation"


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
