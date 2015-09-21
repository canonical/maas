# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handlers: `Subnet`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type

from maasserver.api.support import (
    admin_method,
    operation,
    OperationsHandler,
)
from maasserver.enum import NODE_PERMISSION
from maasserver.exceptions import MAASAPIValidationError
from maasserver.forms_subnet import SubnetForm
from maasserver.models import Subnet
from piston.utils import rc


DISPLAYED_SUBNET_FIELDS = (
    'id',
    'name',
    'vlan',
    'space',
    'cidr',
    'gateway_ip',
    'dns_servers',
)


class SubnetsHandler(OperationsHandler):
    """Manage subnets."""
    api_doc_section_name = "Subnets"
    update = delete = None
    fields = DISPLAYED_SUBNET_FIELDS

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        # See the comment in NodeHandler.resource_uri.
        return ('subnets_handler', [])

    def read(self, request):
        """List all subnets."""
        return Subnet.objects.all()

    @admin_method
    def create(self, request):
        """Create a subnet.

        :param name: Name of the subnet.
        :param fabric: Fabric for the subnet. Defaults to the fabric the
            provided VLAN belongs to or defaults to the default fabric.
        :param vlan: VLAN this subnet belongs to. Defaults to the default
            VLAN for the provided fabric or defaults to the default VLAN in
            the default fabric.
        :param vid: VID of the VLAN this subnet belongs to. Only used when
            vlan is not provided. Picks the VLAN with this VID in the provided
            fabric or the default fabric if one is not given.
        :param space: Space this subnet is in. Defaults to the default space.
        :param cidr: The network CIDR for this subnet.
        :param gateway_ip: The gateway IP address for this subnet.
        :param dns_servers: Comma-seperated list of DNS servers for this \
            subnet.
        """
        form = SubnetForm(data=request.data)
        if form.is_valid():
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)


class SubnetHandler(OperationsHandler):
    """Manage subnet."""
    api_doc_section_name = "Subnet"
    create = None
    model = Subnet
    fields = DISPLAYED_SUBNET_FIELDS

    @classmethod
    def resource_uri(cls, subnet=None):
        # See the comment in NodeHandler.resource_uri.
        subnet_id = "subnet_id"
        if subnet is not None:
            subnet_id = subnet.id
        return ('subnet_handler', (subnet_id,))

    @classmethod
    def space(cls, subnet):
        """Return the name of the space.

        Only the name is returned because the space endpoint will return
        a list of all subnets in that space. If this returned the subnet
        object then it would be an infinite loop.
        """
        return subnet.space.name

    def read(self, request, subnet_id):
        """Read subnet.

        Returns 404 if the subnet is not found.
        """
        return Subnet.objects.get_subnet_or_404(
            subnet_id, request.user, NODE_PERMISSION.VIEW)

    def update(self, request, subnet_id):
        """Update subnet.

        :param name: Name of the subnet.
        :param vlan: VLAN this subnet belongs to.
        :param space: Space this subnet is in.
        :param cidr: The network CIDR for this subnet.
        :param gateway_ip: The gateway IP address for this subnet.
        :param dns_servers: Comma-seperated list of DNS servers for this \
            subnet.

        Returns 404 if the subnet is not found.
        """
        subnet = Subnet.objects.get_subnet_or_404(
            subnet_id, request.user, NODE_PERMISSION.ADMIN)
        form = SubnetForm(instance=subnet, data=request.data)
        if form.is_valid():
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)

    def delete(self, request, subnet_id):
        """Delete subnet.

        Returns 404 if the subnet is not found.
        """
        subnet = Subnet.objects.get_subnet_or_404(
            subnet_id, request.user, NODE_PERMISSION.ADMIN)
        subnet.delete()
        return rc.DELETED

    @operation(idempotent=True)
    def reserved_ip_ranges(self, request, subnet_id):
        """Lists IP ranges currently reserved in the subnet"""
        subnet = Subnet.objects.get_subnet_or_404(
            subnet_id, request.user, NODE_PERMISSION.VIEW)
        return [
            iprange.render_json()
            for iprange in subnet.get_ipranges_in_use().ranges
            ]

    @operation(idempotent=True)
    def unreserved_ip_ranges(self, request, subnet_id):
        """Lists IP ranges currently unreserved in the subnet"""
        subnet = Subnet.objects.get_subnet_or_404(
            subnet_id, request.user, NODE_PERMISSION.VIEW)
        return [
            iprange.render_json(include_purpose=False)
            for iprange in subnet.get_ipranges_not_in_use().ranges
            ]
