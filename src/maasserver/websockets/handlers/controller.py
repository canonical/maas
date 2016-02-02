# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The controller handler for the WebSocket connection."""

__all__ = [
    "ControllerHandler",
    ]

from maasserver.enum import NODE_PERMISSION
from maasserver.models.node import Node
from maasserver.websockets.handlers.node import (
    node_prefetch,
    NodeHandler,
)


class ControllerHandler(NodeHandler):

    class Meta(NodeHandler.Meta):
        abstract = False
        queryset = node_prefetch(Node.controllers.all())
        allowed_methods = [
            'list',
            'get',
        ]
        exclude = [
            "parent",
            "boot_interface",
            "boot_cluster_ip",
            "token",
            "netboot",
            "agent_name",
            "power_state_updated",
            "gateway_link_ipv4",
            "gateway_link_ipv6",
            "enable_ssh",
            "skip_networking",
            "skip_storage",
            "instance_power_parameters",
            "dns_process",
        ]
        list_fields = [
            "system_id",
            "hostname",
            "owner",
            "cpu_count",
            "memory",
            "power_state",
            "domain",
            "zone",
        ]
        listen_channels = [
            "controller",
        ]

    def get_queryset(self):
        """Return `QuerySet` for devices only viewable by `user`."""
        controllers = super(ControllerHandler, self).get_queryset()
        return Node.controllers.get_nodes(
            self.user, NODE_PERMISSION.VIEW, from_nodes=controllers)
