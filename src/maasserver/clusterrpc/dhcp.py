# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""DHCP related RPC helpers."""

__all__ = [
    "update_host_maps",
    "remove_host_maps",
]

from collections import defaultdict
from functools import partial

from maasserver.rpc import getClientFor
from maasserver.utils import async
from netaddr import (
    IPAddress,
    IPRange,
)
from provisioningserver.rpc.cluster import (
    CreateHostMaps,
    RemoveHostMaps,
)
from provisioningserver.utils.twisted import synchronous
from twisted.python.failure import Failure


def gen_calls_to_create_host_maps(clients, static_mappings):
    """Generate calls to create host maps in clusters' DHCP servers.

    This includes only IPv4 addresses.  We don't generate host maps for
    IPv6 addresses.

    :param clients: A mapping of cluster UUIDs to
        :py:class:`~provisioningserver.rpc.common.Client` instances.
        There must be a client for each nodegroup in the
        `static_mappings` argument.
    :param static_mappings: A mapping from `NodeGroup` model instances
        to mappings of ``ip-address -> mac-address``.
    :return: A generator of callables.
    """
    make_mappings_for_call = lambda mappings: [
        {"ip_address": ip_address, "mac_address": mac_address}
        for ip_address, mac_address in mappings.items()
        if IPAddress(ip_address).version == 4
    ]
    for nodegroup, mappings in static_mappings.items():
        yield partial(
            clients[nodegroup], CreateHostMaps,
            mappings=make_mappings_for_call(mappings),
            shared_key=nodegroup.dhcp_key)


def gen_dynamic_ip_addresses_with_host_maps(static_mappings):
    """Generate leased IP addresses that are safe to remove.

    They're safe to remove because they lie outside of all of their cluster's
    static ranges, and are thus no longer officially managed. In most cases
    these will be leftover host maps in the dynamic range that wouldn't have
    worked anyway.

    :param static_mappings: A mapping from `NodeGroup` model instances
        to mappings of ``ip-address -> mac-address``.
    :return: A generator of ``(nodegroup, ip-address/mac-address)`` tuples.
    """
    # Avoid circular imports.
    from maasserver.models.staticipaddress import StaticIPAddress

    for nodegroup, mappings in static_mappings.items():
        managed_ranges = tuple(
            IPRange(ngi.static_ip_range_low, ngi.static_ip_range_high)
            for ngi in nodegroup.get_managed_interfaces()
            if ngi.static_ip_range_low is not None and
            ngi.static_ip_range_high is not None)

        # Note: Pre-1.9, this code worked with the DHCPLease table, which
        # had a direct link to the nodegroup. Now, the association with
        # a nodegroup is implicit (via the attached Subnet).
        dhcp_leases = StaticIPAddress.objects.filter(
            subnet__nodegroupinterface__nodegroup=nodegroup,
            interface__mac_address__in=mappings.values(),
            ip__isnull=False)
        for dhcp_lease in dhcp_leases:
            if dhcp_lease.ip:
                dhcp_lease_ip = IPAddress(dhcp_lease.ip)
                within_managed_range = any(
                    dhcp_lease_ip in static_range
                    for static_range in managed_ranges)
                if not within_managed_range:
                    yield nodegroup, dhcp_lease.ip
                    for interface in dhcp_lease.interface_set.all():
                        yield nodegroup, interface.mac_address.get_raw()


def gen_calls_to_remove_dynamic_host_maps(clients, static_mappings):
    """Generates calls to remove old dynamic leases.

    See `gen_dynamic_ip_addresses_with_host_maps` for the source of the leases
    to remove.

    :param clients: A mapping of cluster UUIDs to
        :py:class:`~provisioningserver.rpc.common.Client` instances.
        There must be a client for each nodegroup in the
        `static_mappings` argument.
    :param static_mappings: A mapping from `NodeGroup` model instances
        to mappings of ``ip-address -> mac-address``.
    :return: A generator of callables.
    """
    mac_addresses_to_remove = defaultdict(set)
    ip_mac_with_maps = (
        gen_dynamic_ip_addresses_with_host_maps(static_mappings))
    for nodegroup, ip_or_mac in ip_mac_with_maps:
        mac_addresses_to_remove[nodegroup].add(ip_or_mac)
    for nodegroup, mac_addresses in mac_addresses_to_remove.items():
        yield partial(
            clients[nodegroup], RemoveHostMaps, ip_addresses=mac_addresses,
            shared_key=nodegroup.dhcp_key)


@synchronous
def update_host_maps(static_mappings, timeout=30):
    """Create host maps in clusters' DHCP servers.

    :param static_mappings: A mapping from `NodeGroup` model instances
        to mappings of ``ip-address -> mac-address``.
    :param timeout: The number of seconds before attempts to create host
        maps are cancelled.
    :return: A generator of :py:class:`~Failure`s, if any.
    """
    clients = {
        nodegroup: getClientFor(nodegroup.uuid)
        for nodegroup in static_mappings
    }
    # Record the number of failures.
    failure_count = 0
    # Remove old host maps first, if there are any.
    calls = gen_calls_to_remove_dynamic_host_maps(clients, static_mappings)
    # Listify the calls so that database access happens in this thread.
    for response in async.gather(list(calls), timeout=timeout):
        if isinstance(response, Failure):
            failure_count += 1
            yield response
    # Don't continue if there have been failures.
    if failure_count != 0:
        return
    # Now create the new host maps.
    calls = gen_calls_to_create_host_maps(clients, static_mappings)
    # Listify the calls so that database access happens in this thread.
    for response in async.gather(list(calls), timeout=timeout):
        if isinstance(response, Failure):
            yield response


def gen_calls_to_remove_host_maps(clients, removal_mappings):
    """Generates calls to remove host maps.

    :param clients: A mapping of cluster UUIDs to
        :py:class:`~provisioningserver.rpc.common.Client` instances. There
        must be a client for each nodegroup in the `removal_mappings`
        argument.
    :param removal_mappings: A mapping from `NodeGroup` model instances to
        sequences of IP addresses.
    :return: A generator of callables.
    """
    for nodegroup, ip_addresses in removal_mappings.items():
        yield partial(
            clients[nodegroup], RemoveHostMaps, ip_addresses=ip_addresses,
            shared_key=nodegroup.dhcp_key)


@synchronous
def remove_host_maps(removal_mappings, timeout=30):
    """Remove host maps from clusters' DHCP servers.

    :param removal_mappings: A mapping from `NodeGroup` model instances to
        sequences of IP addresses.
    :param timeout: The number of seconds before attempts to remove host maps
        are cancelled.
    :return: A generator of :py:class:`~Failure`s, if any.
    """
    clients = {
        nodegroup: getClientFor(nodegroup.uuid)
        for nodegroup in removal_mappings
    }
    # Remove old host maps first, if there are any.
    calls = gen_calls_to_remove_host_maps(clients, removal_mappings)
    # Listify the calls so that database access happens in this thread.
    for response in async.gather(list(calls), timeout=timeout):
        if isinstance(response, Failure):
            yield response
