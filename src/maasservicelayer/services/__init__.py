# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Callable, Self

from maasservicelayer.context import Context
from maasservicelayer.db.repositories.configurations import (
    ConfigurationsRepository,
)
from maasservicelayer.db.repositories.dhcpsnippets import (
    DhcpSnippetsRepository,
)
from maasservicelayer.db.repositories.dnsdata import DNSDataRepository
from maasservicelayer.db.repositories.dnspublications import (
    DNSPublicationRepository,
)
from maasservicelayer.db.repositories.dnsresources import DNSResourceRepository
from maasservicelayer.db.repositories.domains import DomainsRepository
from maasservicelayer.db.repositories.events import EventsRepository
from maasservicelayer.db.repositories.external_auth import (
    ExternalAuthRepository,
)
from maasservicelayer.db.repositories.fabrics import FabricsRepository
from maasservicelayer.db.repositories.filestorage import FileStorageRepository
from maasservicelayer.db.repositories.interfaces import InterfaceRepository
from maasservicelayer.db.repositories.ipranges import IPRangesRepository
from maasservicelayer.db.repositories.machines import MachinesRepository
from maasservicelayer.db.repositories.nodegrouptorackcontrollers import (
    NodeGroupToRackControllersRepository,
)
from maasservicelayer.db.repositories.nodes import NodesRepository
from maasservicelayer.db.repositories.notification_dismissal import (
    NotificationDismissalsRepository,
)
from maasservicelayer.db.repositories.notifications import (
    NotificationsRepository,
)
from maasservicelayer.db.repositories.reservedips import ReservedIPsRepository
from maasservicelayer.db.repositories.resource_pools import (
    ResourcePoolRepository,
)
from maasservicelayer.db.repositories.service_status import (
    ServiceStatusRepository,
)
from maasservicelayer.db.repositories.spaces import SpacesRepository
from maasservicelayer.db.repositories.sshkeys import SshKeysRepository
from maasservicelayer.db.repositories.sslkeys import SSLKeysRepository
from maasservicelayer.db.repositories.staticipaddress import (
    StaticIPAddressRepository,
)
from maasservicelayer.db.repositories.staticroutes import (
    StaticRoutesRepository,
)
from maasservicelayer.db.repositories.subnets import SubnetsRepository
from maasservicelayer.db.repositories.users import UsersRepository
from maasservicelayer.db.repositories.vlans import VlansRepository
from maasservicelayer.db.repositories.vmcluster import VmClustersRepository
from maasservicelayer.db.repositories.zones import ZonesRepository
from maasservicelayer.services._base import ServiceCache
from maasservicelayer.services.agents import AgentsService
from maasservicelayer.services.auth import AuthService
from maasservicelayer.services.configurations import ConfigurationsService
from maasservicelayer.services.dhcpsnippets import DhcpSnippetsService
from maasservicelayer.services.dnsdata import DNSDataService
from maasservicelayer.services.dnspublications import DNSPublicationsService
from maasservicelayer.services.dnsresources import DNSResourcesService
from maasservicelayer.services.domains import DomainsService
from maasservicelayer.services.events import EventsService
from maasservicelayer.services.external_auth import ExternalAuthService
from maasservicelayer.services.fabrics import FabricsService
from maasservicelayer.services.filestorage import FileStorageService
from maasservicelayer.services.interfaces import InterfacesService
from maasservicelayer.services.ipranges import IPRangesService
from maasservicelayer.services.leases import LeasesService
from maasservicelayer.services.machines import MachinesService
from maasservicelayer.services.nodegrouptorackcontrollers import (
    NodeGroupToRackControllersService,
)
from maasservicelayer.services.nodes import NodesService
from maasservicelayer.services.notification_dismissal import (
    NotificationDismissalService,
)
from maasservicelayer.services.notifications import NotificationsService
from maasservicelayer.services.reservedips import ReservedIPsService
from maasservicelayer.services.resource_pools import ResourcePoolsService
from maasservicelayer.services.secrets import (
    SecretsService,
    SecretsServiceFactory,
)
from maasservicelayer.services.service_status import ServiceStatusService
from maasservicelayer.services.spaces import SpacesService
from maasservicelayer.services.sshkeys import SshKeysService
from maasservicelayer.services.sslkey import SSLKeysService
from maasservicelayer.services.staticipaddress import StaticIPAddressService
from maasservicelayer.services.staticroutes import StaticRoutesService
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

    # Keep them in alphabetical order, please
    agents: AgentsService
    auth: AuthService
    configurations: ConfigurationsService
    dhcpsnippets: DhcpSnippetsService
    dnsdata: DNSDataService
    dnspublications: DNSPublicationsService
    dnsresources: DNSResourcesService
    domains: DomainsService
    events: EventsService
    external_auth: ExternalAuthService
    fabrics: FabricsService
    filestorage: FileStorageService
    interfaces: InterfacesService
    ipranges: IPRangesService
    leases: LeasesService
    machines: MachinesService
    nodegrouptorackcontrollers: NodeGroupToRackControllersService
    nodes: NodesService
    notifications: NotificationsService
    notifications_dismissal: NotificationDismissalService
    reservedips: ReservedIPsService
    resource_pools: ResourcePoolsService
    secrets: SecretsService
    service_status: ServiceStatusService
    spaces: SpacesService
    sshkeys: SshKeysService
    sslkeys: SSLKeysService
    staticipaddress: StaticIPAddressService
    staticroutes: StaticRoutesService
    subnets: SubnetsService
    temporal: TemporalService
    users: UsersService
    vlans: VlansService
    vmclusters: VmClustersService
    zones: ZonesService

    @classmethod
    async def produce(
        cls,
        context: Context,
        cache: CacheForServices,
    ) -> Self:
        services = cls()
        services.configurations = ConfigurationsService(
            context=context,
            configurations_repository=ConfigurationsRepository(context),
        )
        services.service_status = ServiceStatusService(
            context=context,
            service_status_repository=ServiceStatusRepository(context),
        )
        services.secrets = await SecretsServiceFactory.produce(
            context=context,
            config_service=services.configurations,
            cache=cache.get(
                SecretsService.__name__, SecretsService.build_cache_object
            ),  # type: ignore
        )
        services.temporal = TemporalService(
            context=context,
            cache=cache.get(
                TemporalService.__name__, TemporalService.build_cache_object
            ),
        )
        services.users = UsersService(
            context=context, users_repository=UsersRepository(context)
        )
        services.auth = AuthService(
            context=context,
            secrets_service=services.secrets,
            users_service=services.users,
        )
        services.external_auth = ExternalAuthService(
            context=context,
            secrets_service=services.secrets,
            users_service=services.users,
            external_auth_repository=ExternalAuthRepository(context),
            cache=cache.get(ExternalAuthService.__name__, ExternalAuthService.build_cache_object),  # type: ignore
        )
        services.nodes = NodesService(
            context=context,
            secrets_service=services.secrets,
            nodes_repository=NodesRepository(context),
        )
        services.vmclusters = VmClustersService(
            context=context, vmcluster_repository=VmClustersRepository(context)
        )
        services.zones = ZonesService(
            context=context,
            nodes_service=services.nodes,
            vmcluster_service=services.vmclusters,
            zones_repository=ZonesRepository(context),
            cache=cache.get(ZonesService.__name__, ZonesService.build_cache_object),  # type: ignore
        )
        services.resource_pools = ResourcePoolsService(
            context=context,
            resource_pools_repository=ResourcePoolRepository(context),
        )
        services.machines = MachinesService(
            context=context,
            secrets_service=services.secrets,
            machines_repository=MachinesRepository(context),
        )
        services.events = EventsService(
            context=context, events_repository=EventsRepository(context)
        )
        services.interfaces = InterfacesService(
            context=context,
            temporal_service=services.temporal,
            interface_repository=InterfaceRepository(context),
        )
        services.vlans = VlansService(
            context=context,
            temporal_service=services.temporal,
            nodes_service=services.nodes,
            vlans_repository=VlansRepository(context),
        )
        services.spaces = SpacesService(
            context=context,
            vlans_service=services.vlans,
            spaces_repository=SpacesRepository(context),
        )
        services.reservedips = ReservedIPsService(
            context=context,
            temporal_service=services.temporal,
            reservedips_repository=ReservedIPsRepository(context),
        )
        services.staticroutes = StaticRoutesService(
            context=context,
            staticroutes_repository=StaticRoutesRepository(context),
        )
        services.dhcpsnippets = DhcpSnippetsService(
            context=context,
            dhcpsnippets_repository=DhcpSnippetsRepository(context),
        )
        services.ipranges = IPRangesService(
            context=context,
            temporal_service=services.temporal,
            dhcpsnippets_service=services.dhcpsnippets,
            ipranges_repository=IPRangesRepository(context),
        )
        services.nodegrouptorackcontrollers = NodeGroupToRackControllersService(
            context=context,
            nodegrouptorackcontrollers_repository=NodeGroupToRackControllersRepository(
                context
            ),
        )
        services.staticipaddress = StaticIPAddressService(
            context=context,
            temporal_service=services.temporal,
            staticipaddress_repository=StaticIPAddressRepository(context),
        )
        services.subnets = SubnetsService(
            context=context,
            temporal_service=services.temporal,
            staticipaddress_service=services.staticipaddress,
            ipranges_service=services.ipranges,
            staticroutes_service=services.staticroutes,
            reservedips_service=services.reservedips,
            dhcpsnippets_service=services.dhcpsnippets,
            nodegrouptorackcontrollers_service=services.nodegrouptorackcontrollers,
            subnets_repository=SubnetsRepository(context),
        )
        services.fabrics = FabricsService(
            context=context,
            vlans_service=services.vlans,
            subnets_service=services.subnets,
            interfaces_service=services.interfaces,
            fabrics_repository=FabricsRepository(context),
        )
        services.agents = AgentsService(
            context=context,
            configurations_service=services.configurations,
            users_service=services.users,
            cache=cache.get(AgentsService.__name__, AgentsService.build_cache_object),  # type: ignore
        )
        services.dnspublications = DNSPublicationsService(
            context=context,
            temporal_service=services.temporal,
            dnspublication_repository=DNSPublicationRepository(context),
        )
        services.domains = DomainsService(
            context=context,
            dnspublications_service=services.dnspublications,
            domains_repository=DomainsRepository(context),
        )
        services.dnsresources = DNSResourcesService(
            context=context,
            domains_service=services.domains,
            dnspublications_service=services.dnspublications,
            dnsresource_repository=DNSResourceRepository(context),
        )
        services.dnsdata = DNSDataService(
            context=context,
            dnspublications_service=services.dnspublications,
            domains_service=services.domains,
            dnsresources_service=services.dnsresources,
            dnsdata_repository=DNSDataRepository(context),
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
        services.sshkeys = SshKeysService(
            context=context,
            sshkeys_repository=SshKeysRepository(context),
            cache=cache.get(SshKeysService.__name__, SshKeysService.build_cache_object),  # type: ignore
        )
        services.sslkeys = SSLKeysService(
            context=context,
            sslkey_repository=SSLKeysRepository(context),
        )
        services.notifications = NotificationsService(
            context=context, repository=NotificationsRepository(context)
        )
        services.notifications_dismissal = NotificationDismissalService(
            context=context,
            repository=NotificationDismissalsRepository(context),
        )
        services.filestorage = FileStorageService(
            context=context, repository=FileStorageRepository(context)
        )
        return services
