# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Callable
from unittest.mock import AsyncMock, Mock, patch

from httpx import AsyncClient
import pytest

from maasapiserver.v3.api.public.models.responses.events_summary import (
    EventsSummaryResponse,
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

_TEST_EVENT_TYPE = EventType(
    id=1,
    created=utcnow(),
    updated=utcnow(),
    name="TYPE_TEST",
    description="A test type",
    level=LoggingLevelEnum.AUDIT.value,
)

_TEST_EVENT = Event(
    id=1,
    created=utcnow(),
    updated=utcnow(),
    type=_TEST_EVENT_TYPE,
    node_system_id="abc123",
    node_hostname="node-1",
    user_id=None,
    owner="admin",
    ip_address=None,
    endpoint=EndpointChoicesEnum.API.value,
    user_agent="",
    description="Node deployed",
    action="deploy",
)


class TestEventsSummaryApi(ApiCommonTests):
    BASE_PATH = f"{V3_API_PREFIX}/events/summary"

    @pytest.fixture
    def endpoints_with_authorization(self) -> list[Endpoint]:
        return [
            Endpoint(
                method="GET",
                path=self.BASE_PATH,
                permission=MAASResourceEntitlement.CAN_VIEW_GLOBAL_ENTITIES,
            ),
        ]

    async def test_get_events_summary(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ) -> None:
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_VIEW_GLOBAL_ENTITIES,
        )
        services_mock.events = Mock(EventsService)
        services_mock.events.list = AsyncMock(
            return_value=ListResult[Event](items=[_TEST_EVENT], total=1)
        )

        with (
            patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"}),
            patch(
                "maasapiserver.v3.api.public.handlers.events_summary._llm_summarize",
                new=AsyncMock(return_value="One deploy event on node-1."),
            ),
        ):
            response = await client.get(self.BASE_PATH)

        assert response.status_code == 200
        body = EventsSummaryResponse(**response.json())
        assert body.summary == "One deploy event on node-1."

    async def test_missing_api_key_returns_503(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ) -> None:
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_VIEW_GLOBAL_ENTITIES,
        )

        env_without_key = {
            k: v for k, v in __import__("os").environ.items()
            if k != "OPENROUTER_API_KEY"
        }
        with patch.dict("os.environ", env_without_key, clear=True):
            response = await client.get(self.BASE_PATH)

        assert response.status_code == 503

    async def test_no_events_returns_empty_summary(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ) -> None:
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_VIEW_GLOBAL_ENTITIES,
        )
        services_mock.events = Mock(EventsService)
        services_mock.events.list = AsyncMock(
            return_value=ListResult[Event](items=[], total=0)
        )

        with patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"}):
            response = await client.get(self.BASE_PATH)

        assert response.status_code == 200
        body = EventsSummaryResponse(**response.json())
        assert "No events found" in body.summary
