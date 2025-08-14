# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from dataclasses import dataclass
from typing import List

from maasservicelayer.apiclient.client import APIClient
from maasservicelayer.builders.agents import AgentBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.agentcertificates import (
    AgentCertificatesClauseFactory,
)
from maasservicelayer.db.repositories.agents import AgentsRepository
from maasservicelayer.models.agents import Agent
from maasservicelayer.models.configurations import MAASUrlConfig
from maasservicelayer.services.agentcertificates import AgentCertificateService
from maasservicelayer.services.base import BaseService, Service, ServiceCache
from maasservicelayer.services.configurations import ConfigurationsService
from maasservicelayer.services.users import UsersService


@dataclass(slots=True)
class AgentsServiceCache(ServiceCache):
    api_client: APIClient | None = None

    async def close(self) -> None:
        if self.api_client:
            await self.api_client.close()


class AgentsService(BaseService[Agent, AgentsRepository, AgentBuilder]):
    def __init__(
        self,
        context: Context,
        repository: AgentsRepository,
        configurations_service: ConfigurationsService,
        users_service: UsersService,
        agentcertificates_service: AgentCertificateService,
        cache: AgentsServiceCache | None = None,
    ):
        super().__init__(context, repository, cache)
        self._apiclient = None
        self.configurations_service = configurations_service
        self.users_service = users_service
        self.agentcertificates_service = agentcertificates_service

    @staticmethod
    def build_cache_object() -> AgentsServiceCache:
        return AgentsServiceCache()

    @Service.from_cache_or_execute(attr="api_client")
    async def _get_apiclient(self) -> APIClient:
        if self._apiclient:
            return self._apiclient

        maas_url = await self.configurations_service.get(
            name=MAASUrlConfig.name
        )

        apikey = await self.users_service.get_MAAS_user_apikey()

        apiclient = APIClient(f"{maas_url}/api/2.0/", apikey)
        self._apiclient = apiclient
        return apiclient

    async def get_service_configuration(
        self, system_id: str, service_name: str
    ):
        apiclient = await self._get_apiclient()
        path = f"agents/{system_id}/services/{service_name}/config/"
        return await apiclient.request(method="GET", path=path)

    async def post_delete_hook(self, resource: Agent) -> None:
        # cascade delete for a single resource
        await self.agentcertificates_service.delete_many(
            query=QuerySpec(
                where=AgentCertificatesClauseFactory.with_agent_id(resource.id)
            )
        )

    async def post_delete_many_hook(self, resources: List[Agent]) -> None:
        # cascade delete for multiple resources
        agent_ids = [resource.id for resource in resources]

        await self.agentcertificates_service.delete_many(
            query=QuerySpec(
                where=AgentCertificatesClauseFactory.with_agent_id_in(
                    agent_ids
                )
            )
        )
