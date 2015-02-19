# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The device handler for the WebSocket connection."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "DeviceHandler",
    ]

from django.core.urlresolvers import reverse
from maasserver.enum import NODE_PERMISSION
from maasserver.models.node import Device
from maasserver.websockets.handlers.timestampedmodel import (
    TimestampedModelHandler,
    )


class DeviceHandler(TimestampedModelHandler):

    class Meta:
        queryset = (
            Device.devices.filter(installable=False)
            .select_related('nodegroup', 'owner')
            .prefetch_related('macaddress_set')
            .prefetch_related('nodegroup__nodegroupinterface_set')
            .prefetch_related('zone')
            .prefetch_related('tags'))
        pk = 'system_id'
        allowed_methods = ['list', 'get']
        exclude = [
            "id",
            "installable",
            "pxe_mac",
            "token",
            "netboot",
            "agent_name",
            "cpu_count",
            "memory",
            "power_state",
            "pxe_mac",
            "routers",
            "architecture",
            "boot_type",
            "status",
            "power_parameters",
            "disable_ipv4",
            "osystem",
            "power_type",
            "error_description",
            "error",
            "license_key",
            "distro_series",
            ]
        list_fields = [
            "system_id",
            "hostname",
            "owner",
            "zone",
            "parent",
            ]
        listen_channels = [
            "device",
            ]

    def get_queryset(self):
        """Return `QuerySet` for devices only vewable by `user`."""
        nodes = super(DeviceHandler, self).get_queryset()
        return Device.devices.get_nodes(
            self.user, NODE_PERMISSION.VIEW, from_nodes=nodes)

    def dehydrate_owner(self, user):
        """Return owners username."""
        if user is None:
            return ""
        else:
            return user.username

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

    def dehydrate(self, obj, data, for_list=False):
        """Add extra fields to `data`."""
        data["url"] = reverse('node-view', args=[obj.system_id])
        data["fqdn"] = obj.fqdn

        data["extra_macs"] = [
            "%s" % mac_address.mac_address
            for mac_address in obj.get_extra_macs()
            ]
        data["tags"] = [
            tag.name
            for tag in obj.tags.all()
            ]
        if not for_list:
            data["ip_addresses"] = list(
                obj.ip_addresses())
        return data

    def get_object(self, params):
        """Get object by using the `pk` in `params`."""
        obj = super(DeviceHandler, self).get_object(params)
        if self.user.is_superuser or obj.owner == self.user:
            return obj
        else:
            return None
