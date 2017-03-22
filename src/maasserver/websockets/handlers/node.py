# Copyright 2015-2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The node handler for the WebSocket connection."""

__all__ = [
    "NodeHandler",
]

from itertools import chain
import logging
from operator import itemgetter

from lxml import etree
from maasserver.enum import (
    FILESYSTEM_FORMAT_TYPE_CHOICES,
    FILESYSTEM_FORMAT_TYPE_CHOICES_DICT,
    NODE_STATUS,
    NODE_TYPE,
    POWER_STATE,
)
from maasserver.models.cacheset import CacheSet
from maasserver.models.config import Config
from maasserver.models.event import Event
from maasserver.models.filesystemgroup import VolumeGroup
from maasserver.models.nodeprobeddetails import get_single_probed_details
from maasserver.models.physicalblockdevice import PhysicalBlockDevice
from maasserver.models.virtualblockdevice import VirtualBlockDevice
from maasserver.node_action import compile_node_actions
from maasserver.third_party_drivers import get_third_party_driver
from maasserver.utils.converters import (
    human_readable_bytes,
    XMLToYAML,
)
from maasserver.utils.osystems import make_hwe_kernel_ui_text
from maasserver.websockets.base import (
    dehydrate_datetime,
    HandlerDoesNotExistError,
)
from maasserver.websockets.handlers.event import dehydrate_event_type_level
from maasserver.websockets.handlers.timestampedmodel import (
    TimestampedModelHandler,
)
from metadataserver.enum import RESULT_TYPE
from provisioningserver.tags import merge_details_cleanly


def node_prefetch(queryset):
    return (
        queryset
        .select_related('boot_interface', 'owner', 'zone', 'domain')
        .prefetch_related('blockdevice_set__physicalblockdevice')
        .prefetch_related('blockdevice_set__virtualblockdevice')
        .prefetch_related('interface_set__ip_addresses__subnet__vlan__space')
        .prefetch_related('interface_set__ip_addresses__subnet__vlan__fabric')
        .prefetch_related('interface_set__vlan__fabric')
        .prefetch_related('special_filesystems')
        .prefetch_related('tags')
    )


