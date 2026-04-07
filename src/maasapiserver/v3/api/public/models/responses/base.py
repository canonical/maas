# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Any, Dict, Generic, Sequence, TypeVar

from fastapi.openapi.models import Header as OpenApiHeader
from fastapi.openapi.models import Schema
from pydantic import BaseModel, ConfigDict, Field


class BaseHref(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    href: str


class BaseHrefWithId(BaseHref):
    id: str | None = None
    name: str | None = None


class BaseHal(BaseModel):
    self: BaseHref = Field(alias="self")


HAL = TypeVar("HAL", bound=BaseHal)


class HalResponse(BaseModel, Generic[HAL]):
    """
    Base HAL response class that every response object must extend. The response object will look like
    {
        '_links': {
            'self': {'href': '/api/v3/'}
            },
        '_embedded': {}
    }
    """

    model_config = ConfigDict(populate_by_name=True)

    hal_links: HAL | None = Field(default=None, alias="_links")
    hal_embedded: Dict[str, Any] | None = Field(
        default=None, alias="_embedded"
    )


T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """
    Base class for offset-paginated responses.
    Derived classes should overwrite the items property
    """

    model_config = ConfigDict(populate_by_name=True)

    items: Sequence[T]
    total: int
    next: str | None = Field(default=None)


OPENAPI_ETAG_HEADER = OpenApiHeader(
    description="The ETag for the resource", schema=Schema(type="string")
)
