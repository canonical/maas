# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handlers: `Network`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'NetworkHandler',
    'NetworksHandler',
    ]


from django.shortcuts import get_object_or_404
from maasserver.api.support import (
    admin_method,
    operation,
    OperationsHandler,
)
from maasserver.enum import NODE_PERMISSION
from maasserver.exceptions import MAASAPIValidationError
from maasserver.forms import (
    NetworkConnectMACsForm,
    NetworkDisconnectMACsForm,
    NetworkForm,
    NetworksListingForm,
)
from maasserver.models import (
    Network,
    Node,
)
from maasserver.utils.orm import get_one
from piston.utils import rc


class NetworkHandler(OperationsHandler):
    """Manage a network."""
    api_doc_section_name = "Network"

    model = Network
    fields = (
        'name', 'ip', 'netmask', 'vlan_tag', 'description', 'default_gateway',
        'dns_servers')

    # Creation happens on the NetworksHandler.
    create = None

    def read(self, request, name):
        """Read network definition."""
        return get_object_or_404(Network, name=name)

    @admin_method
    def update(self, request, name):
        """Update network definition.

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
        network = get_object_or_404(Network, name=name)
        form = NetworkForm(
            instance=network, data=request.data,
            delete_macs_if_not_present=False)
        if not form.is_valid():
            raise MAASAPIValidationError(form.errors)
        return form.save()

    @admin_method
    def delete(self, request, name):
        """Delete network definition.

        A network cannot be deleted while it still has nodes attached to it.
        """
        network = get_one(Network.objects.filter(name=name))
        if network is not None:
            network.delete()
        return rc.DELETED

    @admin_method
    @operation(idempotent=False)
    def connect_macs(self, request, name):
        """Connect the given MAC addresses to this network.

        These MAC addresses must belong to nodes in the MAAS, and have been
        registered as such in MAAS.

        Connecting a network interface to a network which it is already
        connected to does nothing.

        :param macs: A list of node MAC addresses, in text form.
        """
        network = get_object_or_404(Network, name=name)
        form = NetworkConnectMACsForm(network=network, data=request.data)
        if not form.is_valid():
            raise MAASAPIValidationError(form.errors)
        form.save()

    @admin_method
    @operation(idempotent=False)
    def disconnect_macs(self, request, name):
        """Disconnect the given MAC addresses from this network.

        Removing a MAC address from a network which it is not connected to
        does nothing.

        :param macs: A list of node MAC addresses, in text form.
        """
        network = get_object_or_404(Network, name=name)
        form = NetworkDisconnectMACsForm(network=network, data=request.data)
        if not form.is_valid():
            raise MAASAPIValidationError(form.errors)
        form.save()

    @operation(idempotent=True)
    def list_connected_macs(self, request, name):
        """Returns the list of MAC addresses connected to this network.

        Only MAC addresses for nodes visible to the requesting user are
        returned.
        """
        network = get_object_or_404(Network, name=name)
        visible_nodes = Node.objects.get_nodes(
            request.user, NODE_PERMISSION.VIEW,
            from_nodes=Node.objects.all())
        return network.macaddress_set.filter(node__in=visible_nodes).order_by(
            'node__hostname', 'mac_address')

    @classmethod
    def resource_uri(cls, network=None):
        # See the comment in NodeHandler.resource_uri.
        if network is None:
            name = 'name'
        else:
            name = network.name
        return ('network_handler', (name, ))


class NetworksHandler(OperationsHandler):
    """Manage the networks."""
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
        return form.filter_networks(Network.objects.all())

    @admin_method
    def create(self, request):
        """Define a network.

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
        form = NetworkForm(request.data)
        if not form.is_valid():
            raise MAASAPIValidationError(form.errors)
        return form.save()

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ('networks_handler', [])