class NodeHandler(TimestampedModelHandler):

    default_osystem = None
    default_distro_series = None

    class Meta:
        abstract = True
        pk = 'system_id'
        pk_type = str

    def dehydrate_owner(self, user):
        """Return owners username."""
        if user is None:
            return ""
        else:
            return user.username

    def dehydrate_domain(self, domain):
        """Return domain name."""
        return {
            "id": domain.id,
            "name": domain.name,
        }

    def dehydrate_zone(self, zone):
        """Return zone name."""
        return {
            "id": zone.id,
            "name": zone.name,
        }

    def dehydrate_last_image_sync(self, last_image_sync):
        """Return formatted datetime."""
        return dehydrate_datetime(
            last_image_sync) if last_image_sync is not None else None

    def dehydrate_power_parameters(self, power_parameters):
        """Return power_parameters None if empty."""
        return None if power_parameters == '' else power_parameters

    def dehydrate(self, obj, data, for_list=False):
        """Add extra fields to `data`."""
        data["fqdn"] = obj.fqdn
        data["actions"] = list(compile_node_actions(obj, self.user).keys())
        data["node_type_display"] = obj.get_node_type_display()

        data["extra_macs"] = [
            "%s" % mac_address
            for mac_address in obj.get_extra_macs()
        ]
        subnets = self.get_all_subnets(obj)
        data["subnets"] = [subnet.cidr for subnet in subnets]
        data["fabrics"] = self.get_all_fabric_names(obj, subnets)
        data["spaces"] = self.get_all_space_names(subnets)

        data["tags"] = [
            tag.name
            for tag in obj.tags.all()
        ]
        if obj.node_type != NODE_TYPE.DEVICE:
            data["memory"] = obj.display_memory()
            data["status"] = obj.display_status()
            data["status_code"] = obj.status
            boot_interface = obj.get_boot_interface()
            if boot_interface is not None:
                data["pxe_mac"] = "%s" % boot_interface.mac_address
                data["pxe_mac_vendor"] = obj.get_pxe_mac_vendor()
            else:
                data["pxe_mac"] = data["pxe_mac_vendor"] = ""

            blockdevices = self.get_blockdevices_for(obj)
            physical_blockdevices = [
                blockdevice for blockdevice in blockdevices
                if isinstance(blockdevice, PhysicalBlockDevice)
                ]
            data["physical_disk_count"] = len(physical_blockdevices)
            data["storage"] = "%3.1f" % (
                sum(
                    blockdevice.size
                    for blockdevice in physical_blockdevices
                    ) / (1000 ** 3))
            data["storage_tags"] = self.get_all_storage_tags(blockdevices)

            data["osystem"] = obj.get_osystem(
                default=self.default_osystem)
            data["distro_series"] = obj.get_distro_series(
                default=self.default_distro_series)
            data["dhcp_on"] = self.get_providing_dhcp(obj)
        if not for_list:
            data["on_network"] = obj.on_network()
            if obj.node_type != NODE_TYPE.DEVICE:
                # XXX lamont 2017-02-15 Much of this should be split out into
                # individual methods, rather than having this huge block of
                # dense code here.
                # Network
                data["interfaces"] = [
                    self.dehydrate_interface(interface, obj)
                    for interface in obj.interface_set.all().order_by('name')
                ]

                data["hwe_kernel"] = make_hwe_kernel_ui_text(obj.hwe_kernel)

                data["power_type"] = obj.power_type
                data["power_parameters"] = self.dehydrate_power_parameters(
                    obj.power_parameters)
                data["power_bmc_node_count"] = obj.bmc.node_set.count() if (
                    obj.bmc is not None) else 0

                # Storage
                data["disks"] = sorted(chain(
                    (self.dehydrate_blockdevice(blockdevice, obj)
                     for blockdevice in blockdevices),
                    (self.dehydrate_volume_group(volume_group) for volume_group
                     in VolumeGroup.objects.filter_by_node(obj)),
                    (self.dehydrate_cache_set(cache_set) for cache_set
                     in CacheSet.objects.get_cache_sets_for_node(obj)),
                ), key=itemgetter("name"))
                data["supported_filesystems"] = [
                    {'key': key, 'ui': ui}
                    for key, ui in FILESYSTEM_FORMAT_TYPE_CHOICES
                ]
                data["storage_layout_issues"] = obj.storage_layout_issues()
                data["special_filesystems"] = [
                    self.dehydrate_filesystem(filesystem)
                    for filesystem in obj.special_filesystems.order_by("id")
                ]

                # Events
                data["events"] = self.dehydrate_events(obj)

                # Machine output
                data = self.dehydrate_summary_output(obj, data)
                data["commissioning_results"] = self.dehydrate_script_set(
                    obj.current_commissioning_script_set)
                data["testing_results"] = self.dehydrate_script_set(
                    obj.current_testing_script_set)
                data["installation_results"] = self.dehydrate_script_set(
                    obj.current_installation_script_set)

                # Third party drivers
                if Config.objects.get_config('enable_third_party_drivers'):
                    driver = get_third_party_driver(obj)
                    if "module" in driver and "comment" in driver:
                        data["third_party_driver"] = {
                            "module": driver["module"],
                            "comment": driver["comment"],
                        }

        return data

    def dehydrate_blockdevice(self, blockdevice, obj):
        """Return `BlockDevice` formatted for JSON encoding."""
        # model and serial are currently only avalible on physical block
        # devices
        if isinstance(blockdevice, PhysicalBlockDevice):
            model = blockdevice.model
            serial = blockdevice.serial
        else:
            serial = model = ""
        partition_table = blockdevice.get_partitiontable()
        if partition_table is not None:
            partition_table_type = partition_table.table_type
        else:
            partition_table_type = ""
        is_boot = blockdevice.id == obj.get_boot_disk().id
        data = {
            "id": blockdevice.id,
            "is_boot": is_boot,
            "name": blockdevice.get_name(),
            "tags": blockdevice.tags,
            "type": blockdevice.type,
            "path": blockdevice.path,
            "size": blockdevice.size,
            "size_human": human_readable_bytes(blockdevice.size),
            "used_size": blockdevice.used_size,
            "used_size_human": human_readable_bytes(
                blockdevice.used_size),
            "available_size": blockdevice.available_size,
            "available_size_human": human_readable_bytes(
                blockdevice.available_size),
            "block_size": blockdevice.block_size,
            "model": model,
            "serial": serial,
            "partition_table_type": partition_table_type,
            "used_for": blockdevice.used_for,
            "filesystem": self.dehydrate_filesystem(
                blockdevice.get_effective_filesystem()),
            "partitions": self.dehydrate_partitions(
                blockdevice.get_partitiontable()),
        }
        if isinstance(blockdevice, VirtualBlockDevice):
            data["parent"] = {
                "id": blockdevice.filesystem_group.id,
                "uuid": blockdevice.filesystem_group.uuid,
                "type": blockdevice.filesystem_group.group_type,
            }
        return data

    def dehydrate_volume_group(self, volume_group):
        """Return `VolumeGroup` formatted for JSON encoding."""
        size = volume_group.get_size()
        available_size = volume_group.get_lvm_free_space()
        used_size = volume_group.get_lvm_allocated_size()
        return {
            "id": volume_group.id,
            "name": volume_group.name,
            "tags": [],
            "type": volume_group.group_type,
            "path": "",
            "size": size,
            "size_human": human_readable_bytes(size),
            "used_size": used_size,
            "used_size_human": human_readable_bytes(used_size),
            "available_size": available_size,
            "available_size_human": human_readable_bytes(available_size),
            "block_size": volume_group.get_virtual_block_device_block_size(),
            "model": "",
            "serial": "",
            "partition_table_type": "",
            "used_for": "volume group",
            "filesystem": None,
            "partitions": None,
        }

    def dehydrate_cache_set(self, cache_set):
        """Return `CacheSet` formatted for JSON encoding."""
        device = cache_set.get_device()
        used_size = device.get_used_size()
        available_size = device.get_available_size()
        bcache_devices = sorted([
            bcache.name
            for bcache in cache_set.filesystemgroup_set.all()
        ])
        return {
            "id": cache_set.id,
            "name": cache_set.name,
            "tags": [],
            "type": "cache-set",
            "path": "",
            "size": device.size,
            "size_human": human_readable_bytes(device.size),
            "used_size": used_size,
            "used_size_human": human_readable_bytes(used_size),
            "available_size": available_size,
            "available_size_human": human_readable_bytes(available_size),
            "block_size": device.get_block_size(),
            "model": "",
            "serial": "",
            "partition_table_type": "",
            "used_for": ", ".join(bcache_devices),
            "filesystem": None,
            "partitions": None,
        }

    def dehydrate_partitions(self, partition_table):
        """Return `PartitionTable` formatted for JSON encoding."""
        if partition_table is None:
            return None
        partitions = []
        for partition in partition_table.partitions.all():
            partitions.append({
                "filesystem": self.dehydrate_filesystem(
                    partition.get_effective_filesystem()),
                "name": partition.get_name(),
                "path": partition.path,
                "type": partition.type,
                "id": partition.id,
                "size": partition.size,
                "size_human": human_readable_bytes(partition.size),
                "used_for": partition.used_for,
            })
        return partitions

    def dehydrate_filesystem(self, filesystem):
        """Return `Filesystem` formatted for JSON encoding."""
        if filesystem is None:
            return None
        return {
            "id": filesystem.id,
            "label": filesystem.label,
            "mount_point": filesystem.mount_point,
            "mount_options": filesystem.mount_options,
            "fstype": filesystem.fstype,
            "is_format_fstype": (
                filesystem.fstype in FILESYSTEM_FORMAT_TYPE_CHOICES_DICT),
            }

    def dehydrate_interface(self, interface, obj):
        """Dehydrate a `interface` into a interface definition."""
        # Sort the links by ID that way they show up in the same order in
        # the UI.
        links = sorted(interface.get_links(), key=itemgetter("id"))
        for link in links:
            # Replace the subnet object with the subnet_id. The client will
            # use this information to pull the subnet information from the
            # websocket.
            subnet = link.pop("subnet", None)
            if subnet is not None:
                link["subnet_id"] = subnet.id
        data = {
            "id": interface.id,
            "type": interface.type,
            "name": interface.get_name(),
            "enabled": interface.is_enabled(),
            "tags": interface.tags,
            "is_boot": interface == obj.get_boot_interface(),
            "mac_address": "%s" % interface.mac_address,
            "vlan_id": interface.vlan_id,
            "parents": [
                nic.id
                for nic in interface.parents.all()
            ],
            "children": [
                nic.child.id
                for nic in interface.children_relationships.all()
            ],
            "links": links,
        }

        # When the node is an ephemeral state display the discovered IP address
        # for this interface. This will only be shown on interfaces that are
        # connected to a MAAS managed subnet.
        if obj.status in {
                NODE_STATUS.COMMISSIONING, NODE_STATUS.ENTERING_RESCUE_MODE,
                NODE_STATUS.RESCUE_MODE, NODE_STATUS.EXITING_RESCUE_MODE,
                NODE_STATUS.TESTING} or (
                    obj.status == NODE_STATUS.FAILED_TESTING and
                    obj.power_state == POWER_STATE.ON):
            discovereds = interface.get_discovered()
            if discovereds is not None:
                for discovered in discovereds:
                    # Replace the subnet object with the subnet_id. The client
                    # will use this information to pull the subnet information
                    # from the websocket.
                    discovered["subnet_id"] = discovered.pop("subnet").id
                data["discovered"] = discovereds

        return data

    def dehydrate_summary_output(self, obj, data):
        """Dehydrate the machine summary output."""
        # Produce a "clean" composite details document.
        probed_details = merge_details_cleanly(
            get_single_probed_details(obj))

        # We check here if there's something to show instead of after
        # the call to get_single_probed_details() because here the
        # details will be guaranteed well-formed.
        if len(probed_details.xpath('/*/*')) == 0:
            data['summary_xml'] = None
            data['summary_yaml'] = None
        else:
            data['summary_xml'] = etree.tostring(
                probed_details, encoding=str, pretty_print=True)
            data['summary_yaml'] = XMLToYAML(
                etree.tostring(
                    probed_details, encoding=str,
                    pretty_print=True)).convert()
        return data

    def dehydrate_script_set(self, script_set):
        """Dehydrate ScriptResults."""
        if script_set is None:
            return []
        ret = []
        for script_result in script_set:
            # MAAS stores stdout, stderr, and the combined output. The
            # metadata API determine which field uploaded data should go
            # into based on the extention of the uploaded file. .out goes
            # to stdout, .err goes to stderr, otherwise its assumed the
            # data is combined. Curtin uploads the installation log as
            # install.log so its stored as a combined result. This ensures
            # a result is always returned. Always return the combined result
            # for testing.
            if (script_result.stdout == b'' or
                    script_set.result_type == RESULT_TYPE.TESTING):
                output = script_result.output
            else:
                output = script_result.stdout

            # MAAS creates an empty script result when commissioning starts for
            # tracking. Don't show the result in the UI until we actually have
            # something to display.
            if (script_set.result_type == RESULT_TYPE.INSTALLATION and
                    output == b''):
                continue

            if script_result.script is not None:
                tags = ', '.join(script_result.script.tags)
                title = script_result.script.title
            else:
                tags = ''
                title = ''
            if title == '':
                ui_name = script_result.name
            else:
                ui_name = '%s (%s)' % (title, script_result.name)
            ret.append({
                'id': script_result.id,
                'name': script_result.name,
                'ui_name': ui_name,
                'title': title,
                'status': script_result.status,
                'status_name': script_result.status_name,
                'tags': tags,
                'output': output,
                'updated': dehydrate_datetime(script_result.updated),
                'started': dehydrate_datetime(script_result.started),
                'ended': dehydrate_datetime(script_result.ended),
                'runtime': script_result.runtime,
            })
            if (script_result.stderr != b'' and
                    script_set.result_type != RESULT_TYPE.TESTING):
                ret.append({
                    'id': script_result.id,
                    'name': '%s.err' % script_result.name,
                    'ui_name': ui_name,
                    'title': title,
                    'status': script_result.status,
                    'status_name': script_result.status_name,
                    'tags': tags,
                    'output': script_result.stderr,
                    'updated': dehydrate_datetime(script_result.updated),
                    'started': dehydrate_datetime(script_result.started),
                    'ended': dehydrate_datetime(script_result.ended),
                    'runtime': script_result.runtime,
                })
        return sorted(ret, key=lambda i: i['name'])

    def dehydrate_events(self, obj):
        """Dehydrate the node events.

        The latests 50 not including DEBUG events will be dehydrated. The
        `EventsHandler` needs to be used if more are required.
        """
        events = (
            Event.objects.filter(node=obj)
            .exclude(type__level=logging.DEBUG)
            .select_related("type")
            .order_by('-id')[:50])
        return [
            {
                "id": event.id,
                "type": {
                    "id": event.type.id,
                    "name": event.type.name,
                    "description": event.type.description,
                    "level": dehydrate_event_type_level(event.type.level),
                },
                "description": event.description,
                "created": dehydrate_datetime(event.created),
            }
            for event in events
        ]

    def get_all_storage_tags(self, blockdevices):
        """Return list of all storage tags in `blockdevices`."""
        tags = set()
        for blockdevice in blockdevices:
            tags = tags.union(blockdevice.tags)
        return list(tags)

    def get_all_subnets(self, obj):
        subnets = set()
        for interface in obj.interface_set.all():
            for ip_address in interface.ip_addresses.all():
                if ip_address.subnet is not None:
                    subnets.add(ip_address.subnet)
        return list(subnets)

    def get_all_fabric_names(self, obj, subnets):
        fabric_names = set()
        for interface in obj.interface_set.all():
            if interface.vlan is not None:
                fabric_names.add(interface.vlan.fabric.name)
        for subnet in subnets:
            fabric_names.add(subnet.vlan.fabric.name)
        return list(fabric_names)

    def get_all_space_names(self, subnets):
        space_names = set()
        for subnet in subnets:
            if subnet.vlan.space is not None:
                space_names.add(subnet.vlan.space.name)
        return list(space_names)

    def get_blockdevices_for(self, obj):
        """Return only `BlockDevice`s using the prefetched query."""
        return [
            blockdevice.actual_instance
            for blockdevice in obj.blockdevice_set.all()
        ]

    def get_object(self, params):
        """Get object by using the `pk` in `params`."""
        obj = super(NodeHandler, self).get_object(params)
        if self.user.is_superuser:
            return obj.as_self()
        if obj.owner is None or obj.owner == self.user:
            return obj.as_self()
        raise HandlerDoesNotExistError(params[self._meta.pk])

    def get_mac_addresses(self, data):
        """Convert the given `data` into a list of mac addresses.

        This is used by the create method and the hydrate method. The `pxe_mac`
        will always be the first entry in the list.
        """
        macs = data.get("extra_macs", [])
        if "pxe_mac" in data:
            macs.insert(0, data["pxe_mac"])
        return macs

    def get_providing_dhcp(self, obj):
        """Return if providing DHCP using the prefetched query."""
        for interface in obj.interface_set.all():
            if interface.vlan is not None:
                if interface.vlan.dhcp_on:
                    return True
        return False
