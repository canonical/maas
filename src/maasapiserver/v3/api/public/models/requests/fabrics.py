# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from pydantic import Field, field_validator

from maasapiserver.v3.api.public.models.requests.base import NamedBaseModel
from maasservicelayer.builders.fabrics import FabricBuilder


class FabricRequest(NamedBaseModel):
    # inherited from the django model where it's optional in the request and empty by default.
    description: str | None = Field(
        description="The description of the fabric.", default=""
    )
    class_type: str | None

    def to_builder(self) -> FabricBuilder:
        return FabricBuilder(
            name=self.name,
            description=self.description,
            class_type=self.class_type,
        )

    @field_validator("description", mode="after")
    @classmethod
    def set_default(cls, v: str) -> str:
        return v if v else ""
