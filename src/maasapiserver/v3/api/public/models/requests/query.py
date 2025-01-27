# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from fastapi import Query
from pydantic import BaseModel, Field

DEFAULT_PAGE = 1
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 1000


class PaginationParams(BaseModel):
    """Token-based pagination parameters."""

    page: int = Field(Query(default=DEFAULT_PAGE))
    size: int = Field(Query(default=DEFAULT_PAGE_SIZE, le=MAX_PAGE_SIZE, ge=1))

    def to_next_href_format(self) -> str:
        return f"page={self.page + 1}&size={self.size}"
