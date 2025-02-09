# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handlers: `Network`."""

from django.urls import reverse
from piston3.utils import rc

from maasserver.api.subnets import SubnetHandler, SubnetsHandler
from maasserver.api.support import (
    admin_method,
    deprecated,
    operation,
    OperationsHandler,
)
from maasserver.exceptions import MAASAPIValidationError
from maasserver.forms import NetworksListingForm
from maasserver.models import Interface, Node, Subnet
from maasserver.permissions import NodePermission


def convert_to_network_name(subnet):
    """Convert the name of the subnet to a network name."""
    return "subnet-%d" % subnet.id


def render_network_json(subnet):
    cidr = subnet.get_ipnetwork()
    return {
        "name": convert_to_network_name(subnet),
        "ip": cidr.ip,
        "netmask": cidr.netmask,
        "vlan_tag": subnet.vlan.vid,
        "description": subnet.name,
        "default_gateway": subnet.gateway_ip,
        "dns_servers": subnet.dns_servers,
        "resource_uri": reverse(
            "network_handler", args=["subnet-%d" % subnet.id]
        ),
    }


def render_networks_json(subnets):
    return [render_network_json(subnet) for subnet in subnets]


@deprecated(use=SubnetHandler)
class NetworkHandler(OperationsHandler):
    """
    Manage a network.
    """

    api_doc_section_name = "Network"
    create = None

    def read(self, request, name):
        """Read network definition."""
        return render_network_json(
            Subnet.objects.get_object_by_specifiers_or_raise(name)
        )

    @admin_method
    def update(self, request, name):
        """Update network definition.

        This endpoint is no longer available. Use the 'subnet' endpoint
        instead.

        :param name: A simple name for the network, to make it easier to
            refer to.  Must consist only of letters, digits, dashes, and
            underscores.
        :param ip: Base IP address for the network, e.g. `10.1.0.0`.  The host
            bits will be zeroed.
        :param netmask: Subnet mask to indicate which parts of an IP address
            are part of the network address.  For example, `255.255.255.0`.
        :param vlan_tag: Optional VLAN tag: a number between 1 and 0xffe (4094)
            inclusive, or zero for an untagged network.
        :param description: Detailed description of the network for the benefit
            of users and administrators.
        """
        return rc.NOT_HERE

    @admin_method
    def delete(self, request, name):
        """Delete network definition.

        This endpoint is no longer available. Use the 'subnet' endpoint
        instead.
        """
        return rc.NOT_HERE

    @admin_method
    @operation(idempotent=False)
    def connect_macs(self, request, name):
        """Connect the given MAC addresses to this network.

        This endpoint is no longer available. Use the 'subnet' endpoint
        instead.
        """
        return rc.NOT_HERE

    @admin_method
    @operation(idempotent=False)
    def disconnect_macs(self, request, name):
        """Disconnect the given MAC addresses from this network.

        This endpoint is no longer available. Use the 'subnet' endpoint
        instead.
        """
        return rc.NOT_HERE

    @operation(idempotent=True)
    def list_connected_macs(self, request, name):
        """Returns the list of MAC addresses connected to this network.

        Only MAC addresses for nodes visible to the requesting user are
        returned.
        """
        subnet = Subnet.objects.get_object_by_specifiers_or_raise(name)
        visible_nodes = Node.objects.get_nodes(
            request.user, NodePermission.view, from_nodes=Node.objects.all()
        )
        interfaces = Interface.objects.filter(
            node_config__node__in=visible_nodes, ip_addresses__subnet=subnet
        )
        existing_macs = set()
        unique_interfaces_by_mac = [
            interface
            for interface in interfaces
            if (
                interface.mac_address not in existing_macs
                and not existing_macs.add(interface.mac_address)
            )
        ]
        unique_interfaces_by_mac = sorted(
            unique_interfaces_by_mac,
            key=lambda x: (
                x.node_config.node.hostname.lower(),
                x.mac_address,
            ),
        )
        return [
            {"mac_address": str(interface.mac_address)}
            for interface in unique_interfaces_by_mac
        ]

    @classmethod
    def resource_uri(cls, network=None):
        # See the comment in NodeHandler.resource_uri.
        if network is None:
            name = "name"
        else:
            name = convert_to_network_name(network)
        return ("network_handler", (name,))


@deprecated(use=SubnetsHandler)
class NetworksHandler(OperationsHandler):
    """
    Manage the networks.
    """

    api_doc_section_name = "Networks"
    update = delete = None

    def read(self, request):
        """List networks.

        :param node: Optionally, nodes which must be attached to any returned
            networks.  If more than one node is given, the result will be
            restricted to networks that these nodes have in common.
        """
        form = NetworksListingForm(data=request.GET)
        if not form.is_valid():
            raise MAASAPIValidationError(form.errors)
        return render_networks_json(form.filter_subnets(Subnet.objects.all()))

    @admin_method
    def create(self, request):
        """Define a network.

        This endpoint is no longer available. Use the 'subnets' endpoint
        instead.
        """
        return rc.NOT_HERE

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ("networks_handler", [])
