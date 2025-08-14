# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import AsyncMock, Mock

import pytest

from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.agentcertificates import (
    AgentCertificatesClauseFactory,
)
from maasservicelayer.db.repositories.agents import AgentsRepository
from maasservicelayer.models.agents import Agent
from maasservicelayer.services import (
    AgentCertificateService,
    AgentsService,
    ConfigurationsService,
    UsersService,
)
from maasservicelayer.services.agents import AgentsServiceCache
from maasservicelayer.utils.date import utcnow


@pytest.mark.asyncio
class TestAgentsService:
    @pytest.fixture
    def test_instance(self) -> Agent:
        now = utcnow()
        return Agent(
            id=1,
            created=now,
            updated=now,
            secret="secret",
            rack_id=1,
            rackcontroller_id=1,
        )

    async def test_get_service_configuration(self) -> None:
        agents_service = AgentsService(
            context=Context(),
            repository=Mock(AgentsRepository),
            configurations_service=Mock(ConfigurationsService),
            users_service=Mock(UsersService),
            agentcertificates_service=Mock(AgentCertificateService),
        )

        api_client = AsyncMock()
        agents_service._apiclient = api_client

        await agents_service.get_service_configuration(
            system_id="agent", service_name="foo"
        )
        api_client.request.assert_called_with(
            method="GET", path="agents/agent/services/foo/config/"
        )

    async def test_get_apiclient(self) -> None:
        configurations_service = Mock(ConfigurationsService)
        configurations_service.get.return_value = "http://example.com"
        users_service = Mock(UsersService)
        users_service.get_MAAS_user_apikey.return_value = "key:token:secret"

        agents_service = AgentsService(
            context=Context(),
            repository=Mock(AgentsRepository),
            configurations_service=configurations_service,
            users_service=users_service,
            agentcertificates_service=Mock(AgentCertificateService),
        )

        apiclient = await agents_service._get_apiclient()

        assert apiclient.base_url == "http://example.com/api/2.0/"

    async def test_get_apiclient_is_cached(self) -> None:
        configurations_service = Mock(ConfigurationsService)
        configurations_service.get.return_value = "http://example.com"
        users_service = Mock(UsersService)
        users_service.get_MAAS_user_apikey.return_value = "key:token:secret"

        cache = AgentsServiceCache()
        agents_service = AgentsService(
            context=Context(),
            repository=Mock(AgentsRepository),
            configurations_service=configurations_service,
            users_service=users_service,
            agentcertificates_service=Mock(AgentCertificateService),
            cache=cache,
        )

        apiclient = await agents_service._get_apiclient()
        assert apiclient.base_url == "http://example.com/api/2.0/"
        configurations_service.get.assert_called_once()

        await agents_service._get_apiclient()
        configurations_service.get.assert_called_once()

        assert cache.api_client is not None

    async def test_delete(self, test_instance):
        agent = test_instance

        repository_mock = Mock(AgentsRepository)
        repository_mock.get_one.return_value = agent
        repository_mock.delete_by_id.return_value = agent
        configurations_service = Mock(ConfigurationsService)
        configurations_service.get.return_value = "http://example.com"
        users_service = Mock(UsersService)
        users_service.get_MAAS_user_apikey.return_value = "key:token:secret"
        agentcertificate_service = Mock(AgentCertificateService)

        agents_service = AgentsService(
            context=Context(),
            repository=repository_mock,
            configurations_service=configurations_service,
            users_service=users_service,
            agentcertificates_service=agentcertificate_service,
        )

        query = Mock(QuerySpec)
        await agents_service.delete_one(query)

        repository_mock.delete_by_id.assert_called_once_with(id=agent.id)

        agentcertificate_service.delete_many.assert_called_once_with(
            query=QuerySpec(
                where=AgentCertificatesClauseFactory.with_agent_id(agent.id)
            )
        )

    async def test_delete_many(self, test_instance):
        agent1 = test_instance
        agent2 = Agent(
            id=2,
            created=agent1.created,
            updated=agent1.updated,
            secret="secret2",
            rack_id=2,
            rackcontroller_id=2,
        )
        agents = [agent1, agent2]

        repository_mock = Mock(AgentsRepository)
        repository_mock.delete_many.return_value = agents
        configurations_service = Mock(ConfigurationsService)
        configurations_service.get.return_value = "http://example.com"
        users_service = Mock(UsersService)
        users_service.get_MAAS_user_apikey.return_value = "key:token:secret"
        agentcertificate_service = Mock(AgentCertificateService)

        agents_service = AgentsService(
            context=Context(),
            repository=repository_mock,
            configurations_service=configurations_service,
            users_service=users_service,
            agentcertificates_service=agentcertificate_service,
        )

        query = Mock(QuerySpec)
        await agents_service.delete_many(query)

        repository_mock.delete_many.assert_called_once_with(query=query)

        agentcertificate_service.delete_many.assert_called_once_with(
            query=QuerySpec(
                where=AgentCertificatesClauseFactory.with_agent_id_in(
                    [agent1.id, agent2.id]
                )
            )
        )
