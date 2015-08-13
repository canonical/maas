# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""URL API routing configuration."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
)

str = None

__metaclass__ = type
__all__ = []

from django.conf.urls import (
    patterns,
    url,
)
from maasserver.api.account import AccountHandler
from maasserver.api.auth import api_auth
from maasserver.api.bcache import (
    BcacheHandler,
    BcachesHandler,
)
from maasserver.api.bcache_cacheset import (
    BcacheCacheSetHandler,
    BcacheCacheSetsHandler,
)
from maasserver.api.blockdevices import (
    BlockDeviceHandler,
    BlockDevicesHandler,
)
from maasserver.api.boot_images import BootImagesHandler
from maasserver.api.boot_resources import (
    BootResourceFileUploadHandler,
    BootResourceHandler,
    BootResourcesHandler,
)
from maasserver.api.boot_source_selections import (
    BootSourceSelectionBackwardHandler,
    BootSourceSelectionHandler,
    BootSourceSelectionsBackwardHandler,
    BootSourceSelectionsHandler,
)
from maasserver.api.boot_sources import (
    BootSourceBackwardHandler,
    BootSourceHandler,
    BootSourcesBackwardHandler,
    BootSourcesHandler,
)
from maasserver.api.commissioning_scripts import (
    CommissioningScriptHandler,
    CommissioningScriptsHandler,
)
from maasserver.api.devices import (
    DeviceHandler,
    DevicesHandler,
)
from maasserver.api.doc_handler import (
    api_doc,
    describe,
)
from maasserver.api.events import EventsHandler
from maasserver.api.fabrics import (
    FabricHandler,
    FabricsHandler,
)
from maasserver.api.files import (
    FileHandler,
    FilesHandler,
)
from maasserver.api.ip_addresses import IPAddressesHandler
from maasserver.api.license_keys import (
    LicenseKeyHandler,
    LicenseKeysHandler,
)
from maasserver.api.maas import MaasHandler
from maasserver.api.networks import (
    NetworkHandler,
    NetworksHandler,
)
from maasserver.api.node_group_interfaces import (
    NodeGroupInterfaceHandler,
    NodeGroupInterfacesHandler,
)
from maasserver.api.node_macs import (
    NodeMacHandler,
    NodeMacsHandler,
)
from maasserver.api.nodegroups import (
    NodeGroupHandler,
    NodeGroupsHandler,
)
from maasserver.api.nodes import (
    NodeHandler,
    NodesHandler,
)
from maasserver.api.not_found import not_found_handler
from maasserver.api.partitions import (
    PartitionHandler,
    PartitionsHandler,
)
from maasserver.api.pxeconfig import pxeconfig
from maasserver.api.raid import (
    RaidHandler,
    RaidsHandler,
)
from maasserver.api.results import NodeResultsHandler
from maasserver.api.ssh_keys import (
    SSHKeyHandler,
    SSHKeysHandler,
)
from maasserver.api.ssl_keys import (
    SSLKeyHandler,
    SSLKeysHandler,
)
from maasserver.api.support import (
    AdminRestrictedResource,
    RestrictedResource,
)
from maasserver.api.tags import (
    TagHandler,
    TagsHandler,
)
from maasserver.api.users import (
    UserHandler,
    UsersHandler,
)
from maasserver.api.version import VersionHandler
from maasserver.api.vlans import (
    VlanHandler,
    VlansHandler,
)
from maasserver.api.volume_groups import (
    VolumeGroupHandler,
    VolumeGroupsHandler,
)
from maasserver.api.zones import (
    ZoneHandler,
    ZonesHandler,
)


account_handler = RestrictedResource(AccountHandler, authentication=api_auth)
boot_resource_handler = RestrictedResource(
    BootResourceHandler, authentication=api_auth)
boot_resource_file_upload_handler = RestrictedResource(
    BootResourceFileUploadHandler, authentication=api_auth)
boot_resources_handler = RestrictedResource(
    BootResourcesHandler, authentication=api_auth)
events_handler = RestrictedResource(EventsHandler, authentication=api_auth)
files_handler = RestrictedResource(FilesHandler, authentication=api_auth)
file_handler = RestrictedResource(FileHandler, authentication=api_auth)
ipaddresses_handler = RestrictedResource(
    IPAddressesHandler, authentication=api_auth)
