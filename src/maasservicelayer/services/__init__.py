#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.services.auth import AuthService
from maasservicelayer.services.configurations import ConfigurationsService
from maasservicelayer.services.events import EventsService
from maasservicelayer.services.external_auth import ExternalAuthService
from maasservicelayer.services.fabrics import FabricsService
from maasservicelayer.services.interfaces import InterfacesService
from maasservicelayer.services.machines import MachinesService
from maasservicelayer.services.nodes import NodesService
from maasservicelayer.services.resource_pools import ResourcePoolsService
from maasservicelayer.services.secrets import (
    SecretsService,
    SecretsServiceFactory,
)
from maasservicelayer.services.spaces import SpacesService
from maasservicelayer.services.subnets import SubnetsService
from maasservicelayer.services.users import UsersService
from maasservicelayer.services.vlans import VlansService
from maasservicelayer.services.vmcluster import VmClustersService
from maasservicelayer.services.zones import ZonesService


class ServiceCollectionV3:
    """Provide all v3 services."""

    nodes: NodesService
    vmclusters: VmClustersService
    zones: ZonesService
    secrets: SecretsService
    configurations: ConfigurationsService
    resource_pools: ResourcePoolsService
    auth: AuthService
    external_auth: ExternalAuthService
    machines: MachinesService
    events: EventsService
    interfaces: InterfacesService
    fabrics: FabricsService
    spaces: SpacesService
    vlans: VlansService
    users: UsersService
    subnets: SubnetsService

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
        services.external_auth = ExternalAuthService(
            connection=connection,
            secrets_service=services.secrets,
            users_service=services.users,
        )
        services.nodes = NodesService(
            connection=connection, secrets_service=services.secrets
        )
        services.vmclusters = VmClustersService(connection=connection)
        services.zones = ZonesService(
            connection=connection,
            nodes_service=services.nodes,
            vmcluster_service=services.vmclusters,
        )
        services.resource_pools = ResourcePoolsService(connection=connection)
        services.machines = MachinesService(
            connection=connection, secrets_service=services.secrets
        )
        services.events = EventsService(connection=connection)
        services.interfaces = InterfacesService(connection=connection)
        services.fabrics = FabricsService(connection=connection)
        services.spaces = SpacesService(connection=connection)
        services.vlans = VlansService(connection=connection)
        services.subnets = SubnetsService(connection=connection)
        return services
