# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The controller handler for the WebSocket connection."""

__all__ = [
    "ControllerHandler",
    ]

from maasserver.enum import NODE_PERMISSION
from maasserver.forms import AdminMachineWithMACAddressesForm
from maasserver.models.node import Node
from maasserver.websockets.handlers.machine import MachineHandler
from maasserver.websockets.handlers.node import node_prefetch


class ControllerHandler(MachineHandler):

    class Meta(MachineHandler.Meta):
        abstract = False
        queryset = node_prefetch(
            Node.controllers.all().prefetch_related("interface_set"))
        allowed_methods = [
            'list',
            'get',
            'create',
            'update',
            'action',
            'set_active',
            'check_power',
            'create_physical',
            'create_vlan',
            'create_bond',
            'update_interface',
            'delete_interface',
            'link_subnet',
            'unlink_subnet',
        ]
        form = AdminMachineWithMACAddressesForm
        exclude = [
            "status_expires",
            "parent",
            "boot_interface",
            "boot_cluster_ip",
            "token",
            "netboot",
            "agent_name",
            "power_state_queried",
            "power_state_updated",
            "gateway_link_ipv4",
            "gateway_link_ipv6",
            "enable_ssh",
            "skip_networking",
            "skip_storage",
            "instance_power_parameters",
            "address_ttl",
            "url",
            "dns_process",
            "managing_process",
        ]
        list_fields = [
            "system_id",
            "hostname",
            "node_type",
            "status",
            "last_image_sync",
            ]
        # Controller data rides on the machine channel.
        listen_channels = [
            "machine",
        ]

    def get_queryset(self):
        """Return `QuerySet` for controllers only viewable by `user`."""
        controllers = super(ControllerHandler, self).get_queryset()
        return Node.controllers.get_nodes(
            self.user, NODE_PERMISSION.VIEW, from_nodes=controllers)

    def dehydrate(self, obj, data, for_list=False):
        data = super().dehydrate(obj, data, for_list=for_list)
        data["vlan_ids"] = [
            interface.vlan_id
            for interface in obj.interface_set.all()
        ]
        return data
