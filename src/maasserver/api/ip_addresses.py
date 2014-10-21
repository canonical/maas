# Copyright 2014 Canonical Ltd.  This software is licensed under the
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
    IPADDRESS_TYPE,
    NODEGROUP_STATUS,
    )
from maasserver.exceptions import MAASAPIBadRequest
from maasserver.models import (
    NodeGroupInterface,
    StaticIPAddress,
    )
import netaddr
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

    def claim_ip(self, user, interface, requested_address):
        """Attempt to get a USER_RESERVED StaticIPAddress for `user` on
        `interface`.

        :raises StaticIPAddressExhaustion: If no IPs available.
        """
        sip = StaticIPAddress.objects.allocate_new(
            range_low=interface.static_ip_range_low,
            range_high=interface.static_ip_range_high,
            alloc_type=IPADDRESS_TYPE.USER_RESERVED,
            requested_address=requested_address,
            user=user)
        maaslog.info("User %s was allocated IP %s", user.username, sip.ip)
        return sip

    @operation(idempotent=False)
    def reserve(self, request):
        """Reserve an IP address for use outside of MAAS.

        Returns an IP adddress, which MAAS will not allow any of its known
        devices and Nodes to use; it is free for use by the requesting user
        until released by the user.

        :param network: CIDR representation of the network on which the IP
            reservation is required. e.g. 10.1.2.0/24
        :type network: unicode
        """
        network = get_mandatory_param(request.POST, "network")
        requested_address = get_optional_param(
            request.POST, "requested_address")
        # Validate the passed network.
        try:
            valid_network = netaddr.IPNetwork(network)
        except netaddr.core.AddrFormatError:
            raise MAASAPIBadRequest("Invalid network parameter %s" % network)

        # Match the network to a nodegroupinterface.
        interfaces = (
            NodeGroupInterface.objects.filter(
                nodegroup__status=NODEGROUP_STATUS.ACCEPTED)
            .exclude(static_ip_range_low__isnull=True)
            .exclude(static_ip_range_high__isnull=True)
        )
        for interface in interfaces:
            if valid_network == interface.network:
                # Winner winner chicken dinner.
                return self.claim_ip(
                    request.user, interface, requested_address)
        raise MAASAPIBadRequest(
            "No network found matching %s; you may be requesting an IP "
            "on a network with no static IP range defined." % network)

    @operation(idempotent=False)
    def release(self, request):
        """Release an IP address that was previously reserved by the user.

        :param ip: The IP address to release.
        :type ip: unicode
        """
        ip = get_mandatory_param(request.POST, "ip")
        staticaddress = get_object_or_404(
            StaticIPAddress, ip=ip, user=request.user)
        staticaddress.deallocate()
        maaslog.info("User %s released IP %s", request.user.username, ip)

    def read(self, request):
        """List IPAddresses.

        Get a listing of all IPAddresses allocated to the requesting user.
        """
        return StaticIPAddress.objects.filter(user=request.user).order_by('id')
