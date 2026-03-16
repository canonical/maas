# Copyright 2024-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Callable
from unittest.mock import Mock
from urllib.parse import parse_qs, urlparse

from httpx import AsyncClient
import pytest

from maasapiserver.v3.api.public.models.responses.events import (
    EventsListResponse,
)
from maasapiserver.v3.constants import V3_API_PREFIX
from maascommon.openfga.base import MAASResourceEntitlement
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.events import (
    EndpointChoicesEnum,
    Event,
    EventType,
    LoggingLevelEnum,
)
from maasservicelayer.services import ServiceCollectionV3
from maasservicelayer.services.events import EventsService
from maasservicelayer.utils.date import utcnow
from tests.maasapiserver.v3.api.public.handlers.base import (
    ApiCommonTests,
    Endpoint,
)

TEST_EVENT_TYPE = EventType(
    id=1,
    created=utcnow(),
    updated=utcnow(),
    name="TYPE_TEST",
    description="A test type",
    level=LoggingLevelEnum.AUDIT.value,
)

TEST_EVENT = Event(
    id=1,
    created=utcnow(),
    updated=utcnow(),
    type=TEST_EVENT_TYPE,
    node_system_id="1",
    node_hostname="",
    user_id=None,
    owner="",
    ip_address=None,
    endpoint=EndpointChoicesEnum.API.value,
    user_agent="",
    description="",
    action="test",
)

TEST_EVENT_2 = Event(
    id=2,
    created=utcnow(),
    updated=utcnow(),
    type=TEST_EVENT_TYPE,
    node_system_id="2",
    node_hostname="",
    user_id=None,
    owner="",
    ip_address=None,
    endpoint=EndpointChoicesEnum.API.value,
    user_agent="",
    description="",
    action="test",
)


class TestEventsApi(ApiCommonTests):
    BASE_PATH = f"{V3_API_PREFIX}/events"

    @pytest.fixture
    def endpoints_with_authorization(self) -> list[Endpoint]:
        return [
            Endpoint(
                method="GET",
                path=self.BASE_PATH,
                permission=MAASResourceEntitlement.CAN_VIEW_GLOBAL_ENTITIES,
            ),
        ]

    async def test_list_filters(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ) -> None:
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_VIEW_GLOBAL_ENTITIES,
        )
        services_mock.events = Mock(EventsService)
        services_mock.events.list.side_effect = [
            ListResult[Event](items=[TEST_EVENT], total=1),
            ListResult[Event](items=[TEST_EVENT_2], total=1),
            ListResult[Event](items=[TEST_EVENT_2, TEST_EVENT], total=2),
            ListResult[Event](items=[TEST_EVENT_2], total=2),
        ]

        response = await client.get(
            f"{self.BASE_PATH}?system_id={TEST_EVENT.node_system_id}"
        )
        events_response = EventsListResponse(**response.json())
        assert len(events_response.items) == 1
        assert (
            events_response.items[0].node_system_id
            == TEST_EVENT.node_system_id
        )

        response = await client.get(
            f"{self.BASE_PATH}?system_id={TEST_EVENT_2.node_system_id}"
        )
        events_response = EventsListResponse(**response.json())
        assert len(events_response.items) == 1
        assert (
            events_response.items[0].node_system_id
            == TEST_EVENT_2.node_system_id
        )

        response = await client.get(
            f"{self.BASE_PATH}?system_id={TEST_EVENT.node_system_id}&system_id={TEST_EVENT_2.node_system_id}"
        )
        events_response = EventsListResponse(**response.json())
        assert len(events_response.items) == 2
        assert set(map(lambda x: x.node_system_id, events_response.items)) == {
            TEST_EVENT.node_system_id,
            TEST_EVENT_2.node_system_id,
        }

        response = await client.get(
            f"{self.BASE_PATH}?system_id={TEST_EVENT.node_system_id}&system_id={TEST_EVENT_2.node_system_id}&size=1"
        )
        events_response = EventsListResponse(**response.json())
        assert len(events_response.items) == 1
        next_link_params = parse_qs(urlparse(events_response.next).query)
        assert set(next_link_params["system_id"]) == {
            TEST_EVENT.node_system_id,
            TEST_EVENT_2.node_system_id,
        }
        assert next_link_params["size"][0] == "1"
