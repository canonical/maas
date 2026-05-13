# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime

from fastapi import Query
from pydantic import BaseModel, Field

from maasservicelayer.db.filters import Clause
from maasservicelayer.db.repositories.events import EventsClauseFactory


class EventsSummaryFiltersParams(BaseModel):
    system_ids: list[str] | None = Field(
        Query(default=None, title="Filter by system id", alias="system_id")
    )
    created_after: datetime | None = Field(
        Query(default=None, title="Only events created at or after this datetime")
    )
    created_before: datetime | None = Field(
        Query(default=None, title="Only events created at or before this datetime")
    )

    def to_clause(self) -> Clause | None:
        if self.system_ids:
            return EventsClauseFactory.with_system_ids(self.system_ids)
        return None
