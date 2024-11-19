#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Callable

from maasservicelayer.context import Context
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
        context: Context,
        cache: CacheForServices,
    ) -> "ServiceCollectionV3":
        services = cls()
        services.configurations = ConfigurationsService(context=context)
        services.secrets = await SecretsServiceFactory.produce(
            context=context, config_service=services.configurations
        )
        services.temporal = TemporalService(
            context=context,
            cache=cache.get(
                TemporalService.__name__, TemporalService.build_cache_object
            ),
        )
        services.users = UsersService(context=context)
        services.auth = AuthService(
            context=context,
            secrets_service=services.secrets,
            users_service=services.users,
        )
        services.external_auth = ExternalAuthService(
            context=context,
            secrets_service=services.secrets,
            users_service=services.users,
            cache=cache.get(ExternalAuthService.__name__, ExternalAuthService.build_cache_object),  # type: ignore
        )
        services.nodes = NodesService(
            context=context, secrets_service=services.secrets
        )
        services.vmclusters = VmClustersService(context=context)
        services.zones = ZonesService(
            context=context,
            nodes_service=services.nodes,
            vmcluster_service=services.vmclusters,
        )
        services.resource_pools = ResourcePoolsService(context=context)
        services.machines = MachinesService(
            context=context, secrets_service=services.secrets
        )
        services.events = EventsService(context=context)
        services.interfaces = InterfacesService(
            context=context,
            temporal_service=services.temporal,
        )
        services.fabrics = FabricsService(context=context)
        services.spaces = SpacesService(context=context)
        services.vlans = VlansService(
            context=context,
            temporal_service=services.temporal,
            nodes_service=services.nodes,
        )
        services.subnets = SubnetsService(
            context=context,
            temporal_service=services.temporal,
        )
        services.agents = AgentsService(context=context)
        services.dnspublications = DNSPublicationsService(
            context=context,
            temporal_service=services.temporal,
        )
        services.domains = DomainsService(
            context=context,
            dnspublications_service=services.dnspublications,
        )
        services.dnsresources = DNSResourcesService(
            context=context, domains_service=services.domains
        )
        services.staticipaddress = StaticIPAddressService(
            context=context,
            temporal_service=services.temporal,
        )
        services.ipranges = IPRangesService(
            context=context,
            temporal_service=services.temporal,
        )
        services.leases = LeasesService(
            context=context,
            dnsresource_service=services.dnsresources,
            node_service=services.nodes,
            staticipaddress_service=services.staticipaddress,
            subnet_service=services.subnets,
            interface_service=services.interfaces,
            iprange_service=services.ipranges,
        )
        return services
