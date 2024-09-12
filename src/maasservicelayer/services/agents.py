#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.apiclient.client import APIClient
from maasservicelayer.services._base import Service
from maasservicelayer.services.configurations import ConfigurationsService
from maasservicelayer.services.users import UsersService


class AgentsService(Service):
    def __init__(
        self,
        connection: AsyncConnection,
        configurations_service: ConfigurationsService | None = None,
        users_service: UsersService | None = None,
    ):
        super().__init__(connection)
        self._apiclient = None
        self.configurations_service = (
            configurations_service
            if configurations_service
            else ConfigurationsService(connection)
        )
        self.users_service = (
            users_service if users_service else UsersService(connection)
        )

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
