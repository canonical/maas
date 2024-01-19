from typing import Any, Dict, Generic, Optional, Sequence, TypeVar

from pydantic import BaseModel, Field
from pydantic.generics import GenericModel


class BaseHref(BaseModel):
    href: str


class BaseHrefWithId(BaseHref):
    id: Optional[str] = None
    name: Optional[str] = None


class BaseHal(BaseModel):
    self: BaseHref = Field(alias="self")


HAL = TypeVar("HAL", bound=BaseHal)


class HalResponse(GenericModel, Generic[HAL]):
    """
    Base HAL response class that every response object must extend. The response object will look like
    {
        '_links': {
            'self': {'href': '/api/v3/'}
            },
        '_embedded': {}
    }
    """

    hal_links: Optional[HAL] = Field(default=None, alias="_links")
    hal_embedded: Optional[Dict[str, Any]] = Field(
        default=None, alias="_embedded"
    )

    class Config:
        allow_population_by_field_name = True


T = TypeVar("T", bound=HalResponse)


class PaginatedResponse(GenericModel, Generic[T]):
    """
    Base class for paginated responses.
    Derived classes should overwrite the items property
    """

    total: int
    items: Sequence[T]
