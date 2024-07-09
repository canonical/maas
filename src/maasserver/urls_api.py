# Copyright 2012-2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""URL API routing configuration."""


import itertools

from django.urls import re_path as django_re_path

from maasserver.api.account import AccountHandler
from maasserver.api.auth import api_auth
from maasserver.api.bcache import BcacheHandler, BcachesHandler
from maasserver.api.bcache_cacheset import (
    BcacheCacheSetHandler,
    BcacheCacheSetsHandler,
)
from maasserver.api.blockdevices import BlockDeviceHandler, BlockDevicesHandler
from maasserver.api.boot_resources import (
    BootResourceFileUploadHandler,
    BootResourceHandler,
    BootResourcesHandler,
)
from maasserver.api.boot_source_selections import (
    BootSourceSelectionHandler,
    BootSourceSelectionsHandler,
)
from maasserver.api.boot_sources import BootSourceHandler, BootSourcesHandler
from maasserver.api.commissioning_scripts import (
    CommissioningScriptHandler,
    CommissioningScriptsHandler,
)
from maasserver.api.devices import DeviceHandler, DevicesHandler
from maasserver.api.dhcpsnippets import DHCPSnippetHandler, DHCPSnippetsHandler
from maasserver.api.discoveries import DiscoveriesHandler, DiscoveryHandler
from maasserver.api.dnsresourcerecords import (
    DNSResourceRecordHandler,
    DNSResourceRecordsHandler,
)
from maasserver.api.dnsresources import DNSResourceHandler, DNSResourcesHandler
from maasserver.api.doc_handler import describe
from maasserver.api.doc_oapi import endpoint
from maasserver.api.domains import DomainHandler, DomainsHandler
from maasserver.api.events import EventsHandler
from maasserver.api.fabrics import FabricHandler, FabricsHandler
from maasserver.api.files import FileHandler, FilesHandler
from maasserver.api.image_sync import (
    ImagesSyncProgressHandler,
    ImageSyncProgressHandler,
)
from maasserver.api.interfaces import InterfaceHandler, InterfacesHandler
from maasserver.api.ip_addresses import IPAddressesHandler
from maasserver.api.ipranges import IPRangeHandler, IPRangesHandler
from maasserver.api.license_keys import LicenseKeyHandler, LicenseKeysHandler
from maasserver.api.maas import MaasHandler
from maasserver.api.machines import MachineHandler, MachinesHandler
from maasserver.api.networks import NetworkHandler, NetworksHandler
from maasserver.api.nodedevices import NodeDeviceHandler, NodeDevicesHandler
from maasserver.api.nodes import NodeHandler, NodesHandler
from maasserver.api.not_found import not_found_handler
from maasserver.api.notification import (
    NotificationHandler,
    NotificationsHandler,
)
from maasserver.api.packagerepositories import (
    PackageRepositoriesHandler,
    PackageRepositoryHandler,
)
from maasserver.api.partitions import PartitionHandler, PartitionsHandler
from maasserver.api.pods import (
    PodHandler,
    PodsHandler,
    VmHostHandler,
    VmHostsHandler,
)
from maasserver.api.rackcontrollers import (
    RackControllerHandler,
    RackControllersHandler,
)
from maasserver.api.raid import RaidHandler, RaidsHandler
from maasserver.api.regioncontrollers import (
    RegionControllerHandler,
    RegionControllersHandler,
)
from maasserver.api.reservedip import ReservedIpHandler, ReservedIpsHandler
from maasserver.api.resourcepools import (
    ResourcePoolHandler,
    ResourcePoolsHandler,
)
from maasserver.api.results import NodeResultsHandler
from maasserver.api.scriptresults import (
    NodeScriptResultHandler,
    NodeScriptResultsHandler,
)
from maasserver.api.scripts import NodeScriptHandler, NodeScriptsHandler
from maasserver.api.spaces import SpaceHandler, SpacesHandler
from maasserver.api.ssh_keys import SSHKeyHandler, SSHKeysHandler
from maasserver.api.ssl_keys import SSLKeyHandler, SSLKeysHandler
from maasserver.api.staticroutes import StaticRouteHandler, StaticRoutesHandler
from maasserver.api.subnets import SubnetHandler, SubnetsHandler
from maasserver.api.support import (
    AdminRestrictedResource,
    OperationsResource,
    RestrictedResource,
)
from maasserver.api.switch_boot_order import SwitchBootOrderHandler
from maasserver.api.tags import TagHandler, TagsHandler
from maasserver.api.users import UserHandler, UsersHandler
from maasserver.api.version import VersionHandler
from maasserver.api.virtualmachine import (
    VirtualMachineHandler,
    VirtualMachinesHandler,
)
from maasserver.api.vlans import VlanHandler, VlansHandler
from maasserver.api.vmcluster import VmClusterHandler, VmClustersHandler
from maasserver.api.vmfs_datastores import (
    VmfsDatastoreHandler,
    VmfsDatastoresHandler,
)
from maasserver.api.volume_groups import (
    VolumeGroupHandler,
    VolumeGroupsHandler,
)
from maasserver.api.zones import ZoneHandler, ZonesHandler

