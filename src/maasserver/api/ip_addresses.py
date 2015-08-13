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
from maasserver.clusterrpc import dhcp
from maasserver.enum import IPADDRESS_TYPE
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
    PhysicalInterface,
    StaticIPAddress,
)
from maasserver.models.macaddress import MACAddress
from maasserver.models.nodegroupinterface import NodeGroupInterface
from maasserver.utils.orm import (
    commit_within_atomic_block,
    transactional,
)
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
            # address, so we set that up via the MACAddress model.
            mac_address, created = MACAddress.objects.get_or_create(
                mac_address=mac, cluster_interface=interface)
            if created:
                iface = PhysicalInterface(mac=mac_address, name='eth0')
                iface.save()
            ips_on_interface = (
                addr.ip for addr in mac_address.ip_addresses.all()
                if IPAddress(addr.ip) in interface.network)
            if any(ips_on_interface):
                # If this MAC already has static IPs on the interface in
                # question we raise an error, since we can't sanely
                # allocate more addresses for the MAC here.
                raise StaticIPAlreadyExistsForMACAddress(
                    "MAC address %s already has the IP address(es) %s." %
                    (mac, ips_on_interface))

            [sip] = mac_address.claim_static_ips(
                alloc_type=IPADDRESS_TYPE.USER_RESERVED, user=user,
                requested_address=requested_address)
            # Update the DHCP host maps for the cluster so that this MAC
            # gets an entry with this static IP.
            host_map_updates = {
                interface.nodegroup: {
                    sip.ip: mac_address.mac_address,
                }
            }

            # Commit the DB changes before we do RPC calls.
            commit_within_atomic_block()
            update_host_maps_failures = list(
                dhcp.update_host_maps(host_map_updates))
            if len(update_host_maps_failures) > 0:
                # Deallocate the static IPs and delete the MAC address
                # if it doesn't have a Node attached.
                if mac_address.node is None:
                    mac_address.delete()
                sip.deallocate()
                commit_within_atomic_block()

                # There will only ever be one error, so raise that.
                raise update_host_maps_failures[0].value

            maaslog.info(
                "User %s was allocated IP %s for MAC address %s",
                user.username, sip.ip, mac_address.mac_address)
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

        sip = self.claim_ip(
            request.user, ngi, requested_address, mac_address,
            hostname=hostname)

        return sip

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

        staticaddress = get_object_or_404(
            StaticIPAddress, ip=ip, user=request.user)

        linked_mac_addresses = staticaddress.macaddress_set
        linked_mac_address_interfaces = set(
            mac_address.cluster_interface
            for mac_address in linked_mac_addresses.all())

        # Remove any hostmaps for this IP.
        host_maps_to_remove = {
            interface.nodegroup: [staticaddress.ip]
            for interface in linked_mac_address_interfaces
            }
        remove_host_maps_failures = list(
            dhcp.remove_host_maps(host_maps_to_remove))
        if len(remove_host_maps_failures) > 0:
            # There's only going to be one failure, so raise that.
            raise remove_host_maps_failures[0].value

        # Delete any MACAddress entries that are attached to this static
        # IP but that *aren't* attached to a Node. With the DB isolation
        # at SERIALIZABLE there will be no race here, and it's better to
        # keep cruft out of the DB.
        linked_mac_addresses.filter(node=None).delete()
        staticaddress.deallocate()

        maaslog.info("User %s released IP %s", request.user.username, ip)

    def read(self, request):
        """List IPAddresses.

        Get a listing of all IPAddresses allocated to the requesting user.
        """
        return StaticIPAddress.objects.filter(user=request.user).order_by('id')
