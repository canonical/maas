#  Copyright 2025-2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

import pytest
from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from maasservicelayer.builders.events import EventBuilder
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.mappers.event import EventDomainDataMapper
from maasservicelayer.db.tables import EventTable
from maasservicelayer.filters.base import FieldFilter, Operator
from maasservicelayer.filters.events import EventFilters
from maasservicelayer.models.events import Event, EventType, LoggingLevelEnum


def compile_select_ids(query: QuerySpec) -> str:
    stmt = query.enrich_stmt(select(EventTable.c.id))
    return str(
        stmt.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    ).replace("\n", "")


class TestEventDomainDataMapper:
    @pytest.fixture
    def mapper(self) -> EventDomainDataMapper:
        return EventDomainDataMapper(Event, EventTable)

    def test_build_resource(self, mapper: EventDomainDataMapper):
        evt = EventType(
            id=1,
            name="TEST_EVENT",
            description="test event",
            level=LoggingLevelEnum.INFO,
        )
        builder = EventBuilder(type=evt, owner="user1")
        res = mapper.build_resource(builder)
        assert "type_id" in res
        assert res["type_id"] == 1
        assert "username" in res
        assert res["username"] == "user1"

    def test_owner_filter_uses_username_column(
        self, mapper: EventDomainDataMapper
    ):
        clause = mapper.to_clause(
            FieldFilter(Event, "owner", Operator.EQ, "user1")
        )
        assert (
            compile_select_ids(QuerySpec(where=clause))
            == "SELECT maasserver_event.id FROM maasserver_event WHERE maasserver_event.username = 'user1'"
        )

    def test_system_ids_filter_outer_joins_nodes(
        self, mapper: EventDomainDataMapper
    ):
        clause = mapper.to_clause(EventFilters.with_system_ids(["a", "b"]))
        assert (
            compile_select_ids(QuerySpec(where=clause))
            == "SELECT maasserver_event.id FROM maasserver_event LEFT OUTER JOIN maasserver_node ON maasserver_node.id = maasserver_event.node_id WHERE maasserver_event.node_system_id IN ('a', 'b') OR maasserver_node.system_id IN ('a', 'b')"
        )