maas_handler = RestrictedResource(MaasHandler, authentication=api_auth)
account_handler = RestrictedResource(AccountHandler, authentication=api_auth)
boot_resource_handler = RestrictedResource(
    BootResourceHandler, authentication=api_auth
)
boot_resource_file_upload_handler = RestrictedResource(
    BootResourceFileUploadHandler, authentication=api_auth
)
boot_resources_handler = RestrictedResource(
    BootResourcesHandler, authentication=api_auth
)
discovery_handler = RestrictedResource(
    DiscoveryHandler, authentication=api_auth
)
discoveries_handler = RestrictedResource(
    DiscoveriesHandler, authentication=api_auth
)
events_handler = RestrictedResource(EventsHandler, authentication=api_auth)
files_handler = RestrictedResource(FilesHandler, authentication=api_auth)
file_handler = RestrictedResource(FileHandler, authentication=api_auth)
ipaddresses_handler = RestrictedResource(
    IPAddressesHandler, authentication=api_auth
)
network_handler = RestrictedResource(NetworkHandler, authentication=api_auth)
networks_handler = RestrictedResource(NetworksHandler, authentication=api_auth)
node_handler = RestrictedResource(NodeHandler, authentication=api_auth)
nodes_handler = RestrictedResource(NodesHandler, authentication=api_auth)
machine_handler = RestrictedResource(MachineHandler, authentication=api_auth)
machines_handler = RestrictedResource(MachinesHandler, authentication=api_auth)
rackcontroller_handler = RestrictedResource(
    RackControllerHandler, authentication=api_auth
)
rackcontrollers_handler = RestrictedResource(
    RackControllersHandler, authentication=api_auth
)
regioncontroller_handler = RestrictedResource(
    RegionControllerHandler, authentication=api_auth
)
regioncontrollers_handler = RestrictedResource(
    RegionControllersHandler, authentication=api_auth
)
device_handler = RestrictedResource(DeviceHandler, authentication=api_auth)
devices_handler = RestrictedResource(DevicesHandler, authentication=api_auth)
pod_handler = RestrictedResource(PodHandler, authentication=api_auth)
pods_handler = RestrictedResource(PodsHandler, authentication=api_auth)
vm_cluster_handler = RestrictedResource(
    VmClusterHandler, authentication=api_auth
)
vm_clusters_handler = RestrictedResource(
    VmClustersHandler, authentication=api_auth
)
vm_host_handler = RestrictedResource(VmHostHandler, authentication=api_auth)
vm_hosts_handler = RestrictedResource(VmHostsHandler, authentication=api_auth)
virtual_machine_handler = RestrictedResource(
    VirtualMachineHandler, authentication=api_auth
)
virtual_machines_handler = RestrictedResource(
    VirtualMachinesHandler, authentication=api_auth
)
dhcp_snippet_handler = RestrictedResource(
    DHCPSnippetHandler, authentication=api_auth
)
dhcp_snippets_handler = RestrictedResource(
    DHCPSnippetsHandler, authentication=api_auth
)
package_repository_handler = RestrictedResource(
    PackageRepositoryHandler, authentication=api_auth
)
package_repositories_handler = RestrictedResource(
    PackageRepositoriesHandler, authentication=api_auth
)
dnsresourcerecord_handler = RestrictedResource(
    DNSResourceRecordHandler, authentication=api_auth
)
dnsresourcerecords_handler = RestrictedResource(
    DNSResourceRecordsHandler, authentication=api_auth
)
dnsresource_handler = RestrictedResource(
    DNSResourceHandler, authentication=api_auth
)
dnsresources_handler = RestrictedResource(
    DNSResourcesHandler, authentication=api_auth
)
domain_handler = RestrictedResource(DomainHandler, authentication=api_auth)
domains_handler = RestrictedResource(DomainsHandler, authentication=api_auth)
blockdevices_handler = RestrictedResource(
    BlockDevicesHandler, authentication=api_auth
)
blockdevice_handler = RestrictedResource(
    BlockDeviceHandler, authentication=api_auth
)
partition_handler = RestrictedResource(
    PartitionHandler, authentication=api_auth
)
partitions_handler = RestrictedResource(
    PartitionsHandler, authentication=api_auth
)
volume_group_handler = RestrictedResource(
    VolumeGroupHandler, authentication=api_auth
)
volume_groups_handler = RestrictedResource(
    VolumeGroupsHandler, authentication=api_auth
)
raid_device_handler = RestrictedResource(RaidHandler, authentication=api_auth)
raid_devices_handler = RestrictedResource(
    RaidsHandler, authentication=api_auth
)
bcache_device_handler = RestrictedResource(
    BcacheHandler, authentication=api_auth
)
bcache_devices_handler = RestrictedResource(
    BcachesHandler, authentication=api_auth
)
bcache_cache_set_handler = RestrictedResource(
    BcacheCacheSetHandler, authentication=api_auth
)
bcache_cache_sets_handler = RestrictedResource(
    BcacheCacheSetsHandler, authentication=api_auth
)
vmfs_datastore_handler = RestrictedResource(
    VmfsDatastoreHandler, authentication=api_auth
)
vmfs_datastores_handler = RestrictedResource(
    VmfsDatastoresHandler, authentication=api_auth
)
interface_handler = RestrictedResource(
    InterfaceHandler, authentication=api_auth
)
interfaces_handler = RestrictedResource(
    InterfacesHandler, authentication=api_auth
)
tag_handler = RestrictedResource(TagHandler, authentication=api_auth)
tags_handler = RestrictedResource(TagsHandler, authentication=api_auth)
version_handler = OperationsResource(VersionHandler)  # Allow anon.
node_results_handler = RestrictedResource(
    NodeResultsHandler, authentication=api_auth
)
sshkey_handler = RestrictedResource(SSHKeyHandler, authentication=api_auth)
sshkeys_handler = RestrictedResource(SSHKeysHandler, authentication=api_auth)
sslkey_handler = RestrictedResource(SSLKeyHandler, authentication=api_auth)
sslkeys_handler = RestrictedResource(SSLKeysHandler, authentication=api_auth)
user_handler = RestrictedResource(UserHandler, authentication=api_auth)
users_handler = RestrictedResource(UsersHandler, authentication=api_auth)
zone_handler = RestrictedResource(ZoneHandler, authentication=api_auth)
zones_handler = RestrictedResource(ZonesHandler, authentication=api_auth)
fabric_handler = RestrictedResource(FabricHandler, authentication=api_auth)
fabrics_handler = RestrictedResource(FabricsHandler, authentication=api_auth)
vlan_handler = RestrictedResource(VlanHandler, authentication=api_auth)
vlans_handler = RestrictedResource(VlansHandler, authentication=api_auth)
space_handler = RestrictedResource(SpaceHandler, authentication=api_auth)
spaces_handler = RestrictedResource(SpacesHandler, authentication=api_auth)
subnet_handler = RestrictedResource(SubnetHandler, authentication=api_auth)
subnets_handler = RestrictedResource(SubnetsHandler, authentication=api_auth)
iprange_handler = RestrictedResource(IPRangeHandler, authentication=api_auth)
ipranges_handler = RestrictedResource(IPRangesHandler, authentication=api_auth)
reservedip_handler = RestrictedResource(
    ReservedIpHandler, authentication=api_auth
)
reservedips_handler = RestrictedResource(
    ReservedIpsHandler, authentication=api_auth
)
staticroute_handler = RestrictedResource(
    StaticRouteHandler, authentication=api_auth
)
staticroutes_handler = RestrictedResource(
    StaticRoutesHandler, authentication=api_auth
)
notification_handler = RestrictedResource(
    NotificationHandler, authentication=api_auth
)
notifications_handler = RestrictedResource(
    NotificationsHandler, authentication=api_auth
)
script_handler = RestrictedResource(NodeScriptHandler, authentication=api_auth)
scripts_handler = RestrictedResource(
    NodeScriptsHandler, authentication=api_auth
)
script_result_handler = RestrictedResource(
    NodeScriptResultHandler, authentication=api_auth
)
script_results_handler = RestrictedResource(
    NodeScriptResultsHandler, authentication=api_auth
)
resourcepool_handler = RestrictedResource(
    ResourcePoolHandler, authentication=api_auth
)
resourcepools_handler = RestrictedResource(
    ResourcePoolsHandler, authentication=api_auth
)
node_device_handler = RestrictedResource(
    NodeDeviceHandler, authentication=api_auth
)
node_devices_handler = RestrictedResource(
    NodeDevicesHandler, authentication=api_auth
)

