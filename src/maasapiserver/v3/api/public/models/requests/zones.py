# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Optional

from fastapi import Query
from pydantic import BaseModel, Field, validator

from maasapiserver.v3.api.public.models.requests.base import NamedBaseModel
from maasservicelayer.db.filters import FilterQuery


class ZonesFiltersParams(BaseModel):

    ids: Optional[list[int]] = Field(
        Query(default=None, title="Filter by zone id", alias="id")
    )

    def to_query(self) -> FilterQuery:
        # TODO: When the db layer will have removed all the dependencies from the api move this import at module level
        from maasapiserver.v3.db.zones import ZonesFilterQueryBuilder

        return ZonesFilterQueryBuilder().with_ids(self.ids).build()

    def to_href_format(self) -> str:
        if self.ids:
            tokens = [f"id={zone_id}" for zone_id in self.ids]
            return "&".join(tokens)
        return ""


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