network_handler = RestrictedResource(NetworkHandler, authentication=api_auth)
networks_handler = RestrictedResource(NetworksHandler, authentication=api_auth)
node_handler = RestrictedResource(NodeHandler, authentication=api_auth)
nodes_handler = RestrictedResource(NodesHandler, authentication=api_auth)
device_handler = RestrictedResource(DeviceHandler, authentication=api_auth)
devices_handler = RestrictedResource(DevicesHandler, authentication=api_auth)
node_mac_handler = RestrictedResource(NodeMacHandler, authentication=api_auth)
node_macs_handler = RestrictedResource(
    NodeMacsHandler, authentication=api_auth)
blockdevices_handler = RestrictedResource(
    BlockDevicesHandler, authentication=api_auth)
blockdevice_handler = RestrictedResource(
    BlockDeviceHandler, authentication=api_auth)
partition_handler = RestrictedResource(
    PartitionHandler, authentication=api_auth)
partitions_handler = RestrictedResource(
    PartitionsHandler, authentication=api_auth)
volume_group_handler = RestrictedResource(
    VolumeGroupHandler, authentication=api_auth)
volume_groups_handler = RestrictedResource(
    VolumeGroupsHandler, authentication=api_auth)
raid_device_handler = RestrictedResource(
    RaidHandler, authentication=api_auth)
raid_devices_handler = RestrictedResource(
    RaidsHandler, authentication=api_auth)
bcache_device_handler = RestrictedResource(
    BcacheHandler, authentication=api_auth)
bcache_devices_handler = RestrictedResource(
    BcachesHandler, authentication=api_auth)
bcache_cache_set_handler = RestrictedResource(
    BcacheCacheSetHandler, authentication=api_auth)
bcache_cache_sets_handler = RestrictedResource(
    BcacheCacheSetsHandler, authentication=api_auth)
nodegroup_handler = RestrictedResource(
    NodeGroupHandler, authentication=api_auth)
nodegroups_handler = RestrictedResource(
    NodeGroupsHandler, authentication=api_auth)
nodegroupinterface_handler = RestrictedResource(
    NodeGroupInterfaceHandler, authentication=api_auth)
nodegroupinterfaces_handler = RestrictedResource(
    NodeGroupInterfacesHandler, authentication=api_auth)
boot_images_handler = RestrictedResource(
    BootImagesHandler, authentication=api_auth)
tag_handler = RestrictedResource(TagHandler, authentication=api_auth)
tags_handler = RestrictedResource(TagsHandler, authentication=api_auth)
version_handler = RestrictedResource(VersionHandler)
node_results_handler = RestrictedResource(
    NodeResultsHandler, authentication=api_auth)
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


# Admin handlers.
maas_handler = AdminRestrictedResource(MaasHandler, authentication=api_auth)
commissioning_script_handler = AdminRestrictedResource(
    CommissioningScriptHandler, authentication=api_auth)
commissioning_scripts_handler = AdminRestrictedResource(
    CommissioningScriptsHandler, authentication=api_auth)
boot_source_handler = AdminRestrictedResource(
    BootSourceHandler, authentication=api_auth)
boot_sources_handler = AdminRestrictedResource(
    BootSourcesHandler, authentication=api_auth)
boot_source_selection_handler = AdminRestrictedResource(
    BootSourceSelectionHandler, authentication=api_auth)
boot_source_selections_handler = AdminRestrictedResource(
    BootSourceSelectionsHandler, authentication=api_auth)
boot_source_backward_handler = AdminRestrictedResource(
    BootSourceBackwardHandler, authentication=api_auth)
boot_sources_backward_handler = AdminRestrictedResource(
    BootSourcesBackwardHandler, authentication=api_auth)
boot_source_selection_backward_handler = AdminRestrictedResource(
    BootSourceSelectionBackwardHandler, authentication=api_auth)
boot_source_selections_backward_handler = AdminRestrictedResource(
    BootSourceSelectionsBackwardHandler, authentication=api_auth)
license_key_handler = AdminRestrictedResource(
    LicenseKeyHandler, authentication=api_auth)
license_keys_handler = AdminRestrictedResource(
    LicenseKeysHandler, authentication=api_auth)


# API URLs accessible to anonymous users.
urlpatterns = patterns(
    '',
    url(r'doc/$', api_doc, name='api-doc'),
    url(r'describe/$', describe, name='describe'),
    url(r'pxeconfig/$', pxeconfig, name='pxeconfig'),
    url(r'version/$', version_handler, name='version_handler'),
)