# Admin handlers.
commissioning_script_handler = AdminRestrictedResource(
    CommissioningScriptHandler, authentication=api_auth
)
commissioning_scripts_handler = AdminRestrictedResource(
    CommissioningScriptsHandler, authentication=api_auth
)
boot_source_handler = AdminRestrictedResource(
    BootSourceHandler, authentication=api_auth
)
boot_sources_handler = AdminRestrictedResource(
    BootSourcesHandler, authentication=api_auth
)
boot_source_selection_handler = AdminRestrictedResource(
    BootSourceSelectionHandler, authentication=api_auth
)
boot_source_selections_handler = AdminRestrictedResource(
    BootSourceSelectionsHandler, authentication=api_auth
)
license_key_handler = AdminRestrictedResource(
    LicenseKeyHandler, authentication=api_auth
)
license_keys_handler = AdminRestrictedResource(
    LicenseKeysHandler, authentication=api_auth
)


# Internal Handlers
switch_boot_order_handler = OperationsResource(
    SwitchBootOrderHandler, authentication=api_auth
)

image_sync_progress_handler = OperationsResource(
    ImageSyncProgressHandler, authentication=api_auth
)
images_sync_progress_handler = OperationsResource(
    ImagesSyncProgressHandler, authentication=api_auth
)


