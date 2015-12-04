# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The cluster handler for the WebSocket connection."""

__all__ = [
    "ClusterHandler",
    ]

from maasserver.clusterrpc.power_parameters import (
    get_all_power_types_from_clusters,
)
from maasserver.models.nodegroup import NodeGroup
from maasserver.websockets.handlers.timestampedmodel import (
    TimestampedModelHandler,
)


def dehydrate_ip_address(ip_address):
    """Dehydrate `IPAddress` to string."""
    if ip_address is None:
        return None
    else:
        return "%s" % ip_address


class ClusterHandler(TimestampedModelHandler):

    class Meta:
        queryset = (
            NodeGroup.objects.all()
            .prefetch_related('nodegroupinterface_set')
            .prefetch_related('nodegroupinterface_set__subnet'))
        pk = 'id'
        allowed_methods = ['list', 'get', 'set_active']
        exclude = [
            "api_token",
            "api_key",
            "dhcp_key",
            "maas_url",
            ]
        listen_channels = [
            "nodegroup",
            ]

    def dehydrate(self, obj, data, for_list=False):
        """Add extra fields to `data`."""
        data["connected"] = obj.is_connected()
        data["state"] = obj.get_state()
        data["power_types"] = self.dehydrate_power_types(obj)
        data["interfaces"] = self.dehydrate_interfaces(obj)
        return data

    def dehydrate_power_types(self, obj):
        """Return all the power types."""
        return get_all_power_types_from_clusters(nodegroups=[obj])

    def dehydrate_interface(self, interface):
        """Dehydrate a `NodeGroupInterface`."""
        return {
            "id": interface.id,
            "ip": "%s" % interface.ip,
            "name": interface.name,
            "management": interface.management,
            "interface": interface.interface,
            "subnet_mask": dehydrate_ip_address(interface.subnet_mask),
            "broadcast_ip": dehydrate_ip_address(interface.broadcast_ip),
            "router_ip": dehydrate_ip_address(interface.router_ip),
            "dynamic_range": {
                "low": dehydrate_ip_address(interface.ip_range_low),
                "high": dehydrate_ip_address(interface.ip_range_high),
                },
            "static_range": {
                "low": dehydrate_ip_address(
                    interface.static_ip_range_low),
                "high": dehydrate_ip_address(
                    interface.static_ip_range_high),
                },
            "foreign_dhcp_ip": dehydrate_ip_address(
                interface.foreign_dhcp_ip),
            "network": (
                "%s" % interface.network
                if interface.network is not None else None),
            }

    def dehydrate_interfaces(self, obj):
        """Dehydrate all `NodeGroupInterface` for obj."""
        return [
            self.dehydrate_interface(interface)
            for interface in obj.nodegroupinterface_set.all()
            ]
