# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.sql.operators import eq

from maasapiserver.common.db._debug import CompiledQuery
from maasapiserver.common.db.tables import EventTable, NodeTable
from maasapiserver.v3.db.events import (
    EventsFilterQueryBuilder,
    EventsRepository,
)
from maasapiserver.v3.models.events import Event
from tests.fixtures.factories.bmc import create_test_bmc
from tests.fixtures.factories.events import (
    create_test_event_entry,
    create_test_event_type_entry,
)
from tests.fixtures.factories.machines import create_test_machine
from tests.fixtures.factories.user import create_test_user
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasapiserver.v3.db.base import RepositoryCommonTests


class TestEventsFilterQueryBuilder:
    def test_builder(self):
        builder = EventsFilterQueryBuilder()
        builder.with_system_ids(["1", "2", "3"])
        query = builder.build()

        stmt = (
            select(EventTable.c.id)
            .select_from(EventTable)
            .join(
                NodeTable,
                eq(NodeTable.c.id, EventTable.c.node_id),
                isouter=True,
            )
            .where(*query.get_clauses())
        )
        assert (
            str(CompiledQuery(stmt).sql)
            == "SELECT maasserver_event.id \nFROM maasserver_event LEFT OUTER JOIN maasserver_node ON maasserver_node.id = maasserver_event.node_id \nWHERE maasserver_event.node_system_id IN (__[POSTCOMPILE_node_system_id_1]) OR maasserver_node.system_id IN (__[POSTCOMPILE_system_id_1])"
        )
        assert CompiledQuery(stmt).params == {
            "node_system_id_1": ["1", "2", "3"],
            "system_id_1": ["1", "2", "3"],
        }
        assert len(query.get_clauses()) == 1


class TestEventsRepository(RepositoryCommonTests[Event]):
    @pytest.fixture
    def repository_instance(
        self, db_connection: AsyncConnection
    ) -> EventsRepository:
        return EventsRepository(db_connection)

    @pytest.fixture
    async def _setup_test_list(
        self, fixture: Fixture
    ) -> tuple[list[Event], int]:

        event_type = await create_test_event_type_entry(fixture)
        event_count = 10
        created_events = [
            (
                await create_test_event_entry(
                    fixture,
                    event_type=event_type,
                    description=str(i),
                    node_hostname=str(i),
                    user_agent=str(i),
                )
            )
            for i in range(event_count)
        ][::-1]
        return created_events, event_count

    @pytest.fixture
    async def _created_instance(self, fixture: Fixture) -> Event:
        event_type = await create_test_event_type_entry(fixture)
        return await create_test_event_entry(
            fixture,
            event_type=event_type,
            description="description",
            node_hostname="test",
            user_agent="me",
        )

    @pytest.mark.skip(reason="Not implemented yet")
    async def test_find_by_id_not_found(
        self, repository_instance: EventsRepository
    ):
        pass

    @pytest.mark.skip(reason="Not implemented yet")
    async def test_find_by_id(
        self,
        repository_instance: EventsRepository,
        _created_instance: Event,
    ):
        pass

    async def test_list_filter(
        self, repository_instance: EventsRepository, fixture: Fixture
    ) -> None:

        bmc = await create_test_bmc(fixture)
        user = await create_test_user(fixture)
        created_machine = await create_test_machine(
            fixture, description="machine", bmc=bmc, user=user
        )

        event_type = await create_test_event_type_entry(fixture)
        event = await create_test_event_entry(
            fixture,
            event_type=event_type,
            node_id=created_machine.id,
            description="description",
            node_hostname="test",
            user_agent="me",
        )

        # Create another event
        await create_test_event_entry(
            fixture,
            event_type=event_type,
            description="description",
            node_hostname="test",
            user_agent="me",
        )

        events_result = await repository_instance.list(token=None, size=10)
        assert events_result.next_token is None
        assert len(events_result.items) == 2

        query = (
            EventsFilterQueryBuilder()
            .with_system_ids([created_machine.system_id])
            .build()
        )
        events_result = await repository_instance.list(
            token=None, size=10, query=query
        )
        assert events_result.next_token is None
        assert len(events_result.items) == 1
        assert events_result.items[0].id == event.id

        query = (
            EventsFilterQueryBuilder().with_system_ids(["NO MATCH"]).build()
        )
        events_result = await repository_instance.list(
            token=None, size=10, query=query
        )
        assert events_result.next_token is None
        assert len(events_result.items) == 0