def re_path(route, view, name=None, **kwargs):
    paths = [django_re_path(route, view, name=name, **kwargs)]
    if isinstance(view, OperationsResource):
        for _, op in view.handler.exports.keys():
            if op:
                paths.append(
                    django_re_path(
                        route.replace("/$", f"/op-{op}$"),
                        view,
                        name=f"{name}-op-{op}",
                        **kwargs,
                    )
                )
    return paths


# API URLs accessible to anonymous users.
patterns = [
    re_path(r"describe/$", describe, name="describe"),
    re_path(r"version/$", version_handler, name="version_handler"),
    re_path(r"openapi.yaml$", endpoint, name="openapi_endpoint"),
]


# API URLs for logged-in users.
patterns += [
    re_path(r"^maas/$", maas_handler, name="maas_handler"),
    re_path(
        r"^nodes/(?P<system_id>[^/]+)/blockdevices/$",
        blockdevices_handler,
        name="blockdevices_handler",
    ),
    re_path(
        r"^nodes/(?P<system_id>[^/]+)/blockdevices/(?P<id>[^/]+)/$",
        blockdevice_handler,
        name="blockdevice_handler",
    ),
    re_path(
        r"^nodes/(?P<system_id>[^/]+)/blockdevices/"
        "(?P<device_id>[^/]+)/partitions/$",
        partitions_handler,
        name="partitions_handler",
    ),
    # LP:1715230 - When the partition and volume-group endpoints were added
    # they did not include a trailing 's' when accessing an individual resource
    # while reading all resources did include the 's'. Both endpoints work with
    # and without the trailing 's' to be more REST-like while not breaking API
    # compatibility.
    re_path(
        r"^nodes/(?P<system_id>[^/]+)/blockdevices/"
        "(?P<device_id>[^/]+)/partition[s]?/(?P<id>[^/]+)$",
        partition_handler,
        name="partition_handler",
    ),
    re_path(
        r"^nodes/(?P<system_id>[^/]+)/volume-groups/$",
        volume_groups_handler,
        name="volume_groups_handler",
    ),
    re_path(
        r"^nodes/(?P<system_id>[^/]+)/volume-group[s]?/" "(?P<id>[^/]+)/$",
        volume_group_handler,
        name="volume_group_handler",
    ),
    re_path(
        r"^nodes/(?P<system_id>[^/]+)/raids/$",
        raid_devices_handler,
        name="raid_devices_handler",
    ),
    re_path(
        r"^nodes/(?P<system_id>[^/]+)/raid/(?P<id>[^/]+)/$",
        raid_device_handler,
        name="raid_device_handler",
    ),
    re_path(
        r"^nodes/(?P<system_id>[^/]+)/bcaches/$",
        bcache_devices_handler,
        name="bcache_devices_handler",
    ),
    re_path(
        r"^nodes/(?P<system_id>[^/]+)/bcache/(?P<id>[^/]+)/$",
        bcache_device_handler,
        name="bcache_device_handler",
    ),
    re_path(
        r"^nodes/(?P<system_id>[^/]+)/bcache-cache-sets/$",
        bcache_cache_sets_handler,
        name="bcache_cache_sets_handler",
    ),
    re_path(
        r"^nodes/(?P<system_id>[^/]+)/bcache-cache-set/(?P<id>[^/]+)/$",
        bcache_cache_set_handler,
        name="bcache_cache_set_handler",
    ),
    re_path(
        r"^nodes/(?P<system_id>[^/]+)/vmfs-datastores/$",
        vmfs_datastores_handler,
        name="vmfs_datastores_handler",
    ),
    re_path(
        r"^nodes/(?P<system_id>[^/]+)/vmfs-datastore/(?P<id>[^/]+)/$",
        vmfs_datastore_handler,
        name="vmfs_datastore_handler",
    ),
    re_path(
        r"^nodes/(?P<system_id>[^/]+)/interfaces/(?P<id>[^/]+)/$",
        interface_handler,
        name="interface_handler",
    ),
    re_path(
        r"^nodes/(?P<system_id>[^/]+)/interfaces/$",
        interfaces_handler,
        name="interfaces_handler",
    ),
    re_path(
        r"^nodes/(?P<system_id>[^/]+)/results/$",
        script_results_handler,
        name="script_results_handler",
    ),
    re_path(
        r"^nodes/(?P<system_id>[^/]+)/results/(?P<id>[^/]+)/$",
        script_result_handler,
        name="script_result_handler",
    ),
    re_path(
        r"^nodes/(?P<system_id>[^/]+)/devices/$",
        node_devices_handler,
        name="node_devices_handler",
    ),
    re_path(
        r"^nodes/(?P<system_id>[^/]+)/devices/(?P<id>[^/]+)/$",
        node_device_handler,
        name="node_device_handler",
    ),
    re_path(
        r"^nodes/(?P<system_id>[^/]+)/$", node_handler, name="node_handler"
    ),
    re_path(r"^nodes/$", nodes_handler, name="nodes_handler"),
    re_path(
        r"^machines/(?P<system_id>[^/]+)/$",
        machine_handler,
        name="machine_handler",
    ),
    re_path(r"^machines/$", machines_handler, name="machines_handler"),
    re_path(
        r"^rackcontrollers/(?P<system_id>[^/]+)/$",
        rackcontroller_handler,
        name="rackcontroller_handler",
    ),
    re_path(
        r"^rackcontrollers/$",
        rackcontrollers_handler,
        name="rackcontrollers_handler",
    ),
    re_path(
        r"^regioncontrollers/(?P<system_id>[^/]+)/$",
        regioncontroller_handler,
        name="regioncontroller_handler",
    ),
    re_path(
        r"^regioncontrollers/$",
        regioncontrollers_handler,
        name="regioncontrollers_handler",
    ),
    re_path(
        r"^devices/(?P<system_id>[^/]+)/$",
        device_handler,
        name="device_handler",
    ),
    re_path(r"^devices/$", devices_handler, name="devices_handler"),
    re_path(r"^pods/(?P<id>[^/]+)/$", pod_handler, name="pod_handler"),
    re_path(r"^pods/$", pods_handler, name="pods_handler"),
    # XXX: ltrager 2020-05-11 - Pods are being renamed vm-hosts. For now keep
    # pods to not break API compatibility.
    re_path(
        r"^vm-hosts/(?P<id>[^/]+)/$", vm_host_handler, name="vm_host_handler"
    ),
    re_path(r"^vm-hosts/$", vm_hosts_handler, name="vm_hosts_handler"),
    re_path(
        r"^virtual-machines/(?P<id>[^/]+)$",
        virtual_machine_handler,
        name="virtual_machine_handler",
    ),
    re_path(
        r"^virtual-machines/$",
        virtual_machines_handler,
        name="virtual_machines_handler",
    ),
    re_path(
        r"^vm-clusters/(?P<id>[^/]+)$",
        vm_cluster_handler,
        name="vm_cluster_handler",
    ),
    re_path(
        r"^vm-clusters/$",
        vm_clusters_handler,
        name="vm_clusters_handler",
    ),
    re_path(r"^events/$", events_handler, name="events_handler"),
    re_path(r"^discovery/$", discoveries_handler, name="discoveries_handler"),
    re_path(
        r"^discovery/(?P<discovery_id>[.: \w=^]+)/*/$",
        discovery_handler,
        name="discovery_handler",
    ),
    re_path(
        r"^networks/(?P<name>[^/]+)/$", network_handler, name="network_handler"
    ),
    re_path(r"^networks/$", networks_handler, name="networks_handler"),
    re_path(r"^files/$", files_handler, name="files_handler"),
    re_path(r"^files/(?P<filename>.+)/$", file_handler, name="file_handler"),
    re_path(r"^account/$", account_handler, name="account_handler"),
    re_path(
        r"^account/prefs/sslkeys/(?P<id>[^/]+)/$",
        sslkey_handler,
        name="sslkey_handler",
    ),
    re_path(
        r"^account/prefs/sslkeys/$", sslkeys_handler, name="sslkeys_handler"
    ),
    re_path(
        r"^account/prefs/sshkeys/(?P<id>[^/]+)/$",
        sshkey_handler,
        name="sshkey_handler",
    ),
    re_path(
        r"^account/prefs/sshkeys/$", sshkeys_handler, name="sshkeys_handler"
    ),
    re_path(r"^tags/(?P<name>[^/]+)/$", tag_handler, name="tag_handler"),
    re_path(r"^tags/$", tags_handler, name="tags_handler"),
    re_path(
        r"^commissioning-results/$",
        node_results_handler,
        name="node_results_handler",
    ),
    re_path(
        r"^installation-results/$",
        node_results_handler,
        name="node_results_handler",
    ),
    re_path(r"^users/$", users_handler, name="users_handler"),
    re_path(
        r"^users/(?P<username>[^/]+)/$", user_handler, name="user_handler"
    ),
    re_path(r"^zones/(?P<name>[^/]+)/$", zone_handler, name="zone_handler"),
    re_path(r"^zones/$", zones_handler, name="zones_handler"),
    re_path(r"^fabrics/$", fabrics_handler, name="fabrics_handler"),
    re_path(
        r"^fabrics/(?P<id>[^/]+)/$", fabric_handler, name="fabric_handler"
    ),
    re_path(
        r"^fabrics/(?P<fabric_id>[^/]+)/vlans/$",
        vlans_handler,
        name="vlans_handler",
    ),
    re_path(
        r"^vlans/(?P<vlan_id>[^/]+)/$", vlan_handler, name="vlanid_handler"
    ),
    re_path(
        r"^fabrics/(?P<fabric_id>[^/]+)/vlans/(?P<vid>[^/]+)/$",
        vlan_handler,
        name="vlan_handler",
    ),
    re_path(r"^spaces/$", spaces_handler, name="spaces_handler"),
    re_path(r"^spaces/(?P<id>[^/]+)/$", space_handler, name="space_handler"),
    re_path(r"^subnets/$", subnets_handler, name="subnets_handler"),
    # Note: Any changes to the regex here may need to be reflected in
    # models/subnets.py.
    re_path(
        r"^subnets/(?P<id>[.: \w-]+(?:/\d\d\d?)?)/$",
        subnet_handler,
        name="subnet_handler",
    ),
    re_path(
        r"^ipaddresses/$", ipaddresses_handler, name="ipaddresses_handler"
    ),
    re_path(r"^ipranges/$", ipranges_handler, name="ipranges_handler"),
    re_path(
        r"^ipranges/(?P<id>[^/]+)/$", iprange_handler, name="iprange_handler"
    ),
    re_path(
        r"^static-routes/$", staticroutes_handler, name="staticroutes_handler"
    ),
    re_path(
        r"^static-routes/(?P<id>[^/]+)/$",
        staticroute_handler,
        name="staticroute_handler",
    ),
    re_path(
        r"^dnsresourcerecords/$",
        dnsresourcerecords_handler,
        name="dnsresourcerecords_handler",
    ),
    re_path(
        r"^dnsresourcerecords/(?P<id>[^/]+)/$",
        dnsresourcerecord_handler,
        name="dnsresourcerecord_handler",
    ),
    re_path(
        r"^dnsresources/$", dnsresources_handler, name="dnsresources_handler"
    ),
    re_path(
        r"^dnsresources/(?P<id>[^/]+)/$",
        dnsresource_handler,
        name="dnsresource_handler",
    ),
    re_path(r"^domains/$", domains_handler, name="domains_handler"),
    re_path(
        r"^domains/(?P<id>[^/]+)/$", domain_handler, name="domain_handler"
    ),
    re_path(
        r"^boot-resources/$",
        boot_resources_handler,
        name="boot_resources_handler",
    ),
    re_path(
        r"^boot-resources/(?P<id>[^/]+)/$",
        boot_resource_handler,
        name="boot_resource_handler",
    ),
    re_path(
        r"^boot-resources/(?P<id>[^/]+)/upload/(?P<file_id>[^/]+)/$",
        boot_resource_file_upload_handler,
        name="boot_resource_file_upload_handler",
    ),
    re_path(
        r"^package-repositories/$",
        package_repositories_handler,
        name="package_repositories_handler",
    ),
    re_path(
        r"^package-repositories/(?P<id>[^/]+)/$",
        package_repository_handler,
        name="package_repository_handler",
    ),
    re_path(
        r"^dhcp-snippets/$",
        dhcp_snippets_handler,
        name="dhcp_snippets_handler",
    ),
    re_path(
        r"^dhcp-snippets/(?P<id>[^/]+)/$",
        dhcp_snippet_handler,
        name="dhcp_snippet_handler",
    ),
    re_path(
        r"^notifications/$",
        notifications_handler,
        name="notifications_handler",
    ),
    re_path(
        r"^notifications/(?P<id>[^/]+)/$",
        notification_handler,
        name="notification_handler",
    ),
    re_path(r"^scripts/$", scripts_handler, name="scripts_handler"),
    re_path(
        r"^scripts/(?P<name>[^/]+)$", script_handler, name="script_handler"
    ),
    re_path(
        r"^reservedips/$",
        reservedips_handler,
        name="reservedips_handler",
    ),
    re_path(
        r"^reservedips/(?P<id>[^/]+)/$",
        reservedip_handler,
        name="reservedip_handler",
    ),
    re_path(
        r"^resourcepool/(?P<id>[^/]+)/$",
        resourcepool_handler,
        name="resourcepool_handler",
    ),
    re_path(
        r"^resourcepools/$",
        resourcepools_handler,
        name="resourcepools_handler",
    ),
]


