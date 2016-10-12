# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handler: `StaticIPAddress`."""

__all__ = [
    'IPAddressesHandler',
    ]

from django.http import Http404
from django.http.response import (
    HttpResponseBadRequest,
    HttpResponseForbidden,
)
from formencode.validators import StringBool
from maasserver.api.interfaces import DISPLAYED_INTERFACE_FIELDS
from maasserver.api.support import (
    operation,
    OperationsHandler,
)
from maasserver.api.utils import (
    get_mandatory_param,
    get_optional_param,
)
from maasserver.enum import (
    INTERFACE_LINK_TYPE,
    INTERFACE_TYPE,
    IPADDRESS_TYPE,
    NODE_PERMISSION,
)
from maasserver.exceptions import (
    MAASAPIBadRequest,
    MAASAPIForbidden,
    MAASAPIValidationError,
)
from maasserver.forms import (
    ClaimIPForMACForm,
    ReleaseIPForm,
)
from maasserver.models import (
    DNSResource,
    Domain,
    Interface,
    StaticIPAddress,
    Subnet,
)
from maasserver.utils.orm import transactional
from netaddr import IPAddress
from netaddr.core import AddrFormatError
from piston3.utils import rc
from provisioningserver.logger import get_maas_logger


maaslog = get_maas_logger("ip_addresses")


