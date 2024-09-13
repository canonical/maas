#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Optional

from fastapi import Query
from pydantic import BaseModel, Field

from maasapiserver.v3.api.public.models.requests.base import NamedBaseModel
from maasservicelayer.db.filters import Clause
from maasservicelayer.db.repositories.events import EventsClauseFactory


class EventsFiltersParams(BaseModel):

    system_ids: Optional[list[str]] = Field(
        Query(default=None, title="Filter by system id", alias="system_id")
    )

    def to_clause(self) -> Optional[Clause]:
        if self.system_ids:
            return EventsClauseFactory.with_system_ids(
                system_ids=self.system_ids
            )
        return None

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