# API URLs for logged-in users.
urlpatterns += patterns(
    '',
    url(
        r'^nodes/(?P<system_id>[^/]+)/macs/(?P<mac_address>.+)/$',
        node_mac_handler, name='node_mac_handler'),
    url(
        r'^nodes/(?P<system_id>[^/]+)/macs/$', node_macs_handler,
        name='node_macs_handler'),
    url(r'^nodes/(?P<system_id>[^/]+)/blockdevices/$',
        blockdevices_handler, name='blockdevices_handler'),
    url(r'^nodes/(?P<system_id>[^/]+)/blockdevices/(?P<device_id>[^/]+)/$',
        blockdevice_handler, name='blockdevice_handler'),
    url(r'^nodes/(?P<system_id>[^/]+)/blockdevices/'
        '(?P<device_id>[^/]+)/partitions/$',
        partitions_handler, name='partitions_handler'),
    url(r'^nodes/(?P<system_id>[^/]+)/blockdevices/'
        '(?P<device_id>[^/]+)/partition/(?P<partition_id>[^/]+)$',
        partition_handler, name='partition_handler'),
    url(r'^nodes/(?P<system_id>[^/]+)/volume-groups/$',
        volume_groups_handler, name='volume_groups_handler'),
    url(r'^nodes/(?P<system_id>[^/]+)/volume-group/'
        '(?P<volume_group_id>[^/]+)/$',
        volume_group_handler, name='volume_group_handler'),
    url(r'^nodes/(?P<system_id>[^/]+)/raids/$',
        raid_devices_handler, name='raid_devices_handler'),
    url(r'^nodes/(?P<system_id>[^/]+)/raid/(?P<raid_id>[^/]+)/$',
        raid_device_handler, name='raid_device_handler'),
    url(r'^nodes/(?P<system_id>[^/]+)/bcaches/$',
        bcache_devices_handler, name='bcache_devices_handler'),
    url(r'^nodes/(?P<system_id>[^/]+)/bcache/(?P<bcache_id>[^/]+)/$',
        bcache_device_handler, name='bcache_device_handler'),
    url(r'^nodes/(?P<system_id>[^/]+)/bcache-cache-sets/$',
        bcache_cache_sets_handler, name='bcache_cache_sets_handler'),
    url(r'^nodes/(?P<system_id>[^/]+)/bcache-cache-set/'
        '(?P<cache_set_id>[^/]+)/$',
        bcache_cache_set_handler, name='bcache_cache_set_handler'),
    url(
        r'^nodes/(?P<system_id>[^/]+)/$', node_handler,
        name='node_handler'),
    url(r'^nodes/$', nodes_handler, name='nodes_handler'),
    # For backward compatibility, handle obviously repeated paths as if they
    # were not repeated. See https://bugs.launchpad.net/maas/+bug/1131323.
    url(r'^nodes/.*/nodes/$', nodes_handler),
    url(
        r'^devices/(?P<system_id>[^/]+)/$', device_handler,
        name='device_handler'),
    url(r'^devices/$', devices_handler, name='devices_handler'),
    url(r'^events/$', events_handler, name='events_handler'),
    url(
        r'^nodegroups/(?P<uuid>[^/]+)/$',
        nodegroup_handler, name='nodegroup_handler'),
    url(r'^nodegroups/$', nodegroups_handler, name='nodegroups_handler'),
    url(r'^nodegroups/(?P<uuid>[^/]+)/interfaces/$',
        nodegroupinterfaces_handler, name='nodegroupinterfaces_handler'),
    url(r'^nodegroups/(?P<uuid>[^/]+)/interfaces/(?P<name>[^/]+)/$',
        nodegroupinterface_handler, name='nodegroupinterface_handler'),
    url(r'^nodegroups/(?P<uuid>[^/]+)/boot-images/$',
        boot_images_handler, name='boot_images_handler'),
    url(
        r'^networks/(?P<name>[^/]+)/$',
        network_handler, name='network_handler'),
    url(r'^networks/$', networks_handler, name='networks_handler'),
    url(r'^files/$', files_handler, name='files_handler'),
    url(r'^files/(?P<filename>.+)/$', file_handler, name='file_handler'),
    url(r'^account/$', account_handler, name='account_handler'),
    url(
        r'^account/prefs/sslkeys/(?P<keyid>[^/]+)/$', sslkey_handler,
        name='sslkey_handler'),
    url(r'^account/prefs/sslkeys/$', sslkeys_handler, name='sslkeys_handler'),
    url(
        r'^account/prefs/sshkeys/(?P<keyid>[^/]+)/$', sshkey_handler,
        name='sshkey_handler'),
    url(r'^account/prefs/sshkeys/$', sshkeys_handler, name='sshkeys_handler'),
    url(r'^tags/(?P<name>[^/]+)/$', tag_handler, name='tag_handler'),
    url(r'^tags/$', tags_handler, name='tags_handler'),
    url(
        r'^commissioning-results/$',
        node_results_handler, name='node_results_handler'),
    url(
        r'^installation-results/$',
        node_results_handler, name='node_results_handler'),
    url(r'^users/$', users_handler, name='users_handler'),
    url(r'^users/(?P<username>[^/]+)/$', user_handler, name='user_handler'),
    url(r'^zones/(?P<name>[^/]+)/$', zone_handler, name='zone_handler'),
    url(r'^zones/$', zones_handler, name='zones_handler'),
    url(
        r'^fabrics/$',
        fabrics_handler, name='fabrics_handler'),
    url(
        r'^fabrics/(?P<fabric_id>[^/]+)/$',
        fabric_handler, name='fabric_handler'),
    url(
        r'^fabrics/(?P<fabric_id>[^/]+)/vlans/$',
        vlans_handler, name='vlans_handler'),
    url(
        r'^fabrics/(?P<fabric_id>[^/]+)/vlans/(?P<vlan_id>[^/]+)/$',
        vlan_handler, name='vlan_handler'),
    url(r'^ipaddresses/$', ipaddresses_handler, name='ipaddresses_handler'),
    url(
        r'^boot-resources/$',
        boot_resources_handler, name='boot_resources_handler'),
    url(
        r'^boot-resources/(?P<id>[^/]+)/$',
        boot_resource_handler, name='boot_resource_handler'),
    url(
        r'^boot-resources/(?P<id>[^/]+)/upload/(?P<file_id>[^/]+)/$',
        boot_resource_file_upload_handler,
        name='boot_resource_file_upload_handler'),
)


