# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The VLAN handler for the WebSocket connection."""


import netaddr

from maasserver.enum import IPRANGE_TYPE
from maasserver.forms.iprange import IPRangeForm
from maasserver.forms.vlan import VLANForm
from maasserver.models import Fabric, IPRange, Subnet, VLAN
from maasserver.permissions import NodePermission
from maasserver.websockets.base import (
    HandlerPermissionError,
    HandlerValidationError,
)
from maasserver.websockets.handlers.timestampedmodel import (
    TimestampedModelHandler,
)
from provisioningserver.logger import get_maas_logger

maaslog = get_maas_logger("websockets.vlan")


class VLANHandler(TimestampedModelHandler):
    class Meta:
        queryset = (
            VLAN.objects.all()
            .select_related("primary_rack", "secondary_rack")
            .prefetch_related("interface_set")
            .prefetch_related("interface_set__node_config__node")
            .prefetch_related("subnet_set")
        )
        pk = "id"
        form = VLANForm
        form_requires_request = False
        allowed_methods = [
            "create",
            "update",
            "list",
            "get",
            "set_active",
            "configure_dhcp",
            "delete",
        ]
        listen_channels = ["vlan"]

    def dehydrate_primary_rack(self, rack):
        if rack is None:
            return None
        else:
            return rack.system_id

    def dehydrate_secondary_rack(self, rack):
        if rack is None:
            return None
        else:
            return rack.system_id

    def dehydrate(self, obj, data, for_list=False):
        nodes = {
            interface.node_config.node
            for interface in obj.interface_set.all()
            if interface.node_config_id is not None
        }
        data["rack_sids"] = sorted(
            node.system_id for node in nodes if node.is_rack_controller
        )
        data["subnet_ids"] = list(
            obj.subnet_set.values_list("id", flat=True).order_by("id")
        )
        if not for_list:
            data["node_ids"] = sorted(node.id for node in nodes)
            data["space_ids"] = sorted(
                list({subnet.vlan.space_id for subnet in obj.subnet_set.all()})
            )
        return data

    def get_form_class(self, action):
        if action == "create":

            def create_vlan_form(*args, **kwargs):
                data = kwargs.get("data", {})
                fabric = data.get("fabric", None)
                if fabric is not None:
                    kwargs["fabric"] = Fabric.objects.get(id=fabric)
                return VLANForm(*args, **kwargs)

            return create_vlan_form
        else:
            return super().get_form_class(action)

    def delete(self, parameters):
        """Delete this VLAN."""
        vlan = self.get_object(parameters)
        if not self.user.has_perm(NodePermission.admin, vlan):
            raise HandlerPermissionError()
        vlan.delete()

    def update(self, parameters):
        """Delete this VLAN."""
        return super().update(parameters)

    def _configure_iprange_and_gateway(self, parameters):
        if "subnet" in parameters and parameters["subnet"] is not None:
            subnet = Subnet.objects.get(id=parameters["subnet"])
        else:
            # Without a subnet, we cannot continue. (We need one to either
            # add an IP range, or specify a gateway IP.)
            return
        gateway = None
        if "gateway" in parameters and parameters["gateway"] is not None:
            gateway_text = parameters["gateway"].strip()
            if len(gateway_text) > 0:
                gateway = netaddr.IPAddress(gateway_text)
                ipnetwork = netaddr.IPNetwork(subnet.cidr)
                if gateway not in ipnetwork and not (
                    gateway.version == 6 and gateway.is_link_local()
                ):
                    raise ValueError(
                        "Gateway IP must be within specified subnet: %s"
                        % subnet.cidr
                    )
        if (
            "start" in parameters
            and "end" in parameters
            and parameters["start"] is not None
            and parameters["end"] is not None
        ):
            start_text = parameters["start"].strip()
            end_text = parameters["end"].strip()
            # User wishes to add a range.
            if len(start_text) > 0 and len(end_text) > 0:
                start_ipaddr = netaddr.IPAddress(start_text)
                end_ipaddr = netaddr.IPAddress(end_text)
                if gateway is not None:
                    # If a gateway was specified, validate that it is not
                    # within the range the user wants to define.
                    desired_range = netaddr.IPRange(start_ipaddr, end_ipaddr)
                    if gateway in desired_range:
                        raise ValueError(
                            "Gateway IP must be outside the specified dynamic "
                            "range."
                        )
                iprange_form = IPRangeForm(
                    data={
                        "start_ip": str(start_ipaddr),
                        "end_ip": str(end_ipaddr),
                        "type": IPRANGE_TYPE.DYNAMIC,
                        "subnet": subnet.id,
                        "user": self.user.username,
                        "comment": "Added via 'Provide DHCP...' in Web UI.",
                    }
                )
                iprange_form.save()
        if gateway is not None:
            subnet.gateway_ip = str(gateway)
            subnet.save()

    def configure_dhcp(self, parameters):
        """Helper method to look up rack controllers based on the parameters
        provided in the action input, and then reconfigure DHCP on the VLAN
        based on them.

        Requires a dictionary of parameters containing an ordered list of
        each desired rack controller system_id.

        If no controllers are specified, disables DHCP on the VLAN.
        """
        vlan = self.get_object(parameters)
        if not self.user.has_perm(NodePermission.admin, vlan):
            raise HandlerPermissionError()
        # Make sure the dictionary both exists, and has the expected number
        # of parameters, to prevent spurious log statements.
        if "extra" in parameters:
            self._configure_iprange_and_gateway(parameters["extra"])
        if "relay_vlan" not in parameters:
            iprange_exists = IPRange.objects.filter(
                type=IPRANGE_TYPE.DYNAMIC, subnet__vlan=vlan
            ).exists()
            if not iprange_exists:
                raise ValueError(
                    "Cannot configure DHCP: At least one dynamic range is "
                    "required."
                )
        controllers = parameters.get("controllers", [])
        data = {
            "dhcp_on": True if len(controllers) > 0 else False,
            "primary_rack": controllers[0] if len(controllers) > 0 else None,
            "secondary_rack": controllers[1] if len(controllers) > 1 else None,
        }
        if "relay_vlan" in parameters:
            data["relay_vlan"] = parameters["relay_vlan"]
        form = VLANForm(instance=vlan, data=data)
        if form.is_valid():
            form.save()
        else:
            raise HandlerValidationError(form.errors)
