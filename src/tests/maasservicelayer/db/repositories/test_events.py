#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.sql.operators import eq

from maasservicelayer.context import Context
from maasservicelayer.db._debug import CompiledQuery
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.base import ResourceBuilder
from maasservicelayer.db.repositories.events import (
    EventsClauseFactory,
    EventsRepository,
)
from maasservicelayer.db.tables import EventTable, NodeTable
from maasservicelayer.models.events import Event
from tests.fixtures.factories.bmc import create_test_bmc
from tests.fixtures.factories.events import (
    create_test_event_entry,
    create_test_event_type_entry,
)
from tests.fixtures.factories.machines import create_test_machine
from tests.fixtures.factories.user import create_test_user
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasservicelayer.db.repositories.base import RepositoryCommonTests


class TestEventsClauseFactory:
    def test_factory(self):
        clause = EventsClauseFactory.with_system_ids(["1", "2", "3"])

        stmt = (
            select(EventTable.c.id)
            .select_from(EventTable)
            .join(
                NodeTable,
                eq(NodeTable.c.id, EventTable.c.node_id),
                isouter=True,
            )
            .where(clause.condition)
        )
        assert (
            str(CompiledQuery(stmt).sql)
            == "SELECT maasserver_event.id \nFROM maasserver_event LEFT OUTER JOIN maasserver_node ON maasserver_node.id = maasserver_event.node_id \nWHERE maasserver_event.node_system_id IN (__[POSTCOMPILE_node_system_id_1]) OR maasserver_node.system_id IN (__[POSTCOMPILE_system_id_1])"
        )
        assert CompiledQuery(stmt).params == {
            "node_system_id_1": ["1", "2", "3"],
            "system_id_1": ["1", "2", "3"],
        }


class TestEventsRepository(RepositoryCommonTests[Event]):
    @pytest.fixture
    def repository_instance(
        self, db_connection: AsyncConnection
    ) -> EventsRepository:
        return EventsRepository(Context(connection=db_connection))

    @pytest.fixture
    async def _setup_test_list(
        self, fixture: Fixture, num_objects: int
    ) -> list[Event]:

        event_type = await create_test_event_type_entry(fixture)
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
            for i in range(num_objects)
        ]
        return created_events

    @pytest.fixture
    async def created_instance(self, fixture: Fixture) -> Event:
        event_type = await create_test_event_type_entry(fixture)
        return await create_test_event_entry(
            fixture,
            event_type=event_type,
            description="description",
            node_hostname="test",
            user_agent="me",
        )

    # TODO
    @pytest.fixture
    async def instance_builder(self) -> ResourceBuilder:
        return ResourceBuilder()

    @pytest.mark.skip(reason="Not implemented yet")
    async def test_create(self, repository_instance, instance_builder):
        pass

    @pytest.mark.skip(reason="Not implemented yet")
    async def test_create_duplicated(
        self, repository_instance, instance_builder
    ):
        pass

    @pytest.mark.skip(reason="Not implemented yet")
    async def test_delete(self, repository_instance, created_instance):
        pass

    @pytest.mark.skip(reason="Not implemented yet")
    async def test_update(self, repository_instance, instance_builder):
        pass

    @pytest.mark.skip(reason="Not implemented yet")
    async def test_get_by_id_not_found(
        self, repository_instance: EventsRepository
    ):
        pass

    @pytest.mark.skip(reason="Not implemented yet")
    async def test_get_by_id(
        self,
        repository_instance: EventsRepository,
        created_instance: Event,
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

        query = QuerySpec(
            where=EventsClauseFactory.with_system_ids(
                [created_machine.system_id]
            )
        )
        events_result = await repository_instance.list(
            token=None, size=10, query=query
        )
        assert events_result.next_token is None
        assert len(events_result.items) == 1
        assert events_result.items[0].id == event.id

        query = QuerySpec(
            where=EventsClauseFactory.with_system_ids(["NO MATCH"])
        )
        events_result = await repository_instance.list(
            token=None, size=10, query=query
        )
        assert events_result.next_token is None
        assert len(events_result.items) == 0
