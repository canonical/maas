from unittest.mock import ANY, Mock, PropertyMock

import pytest

from maascommon.enums.events import EventTypeEnum
from maascommon.events import EVENT_DETAILS_MAP
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.events import (
    EventsRepository,
    EventTypesRepository,
)
from maasservicelayer.models.events import Event, EventType
from maasservicelayer.models.nodes import Node
from maasservicelayer.services.events import EventsService


@pytest.mark.asyncio
class TestEventsService:

    @pytest.fixture(scope="function")
    def events_repository(self):
        return Mock(EventsRepository)

    @pytest.fixture(scope="function")
    def eventtypes_repository(self):
        return Mock(EventTypesRepository)

    @pytest.fixture(scope="function")
    def node(self):
        node = Mock(Node)
        type(node).id = PropertyMock(return_value=100)
        type(node).system_id = PropertyMock(return_value="system_id")
        type(node).hostname = PropertyMock(return_value="hostname")
        return node

    def test_evenry_event_type_have_details(self):
        assert len(EVENT_DETAILS_MAP) == len(EventTypeEnum)

    async def test_ensure_event_type(
        self, events_repository, eventtypes_repository
    ):
        event_type = Mock(EventType)
        eventtypes_repository.ensure.return_value = event_type
        events_service = EventsService(
            context=Context(),
            events_repository=events_repository,
            eventtypes_repository=eventtypes_repository,
        )

        et = await events_service.ensure_event_type(EventTypeEnum.DEPLOYED)
        assert et == event_type
        eventtypes_repository.ensure.assert_called_once_with(
            EventTypeEnum.DEPLOYED, EVENT_DETAILS_MAP[EventTypeEnum.DEPLOYED]
        )

    async def test_record_event(
        self, events_repository, eventtypes_repository, node
    ):
        event_type = EventType(
            id=1, name=EventTypeEnum.DEPLOYING, description="desc", level=0
        )
        eventtypes_repository.ensure.return_value = event_type
        event = Mock(Event)
        events_repository.create.return_value = event
        events_service = EventsService(
            context=Context(),
            events_repository=events_repository,
            eventtypes_repository=eventtypes_repository,
        )

        ev = await events_service.record_event(
            node=node,
            event_type=EventTypeEnum.DEPLOYING,
            event_action="action",
            event_description="description",
        )
        assert ev == event
        eventtypes_repository.ensure.assert_called_with(
            EventTypeEnum.DEPLOYING, ANY
        )
        events_repository.create.assert_called_once()
        builder = events_repository.create.call_args.args[0]
        assert builder.type == event_type
        assert builder.node_system_id == node.system_id
        assert builder.node_hostname == node.hostname
        assert builder.description == "description"
        assert builder.action == "action"