class IPAddressesHandler(OperationsHandler):
    """Manage IP addresses allocated by MAAS."""
    api_doc_section_name = "IP Addresses"
    model = StaticIPAddress
    fields = (
        'alloc_type',
        'alloc_type_name',
        'created',
        'ip',
        'owner',
        ('interface_set', DISPLAYED_INTERFACE_FIELDS),
        'subnet'
    )
    create = update = delete = None

    @classmethod
    def owner(cls, static_ip_address):
        return static_ip_address.user

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ('ipaddresses_handler', [])

    @transactional
    def _claim_ip(
            self, user, subnet, ip_address, mac=None, hostname=None):
        """Attempt to get a USER_RESERVED StaticIPAddress for `user`.

        :param subnet: Subnet to use use for claiming the IP.
        :param ip_address: Any requested address
        :param mac: MAC address to use
        :param hostname: The hostname
        :param domain: The domain to use
        :type subnet: Subnet
        :type ip_address: str
        :type mac: str
        :type hostname: str
        :type domain: Domain
        :raises StaticIPAddressExhaustion: If no IPs available.
        """
        dynamic_range = subnet.get_dynamic_maasipset()
        if ip_address is not None and ip_address in dynamic_range:
            raise MAASAPIForbidden(
                "IP address %s belongs to an existing dynamic range. To "
                "reserve this IP address, a MAC address is required. (Create "
                "a device instead.)" % ip_address)
        if hostname is not None and hostname.find('.') > 0:
            hostname, domain = hostname.split('.', 1)
            domain = Domain.objects.get_domain_or_404(
                "name:%s" % domain, user, NODE_PERMISSION.VIEW)
        else:
            domain = Domain.objects.get_default_domain()
        if mac is None:
            sip = StaticIPAddress.objects.allocate_new(
                alloc_type=IPADDRESS_TYPE.USER_RESERVED,
                requested_address=ip_address,
                subnet=subnet,
                user=user)
            if hostname is not None and hostname != '':
                dnsrr, _ = DNSResource.objects.get_or_create(
                    name=hostname, domain=domain)
                dnsrr.ip_addresses.add(sip)
            maaslog.info("User %s was allocated IP %s", user.username, sip.ip)
        else:
            # The user has requested a static IP linked to a MAC address, so we
            # set that up via the Interface model. If the MAC address is part
            # of a node, then this operation is not allowed. The 'link_subnet'
            # API should be used on that interface.
            nic, created = (
                Interface.objects.get_or_create(
                    mac_address=mac,
                    defaults={
                        'type': INTERFACE_TYPE.UNKNOWN,
                        'name': 'eth0',
                    }))
            if nic.type != INTERFACE_TYPE.UNKNOWN:
                raise MAASAPIBadRequest(
                    "MAC address %s already belongs to %s. Use of the "
                    "interface API is required, for an interface that belongs "
                    "to a node." % (nic.mac_address, nic.node.hostname))

            # Link the new interface on the same subnet as the
            # ip_address.
            sip = nic.link_subnet(
                INTERFACE_LINK_TYPE.STATIC,
                subnet,
                ip_address=ip_address,
                alloc_type=IPADDRESS_TYPE.USER_RESERVED,
                user=user)
            if hostname is not None and hostname != '':
                dnsrr, _ = DNSResource.objects.get_or_create(
                    name=hostname, domain=domain)
                dnsrr.ip_addresses.add(sip)
            maaslog.info(
                "User %s was allocated IP %s for MAC address %s",
                user.username, sip.ip, nic.mac_address)
        return sip

    @operation(idempotent=False)
    def reserve(self, request):
        """Reserve an IP address for use outside of MAAS.

        Returns an IP adddress, which MAAS will not allow any of its known
        nodes to use; it is free for use by the requesting user until released
        by the user.

        The user may supply either a subnet or a specific IP address within a
        subnet.

        :param subnet: CIDR representation of the subnet on which the IP
            reservation is required. e.g. 10.1.2.0/24
        :param ip: The IP address, which must be within
            a known subnet.
        :param ip_address: (Deprecated.) Alias for 'ip' parameter. Provided
            for backward compatibility.
        :param hostname: The hostname to use for the specified IP address.  If
            no domain component is given, the default domain will be used.
        :param mac: The MAC address that should be linked to this reservation.

        Returns 400 if there is no subnet in MAAS matching the provided one,
        or a ip_address is supplied, but a corresponding subnet
        could not be found.
        Returns 503 if there are no more IP addresses available.
        """
        subnet = get_optional_param(request.POST, "subnet")
        ip = get_optional_param(request.POST, "ip")
        ip_address = get_optional_param(request.POST, "ip_address")
        hostname = get_optional_param(request.POST, "hostname")
        mac_address = get_optional_param(request.POST, "mac")

        # Fix to make the API backward compatible, yet consistent with the
        # other APIs in this file.
        if ip is None and ip_address is not None:
            ip = ip_address

        form = ClaimIPForMACForm(data={
            'subnet': subnet,
            'ip_address': ip,
            'hostname': hostname,
            'mac': mac_address,
        })
        if not form.is_valid():
            raise MAASAPIValidationError(form.errors)

        if ip is not None:
            subnet = Subnet.objects.get_best_subnet_for_ip(ip)
            if subnet is None:
                raise MAASAPIBadRequest(
                    "No known subnet for IP address: %s." % ip)
        elif subnet is not None:
            try:
                subnet = Subnet.objects.get_object_by_specifiers_or_raise(
                    subnet)
            except Http404:
                raise MAASAPIBadRequest(
                    "Unable to identify subnet: %s." % subnet) from None
        else:
            raise MAASAPIBadRequest(
                "Must supply either the 'subnet' or the 'ip' parameter.")

        return self._claim_ip(
            request.user, subnet, ip, mac_address,
            hostname=hostname)

    @operation(idempotent=False)
    def release(self, request):
        """Release an IP address that was previously reserved by the user.

        :param ip: The IP address to release.
        :type ip: unicode

        :param force: If True, allows a MAAS administrator to force an IP
            address to be released, even if it is not a user-reserved IP
            address or does not belong to the requesting user. Use with
            caution.
        :type force: bool

        Returns 404 if the provided IP address is not found.
        """
        ip = get_mandatory_param(request.POST, "ip")
        force = get_optional_param(
            request.POST, 'force', default=False, validator=StringBool)

        if force is True and not request.user.is_superuser:
            return HttpResponseForbidden(
                content_type='text/plain',
                content="Force-releasing an IP address requires admin "
                        "privileges.")

        form = ReleaseIPForm(request.POST)
        if not form.is_valid():
            raise MAASAPIValidationError(form.errors)

        if force:
            query_args = dict(ip=ip)
        else:
            query_args = dict(
                alloc_type=IPADDRESS_TYPE.USER_RESERVED, ip=ip,
                user=request.user)

        # Get the reserved IP address, or raise bad request.
        try:
            ip_address = StaticIPAddress.objects.get(**query_args)
        except StaticIPAddress.DoesNotExist:
            if force:
                error = "IP address %s does not exist."
            else:
                error = (
                    "IP address %s does not exist, is not a user-reserved "
                    "address, or does not belong to the requesting user.\n"
                    "If you are sure you want to release this address, use "
                    "force=true as a MAAS administrator.")
            raise MAASAPIBadRequest(error % ip) from None

        # Unlink the IP address from the interfaces it is connected.
        interfaces = list(ip_address.interface_set.all())
        if len(interfaces) > 0:
            for interface in interfaces:
                interface.unlink_ip_address(ip_address)
        else:
            ip_address.delete()

        # Delete any interfaces that no longer have any IP addresses and have
        # no associated nodes.
        for interface in interfaces:
            if interface.node is None and interface.only_has_link_up():
                interface.delete()

        maaslog.info(
            "User %s%s released IP address: %s (%s).", request.user.username,
            " forcibly" if force else "", ip,
            ip_address.alloc_type_name)

        return rc.DELETED

    def read(self, request):
        """List IP addresses known to MAAS.

        By default, gets a listing of all IP addresses allocated to the
        requesting user.

        :param ip: If specified, will only display information for the
            specified IP address.
        :type ip: unicode (must be an IPv4 or IPv6 address)

        If the requesting user is a MAAS administrator, the following options
        may also be supplied:

        :param all: If True, all reserved IP addresses will be shown. (By
            default, only addresses of type 'User reserved' that are assigned
            to the requesting user are shown.)
        :type all: bool

        :param owner: If specified, filters the list to show only IP addresses
            owned by the specified username.
        :type user: unicode
        """
        _all = get_optional_param(
            request.GET, 'all', default=False, validator=StringBool)
        ip = get_optional_param(request.GET, 'ip', default=None)
        owner = get_optional_param(request.GET, 'owner', default=None)
        # If an IP address was specified, validate that it is indeed a valid
        # IP address before trying to hit the database with it.
        if ip is not None:
            try:
                IPAddress(ip)
            except AddrFormatError:
                return HttpResponseBadRequest(
                    content_type='text/plain',
                    content="Parameter 'ip' must contain an IP address.")
        # It doesn't make sense for this API to display NULL IP addresses.
        # These indicate things like "do DHCP on <interface>", "we observed a
        # commissioned node connected to <subnet>", and "we would assign an
        # automatic address to <machine-interface>, but it isn't deployed at
        # the moment".
        query = StaticIPAddress.objects.exclude(ip__isnull=True)
        if _all and not request.user.is_superuser:
            return HttpResponseForbidden(
                content_type='text/plain',
                content="Listing all IP addresses requires admin "
                        "privileges.")
        if owner is not None and not request.user.is_superuser:
            return HttpResponseForbidden(
                content_type='text/plain',
                content="Listing another user's IP addresses requires admin "
                        "privileges.")
        # Add additional filters based on permissions, and based on the
        # request parameters.
        if not request.user.is_superuser:
            # If the requesting user isn't an admin, always filter by the
            # currently-logged-in API user.
            query = query.filter(user=request.user)
        elif owner is not None:
            # If the admin specified a username filter, use that.
            query = query.filter(user__username=owner)
        elif _all is False:
            # If the admin didn't specify 'all=true' (and didn't specify a
            # specific username), only show IP addresses belonging to the
            # admin. (This preserves API compatibility.)
            query = query.filter(user=request.user)
        # If we're not displaying all addresses, we also need to filter by
        # address type (again, to preserve API compatibility).
        if not _all:
            query = query.filter(alloc_type=IPADDRESS_TYPE.USER_RESERVED)
        if ip is not None:
            query = query.filter(ip=ip)
        query = query.order_by('id')
        return query
