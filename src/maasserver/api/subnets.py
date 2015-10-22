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

from formencode.validators import StringBool
from maasserver.api.support import (
    admin_method,
    operation,
    OperationsHandler,
)
from maasserver.api.utils import get_optional_param
from maasserver.enum import NODE_PERMISSION
from maasserver.exceptions import MAASAPIValidationError
from maasserver.forms_subnet import SubnetForm
from maasserver.models import Subnet
from piston.utils import rc
from provisioningserver.utils.network import IPRangeStatistics


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
        return subnet.space.get_name()

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
        """Lists IP ranges currently reserved in the subnet.

        Returns 404 if the subnet is not found.
        """
        subnet = Subnet.objects.get_subnet_or_404(
            subnet_id, request.user, NODE_PERMISSION.VIEW)
        return subnet.get_ipranges_in_use().render_json()

    @operation(idempotent=True)
    def unreserved_ip_ranges(self, request, subnet_id):
        """Lists IP ranges currently unreserved in the subnet.

        Returns 404 if the subnet is not found.
        """
        subnet = Subnet.objects.get_subnet_or_404(
            subnet_id, request.user, NODE_PERMISSION.VIEW)
        return subnet.get_ipranges_not_in_use().render_json(
            include_purpose=False)

    @operation(idempotent=True)
    def statistics(self, request, subnet_id):
        """
        Returns statistics for the specified subnet, including:

        num_available - the number of available IP addresses
        largest_available - the largest number of contiguous free IP addresses
        num_unavailable - the number of unavailable IP addresses
        total_addresses - the sum of the available plus unavailable addresses
        usage - the (floating point) usage percentage of this subnet
        usage_string - the (formatted unicode) usage percentage of this subnet
        ranges - the specific IP ranges present in ths subnet (if specified)

        Optional arguments:
        include_ranges: if True, includes detailed information
        about the usage of this range.

        Returns 404 if the subnet is not found.
        """
        subnet = Subnet.objects.get_subnet_or_404(
            subnet_id, request.user, NODE_PERMISSION.VIEW)
        include_ranges = get_optional_param(
            request.GET, 'include_ranges', default=False, validator=StringBool)
        full_iprange = subnet.get_iprange_usage()
        statistics = IPRangeStatistics(full_iprange)
        return statistics.render_json(include_ranges=include_ranges)

    @operation(idempotent=True)
    def ip_addresses(self, request, subnet_id):
        """
        Returns a summary of IP addresses assigned to this subnet.

        Optional arguments:
        with_username: (default=True) if False, suppresses the display
        of usernames associated with each address.
        with_node_summary: (default=True) if False, suppresses the display
        of any node associated with each address.
        """
        subnet = Subnet.objects.get_subnet_or_404(
            subnet_id, request.user, NODE_PERMISSION.VIEW)
        with_username = get_optional_param(
            request.GET, 'with_username', default=True, validator=StringBool)
        with_node_summary = get_optional_param(
            request.GET, 'with_node_summary', True, validator=StringBool)
        return subnet.render_json_for_related_ips(
            with_username=with_username, with_node_summary=with_node_summary)
