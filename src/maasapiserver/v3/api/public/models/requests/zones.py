# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from fastapi import Query
from pydantic import BaseModel, Field, field_validator

from maasapiserver.v3.api.public.models.requests.base import NamedBaseModel
from maasservicelayer.builders.zones import ZoneBuilder
from maasservicelayer.db.filters import Clause
from maasservicelayer.db.repositories.zones import ZonesClauseFactory


class ZonesFiltersParams(BaseModel):
    ids: list[int] | None = Field(
        Query(default=None, title="Filter by zone id", alias="id")
    )

    def to_clause(self) -> Clause | None:
        if self.ids:
            return ZonesClauseFactory.with_ids(self.ids)
        return None

    def to_href_format(self) -> str:
        if self.ids:
            tokens = [f"id={zone_id}" for zone_id in self.ids]
            return "&".join(tokens)
        return ""


class ZoneRequest(NamedBaseModel):
    # inherited from the django model where it's optional in the request and empty by default.
    description: str | None = Field(
        description="The description of the zone.", default=""
    )

    @field_validator("description", mode="after")
    @classmethod
    def set_default(cls, v: str) -> str:
        return v if v else ""

    def to_builder(self) -> ZoneBuilder:
        return ZoneBuilder(name=self.name, description=self.description)  # pyright: ignore [reportArgumentType]
