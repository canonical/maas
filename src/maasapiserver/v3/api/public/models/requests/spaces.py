# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Optional

from pydantic import Field

from maasapiserver.v3.api.public.models.requests.base import NamedBaseModel
from maasservicelayer.builders.spaces import SpaceBuilder


class SpaceRequest(NamedBaseModel):
    description: Optional[str] = Field(
        description="The description of the zone.", default=""
    )

    def to_builder(self) -> SpaceBuilder:
        return SpaceBuilder(name=self.name, description=self.description)
