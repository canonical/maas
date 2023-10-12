# Copyright 2015-2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handlers: `Subnet`."""

from formencode.validators import StringBool
from piston3.utils import rc

from maasserver.api.support import admin_method, operation, OperationsHandler
from maasserver.api.utils import get_optional_param
from maasserver.exceptions import MAASAPIValidationError
from maasserver.forms.subnet import SubnetForm
from maasserver.models import Space, Subnet
from maasserver.permissions import NodePermission
from provisioningserver.utils.network import IPRangeStatistics

DISPLAYED_SUBNET_FIELDS = (
    "id",
    "name",
    "description",
    "vlan",
    "space",
    "cidr",
    "gateway_ip",
    "dns_servers",
    "rdns_mode",
    "active_discovery",
    "allow_dns",
    "allow_proxy",
    "managed",
    "disabled_boot_architectures",
)


class SubnetsHandler(OperationsHandler):
    """Manage subnets."""

    api_doc_section_name = "Subnets"
    update = delete = None
    fields = DISPLAYED_SUBNET_FIELDS

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        # See the comment in NodeHandler.resource_uri.
        return ("subnets_handler", [])

    def read(self, request):
        """@description-title List all subnets
        @description Get a list of all subnets.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing list of all
        known subnets.
        @success-example "success-json" [exkey=subnets-read] placeholder text
        """
        return Subnet.objects.all()

    @admin_method
    def create(self, request):
        """@description-title Create a subnet
        @description Creates a new subnet.

        @param (string) "cidr" [required=true] The network CIDR for this
        subnet.
        @param-example "cidr"
            192.168.1.1/24

        @param (string) "name" [required=false] The subnet's name.

        @param (string) "description" [required=false] The subnet's
        description.

        @param (string) "vlan" [required=false] VLAN this subnet belongs to.
        Defaults to the default VLAN for the provided fabric or defaults to the
        default VLAN in the default fabric (if unspecified).

        @param (string) "fabric" [required=false] Fabric for the subnet.
        Defaults to the fabric the provided VLAN belongs to, or defaults to the
        default fabric.

        @param (int) "vid" [required=false] VID of the VLAN this subnet belongs
        to. Only used when vlan is not provided. Picks the VLAN with this VID
        in the provided fabric or the default fabric if one is not given.

        @param (string) "gateway_ip" [required=false] The gateway IP address
        for this subnet.

        @param (int) "rdns_mode" [required=false,formatting=true] How reverse
        DNS is handled for this subnet.  One of:

        - ``0`` Disabled: No reverse zone is created.
        - ``1`` Enabled: Generate reverse zone.
        - ``2`` RFC2317: Extends '1' to create the necessary parent zone with
          the appropriate CNAME resource records for the network, if the the
          network is small enough to require the support described in RFC2317.

        @param (int) "allow_dns" [required=false] Configure MAAS DNS to allow
        DNS resolution from this subnet. '0' == False,'1' == True.

        @param (int) "allow_proxy" [required=false] Configure maas-proxy to
        allow requests from this subnet. '0' == False, '1' == True.

        @param (string) "dns_servers" [required=false] Comma-separated list of
        DNS servers for this subnet.

        @param (int) "managed" [required=false,formatting=true] In MAAS 2.0+,
        all subnets are assumed to be managed by default.

        @param (string) "disabled_boot_architectures" [required=false] A comma
        or space separated list of boot architectures which will not be
        responded to by isc-dhcpd. Values may be the MAAS name for the boot
        architecture, the IANA hex value, or the isc-dhcpd octet.

        Only managed subnets allow DHCP to be enabled on their related dynamic
        ranges. (Thus, dynamic ranges become "informational only"; an
        indication that another DHCP server is currently handling them, or that
        MAAS will handle them when the subnet is enabled for management.)

        Managed subnets do not allow IP allocation by default. The meaning of a
        "reserved" IP range is reversed for an unmanaged subnet. (That is, for
        managed subnets, "reserved" means "MAAS cannot allocate any IP address
        within this reserved block". For unmanaged subnets, "reserved" means
        "MAAS must allocate IP addresses only from reserved IP ranges."

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing information
        about the new subnet.
        @success-example "success-json" [exkey=subnets-create] placeholder text
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
        return ("subnet_handler", (subnet_id,))

    @classmethod
    def space(cls, subnet):
        """Return the name of the space, or None if the space is undefined."""
        if subnet.space is None:
            return Space.UNDEFINED
        return subnet.space.get_name()

    def read(self, request, id):
        """@description-title Get a subnet
        @description Get information about a subnet with the given ID.

        @param (int) "{id}" [required=true] A subnet ID.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing information
        about the subnet.
        @success-example "success-json" [exkey=subnets-read-by-id] placeholder
        text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested subnet is not found.
        @error-example "not-found"
            No Subnet matches the given query.
        """
        return Subnet.objects.get_subnet_or_404(
            id, request.user, NodePermission.view
        )

    def update(self, request, id):
        """@description-title Update a subnet
        @description Update a subnet with the given ID.

        @param (int) "{id}" [required=true] A subnet ID.

        @param (string) "cidr" [required=false] The network CIDR for this
        subnet.
        @param-example "cidr"
            192.168.1.1/24

        @param (string) "name" [required=false] The subnet's name.

        @param (string) "description" [required=false] The subnet's
        description.

        @param (string) "vlan" [required=false] VLAN this subnet belongs to.
        Defaults to the default VLAN for the provided fabric or defaults to the
        default VLAN in the default fabric (if unspecified).

        @param (string) "fabric" [required=false] Fabric for the subnet.
        Defaults to the fabric the provided VLAN belongs to, or defaults to the
        default fabric.

        @param (int) "vid" [required=false] VID of the VLAN this subnet belongs
        to. Only used when vlan is not provided. Picks the VLAN with this VID
        in the provided fabric or the default fabric if one is not given.

        @param (string) "gateway_ip" [required=false] The gateway IP address
        for this subnet.

        @param (int) "rdns_mode" [required=false,formatting=true] How reverse
        DNS is handled for this subnet.  One of:

        - ``0`` Disabled: No reverse zone is created.
        - ``1`` Enabled: Generate reverse zone.
        - ``2`` RFC2317: Extends '1' to create the necessary parent zone with
          the appropriate CNAME resource records for the network, if the the
          network is small enough to require the support described in RFC2317.

        @param (int) "allow_dns" [required=false] Configure MAAS DNS to allow
        DNS resolution from this subnet. '0' == False,'1' == True.

        @param (int) "allow_proxy" [required=false] Configure maas-proxy to
        allow requests from this subnet. '0' == False, '1' == True.

        @param (string) "dns_servers" [required=false] Comma-separated list of
        DNS servers for this subnet.

        @param (int) "managed" [required=false,formatting=true] In MAAS 2.0+,
        all subnets are assumed to be managed by default.

        @param (string) "disabled_boot_architectures" [required=false] A comma
        or space separated list of boot architectures which will not be
        responded to by isc-dhcpd. Values may be the MAAS name for the boot
        architecture, the IANA hex value, or the isc-dhcpd octet.

        Only managed subnets allow DHCP to be enabled on their related dynamic
        ranges. (Thus, dynamic ranges become "informational only"; an
        indication that another DHCP server is currently handling them, or that
        MAAS will handle them when the subnet is enabled for management.)

        Managed subnets do not allow IP allocation by default. The meaning of a
        "reserved" IP range is reversed for an unmanaged subnet. (That is, for
        managed subnets, "reserved" means "MAAS cannot allocate any IP address
        within this reserved block". For unmanaged subnets, "reserved" means
        "MAAS must allocate IP addresses only from reserved IP ranges."

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing information
        about the updated subnet.
        @success-example "success-json" [exkey=subnets-create] placeholder text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested subnet is not found.
        @error-example "not-found"
            No Subnet matches the given query.
        """
        subnet = Subnet.objects.get_subnet_or_404(
            id, request.user, NodePermission.admin
        )
        form = SubnetForm(instance=subnet, data=request.data)
        if form.is_valid():
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)

    def delete(self, request, id):
        """@description-title Delete a subnet
        @description Delete a subnet with the given ID.

        @param (int) "{id}" [required=true] A subnet ID.

        @success (http-status-code) "server-success" 204

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested subnet is not found.
        @error-example "not-found"
            No Subnet matches the given query.
        """
        subnet = Subnet.objects.get_subnet_or_404(
            id, request.user, NodePermission.admin
        )
        subnet.delete()
        return rc.DELETED

    @operation(idempotent=True)
    def reserved_ip_ranges(self, request, id):
        """@description-title List reserved IP ranges
        @description Lists IP ranges currently reserved in the subnet.

        @param (int) "{id}" [required=true] A subnet ID.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing a list of
        reserved IP ranges.
        @success-example "success-json" [exkey=subnets-reserved-ips]
        placeholder text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested subnet is not found.
        @error-example "not-found"
            No Subnet matches the given query.
        """
        subnet = Subnet.objects.get_subnet_or_404(
            id, request.user, NodePermission.view
        )
        return subnet.get_ipranges_in_use().render_json()

    @operation(idempotent=True)
    def unreserved_ip_ranges(self, request, id):
        """@description-title List unreserved IP ranges
        @description Lists IP ranges currently unreserved in the subnet.

        @param (int) "{id}" [required=true] A subnet ID.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing a list of
        unreserved IP ranges.
        @success-example "success-json" [exkey=subnets-unreserved-ips]
        placeholder text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested subnet is not found.
        @error-example "not-found"
            No Subnet matches the given query.
        """
        subnet = Subnet.objects.get_subnet_or_404(
            id, request.user, NodePermission.view
        )
        return subnet.get_ipranges_not_in_use().render_json(
            include_purpose=False
        )

    @operation(idempotent=True)
    def statistics(self, request, id):
        """@description-title Get subnet statistics
        @description Returns statistics for the specified subnet, including:

        - **num_available**: the number of available IP addresses
        - **largest_available**: the largest number of contiguous free IP
          addresses
        - **num_unavailable**: the number of unavailable IP addresses
        - **total_addresses**: the sum of the available plus unavailable
          addresses
        - **usage**: the (floating point) usage percentage of this subnet
        - **usage_string**: the (formatted unicode) usage percentage of this
          subnet
        - **ranges**: the specific IP ranges present in ths subnet (if
          specified)

        Note: to supply additional optional parameters for this request, add
        them to the request URI: e.g.
        ``/subnets/1/?op=statistics&include_suggestions=1``

        @param (int) "{id}" [required=true] A subnet ID.

        @param (int) "include_ranges" [required=false] If '1', includes
        detailed information about the usage of this range. '1' == True, '0' ==
        False.

        @param (int) "include_suggestions" [required=false] If '1', includes
        the suggested gateway and dynamic range for this subnet, if it were to
        be configured. '1' == True, '0' == False.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing the statistics.
        @success-example "success-json" [exkey=subnets-statistics]
        placeholder text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested subnet is not found.
        @error-example "not-found"
            No Subnet matches the given query.
        """
        subnet = Subnet.objects.get_subnet_or_404(
            id, request.user, NodePermission.view
        )
        include_ranges = get_optional_param(
            request.GET, "include_ranges", default=False, validator=StringBool
        )
        include_suggestions = get_optional_param(
            request.GET,
            "include_suggestions",
            default=False,
            validator=StringBool,
        )
        full_iprange = subnet.get_iprange_usage()
        statistics = IPRangeStatistics(full_iprange)
        return statistics.render_json(
            include_ranges=include_ranges,
            include_suggestions=include_suggestions,
        )

    @operation(idempotent=True)
    def ip_addresses(self, request, id):
        """@description-title Summary of IP addresses
        @description Returns a summary of IP addresses assigned to this subnet.

        @param (int) "{id}" [required=true] A subnet ID.

        @param (int) "with_username" [required=false] If '0', suppresses the
        display of usernames associated with each address. '1' == True, '0' ==
        False. (Default: '1')

        @param (int) "with_summary" [required=false] If '0', suppresses the
        display of nodes, BMCs, and and DNS records associated with each
        address. '1' == True, '0' == False. (Default: True)

        @param (int) "with_node_summary" [required=false] Deprecated. Use
        'with_summary'.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing a list of IP
        addresses and information about each.
        @success-example "success-json" [exkey=subnets-ip-addresses]
        placeholder text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested subnet is not found.
        @error-example "not-found"
            No Subnet matches the given query.
        """
        subnet = Subnet.objects.get_subnet_or_404(
            id, request.user, NodePermission.view
        )
        with_username = get_optional_param(
            request.GET, "with_username", default=True, validator=StringBool
        )
        with_summary = get_optional_param(
            request.GET, "with_summary", True, validator=StringBool
        )
        with_node_summary = get_optional_param(
            request.GET, "with_node_summary", True, validator=StringBool
        )
        # Handle deprecated with_node_summary parameter.
        if with_node_summary is False:
            with_summary = False
        return subnet.render_json_for_related_ips(
            with_username=with_username, with_summary=with_summary
        )
