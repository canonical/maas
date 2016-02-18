# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handler: `StaticIPAddress`."""

__all__ = [
    'IPAddressesHandler',
    ]

from django.http import Http404
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
from provisioningserver.logger import get_maas_logger


maaslog = get_maas_logger("ip_addresses")


class IPAddressesHandler(OperationsHandler):
    """Manage IP addresses allocated by MAAS."""
    api_doc_section_name = "IP Addresses"
    model = StaticIPAddress
    fields = ('alloc_type', 'created', 'ip', 'subnet')
    create = update = delete = None

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
            from maasserver.dns import config as dns_config
            if hostname is not None and hostname != '':
                dnsrr, _ = DNSResource.objects.get_or_create(
                    name=hostname, domain=domain)
                dnsrr.ip_addresses.add(sip)
                dns_config.dns_update_domains([domain])
            dns_config.dns_update_subnets([subnet])
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
            from maasserver.dns import config as dns_config
            if hostname is not None and hostname != '':
                dnsrr = DNSResource.objects.get_or_create(
                    name=hostname, domain=domain)
                dnsrr.ip_addresses.add(sip)
                dns_config.dns_update_domains([domain])
            dns_config.dns_update_subnets([subnet])
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
        :param ip_address: The IP address, which must be within
            a known subnet.
        :param hostname: The hostname to use for the specified IP address.  If
            no domain component is given, the default domain will be used.
        :param mac: The MAC address that should be linked to this reservation.

        Returns 400 if there is no subnet in MAAS matching the provided one,
        or a ip_address is supplied, but a corresponding subnet
        could not be found.
        Returns 503 if there are no more IP addresses available.
        """
        subnet = get_optional_param(request.POST, "subnet")
        ip_address = get_optional_param(
            request.POST, "ip_address")
        hostname = get_optional_param(request.POST, "hostname")
        mac_address = get_optional_param(request.POST, "mac")

        form = ClaimIPForMACForm(request.POST)
        if not form.is_valid():
            raise MAASAPIValidationError(form.errors)

        if ip_address is not None:
            subnet = Subnet.objects.get_best_subnet_for_ip(ip_address)
            if subnet is None:
                raise MAASAPIBadRequest(
                    "No known subnet for IP %s." % ip_address)
        elif subnet is not None:
            try:
                subnet = Subnet.objects.get_object_by_specifiers_or_raise(
                    subnet)
            except Http404:
                raise MAASAPIBadRequest(
                    "Unable to identify subnet %s." % subnet) from None
        else:
            raise MAASAPIBadRequest(
                "Must supply either a subnet or a ip_address.")

        return self._claim_ip(
            request.user, subnet, ip_address, mac_address,
            hostname=hostname)

    @operation(idempotent=False)
    def release(self, request):
        """Release an IP address that was previously reserved by the user.

        :param ip: The IP address to release.
        :type ip: unicode

        Returns 404 if the provided IP address is not found.
        """
        ip = get_mandatory_param(request.POST, "ip")
        form = ReleaseIPForm(request.POST)
        if not form.is_valid():
            raise MAASAPIValidationError(form.errors)

        # Get the reserved IP address, or raise bad request.
        try:
            ip_address = StaticIPAddress.objects.get(
                alloc_type=IPADDRESS_TYPE.USER_RESERVED, ip=ip,
                user=request.user)
        except StaticIPAddress.DoesNotExist:
            raise MAASAPIBadRequest(
                "User reserved IP %s does not exist." % ip) from None

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

        maaslog.info("User %s released IP %s", request.user.username, ip)

    def read(self, request):
        """List IPAddresses.

        Get a listing of all IPAddresses allocated to the requesting user.
        """
        return StaticIPAddress.objects.filter(
            user=request.user).order_by('id')
