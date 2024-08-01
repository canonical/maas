from typing import Optional

from pydantic import validator

from maasapiserver.v3.api.models.requests.base import (
    NamedBaseModel,
    OptionalNamedBaseModel,
)


class ResourcePoolRequest(NamedBaseModel):
    description: str


class ResourcePoolUpdateRequest(OptionalNamedBaseModel):
    description: Optional[str]

    @validator("description")
    def check_description(cls, v: str) -> str:
        # If the description is set in the request, it must not be None
        if v is None:
            raise ValueError(
                "The description for the resource must not be null."
            )
        return v
