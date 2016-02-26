# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The VLAN handler for the WebSocket connection."""

__all__ = [
    "VLANHandler",
    ]

from maasserver.enum import NODE_PERMISSION
from maasserver.models import (
    RackController,
    VLAN,
)
from maasserver.testing.orm import reload_object
from maasserver.websockets.handlers.timestampedmodel import (
    TimestampedModelHandler,
)
from provisioningserver.logger import get_maas_logger


maaslog = get_maas_logger("websockets.vlan")


class VLANHandler(TimestampedModelHandler):

    class Meta:
        queryset = (
            VLAN.objects.all()
                .select_related('primary_rack', 'secondary_rack')
                .prefetch_related("interface_set")
                .prefetch_related("subnet_set"))
        pk = 'id'
        allowed_methods = [
            'list',
            'get',
            'set_active',
            'configure_dhcp',
            'delete',
        ]
        listen_channels = [
            "vlan",
        ]

    def dehydrate(self, obj, data, for_list=False):
        # We need the system_id for each controller, since that's how we
        # need to look them up inside the Javascript controller.
        if obj.primary_rack is not None:
            data["primary_rack_sid"] = obj.primary_rack.system_id
        if obj.secondary_rack is not None:
            data["secondary_rack_sid"] = obj.secondary_rack.system_id
        data["subnet_ids"] = sorted([
            subnet.id
            for subnet in obj.subnet_set.all()
        ])
        node_ids = {
            interface.node_id
            for interface in obj.interface_set.all()
            if interface.node_id is not None
        }
        data["nodes_count"] = len(node_ids)
        if not for_list:
            data["node_ids"] = sorted(list(node_ids))
            data["space_ids"] = sorted(list({
                subnet.space_id
                for subnet in obj.subnet_set.all()
            }))
        return data

    def delete(self, parameters):
        """Delete this VLAN."""
        vlan = self.get_object(parameters)
        self.user = reload_object(self.user)
        assert self.user.has_perm(
            NODE_PERMISSION.ADMIN, vlan), "Permission denied."
        vlan.delete()

    def configure_dhcp(self, parameters):
        """Helper method to look up rack controllers based on the parameters
        provided in the action input, and then reconfigure DHCP on the VLAN
        based on them.

        Requires a dictionary of parameters containing an ordered list of
        each desired rack controller system_id.

        If no controllers are specified, disables DHCP on the VLAN.
        """
        vlan = self.get_object(parameters)
        self.user = reload_object(self.user)
        assert self.user.has_perm(
            NODE_PERMISSION.ADMIN, vlan), "Permission denied."
        controllers = [
            RackController.objects.get(system_id=system_id)
            for system_id in parameters['controllers']
        ]
        vlan.configure_dhcp(controllers)
        vlan.save()
