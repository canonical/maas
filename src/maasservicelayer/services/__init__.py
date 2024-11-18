#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Callable, Optional

from sqlalchemy.ext.asyncio import AsyncConnection
from temporalio.client import Client

from maasservicelayer.services._base import ServiceCache
from maasservicelayer.services.agents import AgentsService
from maasservicelayer.services.auth import AuthService
from maasservicelayer.services.configurations import ConfigurationsService
from maasservicelayer.services.dnspublications import DNSPublicationsService
from maasservicelayer.services.dnsresources import DNSResourcesService
from maasservicelayer.services.domains import DomainsService
from maasservicelayer.services.events import EventsService
from maasservicelayer.services.external_auth import ExternalAuthService
from maasservicelayer.services.fabrics import FabricsService
from maasservicelayer.services.interfaces import InterfacesService
from maasservicelayer.services.ipranges import IPRangesService
from maasservicelayer.services.leases import LeasesService
from maasservicelayer.services.machines import MachinesService
from maasservicelayer.services.nodes import NodesService
from maasservicelayer.services.resource_pools import ResourcePoolsService
from maasservicelayer.services.secrets import (
    SecretsService,
    SecretsServiceFactory,
)
from maasservicelayer.services.spaces import SpacesService
from maasservicelayer.services.staticipaddress import StaticIPAddressService
from maasservicelayer.services.subnets import SubnetsService
from maasservicelayer.services.temporal import TemporalService
from maasservicelayer.services.users import UsersService
from maasservicelayer.services.vlans import VlansService
from maasservicelayer.services.vmcluster import VmClustersService
from maasservicelayer.services.zones import ZonesService


class CacheForServices:
    def __init__(self):
        self.cache: dict[str, ServiceCache] = {}

    def get(self, name: str, fn: Callable) -> ServiceCache:
        """Get the ServiceCache for service named *name*.
        Params:
            - name: class name of the service
            - fn: function to create the cache if it doesn't exists
        Returns:
            ServiceCache: cache for the specified service.
        """
        if name in self.cache:
            return self.cache[name]
        self.cache[name] = fn()
        return self.cache[name]

    async def close(self) -> None:
        """Perform all the shutdown operations for all caches."""
        for cache in self.cache.values():
            await cache.close()


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
    agents: AgentsService
    leases: LeasesService
    domains: DomainsService
    dnsresources: DNSResourcesService
    dnspublications: DNSPublicationsService
    staticipaddress: StaticIPAddressService
    ipranges: IPRangesService
    temporal: TemporalService

    @classmethod
    async def produce(
        cls,
        connection: AsyncConnection,
        cache: CacheForServices,
        temporal: Optional[Client] = None,
    ) -> "ServiceCollectionV3":
        services = cls()
        services.configurations = ConfigurationsService(connection=connection)
        services.secrets = await SecretsServiceFactory.produce(
            connection=connection, config_service=services.configurations
        )
        services.temporal = TemporalService(temporal=temporal)
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
            cache=cache.get(ExternalAuthService.__name__, ExternalAuthService.build_cache_object),  # type: ignore
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
        services.interfaces = InterfacesService(
            connection=connection,
            temporal_service=services.temporal,
        )
        services.fabrics = FabricsService(connection=connection)
        services.spaces = SpacesService(connection=connection)
        services.vlans = VlansService(
            connection=connection,
            temporal_service=services.temporal,
            nodes_service=services.nodes,
        )
        services.subnets = SubnetsService(
            connection=connection,
            temporal_service=services.temporal,
        )
        services.agents = AgentsService(connection=connection)
        services.dnspublications = DNSPublicationsService(
            connection=connection,
            temporal_service=services.temporal,
        )
        services.domains = DomainsService(
            connection=connection,
            dnspublications_service=services.dnspublications,
        )
        services.dnsresources = DNSResourcesService(
            connection=connection, domains_service=services.domains
        )
        services.staticipaddress = StaticIPAddressService(
            connection=connection,
            temporal_service=services.temporal,
        )
        services.ipranges = IPRangesService(
            connection=connection,
            temporal_service=services.temporal,
        )
        services.leases = LeasesService(
            connection=connection,
            dnsresource_service=services.dnsresources,
            node_service=services.nodes,
            staticipaddress_service=services.staticipaddress,
            subnet_service=services.subnets,
            interface_service=services.interfaces,
            iprange_service=services.ipranges,
        )
        return services
