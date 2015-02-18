# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The node handler for the WebSocket connection."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "NodeHandler",
    ]

from django.core.urlresolvers import reverse
from maasserver.enum import NODE_PERMISSION
from maasserver.models.node import Node
from maasserver.utils.converters import human_readable_bytes
from maasserver.websockets.handlers.timestampedmodel import (
    TimestampedModelHandler,
    )


class NodeHandler(TimestampedModelHandler):

    class Meta:
        queryset = (
            Node.objects.filter(installable=True)
                .select_related('nodegroup', 'pxe_mac', 'owner')
                .prefetch_related('macaddress_set')
                .prefetch_related('nodegroup__nodegroupinterface_set')
                .prefetch_related('zone')
                .prefetch_related('tags')
                .prefetch_related('blockdevice_set__physicalblockdevice'))
        pk = 'system_id'
        allowed_methods = ['list', 'get']
        exclude = [
            "id",
            "installable",
            "parent",
            "pxe_mac",
            "token",
            "netboot",
            "agent_name",
            ]
        list_fields = [
            "system_id",
            "hostname",
            "owner",
            "zone",
            "cpu_count",
            "memory",
            "power_state",
            "pxe_mac",
            "zone",
            ]
        listen_channels = [
            "node",
            ]

    def get_queryset(self):
        """Return `QuerySet` for nodes only vewable by `user`."""
        nodes = super(NodeHandler, self).get_queryset()
        return Node.objects.get_nodes(
            self.user, NODE_PERMISSION.VIEW, from_nodes=nodes)

    def dehydrate_owner(self, user):
        """Return owners username."""
        if user is None:
            return ""
        else:
            return user.username

    def dehydrate_pxe_mac(self, mac_address):
        """Return pxe mac as a string."""
        if mac_address is None:
            return None
        else:
            return "%s" % mac_address.mac_address

    def dehydrate_zone(self, zone):
        """Return zone name."""
        return {
            "id": zone.id,
            "name": zone.name,
            "url": reverse('zone-view', args=[zone.name])
            }

    def dehydrate_nodegroup(self, nodegroup):
        """Return the nodegroup name."""
        if nodegroup is None:
            return None
        else:
            return nodegroup.name

    def dehydrate_routers(self, routers):
        """Return list of routers."""
        if routers is None:
            return []
        return [
            "%s" % router
            for router in routers
            ]

    def dehydrate(self, obj, data, for_list=False):
        """Add extra fields to `data`."""
        data["url"] = reverse('node-view', args=[obj.system_id])
        data["fqdn"] = obj.fqdn
        data["status"] = obj.display_status()

        data["extra_macs"] = [
            "%s" % mac_address.mac_address
            for mac_address in obj.get_extra_macs()
            ]
        pxe_mac = obj.get_pxe_mac()
        if pxe_mac is not None:
            data["pxe_mac"] = "%s" % pxe_mac
            data["pxe_mac_vendor"] = obj.get_pxe_mac_vendor()
        else:
            data["pxe_mac"] = data["pxe_mac_vendor"] = ""

        physicalblockdevices = self.get_physicalblockdevices_for(obj)
        data["disks"] = len(physicalblockdevices)
        data["disk_tags"] = self.get_all_disk_tags(physicalblockdevices)
        data["storage"] = human_readable_bytes(
            sum([
                blockdevice.size
                for blockdevice in physicalblockdevices
                ]), include_suffix=False)

        data["tags"] = [
            tag.name
            for tag in obj.tags.all()
            ]
        if not for_list:
            data["ip_addresses"] = list(
                obj.ip_addresses())
            data["physical_disks"] = [
                self.dehydrate_physicalblockdevice(blockdevice)
                for blockdevice in physicalblockdevices
                ]
        return data

    def dehydrate_physicalblockdevice(self, blockdevice,):
        """Return `PhysicalBlockDevice` formatted for JSON encoding."""
        return {
            "name": blockdevice.name,
            "tags": blockdevice.tags,
            "path": blockdevice.path,
            "size": blockdevice.size,
            "block_size": blockdevice.block_size,
            "model": blockdevice.model,
            "serial": blockdevice.serial,
            }

    def get_all_disk_tags(self, physicalblockdevices):
        """Return list of all disk tags in `physicalblockdevices`."""
        tags = set()
        for blockdevice in physicalblockdevices:
            tags = tags.union(blockdevice.tags)
        return list(tags)

    def get_physicalblockdevices_for(self, obj):
        """Return only `PhysicalBlockDevice`s using the prefetched query."""
        return [
            blockdevice.physicalblockdevice
            for blockdevice in obj.blockdevice_set.all()
            if hasattr(blockdevice, "physicalblockdevice")
            ]

    def get_object(self, params):
        """Get object by using the `pk` in `params`."""
        obj = super(NodeHandler, self).get_object(params)
        if self.user.is_superuser:
            return obj
        if obj.owner is None or obj.owner == self.user:
            return obj
        return None
