#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Optional

from fastapi import Query
from pydantic import BaseModel, Field

from maasapiserver.common.db.filters import FilterQuery
from maasapiserver.v3.api.models.requests.base import NamedBaseModel


class EventsFiltersParams(BaseModel):

    system_ids: Optional[list[str]] = Field(
        Query(default=None, title="Filter by system id", alias="system_id")
    )

    def to_query(self) -> FilterQuery:
        # TODO: When the db layer will have removed all the dependencies from the api move this import at module level
        from maasapiserver.v3.db.events import EventsFilterQueryBuilder

        return (
            EventsFilterQueryBuilder().with_system_ids(self.system_ids).build()
        )

    def to_href_format(self) -> str:
        if self.system_ids:
            tokens = [
                f"system_id={system_id}" for system_id in self.system_ids
            ]
            return "&".join(tokens)
        return ""


class EventRequest(NamedBaseModel):
    # TODO
    pass
