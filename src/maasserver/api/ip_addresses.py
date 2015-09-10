# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handler: `StaticIPAddress`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )


str = None

__metaclass__ = type
__all__ = [
    'IPAddressesHandler',
    ]

from django.shortcuts import get_object_or_404
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
)
from maasserver.exceptions import (
    MAASAPIBadRequest,
    MAASAPIValidationError,
    StaticIPAlreadyExistsForMACAddress,
)
from maasserver.forms import (
    ClaimIPForm,
    ReleaseIPForm,
)
from maasserver.models import (
    Interface,
    StaticIPAddress,
)
from maasserver.models.nodegroupinterface import NodeGroupInterface
from maasserver.utils.orm import transactional
from netaddr import (
    IPAddress,
    IPNetwork,
)
from netaddr.core import AddrFormatError
from provisioningserver.logger import get_maas_logger


maaslog = get_maas_logger("ip_addresses")


class IPAddressesHandler(OperationsHandler):
    """Manage IP addresses allocated by MAAS."""
    api_doc_section_name = "IP Addresses"
    model = StaticIPAddress
    fields = ('alloc_type', 'created', 'ip')
    create = update = delete = None

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ('ipaddresses_handler', [])

    @transactional
    def claim_ip(
            self, user, interface, requested_address, mac=None,
            hostname=None):
        """Attempt to get a USER_RESERVED StaticIPAddress for `user` on
        `interface`.

        :raises StaticIPAddressExhaustion: If no IPs available.
        """
        if mac is None:
            sip = StaticIPAddress.objects.allocate_new(
                network=interface.network,
                static_range_low=interface.static_ip_range_low,
                static_range_high=interface.static_ip_range_high,
                dynamic_range_low=interface.ip_range_low,
                dynamic_range_high=interface.ip_range_high,
                alloc_type=IPADDRESS_TYPE.USER_RESERVED,
                requested_address=requested_address,
                user=user, hostname=hostname)
            from maasserver.dns import config as dns_config
            dns_config.dns_update_zones([interface.nodegroup])
            maaslog.info("User %s was allocated IP %s", user.username, sip.ip)
        else:
            # The user has requested a static IP linked to a MAC
            # address, so we set that up via the Interface model.
            nic, created = (
                Interface.objects.get_or_create(
                    mac_address=mac,
                    defaults={
                        'type': INTERFACE_TYPE.UNKNOWN,
                        'name': 'eth0',
                    }))
            ips_on_interface = [
                addr.ip
                for addr in nic.ip_addresses.filter(
                    alloc_type__in=[
                        IPADDRESS_TYPE.AUTO,
                        IPADDRESS_TYPE.STICKY,
                        IPADDRESS_TYPE.USER_RESERVED,
                    ])
                if addr.ip and IPAddress(addr.ip) in interface.network
            ]
            if any(ips_on_interface):
                # If this inteface already has static IPs on the interface in
                # question we raise an error, since we can't sanely
                # allocate more addresses for the MAC here.
                raise StaticIPAlreadyExistsForMACAddress(
                    "MAC address %s already has the IP address(es) %s." %
                    (mac, ', '.join(ips_on_interface)))

            # Link the new interface on the same subnet as the passed
            # nodegroup interface.
            sip = nic.link_subnet(
                INTERFACE_LINK_TYPE.STATIC,
                interface.subnet,
                ip_address=requested_address,
                alloc_type=IPADDRESS_TYPE.USER_RESERVED,
                user=user)
            maaslog.info(
                "User %s was allocated IP %s for MAC address %s",
                user.username, sip.ip, nic.mac_address)
        return sip

    @operation(idempotent=False)
    def reserve(self, request):
        """Reserve an IP address for use outside of MAAS.

        Returns an IP adddress, which MAAS will not allow any of its known
        devices and Nodes to use; it is free for use by the requesting user
        until released by the user.

        The user may supply either a range matching the subnet of an
        existing cluster interface, or a specific IP address within the
        static IP address range on a cluster interface.

        :param network: CIDR representation of the network on which the IP
            reservation is required. e.g. 10.1.2.0/24
        :param requested_address: the requested address, which must be within
            a static IP address range managed by MAAS.
        :param hostname: the hostname to use for the specified IP address
        :type network: unicode

        Returns 400 if there is no network in MAAS matching the provided one,
        or a requested_address is supplied, but a corresponding network
        could not be found.
        Returns 503 if there are no more IP addresses available.
        """
        network = get_optional_param(request.POST, "network")
        requested_address = get_optional_param(
            request.POST, "requested_address")
        hostname = get_optional_param(request.POST, "hostname")
        mac_address = get_optional_param(request.POST, "mac")

        form = ClaimIPForm(request.POST)
        if not form.is_valid():
            raise MAASAPIValidationError(form.errors)

        if requested_address is not None:
            try:
                # Validate the passed address.
                valid_address = IPAddress(requested_address)
                ngi = (NodeGroupInterface.objects
                       .get_by_address_for_static_allocation(valid_address))
            except AddrFormatError:
                raise MAASAPIBadRequest(
                    "Invalid requested_address parameter: %s" %
                    requested_address)
        elif network is not None:
            try:
                # Validate the passed network.
                valid_network = IPNetwork(network)
                ngi = (NodeGroupInterface.objects
                       .get_by_network_for_static_allocation(valid_network))
            except AddrFormatError:
                raise MAASAPIBadRequest(
                    "Invalid network parameter: %s" % network)
        else:
            raise MAASAPIBadRequest(
                "Must supply either a network or a requested_address.")

        if ngi is None:
            raise MAASAPIBadRequest(
                "No network found matching %s; you may be requesting an IP "
                "on a network with no static IP range defined." % network)

        return self.claim_ip(
            request.user, ngi, requested_address, mac_address,
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

        ip_address = get_object_or_404(
            StaticIPAddress, alloc_type=IPADDRESS_TYPE.USER_RESERVED,
            ip=ip, user=request.user)
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
        return StaticIPAddress.objects.filter(user=request.user).order_by('id')
