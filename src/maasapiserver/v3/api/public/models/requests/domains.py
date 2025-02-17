# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Optional

from pydantic import Field

from maasapiserver.v3.api.public.models.requests.base import NamedBaseModel
from maasservicelayer.builders.domains import DomainBuilder


class DomainRequest(NamedBaseModel):
    name: str = Field(description="Name of the domain.")
    authoritative: bool = Field(
        description="Class type of the domain", default=True
    )
    ttl: Optional[int] = Field(
        description="TTL for the domain.", default=None, ge=1, le=604800
    )

    def to_builder(self) -> DomainBuilder:
        return DomainBuilder(
            name=self.name, authoritative=self.authoritative, ttl=self.ttl
        )
