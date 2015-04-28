# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Generic helpers for `netaddr` and network-related types."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'clean_up_netifaces_address',
    'find_ip_via_arp',
    'find_mac_via_arp',
    'get_all_addresses_for_interface',
    'get_all_interface_addresses',
    'intersect_iprange',
    'ip_range_within_network',
    'make_network',
    'NeighboursProtocol',
    'resolve_hostname',
    ]

from collections import defaultdict
import io
from socket import (
    AF_INET,
    AF_INET6,
    EAI_NODATA,
    EAI_NONAME,
    gaierror,
    getaddrinfo,
)

from netaddr import (
    EUI,
    IPAddress,
    IPNetwork,
    IPRange,
)
import netifaces
import provisioningserver
from twisted.internet.defer import Deferred
from twisted.internet.error import ProcessDone
from twisted.internet.protocol import ProcessProtocol
from twisted.python import log


def make_network(ip_address, netmask_or_bits, **kwargs):
    """Construct an `IPNetwork` with the given address and netmask or width.

    This is a thin wrapper for the `IPNetwork` constructor.  It's here because
    the constructor for `IPNetwork` is easy to get wrong.  If you pass it an
    IP address and a netmask, or an IP address and a bit size, it will seem to
    work... but it will pick a default netmask, not the one you specified.

    :param ip_address:
    :param netmask_or_bits:
    :param kwargs: Any other (keyword) arguments you want to pass to the
        `IPNetwork` constructor.
    :raise netaddr.core.AddrFormatError: If the network specification is
        malformed.
    :return: An `IPNetwork` of the given base address and netmask or bit width.
    """
    return IPNetwork("%s/%s" % (ip_address, netmask_or_bits), **kwargs)


def find_ip_via_arp(mac):
    """Find the IP address for `mac` by reading the output of arp -n.

    Returns `None` if the MAC is not found.

    We do this because we aren't necessarily the only DHCP server on the
    network, so we can't check our own leases file and be guaranteed to find an
    IP that matches.

    :param mac: The mac address, e.g. '1c:6f:65:d5:56:98'.
    """
    try:
        neighbours = provisioningserver.services.getServiceNamed("neighbours")
    except KeyError:
        return None
    else:
        ipaddr = neighbours.find_ip_address(EUI(mac))
        if ipaddr is None:
            return None
        else:
            return unicode(ipaddr).lower()


def find_mac_via_arp(ip):
    """Find the MAC address for `ip` by reading the output of arp -n.

    Returns `None` if the IP is not found.

    We do this because we aren't necessarily the only DHCP server on the
    network, so we can't check our own leases file and be guaranteed to find an
    IP that matches.

    :param ip: The ip address, e.g. '192.168.1.1'.
    """
    try:
        neighbours = provisioningserver.services.getServiceNamed("neighbours")
    except KeyError:
        return None
    else:
        macaddr = neighbours.find_mac_address(IPAddress(ip))
        if macaddr is None:
            return None
        else:
            return unicode(macaddr).lower().replace("-", ":")


def clean_up_netifaces_address(address, interface):
    """Strip extraneous matter from `netifaces` IPv6 address.

    Each IPv6 address we get from `netifaces` has a "zone index": a suffix
    consisting of a percent sign and a network interface name, e.g. `eth0`
    in GNU/Linux or `0` in Windows.  These are normally used to disambiguate
    link-local addresses (which have the same network prefix on each link,
    but may not actually be connected).  `IPAddress` doesn't parse that
    suffix, so we strip it off.
    """
    return address.replace('%' + interface, '')


def get_all_addresses_for_interface(interface):
    """Yield all IPv4 and IPv6 addresses for an interface as `IPAddress`es.

    IPv4 addresses will be yielded first, followed by v6 addresses.

    :param interface: The name of the interface whose addresses we
        should retrieve.
    """
    addresses = netifaces.ifaddresses(interface)
    if netifaces.AF_INET in addresses:
        for inet_address in addresses[netifaces.AF_INET]:
            if "addr" in inet_address:
                yield inet_address["addr"]
    if netifaces.AF_INET6 in addresses:
        for inet6_address in addresses[netifaces.AF_INET6]:
            if "addr" in inet6_address:
                # There's a bug in netifaces which results in the
                # interface name being appended to the IPv6 address.
                # Goodness knows why. Anyway, we deal with that
                # here.
                yield clean_up_netifaces_address(
                    inet6_address["addr"], interface)


def get_all_interface_addresses():
    """For each network interface, yield its addresses."""
    for interface in netifaces.interfaces():
        for address in get_all_addresses_for_interface(interface):
            yield address


