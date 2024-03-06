from sqlalchemy.ext.asyncio import AsyncConnection

from maasapiserver.v3.services.auth import AuthService
from maasapiserver.v3.services.bmc import BmcService
from maasapiserver.v3.services.configurations import ConfigurationsService
from maasapiserver.v3.services.nodes import NodesService
from maasapiserver.v3.services.secrets import (
    SecretsService,
    SecretsServiceFactory,
)
from maasapiserver.v3.services.users import UsersService
from maasapiserver.v3.services.vmcluster import VmClustersService
from maasapiserver.v3.services.zones import ZonesService


class ServiceCollectionV3:
    """Provide all v3 services."""

    nodes: NodesService
    vmcluster: VmClustersService
    bmc: BmcService
    zones: ZonesService
    secrets: SecretsService
    configurations: ConfigurationsService
    auth: AuthService

    @classmethod
    async def produce(
        cls, connection: AsyncConnection
    ) -> "ServiceCollectionV3":
        services = cls()
        services.configurations = ConfigurationsService(connection=connection)
        services.secrets = await SecretsServiceFactory.produce(
            connection=connection, config_service=services.configurations
        )
        services.users = UsersService(connection=connection)
        services.auth = AuthService(
            connection=connection,
            secrets_service=services.secrets,
            users_service=services.users,
        )
        services.nodes = NodesService(connection=connection)
        services.vmclusters = VmClustersService(connection=connection)
        services.bmc = BmcService(connection=connection)
        services.zones = ZonesService(
            connection=connection,
            nodes_service=services.nodes,
            vmcluster_service=services.vmclusters,
            bmc_service=services.bmc,
        )
        return services
