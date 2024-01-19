from fastapi import Query
from pydantic import BaseModel, Field

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 1000


class PaginationParams(BaseModel):
    """Pagination parameters."""

    page: int = Field(Query(default=1, ge=1))
    size: int = Field(Query(default=DEFAULT_PAGE_SIZE, le=MAX_PAGE_SIZE, ge=1))
