#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).
from dataclasses import dataclass

from maasservicelayer.apiclient.client import APIClient
from maasservicelayer.context import Context
from maasservicelayer.services._base import Service, ServiceCache
from maasservicelayer.services.configurations import ConfigurationsService
from maasservicelayer.services.users import UsersService


@dataclass(slots=True)
class AgentsServiceCache(ServiceCache):
    api_client: APIClient | None = None

    async def close(self) -> None:
        if self.api_client:
            await self.api_client.close()


class AgentsService(Service):
    def __init__(
        self,
        context: Context,
        configurations_service: ConfigurationsService,
        users_service: UsersService,
        cache: AgentsServiceCache | None = None,
    ):
        super().__init__(context, cache)
        self._apiclient = None
        self.configurations_service = configurations_service
        self.users_service = users_service

    @staticmethod
    def build_cache_object() -> AgentsServiceCache:
        return AgentsServiceCache()

    @Service.from_cache_or_execute(attr="api_client")
    async def _get_apiclient(self) -> APIClient:
        if self._apiclient:
            return self._apiclient

        maas_url = await self.configurations_service.get("maas_url")

        apikeys = await self.users_service.get_user_apikeys("MAAS")
        apikey = apikeys[0]

        apiclient = APIClient(f"{maas_url}/api/2.0/", apikey)
        self._apiclient = apiclient
        return apiclient

    async def get_service_configuration(
        self, system_id: str, service_name: str
    ):
        apiclient = await self._get_apiclient()
        path = f"agents/{system_id}/services/{service_name}/config/"
        return await apiclient.request(method="GET", path=path)
