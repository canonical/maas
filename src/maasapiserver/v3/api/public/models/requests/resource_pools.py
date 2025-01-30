# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).
from pydantic import Field

from maasapiserver.v3.api.public.models.requests.base import NamedBaseModel
from maasservicelayer.builders.resource_pools import ResourcePoolBuilder


class ResourcePoolRequest(NamedBaseModel):
    description: str = Field(default="")

    def to_builder(self) -> ResourcePoolBuilder:
        return ResourcePoolBuilder(
            name=self.name,
            description=self.description,
        )
