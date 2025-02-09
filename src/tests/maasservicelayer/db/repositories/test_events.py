#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.sql.operators import eq

from maascommon.enums.events import EventTypeEnum
from maascommon.events import EventDetail
from maasservicelayer.builders.events import EventBuilder, EventTypeBuilder
from maasservicelayer.context import Context
from maasservicelayer.db._debug import CompiledQuery
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.events import (
    EventsClauseFactory,
    EventsRepository,
    EventTypesRepository,
)
from maasservicelayer.db.tables import EventTable, NodeTable
from maasservicelayer.models.base import ResourceBuilder
from maasservicelayer.models.events import (
    EndpointChoicesEnum,
    Event,
    EventType,
    LoggingLevelEnum,
)
from tests.fixtures.factories.bmc import create_test_bmc
from tests.fixtures.factories.events import (
    create_test_event_entry,
    create_test_event_type_entry,
)
from tests.fixtures.factories.machines import (
    create_test_machine,
    create_test_machine_entry,
)
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
    async def event_type(self, fixture: Fixture) -> EventType:
        return await create_test_event_type_entry(fixture)

    @pytest.fixture
    async def node(self, fixture: Fixture):
        return await create_test_machine_entry(fixture)

    @pytest.fixture
    async def _setup_test_list(
        self, fixture: Fixture, event_type: EventType, num_objects: int
    ) -> list[Event]:
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
    async def created_instance(
        self, fixture: Fixture, event_type: EventType
    ) -> Event:
        return await create_test_event_entry(
            fixture,
            event_type=event_type,
            description="description",
            node_hostname="test",
            user_agent="me",
        )

    @pytest.fixture
    async def instance_builder(
        self, event_type: EventType, node
    ) -> ResourceBuilder:
        return EventBuilder(
            type=event_type,
            node_system_id=node["system_id"],
            node_hostname=node["hostname"],
            owner="",
            endpoint=EndpointChoicesEnum.API,
            user_agent="user_agent",
            description="event_description",
            action="event_action",
        )

    @pytest.fixture
    async def instance_builder_model(self) -> type[ResourceBuilder]:
        return EventBuilder

    @pytest.mark.skip(reason="Not applicable")
    async def test_create_duplicated(self):
        pass

    @pytest.mark.skip(reason="Not implemented yet")
    async def test_delete_one(self):
        pass

    @pytest.mark.skip(reason="Not implemented yet")
    async def test_delete_one_multiple_results(self):
        pass

    @pytest.mark.skip(reason="Not implemented yet")
    async def test_delete_by_id(self):
        pass

    @pytest.mark.skip(reason="Not implemented yet")
    async def test_delete_many(self):
        pass

    @pytest.mark.skip(reason="Not implemented yet")
    async def test_update_by_id(self):
        pass

    @pytest.mark.skip(reason="Not implemented yet")
    async def test_update_one(self):
        pass

    @pytest.mark.skip(reason="Not implemented yet")
    async def test_update_one_multiple_results(self):
        pass

    @pytest.mark.skip(reason="Not implemented yet")
    async def test_update_many(self):
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

        events_result = await repository_instance.list(page=1, size=10)
        assert len(events_result.items) == 2
        assert events_result.total == 2

        query = QuerySpec(
            where=EventsClauseFactory.with_system_ids(
                [created_machine.system_id]
            )
        )
        events_result = await repository_instance.list(
            page=1, size=10, query=query
        )
        assert len(events_result.items) == 1
        assert events_result.total == 1
        assert events_result.items[0].id == event.id

        query = QuerySpec(
            where=EventsClauseFactory.with_system_ids(["NO MATCH"])
        )
        events_result = await repository_instance.list(
            page=1, size=10, query=query
        )
        assert len(events_result.items) == 0
        assert events_result.total == 0


class TestEventTypesRepository(RepositoryCommonTests[EventType]):
    @pytest.fixture
    def repository_instance(
        self, db_connection: AsyncConnection
    ) -> EventTypesRepository:
        return EventTypesRepository(Context(connection=db_connection))

    @pytest.fixture
    async def _setup_test_list(
        self, fixture: Fixture, num_objects: int
    ) -> list[EventType]:
        created_types = [
            (await create_test_event_type_entry(fixture, name=i.value))
            for i in list(EventTypeEnum)[:num_objects]
        ]
        return created_types

    @pytest.fixture
    async def instance_builder(self) -> ResourceBuilder:
        return EventTypeBuilder(
            name=EventTypeEnum.COMMISSIONING.value,
            description="description",
            level=LoggingLevelEnum.AUDIT,
        )

    @pytest.fixture
    async def created_instance(self, fixture: Fixture) -> EventType:
        return await create_test_event_type_entry(
            fixture,
            name=EventTypeEnum.NODE_POWERED_ON.value,
        )

    @pytest.fixture
    async def instance_builder_model(self) -> type[ResourceBuilder]:
        return EventTypeBuilder

    async def test_ensure(self, repository_instance):
        created_resource = await repository_instance.ensure(
            EventTypeEnum.DEPLOYED,
            EventDetail(
                description="description", level=LoggingLevelEnum.DEBUG
            ),
        )
        assert created_resource is not None

    async def test_ensure_existing(
        self, repository_instance, created_instance
    ):
        created_resource = await repository_instance.ensure(
            EventTypeEnum[created_instance.name],
            EventDetail(
                description=created_instance.description,
                level=created_instance.level,
            ),
        )
        assert created_resource == created_instance
