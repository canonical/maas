# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handlers: `Subnet`."""

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
from piston3.utils import rc
from provisioningserver.utils.network import IPRangeStatistics


DISPLAYED_SUBNET_FIELDS = (
    'id',
    'name',
    'vlan',
    'space',
    'cidr',
    'gateway_ip',
    'dns_servers',
    'rdns_mode',
    'active_discovery',
    'allow_proxy',
    'managed',
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
        """\
        Create a subnet.

        Required parameters
        -------------------

        cidr
          The network CIDR for this subnet.


        Optional parameters
        -------------------

        name
          Name of the subnet.

        description
          Description of the subnet.

        vlan
          VLAN this subnet belongs to. Defaults to the default VLAN for the
          provided fabric or defaults to the default VLAN in the default fabric
          (if unspecified).

        fabric
          Fabric for the subnet. Defaults to the fabric the
          provided VLAN belongs to, or defaults to the default fabric.

        vid
          VID of the VLAN this subnet belongs to. Only used when vlan is
          not provided. Picks the VLAN with this VID in the provided
          fabric or the default fabric if one is not given.

        space
          Space this subnet is in. Defaults to the default space.

        gateway_ip
          The gateway IP address for this subnet.

        rdns_mode
          How reverse DNS is handled for this subnet.
          One of: 0 (Disabled), 1 (Enabled), or 2 (RFC2317).  Disabled
          means no reverse zone is created; Enabled means generate the
          reverse zone; RFC2317 extends Enabled to create the necessary
          parent zone with the appropriate CNAME resource records for the
          network, if the network is small enough to require the support
          described in RFC2317.

        allow_proxy
          Configure maas-proxy to allow requests from this
          subnet.

        dns_servers
          Comma-seperated list of DNS servers for this subnet.

        managed
          In MAAS 2.0+, all subnets are assumed to be managed by default.

          Only managed subnets allow DHCP to be enabled on their related
          dynamic ranges. (Thus, dynamic ranges become "informational
          only"; an indication that another DHCP server is currently
          handling them, or that MAAS will handle them when the subnet is
          enabled for management.)

          Managed subnets do not allow IP allocation by default. The
          meaning of a "reserved" IP range is reversed for an unmanaged
          subnet. (That is, for managed subnets, "reserved" means "MAAS
          cannot allocate any IP address within this reserved block". For
          unmanaged subnets, "reserved" means "MAAS must allocate IP
          addresses only from reserved IP ranges".
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
        subnet_id = "id"
        if subnet is not None:
            subnet_id = subnet.id
        return ('subnet_handler', (subnet_id,))

    @classmethod
    def space(cls, subnet):
        """Return the name of the space, or None if the space is undefined."""
        if subnet.space is None:
            return None
        return subnet.space.get_name()

    def read(self, request, id):
        """\
        Read subnet.

        Returns 404 if the subnet is not found.
        """
        return Subnet.objects.get_subnet_or_404(
            id, request.user, NODE_PERMISSION.VIEW)

    def update(self, request, id):
        """\
        Update the specified subnet.

        Please see the documentation for the 'create' operation for detailed
        descriptions of each parameter.

        Optional parameters
        -------------------

        name
          Name of the subnet.

        description
          Description of the subnet.

        vlan
          VLAN this subnet belongs to.

        space
          Space this subnet is in.

        cidr
          The network CIDR for this subnet.

        gateway_ip
          The gateway IP address for this subnet.

        rdns_mode
          How reverse DNS is handled for this subnet.

        allow_proxy
          Configure maas-proxy to allow requests from this subnet.

        dns_servers
          Comma-seperated list of DNS servers for this subnet.

        managed
          If False, MAAS should not manage this subnet. (Default: True)

        Returns 404 if the subnet is not found.
        """
        subnet = Subnet.objects.get_subnet_or_404(
            id, request.user, NODE_PERMISSION.ADMIN)
        form = SubnetForm(instance=subnet, data=request.data)
        if form.is_valid():
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)

    def delete(self, request, id):
        """\
        Delete subnet.

        Returns 404 if the subnet is not found.
        """
        subnet = Subnet.objects.get_subnet_or_404(
            id, request.user, NODE_PERMISSION.ADMIN)
        subnet.delete()
        return rc.DELETED

    @operation(idempotent=True)
    def reserved_ip_ranges(self, request, id):
        """\
        Lists IP ranges currently reserved in the subnet.

        Returns 404 if the subnet is not found.
        """
        subnet = Subnet.objects.get_subnet_or_404(
            id, request.user, NODE_PERMISSION.VIEW)
        return subnet.get_ipranges_in_use().render_json()

    @operation(idempotent=True)
    def unreserved_ip_ranges(self, request, id):
        """\
        Lists IP ranges currently unreserved in the subnet.

        Returns 404 if the subnet is not found.
        """
        subnet = Subnet.objects.get_subnet_or_404(
            id, request.user, NODE_PERMISSION.VIEW)
        return subnet.get_ipranges_not_in_use().render_json(
            include_purpose=False)

    @operation(idempotent=True)
    def statistics(self, request, id):
        """\
        Returns statistics for the specified subnet, including:

        num_available: the number of available IP addresses
        largest_available: the largest number of contiguous free IP addresses
        num_unavailable: the number of unavailable IP addresses
        total_addresses: the sum of the available plus unavailable addresses
        usage: the (floating point) usage percentage of this subnet
        usage_string: the (formatted unicode) usage percentage of this subnet
        ranges: the specific IP ranges present in ths subnet (if specified)

        Optional parameters
        -------------------

        include_ranges
           If True, includes detailed information
           about the usage of this range.

        include_suggestions
          If True, includes the suggested gateway and dynamic range for this
          subnet, if it were to be configured.

        Returns 404 if the subnet is not found.
        """
        subnet = Subnet.objects.get_subnet_or_404(
            id, request.user, NODE_PERMISSION.VIEW)
        include_ranges = get_optional_param(
            request.GET, 'include_ranges', default=False, validator=StringBool)
        include_suggestions = get_optional_param(
            request.GET, 'include_suggestions', default=False,
            validator=StringBool)
        full_iprange = subnet.get_iprange_usage()
        statistics = IPRangeStatistics(full_iprange)
        return statistics.render_json(
            include_ranges=include_ranges,
            include_suggestions=include_suggestions)

    @operation(idempotent=True)
    def ip_addresses(self, request, id):
        """\
        Returns a summary of IP addresses assigned to this subnet.

        Optional parameters
        -------------------

        with_username
          If False, suppresses the display of usernames associated with each
          address. (Default: True)

        with_node_summary
          If False, suppresses the display of any node associated with each
          address. (Default: True)
        """
        subnet = Subnet.objects.get_subnet_or_404(
            id, request.user, NODE_PERMISSION.VIEW)
        with_username = get_optional_param(
            request.GET, 'with_username', default=True, validator=StringBool)
        with_node_summary = get_optional_param(
            request.GET, 'with_node_summary', True, validator=StringBool)
        return subnet.render_json_for_related_ips(
            with_username=with_username, with_node_summary=with_node_summary)
