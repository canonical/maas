# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Optional

from fastapi import Query
from pydantic import BaseModel, Field

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 1000


class TokenPaginationParams(BaseModel):
    """Token-based pagination parameters."""

    token: Optional[str] = Field(Query(default=None))
    size: int = Field(Query(default=DEFAULT_PAGE_SIZE, le=MAX_PAGE_SIZE, ge=1))

    @classmethod
    def to_href_format(cls, token, size) -> str:
        return f"token={token}&size={size}"