# API URLs for admin users.
urlpatterns += patterns(
    '',
    url(r'^maas/$', maas_handler, name='maas_handler'),
    url(
        r'^commissioning-scripts/$', commissioning_scripts_handler,
        name='commissioning_scripts_handler'),
    url(
        r'^commissioning-scripts/(?P<name>[^/]+)$',
        commissioning_script_handler, name='commissioning_script_handler'),
    url(
        r'^license-keys/$', license_keys_handler, name='license_keys_handler'),
    url(
        r'^license-key/(?P<osystem>[^/]+)/(?P<distro_series>[^/]+)$',
        license_key_handler, name='license_key_handler'),
    url(r'^boot-sources/$',
        boot_sources_handler, name='boot_sources_handler'),
    url(r'^boot-sources/(?P<id>[^/]+)/$',
        boot_source_handler, name='boot_source_handler'),
    url(r'^boot-sources/(?P<boot_source_id>[^/]+)/selections/$',
        boot_source_selections_handler,
        name='boot_source_selections_handler'),
    url(r'^boot-sources/(?P<boot_source_id>[^/]+)/selections/(?P<id>[^/]+)/$',
        boot_source_selection_handler,
        name='boot_source_selection_handler'),
    url(r'^nodegroups/(?P<uuid>[^/]+)/boot-sources/$',
        boot_sources_backward_handler, name='boot_sources_backward_handler'),
    url(r'^nodegroups/(?P<uuid>[^/]+)/boot-sources/(?P<id>[^/]+)/$',
        boot_source_backward_handler, name='boot_source_backward_handler'),
    url(r'^nodegroups/(?P<uuid>[^/]+)/boot-sources/(?P<boot_source_id>[^/]+)/'
        'selections/$',
        boot_source_selections_backward_handler,
        name='boot_source_selections_backward_handler'),
    url(r'^nodegroups/(?P<uuid>[^/]+)/boot-sources/(?P<boot_source_id>[^/]+)/'
        'selections/(?P<id>[^/]+)/$',
        boot_source_selection_backward_handler,
        name='boot_source_selection_backward_handler'),
)


# Last resort: return an API 404 response.
urlpatterns += patterns(
    '',
    url(r'^.*', not_found_handler, name='handler_404')
)