def resolve_hostname(hostname, ip_version=4):
    """Wrapper around `getaddrinfo`: return addresses for `hostname`.

    :param hostname: Host name (or IP address).
    :param ip_version: Look for addresses of this IP version only: 4 for IPv4,
        or 6 for IPv6.
    :return: A set of `IPAddress`.  Empty if `hostname` does not resolve for
        the requested IP version.
    """
    addr_families = {
        4: AF_INET,
        6: AF_INET6,
        }
    assert ip_version in addr_families
    # Arbitrary non-privileged port, on which we can call getaddrinfo.
    port = 33360
    try:
        address_info = getaddrinfo(hostname, port, addr_families[ip_version])
    except gaierror as e:
        if e.errno in (EAI_NONAME, EAI_NODATA):
            # Name does not resolve.
            address_info = []
        else:
            raise

    # The contents of sockaddr differ for IPv6 and IPv4, but the
    # first element is always the address, and that's all we care
    # about.
    return {
        IPAddress(sockaddr[0])
        for family, socktype, proto, canonname, sockaddr in address_info
        }


def intersect_iprange(network, iprange):
    """Return the intersection between two IPNetworks or IPRanges.

    IPSet is notoriously inefficient so we intersect ourselves here.
    """
    if network.last >= iprange.first and network.first <= iprange.last:
        first = max(network.first, iprange.first)
        last = min(network.last, iprange.last)
        return IPRange(first, last)
    else:
        return None


def ip_range_within_network(ip_range, network):
    """Check that the whole of a given IP range is within a given network."""
    # Make sure that ip_range is an IPRange and not an IPNetwork,
    # otherwise this won't work.
    if isinstance(ip_range, IPNetwork):
        ip_range = IPRange(
            IPAddress(network.first), IPAddress(network.last))
    return all([
        intersect_iprange(cidr, network) for cidr in ip_range.cidrs()])


class NeighboursProtocol(ProcessProtocol, object):
    """An `IProcessProtocol` to parse the output from `ip neigh`.

    Specifically, it's interested only in mapping between IPv4/IPv6 addresses
    and related link-layer addresses.

    Rationale: `ip neigh` can take 2-3ms to run. When run frequently -- as was
    previously done when handling TFTP requests via `subprocess` -- this ends
    up blocking the reactor for too long.
    """

    def __init__(self):
        super(NeighboursProtocol, self).__init__()
        self.done = Deferred()

    def connectionMade(self):
        self.out = io.BytesIO()
        self.err = io.BytesIO()

    def outReceived(self, data):
        self.out.write(data)

    def errReceived(self, data):
        self.err.write(data)

    def processEnded(self, reason):
        error = self.err.getvalue().decode("ascii", "replace")
        if len(error) != 0:
            log.msg(
                "`ip neigh` wrote to stderr (an error may be "
                "reported separately): %s" % error)

        if reason.check(ProcessDone):
            try:
                output = self.out.getvalue().decode("ascii")
                lladdrs = self.parseOutput(output.splitlines())
                neighbours = self.collateNeighbours(lladdrs)
            except:
                self.done.errback()
            else:
                self.done.callback(neighbours)
        else:
            self.done.errback(reason)

    @staticmethod
    def parseOutput(lines):
        """Parse the output of `ip neigh`, looking for 'lladdr' records.

        Normal ``ip neigh`` output lines look like::

          <IP> dev <interface> lladdr <MAC> [router] <status>

        where ``<IP>`` is an IPv4 or IPv6 address, ``<interface>`` is a
        network interface name such as ``eth0``, ``<MAC>`` is a MAC address,
        and status can be ``REACHABLE``, ``STALE``, etc.

        However sometimes you'll also see lines like::

          <IP> dev <interface>  FAILED

        Note the missing ``lladdr`` entry.

        :return: A generator, yielding ``(ip-address, mac-address)`` tuples,
            where ``ip-address`` is an `netaddr.IPAddress` and ``mac-address``
            is a `netaddr.EUI`.
        """
        for line in lines:
            columns = line.strip().split()
            assert len(columns) >= 4, (
                "Output line from `ip neigh` does not look like a "
                "neighbour entry: %r" % line)
            if columns[3] == "lladdr":
                ipaddr, macaddr = columns[0], columns[4]
                yield IPAddress(ipaddr), EUI(macaddr)

    @staticmethod
    def collateNeighbours(lladdrs):
        ip_to_mac = defaultdict(set)
        mac_to_ip = defaultdict(set)
        for ipaddr, macaddr in lladdrs:
            ip_to_mac[ipaddr].add(macaddr)
            mac_to_ip[macaddr].add(ipaddr)
        return ip_to_mac, mac_to_ip
