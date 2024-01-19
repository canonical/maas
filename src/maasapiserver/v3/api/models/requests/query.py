from typing import NamedTuple

from fastapi import Query

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 1000


class PaginationParams(NamedTuple):
    """Pagination parameters."""

    page: int
    size: int


async def pagination_params(
    page: int = Query(default=1, gte=1),
    size: int = Query(default=DEFAULT_PAGE_SIZE, lte=MAX_PAGE_SIZE, gte=1),
) -> PaginationParams:
    """Return pagination parameters."""
    return PaginationParams(page=page, size=size)