# API URLs for admin users.
patterns += [
    re_path(
        r"^commissioning-scripts/$",
        commissioning_scripts_handler,
        name="commissioning_scripts_handler",
    ),
    re_path(
        r"^commissioning-scripts/(?P<name>[^/]+)$",
        commissioning_script_handler,
        name="commissioning_script_handler",
    ),
    re_path(
        r"^license-keys/$", license_keys_handler, name="license_keys_handler"
    ),
    re_path(
        r"^license-key/(?P<osystem>[^/]+)/(?P<distro_series>[^/]+)$",
        license_key_handler,
        name="license_key_handler",
    ),
    re_path(
        r"^boot-sources/$", boot_sources_handler, name="boot_sources_handler"
    ),
    re_path(
        r"^boot-sources/(?P<id>[^/]+)/$",
        boot_source_handler,
        name="boot_source_handler",
    ),
    re_path(
        r"^boot-sources/(?P<boot_source_id>[^/]+)/selections/$",
        boot_source_selections_handler,
        name="boot_source_selections_handler",
    ),
    re_path(
        r"^boot-sources/(?P<boot_source_id>[^/]+)/selections/(?P<id>[^/]+)/$",
        boot_source_selection_handler,
        name="boot_source_selection_handler",
    ),
]

# API URLs for internal endpoints
patterns += [
    re_path(
        r"^switch-boot-order/(?P<system_id>[^/]+)/$",
        switch_boot_order_handler,
        name="switch_boot_order_handler",
    ),
    re_path(
        r"^images-sync-progress/(?P<file_id>[^/]+)/(?P<system_id>[^/]+)/$",
        image_sync_progress_handler,
        name="image_sync_progress_handler",
    ),
    re_path(
        r"^images-sync-progress/$",
        images_sync_progress_handler,
        name="images_sync_progress_handler",
    ),
]

# Last resort: return an API 404 response.
patterns += [re_path(r"^.*", not_found_handler, name="handler_404")]

urlpatterns = list(itertools.chain(*patterns))
