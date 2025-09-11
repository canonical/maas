# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock

from httpx import AsyncClient
import pytest

from maasapiserver.common.api.models.responses.errors import ErrorBodyResponse
from maasapiserver.v3.api.public.models.responses.agents import (
    AgentResponse,
    AgentsListResponse,
)
from maasapiserver.v3.constants import V3_API_PREFIX
from maasservicelayer.models.agents import Agent
from maasservicelayer.models.base import ListResult
from maasservicelayer.services import ServiceCollectionV3
from maasservicelayer.services.agents import AgentsService
from maasservicelayer.utils.date import utcnow
from tests.maasapiserver.v3.api.public.handlers.base import (
    ApiCommonTests,
    Endpoint,
)

TEST_AGENT_1 = Agent(
    id=1,
    created=utcnow(),
    updated=utcnow(),
    secret="secret-1",
    rack_id=1,
    rackcontroller_id=1,
)

TEST_AGENT_2 = Agent(
    id=2,
    created=utcnow(),
    updated=utcnow(),
    secret="secret-2",
    rack_id=2,
    rackcontroller_id=2,
)


class TestAgentsApi(ApiCommonTests):
    BASE_PATH = f"{V3_API_PREFIX}/agents"

    @pytest.fixture
    def user_endpoints(self) -> list[Endpoint]:
        return [
            Endpoint(method="GET", path=self.BASE_PATH),
            Endpoint(method="GET", path=f"{self.BASE_PATH}/1"),
        ]

    @pytest.fixture
    def admin_endpoints(self) -> list[Endpoint]:
        return [
            Endpoint(method="DELETE", path=f"{self.BASE_PATH}/1"),
        ]

    async def test_list_no_other_page(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.agents = Mock(AgentsService)
        services_mock.agents.list.return_value = ListResult[Agent](
            items=[TEST_AGENT_1], total=1
        )
        response = await mocked_api_client_user.get(f"{self.BASE_PATH}?size=1")
        assert response.status_code == 200
        agents_response = AgentsListResponse(**response.json())
        assert len(agents_response.items) == 1
        assert agents_response.total == 1
        assert agents_response.next is None

    async def test_list_other_page(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.agents = Mock(AgentsService)
        services_mock.agents.list.return_value = ListResult[Agent](
            items=[TEST_AGENT_1, TEST_AGENT_2], total=2
        )
        response = await mocked_api_client_user.get(f"{self.BASE_PATH}?size=1")
        assert response.status_code == 200
        agents_response = AgentsListResponse(**response.json())
        assert len(agents_response.items) == 2
        assert agents_response.total == 2
        assert agents_response.next == f"{self.BASE_PATH}?page=2&size=1"

    async def test_get_200(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ):
        services_mock.agents = Mock(AgentsService)
        services_mock.agents.get_by_id.return_value = TEST_AGENT_1
        response = await mocked_api_client_user.get(
            f"{self.BASE_PATH}/{TEST_AGENT_1.id}"
        )
        assert response.status_code == 200
        assert response.headers["ETag"]
        agent_response = AgentResponse(**response.json())
        assert agent_response.id == TEST_AGENT_1.id

    async def test_get_404(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.agents = Mock(AgentsService)
        services_mock.agents.get_by_id.return_value = None
        response = await mocked_api_client_user.get(f"{self.BASE_PATH}/101")
        assert response.status_code == 404
        assert "ETag" not in response.headers

        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 404

    async def test_delete_resource(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        services_mock.agents = Mock(AgentsService)
        services_mock.agents.delete_by_id.side_effect = None
        response = await mocked_api_client_admin.delete(
            f"{self.BASE_PATH}/100"
        )
        assert response.status_code == 204
