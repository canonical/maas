from typing import Optional

from pydantic import Field, validator

from maasapiserver.v3.api.models.requests.base import NamedBaseModel


class ZoneRequest(NamedBaseModel):
    # inherited from the django model where it's optional in the request and empty by default.
    description: Optional[str] = Field(
        description="The description of the zone.", default=""
    )

    # TODO: move to @field_validator when we migrate to pydantic 2.x
    # This handles the case where the client sends a request with {"description": null}.
    @validator("description")
    def set_default(cls, v: str) -> str:
        return v if v else ""
