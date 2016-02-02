# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""RPC helpers relating to DHCP leases."""

__all__ = [
    "update_lease",
]

from datetime import datetime

from maasserver.enum import (
    IPADDRESS_FAMILY,
    IPADDRESS_TYPE,
)
from maasserver.models.dnsresource import DNSResource
from maasserver.models.interface import (
    Interface,
    UnknownInterface,
)
from maasserver.models.staticipaddress import StaticIPAddress
from maasserver.models.subnet import Subnet
from maasserver.utils.orm import transactional
from netaddr import IPAddress
from provisioningserver.utils.twisted import synchronous


class LeaseUpdateError(Exception):
    """Raise when `update_lease` fails to update lease information."""


@synchronous
@transactional
def update_lease(
        action, mac, ip_family, ip, timestamp,
        lease_time=None, hostname=None):
    """Update one DHCP leases from a cluster.

    :param action: DHCP action taken on the cluster as found in
        :py:class`~provisioningserver.rpc.region.UpdateLease`.
    :param mac: MAC address for the action taken on the cluster as found in
        :py:class`~provisioningserver.rpc.region.UpdateLease`.
    :param ip_family: IP address family for the action taken on the cluster as
        found in :py:class`~provisioningserver.rpc.region.UpdateLease`.
    :param ip: IP address for the action taken on the cluster as found in
        :py:class`~provisioningserver.rpc.region.UpdateLease`.
    :param timestamp: Epoch time for the action taken on the cluster as found
        in :py:class`~provisioningserver.rpc.region.UpdateLease`.
    :param lease_time: Number of seconds the lease is active on the cluster
        as found in :py:class`~provisioningserver.rpc.region.UpdateLease`.
    :param hostname: Hostname of the machine for the lease on the cluster as
        found in :py:class`~provisioningserver.rpc.region.UpdateLease`.

    Based on the action a DISCOVERED StaticIPAddress will be either created or
    updated for a Interface that matches `mac`.

    Actions:
        commit -  When a new lease is given to a client. `lease_time` is
                  required for this action. `hostname` is optional.
        expiry -  When a lease has expired. Occurs when a client fails to renew
                  their lease before the end of the `lease_time`.
        release - When a client explicitly releases the lease.

    :raises NoSuchCluster: If the cluster identified by `cluster_uuid` does not
        exist.
    """
    # Check for a valid action.
    if action not in ["commit", "expiry", "release"]:
        raise LeaseUpdateError("Unknown lease action: %s" % action)

    # Get the subnet for this IP address. If no subnet exists then something
    # is wrong as we should not be recieving message about unknown subnets.
    subnet = Subnet.objects.get_best_subnet_for_ip(ip)
    if subnet is None:
        raise LeaseUpdateError("No subnet exists for: %s" % ip)

    # Check that the subnet family is the same.
    subnet_family = subnet.get_ipnetwork().version
    if ip_family == "ipv4" and subnet_family != IPADDRESS_FAMILY.IPv4:
        raise LeaseUpdateError(
            "Family for the subnet does not match. Expected: %s" % ip_family)
    elif ip_family == "ipv6" and subnet_family != IPADDRESS_FAMILY.IPv6:
        raise LeaseUpdateError(
            "Family for the subnet does not match. Expected: %s" % ip_family)

    # We will recieve actions on all addresses in the subnet. We only want
    # to update the addresses in the dynamic range.
    dynamic_range = subnet.get_dynamic_range_for_ip(IPAddress(ip))
    if dynamic_range is None:
        # Do nothing.
        return {}

    interfaces = list(Interface.objects.filter(mac_address=mac))
    if len(interfaces) == 0 and action == "commit":
        # A MAC address that is unknown to MAAS was given an IP address. Create
        # an unknown interface for this lease.
        unknown_interface = UnknownInterface(
            name="eth0", mac_address=mac, vlan_id=subnet.vlan_id)
        unknown_interface.save()
        interfaces = [unknown_interface]
    elif len(interfaces) == 0:
        # No interfaces and not commit action so nothing needs to be done.
        return {}

    # Delete all discovered IP addresses attached to all interfaces of the same
    # IP address family.
    old_family_addresses = StaticIPAddress.objects.filter_by_ip_family(
        subnet_family)
    old_family_addresses = old_family_addresses.filter(
        alloc_type=IPADDRESS_TYPE.DISCOVERED,
        interface__in=interfaces)
    old_family_addresses.delete()

    # Create the new StaticIPAddress object based on the action.
    if action == "commit":
        # Interfaces received a new lease. Create the new object with the
        # updated lease information.

        # Hostname sent from the cluster is either blank or can be "(none)". In
        # either of those cases we do not set the hostname.
        sip_hostname = None
        if (hostname is not None and
                len(hostname) > 0 and
                not hostname.isspace() and
                hostname != "(none)"):
            sip_hostname = hostname

        # Use the timestamp from the lease to create the StaticIPAddress
        # object. That will make sure that the lease_time is correct from
        # the created time.
        created = datetime.fromtimestamp(timestamp)
        sip = StaticIPAddress.objects.create(
            alloc_type=IPADDRESS_TYPE.DISCOVERED, ip=ip, subnet=subnet,
            lease_time=lease_time, created=created, updated=created)
        for interface in interfaces:
            interface.ip_addresses.add(sip)
        if sip_hostname is not None:
            dnsrr, created = DNSResource.objects.get_or_create(
                name=sip_hostname)
            dnsrr.ip_addresses.add(sip)
    elif action == "expiry" or action == "release":
        # Interfaces no longer holds an active lease. Create the new object
        # to show that it used to be connected to this subnet.
        sip = StaticIPAddress.objects.create(
            alloc_type=IPADDRESS_TYPE.DISCOVERED, ip=None, subnet=subnet)
        for interface in interfaces:
            interface.ip_addresses.add(sip)

    return {}
