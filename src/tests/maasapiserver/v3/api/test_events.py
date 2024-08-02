# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).
from urllib.parse import parse_qs, urlparse

from httpx import AsyncClient

from maasapiserver.v3.api.models.responses.events import EventsListResponse
from maasapiserver.v3.auth.jwt import UserRole
from maasapiserver.v3.constants import V3_API_PREFIX
from maasapiserver.v3.models.events import Event
from tests.fixtures.factories.events import (
    create_test_event_entry,
    create_test_event_type_entry,
)
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasapiserver.v3.api.base import (
    ApiCommonTests,
    EndpointDetails,
    PaginatedEndpointTestConfig,
)


class TestEventsApi(ApiCommonTests):
    def get_endpoints_configuration(self) -> list[EndpointDetails]:
        async def create_pagination_test_resources(
            fixture: Fixture, size: int
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
                for i in range(size)
            ]
            return created_events

        return [
            EndpointDetails(
                method="GET",
                path=f"{V3_API_PREFIX}/events",
                user_role=UserRole.USER,
                pagination_config=PaginatedEndpointTestConfig[
                    Event, EventsListResponse
                ](
                    response_type=EventsListResponse,
                    create_resources_routine=create_pagination_test_resources,
                ),
            ),
        ]

    async def test_list_filters(
        self, fixture: Fixture, authenticated_user_api_client_v3: AsyncClient
    ) -> None:
        event_type = await create_test_event_type_entry(fixture)
        for i in range(3):
            await create_test_event_entry(
                fixture, event_type=event_type, node_system_id=str(i)
            )

        response = await authenticated_user_api_client_v3.get(
            f"{V3_API_PREFIX}/events?system_id=0"
        )
        events_response = EventsListResponse(**response.json())
        assert len(events_response.items) == 1
        assert events_response.items[0].node_system_id == "0"

        response = await authenticated_user_api_client_v3.get(
            f"{V3_API_PREFIX}/events?system_id=1"
        )
        events_response = EventsListResponse(**response.json())
        assert len(events_response.items) == 1
        assert events_response.items[0].node_system_id == "1"

        response = await authenticated_user_api_client_v3.get(
            f"{V3_API_PREFIX}/events?system_id=0&system_id=2"
        )
        events_response = EventsListResponse(**response.json())
        assert len(events_response.items) == 2
        assert set(map(lambda x: x.node_system_id, events_response.items)) == {
            "0",
            "2",
        }

        response = await authenticated_user_api_client_v3.get(
            f"{V3_API_PREFIX}/events?system_id=3"
        )
        events_response = EventsListResponse(**response.json())
        assert len(events_response.items) == 0

        response = await authenticated_user_api_client_v3.get(
            f"{V3_API_PREFIX}/events?system_id=0&system_id=1&size=1"
        )
        events_response = EventsListResponse(**response.json())
        assert len(events_response.items) == 1
        next_link_params = parse_qs(urlparse(events_response.next).query)
        assert set(next_link_params["system_id"]) == {"0", "1"}
        assert next_link_params["size"][0] == "1"
