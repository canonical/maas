# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Optional

from pydantic import Field

from maasapiserver.v3.api.public.models.requests.base import NamedBaseModel
from maasservicelayer.db.repositories.spaces import SpaceResourceBuilder


class SpaceRequest(NamedBaseModel):
    description: Optional[str] = Field(
        description="The description of the zone.", default=""
    )

    def to_builder(self) -> SpaceResourceBuilder:
        return (
            SpaceResourceBuilder()
            .with_name(self.name)
            .with_description(self.description)
        )
