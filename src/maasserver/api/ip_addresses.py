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

from django.db import transaction
from django.shortcuts import get_object_or_404
from maasserver.api.support import (
    operation,
    OperationsHandler,
    )
from maasserver.api.utils import (
    get_mandatory_param,
    get_optional_param,
    )
from maasserver.clusterrpc.dhcp import (
    remove_host_maps,
    update_host_maps,
    )
from maasserver.enum import (
    IPADDRESS_TYPE,
    NODEGROUP_STATUS,
    )
from maasserver.exceptions import (
    MAASAPIBadRequest,
    StaticIPAlreadyExistsForMACAddress,
    )
from maasserver.models import (
    NodeGroupInterface,
    StaticIPAddress,
    )
from maasserver.models.macaddress import MACAddress
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

    @transaction.atomic
    def claim_ip(self, user, interface, requested_address, mac=None):
        """Attempt to get a USER_RESERVED StaticIPAddress for `user` on
        `interface`.

        :raises StaticIPAddressExhaustion: If no IPs available.
        """
        if mac is None:
            sip = StaticIPAddress.objects.allocate_new(
                range_low=interface.static_ip_range_low,
                range_high=interface.static_ip_range_high,
                alloc_type=IPADDRESS_TYPE.USER_RESERVED,
                requested_address=requested_address,
                user=user)
            transaction.commit()
            maaslog.info("User %s was allocated IP %s", user.username, sip.ip)
        else:
            # The user has requested a static IP linked to a MAC
            # address, so we set that up via the MACAddress model.
            mac_address, _ = MACAddress.objects.get_or_create(
                mac_address=mac, cluster_interface=interface)
            ips_on_interface = (
                addr.ip for addr in mac_address.ip_addresses.all()
                if netaddr.IPAddress(addr.ip) in interface.network)
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
            transaction.commit()
            update_host_maps_failures = list(
                update_host_maps(host_map_updates))
            if len(update_host_maps_failures) > 0:
                # Deallocate the static IPs and delete the MAC address
                # if it doesn't have a Node attached.
                if mac_address.node is None:
                    mac_address.delete()
                sip.deallocate()
                transaction.commit()

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

        :param network: CIDR representation of the network on which the IP
            reservation is required. e.g. 10.1.2.0/24
        :type network: unicode

        Returns 400 if there is no network in MAAS matching the provided one.
        Returns 503 if there are no more IP addresses available.
        """
        network = get_mandatory_param(request.POST, "network")
        requested_address = get_optional_param(
            request.POST, "requested_address")
        mac_address = get_optional_param(request.POST, "mac")
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
                    request.user, interface, requested_address, mac_address)
        raise MAASAPIBadRequest(
            "No network found matching %s; you may be requesting an IP "
            "on a network with no static IP range defined." % network)

    @operation(idempotent=False)
    def release(self, request):
        """Release an IP address that was previously reserved by the user.

        :param ip: The IP address to release.
        :type ip: unicode

        Returns 404 if the provided IP address is not found.
        """
        ip = get_mandatory_param(request.POST, "ip")
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
            remove_host_maps(host_maps_to_remove))
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
