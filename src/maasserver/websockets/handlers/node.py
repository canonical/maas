# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The node handler for the WebSocket connection."""

__all__ = [
    "NodeHandler",
]

import logging
from operator import itemgetter

from lxml import etree
from maasserver.enum import (
    FILESYSTEM_FORMAT_TYPE_CHOICES,
    FILESYSTEM_FORMAT_TYPE_CHOICES_DICT,
    NODE_STATUS,
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
from maasserver.websockets.base import HandlerDoesNotExistError
from maasserver.websockets.handlers.event import dehydrate_event_type_level
from maasserver.websockets.handlers.timestampedmodel import (
    dehydrate_datetime,
    TimestampedModelHandler,
)
from metadataserver.enum import RESULT_TYPE
from metadataserver.models import NodeResult
from provisioningserver.tags import merge_details_cleanly


def node_prefetch(queryset):
    return (
        queryset
        .select_related('boot_interface', 'owner', 'zone', 'domain')
        .prefetch_related(
            'interface_set__ip_addresses__subnet__vlan__fabric')
        .prefetch_related('interface_set__ip_addresses__subnet__space')
        .prefetch_related('interface_set__vlan__fabric')
        .prefetch_related('tags')
        .prefetch_related('blockdevice_set__physicalblockdevice')
        .prefetch_related('blockdevice_set__virtualblockdevice'))


class NodeHandler(TimestampedModelHandler):

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

    def dehydrate_power_parameters(self, power_parameters):
        """Return power_parameters None if empty."""
        return None if power_parameters == '' else power_parameters

    def dehydrate(self, obj, data, for_list=False):
        """Add extra fields to `data`."""
        data["fqdn"] = obj.fqdn
        data["status"] = obj.display_status()
        data["actions"] = list(compile_node_actions(obj, self.user).keys())
        data["memory"] = obj.display_memory()

        data["extra_macs"] = [
            "%s" % mac_address
            for mac_address in obj.get_extra_macs()
        ]
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
            sum([
                blockdevice.size
                for blockdevice in physical_blockdevices
                ]) / (1000 ** 3))
        data["storage_tags"] = self.get_all_storage_tags(blockdevices)

        subnets = self.get_all_subnets(obj)
        data["subnets"] = [subnet.cidr for subnet in subnets]
        data["fabrics"] = self.get_all_fabric_names(obj, subnets)
        data["spaces"] = self.get_all_space_names(subnets)

        data["tags"] = [
            tag.name
            for tag in obj.tags.all()
        ]
        if not for_list:
            data["osystem"] = obj.get_osystem()
            data["distro_series"] = obj.get_distro_series()
            data["hwe_kernel"] = make_hwe_kernel_ui_text(obj.hwe_kernel)

            data["power_type"] = obj.power_type
            data["power_parameters"] = self.dehydrate_power_parameters(
                obj.power_parameters)
            data["power_bmc_node_count"] = obj.bmc.node_set.count() if (
                obj.bmc is not None) else 0

            # Network
            data["interfaces"] = [
                self.dehydrate_interface(interface, obj)
                for interface in obj.interface_set.all().order_by('name')
            ]
            data["on_network"] = obj.on_network()

            # Storage
            data["disks"] = [
                self.dehydrate_blockdevice(blockdevice, obj)
                for blockdevice in blockdevices
            ]
            data["disks"] = data["disks"] + [
                self.dehydrate_volume_group(volume_group)
                for volume_group in VolumeGroup.objects.filter_by_node(obj)
            ] + [
                self.dehydrate_cache_set(cache_set)
                for cache_set in CacheSet.objects.get_cache_sets_for_node(obj)
            ]
            data["disks"] = sorted(data["disks"], key=itemgetter("name"))
            data["supported_filesystems"] = [
                {'key': key, 'ui': ui}
                for key, ui in FILESYSTEM_FORMAT_TYPE_CHOICES
            ]
            data["storage_layout_issues"] = obj.storage_layout_issues()

            # Events
            data["events"] = self.dehydrate_events(obj)

            # Machine output
            data = self.dehydrate_summary_output(obj, data)
            data["commissioning_results"] = self.dehydrate_node_results(
                obj, RESULT_TYPE.COMMISSIONING)
            data["installation_results"] = self.dehydrate_node_results(
                obj, RESULT_TYPE.INSTALLATION)

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
            "label": filesystem.label,
            "mount_point": filesystem.mount_point,
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
            "is_boot": interface == obj.boot_interface,
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

        # When the node is commissioning display the discovered IP address for
        # this interface. This will only be shown on interfaces that are
        # connected to a MAAS managed subnet.
        if obj.status == NODE_STATUS.COMMISSIONING:
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
            get_single_probed_details(obj.system_id))

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

    def dehydrate_node_results(self, obj, result_type):
        """Dehydrate node results with the given `result_type`."""
        return [
            {
                "id": result.id,
                "result": result.script_result,
                "name": result.name,
                "data": result.data,
                "line_count": len(result.data.splitlines()),
                "created": dehydrate_datetime(result.created),
            }
            for result in NodeResult.objects.filter(
                node=obj, result_type=result_type)
        ]

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
            fabric_names.add(interface.vlan.fabric.name)
        for subnet in subnets:
            fabric_names.add(subnet.vlan.fabric.name)
        return list(fabric_names)

    def get_all_space_names(self, subnets):
        space_names = set()
        for subnet in subnets:
            space_names.add(subnet.space.name)
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
            return obj
        if obj.owner is None or obj.owner == self.user:
            return obj
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
