# Copyright 2016-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The controller handler for the WebSocket connection."""

__all__ = [
    "ControllerHandler",
    ]

from maasserver.enum import NODE_PERMISSION
from maasserver.forms import ControllerForm
from maasserver.models.node import (
    Controller,
    RackController,
)
from maasserver.websockets.base import HandlerError
from maasserver.websockets.handlers.machine import MachineHandler
from maasserver.websockets.handlers.node import node_prefetch
from provisioningserver.utils.version import get_version_tuple


class ControllerHandler(MachineHandler):

    class Meta(MachineHandler.Meta):
        abstract = False
        queryset = node_prefetch(
            Controller.controllers.all().prefetch_related("interface_set"),
            'controllerinfo'
        )
        allowed_methods = [
            'list',
            'get',
            'create',
            'update',
            'action',
            'set_active',
            'check_power',
            'check_images',
            'create_physical',
            'create_vlan',
            'create_bond',
            'update_interface',
            'delete_interface',
            'link_subnet',
            'unlink_subnet',
            'get_summary_xml',
            'get_summary_yaml',
        ]
        form = ControllerForm
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
            "id",
            "system_id",
            "hostname",
            "node_type",
            "status",
            "last_image_sync",
            "cpu_count",
            "cpu_speed",
        ]
        listen_channels = [
            "controller",
        ]

    def get_form_class(self, action):
        """Return the form class used for `action`."""
        if action in ("create", "update"):
            return ControllerForm
        else:
            raise HandlerError("Unknown action: %s" % action)

    def get_queryset(self):
        """Return `QuerySet` for controllers only viewable by `user`."""
        return Controller.controllers.get_nodes(
            self.user, NODE_PERMISSION.VIEW, from_nodes=self._meta.queryset)

    def dehydrate(self, obj, data, for_list=False):
        obj = obj.as_self()
        data = super().dehydrate(obj, data, for_list=for_list)
        data["version"] = obj.version
        if obj.version is not None and len(obj.version) > 0:
            version = get_version_tuple(obj.version)
            data["version__short"] = version.short_version
            long_version = version.short_version
            if len(version.extended_info) > 0:
                long_version += " (%s)" % version.extended_info
            if version.is_snap:
                long_version += " (snap)"
            data["version__long"] = long_version
        data["vlan_ids"] = [
            interface.vlan_id
            for interface in obj.interface_set.all()
        ]
        data["service_ids"] = [
            service.id
            for service in obj.service_set.all()
        ]
        return data

    def check_images(self, params):
        """Get the image sync statuses of requested controllers."""
        result = {}
        for node in [self.get_object(param) for param in params]:
            # We use a RackController method; without the cast, it's a Node.
            node = node.as_rack_controller()
            if isinstance(node, RackController):
                result[node.system_id] = node.get_image_sync_status().replace(
                    "-", " ").title()
        return result

    def dehydrate_show_os_info(self, obj):
        """Always show the OS information for controllers in the UI."""
        return True
