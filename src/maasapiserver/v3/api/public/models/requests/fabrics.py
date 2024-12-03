# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Optional

from pydantic import Field, validator

from maasapiserver.v3.api.public.models.requests.base import NamedBaseModel
from maasservicelayer.db.repositories.fabrics import FabricsResourceBuilder


class FabricRequest(NamedBaseModel):
    # inherited from the django model where it's optional in the request and empty by default.
    description: Optional[str] = Field(
        description="The description of the fabric.", default=""
    )
    class_type: Optional[str]

    def to_builder(self) -> FabricsResourceBuilder:
        return (
            FabricsResourceBuilder()
            .with_name(self.name)
            .with_description(self.description)
            .with_class_type(self.class_type)
        )

    # TODO: move to @field_validator when we migrate to pydantic 2.x
    # This handles the case where the client sends a request with {"description": null}.
    @validator("description")
    def set_default(cls, v: str) -> str:
        return v if v else ""
