# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Generic helpers for `netaddr` and network-related types."""

__all__ = [
    'clean_up_netifaces_address',
    'find_ip_via_arp',
    'find_mac_via_arp',
    'get_all_addresses_for_interface',
    'get_all_interface_addresses',
    'is_loopback_address',
    'make_network',
    'resolve_hostname',
    'resolves_to_loopback_address',
    'intersect_iprange',
    'ip_range_within_network',
    ]


import codecs
from collections import namedtuple
from operator import attrgetter
import socket
from socket import (
    AF_INET,
    AF_INET6,
    EAI_NODATA,
    EAI_NONAME,
    gaierror,
    getaddrinfo,
    IPPROTO_TCP,
)

from netaddr import (
    IPAddress,
    IPNetwork,
    IPRange,
)
from netaddr.core import AddrFormatError
import netifaces
from provisioningserver.utils.dhclient import get_dhclient_info
from provisioningserver.utils.ipaddr import get_ip_addr
from provisioningserver.utils.iproute import get_ip_route
from provisioningserver.utils.ps import running_in_container
from provisioningserver.utils.shell import call_and_check
from provisioningserver.utils.twisted import synchronous

# Address families in /etc/network/interfaces that MAAS chooses to parse. All
# other families are ignored.
ENI_PARSED_ADDRESS_FAMILIES = [
    "inet",
    "inet6",
]

# Interface method in /etc/network/interfaces that MAAS chooses to parse. All
# other methods are ignored.
ENI_PARSED_METHODS = [
    "static",
    "manual",
    "dhcp",
]


class IPRANGE_TYPE:
    """Well-known purpose types for IP ranges."""
    UNUSED = 'unused'
    GATEWAY_IP = 'gateway-ip'
    DYNAMIC = 'dynamic'
    PROPOSED_DYNAMIC = 'proposed-dynamic'


class MAASIPRange(IPRange):
    """IPRange object whose default end address is the start address if not
    specified. Capable of storing a string to indicate the purpose of
    the range."""
    def __init__(self, start, end=None, flags=0, purpose=None):
        if end is None:
            end = start
        if type(start) == IPRange:
            end = start.last
            start = start.first
        super(MAASIPRange, self).__init__(start, end, flags=flags)
        self.flags = flags
        if type(purpose) != set:
            purpose = {purpose}
        self.purpose = purpose

    def __str__(self):
        range_str = str(IPAddress(self.first))
        if not self.first == self.last:
            range_str += '-' + str(IPAddress(self.last))
            range_str += (" num_addresses=" +
                          str((self.last - self.first + 1)))
        if self.purpose:
            range_str += " purpose=" + repr(self.purpose)
        return range_str

    def __repr__(self):
        return ("%s('%s', '%s'%s%s)" %
                (self.__class__.__name__,
                 self._start, self._end,
                 (" flags=%d" % self.flags if self.flags else ''),
                 (" purpose=%s" % repr(self.purpose) if self.purpose else '')))

    @property
    def num_addresses(self):
        return self.last - self.first + 1

    def render_json(self, include_purpose=True):
        json = {
            "start": inet_ntop(self.first),
            "end": inet_ntop(self.last),
            "num_addresses": self.num_addresses,
        }
        if include_purpose:
            json["purpose"] = sorted(list(self.purpose))
        return json


def _deduplicate_sorted_maasipranges(ranges):
    """Given a sorted list of `MAASIPRange` objects, returns a new (sorted)
    list where any adjacent overlapping ranges have been combined into a single
    range."""
    new_ranges = []
    previous_min = None
    previous_max = None
    for item in ranges:
        if previous_min is not None and previous_max is not None:
            min_overlaps = previous_min <= item.first <= previous_max
            max_overlaps = previous_min <= item.last <= previous_max
            if min_overlaps or max_overlaps:
                previous = new_ranges.pop()
                item = make_iprange(
                    min(item.first, previous_min),
                    max(item.last, previous_max),
                    previous.purpose | item.purpose)
        previous_min = item.first
        previous_max = item.last
        new_ranges.append(item)
    return new_ranges


def normalize_ipranges(ranges):
    """Converts each object in the list of ranges to an MAASIPRange, if
    the object is not already a MAASIPRange. Then, returns a sorted list
    of those MAASIPRange objects."""
    new_ranges = []
    for item in ranges:
        if not isinstance(item, MAASIPRange):
            item = MAASIPRange(item)
        new_ranges.append(item)
    return sorted(new_ranges)


class IPRangeStatistics(object):
    """Class to encapsulate statistics we want to display about a given
    `MAASIPSet`, which must be a set returned from
    `MAASIPSet.get_full_range()`. That is, the set must include a `MAASIPRange`
    to cover every possible IP address present in the desired range."""
    def __init__(self, full_maasipset):
        self.ranges = full_maasipset
        self.first_address_value = self.ranges.first
        self.last_address_value = self.ranges.last
        self.ip_version = IPAddress(self.ranges.last).version
        self.first_address = str(IPAddress(self.first_address_value))
        self.last_address = str(IPAddress(self.last_address_value))
        self.num_available = 0
        self.num_unavailable = 0
        self.largest_available = 0
        self.suggested_gateway = None
        self.suggested_dynamic_range = None
        for range in full_maasipset.ranges:
            if IPRANGE_TYPE.UNUSED in range.purpose:
                self.num_available += range.num_addresses
                if range.num_addresses > self.largest_available:
                    self.largest_available = range.num_addresses
            else:
                self.num_unavailable += range.num_addresses
        self.total_addresses = self.num_available + self.num_unavailable
        if not self.ranges.includes_purpose(IPRANGE_TYPE.GATEWAY_IP):
            self.suggested_gateway = self.get_recommended_gateway()
        if not self.ranges.includes_purpose(IPRANGE_TYPE.DYNAMIC):
            self.suggested_dynamic_range = self.get_recommended_dynamic_range()

    def get_recommended_gateway(self):
        """Returns a suggested gateway for the set of ranges in `self.ranges`.
        Will attempt to choose the first IP address available, then the last IP
        address available, then the first IP address in the first unused range,
        in that order of preference.

        Must be called after the range usage has been calculated.
        """
        suggested_gateway = None
        first_address = self.first_address_value
        last_address = self.last_address_value
        if self.ip_version == 6:
            # For IPv6 addresses, always return the subnet-router anycast
            # address. (See RFC 4291 section 2.6.1 for more information.)
            return str(IPAddress(first_address - 1))
        if self.ranges.is_unused(first_address):
            suggested_gateway = str(IPAddress(first_address))
        elif self.ranges.is_unused(last_address):
            suggested_gateway = str(IPAddress(last_address))
        else:
            first_unused = self.ranges.get_first_unused_ip()
            if first_unused is not None:
                suggested_gateway = str(IPAddress(first_unused))
        return suggested_gateway

    def get_recommended_dynamic_range(self):
        """Returns a recommended dynamic range for the set of ranges in
        `self.ranges`, or None if one could not be found.

        Must be called after the recommended gateway is selected, the
        range usage has been calculated, and the number of total and available
        addresses have been determined.
        """
        largest_unused = self.ranges.get_largest_unused_block()
        if largest_unused is None:
            return None
        if self.suggested_gateway is not None and largest_unused.size == 1:
            # Can't suggest a range if we're also suggesting the only available
            # IP address as the gateway.
            return None
        candidate = MAASIPRange(
            largest_unused.first, largest_unused.last,
            purpose=IPRANGE_TYPE.PROPOSED_DYNAMIC)
        # Adjust the largest unused block if it contains the suggested gateway.
        if self.suggested_gateway is not None:
            gateway_value = IPAddress(self.suggested_gateway).value
            if gateway_value in candidate:
                # The suggested gateway is going to be either the first
                # or the last IP address in the range.
                if gateway_value == candidate.first:
                    candidate = MAASIPRange(
                        candidate.first + 1, candidate.last,
                        purpose=IPRANGE_TYPE.PROPOSED_DYNAMIC)
                else:
                    # Must be the last address.
                    candidate = MAASIPRange(
                        candidate.first, candidate.last - 1,
                        purpose=IPRANGE_TYPE.PROPOSED_DYNAMIC)
        if candidate is not None:
            one_fourth_range = self.total_addresses >> 2
            half_remaining_space = self.num_available >> 1
            if candidate.size > one_fourth_range:
                # Prevent the proposed range from taking up too much available
                # space in the subnet.
                candidate = MAASIPRange(
                    candidate.last - one_fourth_range, candidate.last,
                    purpose=IPRANGE_TYPE.PROPOSED_DYNAMIC)
            elif candidate.size >= half_remaining_space:
                # Prevent the proposed range from taking up the remainder of
                # the available IP addresses. (take at most half.)
                candidate = MAASIPRange(
                    candidate.last - half_remaining_space + 1, candidate.last,
                    purpose=IPRANGE_TYPE.PROPOSED_DYNAMIC)
        return candidate

    @property
    def available_percentage(self):
        """Returns the utilization percentage for this set of addresses.
        :return:float"""
        return float(self.num_available) / float(self.total_addresses)

    @property
    def available_percentage_string(self):
        """Returns the utilization percentage for this set of addresses.
        :return:unicode"""
        return "{0:.0%}".format(self.available_percentage)

    @property
    def usage_percentage(self):
        """Returns the utilization percentage for this set of addresses.
        :return:float"""
        return float(self.num_unavailable) / float(self.total_addresses)

    @property
    def usage_percentage_string(self):
        """Returns the utilization percentage for this set of addresses.
        :return:unicode"""
        return "{0:.0%}".format(self.usage_percentage)

    def render_json(self, include_ranges=False, include_suggestions=False):
        """Returns a representation of the statistics suitable for rendering
        into JSON format."""
        data = {
            "num_available": self.num_available,
            "largest_available": self.largest_available,
            "num_unavailable": self.num_unavailable,
            "total_addresses": self.total_addresses,
            "usage": self.usage_percentage,
            "usage_string": self.usage_percentage_string,
            "available_string": self.available_percentage_string,
            "first_address": self.first_address,
            "last_address": self.last_address,
            "ip_version": self.ip_version
        }
        if include_ranges:
            data["ranges"] = self.ranges.render_json()
        if include_suggestions:
            data["suggested_gateway"] = self.suggested_gateway
            suggested_dynamic_range = None
            if self.suggested_dynamic_range is not None:
                suggested_dynamic_range = (
                    self.suggested_dynamic_range.render_json()
                )
            data["suggested_dynamic_range"] = suggested_dynamic_range
        return data


class MAASIPSet(set):

    def __init__(self, ranges, cidr=None):
        self.ranges = normalize_ipranges(ranges)
        self.ranges = _deduplicate_sorted_maasipranges(self.ranges)
        self.cidr = cidr
        super(MAASIPSet, self).__init__(set(self.ranges))

    def find(self, search):
        """Searches the list of IPRange objects until it finds the specified
        search parameter, and returns the range it belongs to if found.
        (If the search parameter is a range, returns the result based on
        matching the searching for the range containing the first IP address
        within that range.)"""
        if isinstance(search, IPRange):
            for item in self.ranges:
                if (item.first <= search.first <= item.last and
                        item.first <= search.last <= item.last):
                    return item
        else:
            addr = IPAddress(search)
            addr = int(addr)
            for item in self.ranges:
                if item.first <= addr <= item.last:
                    return item
        return None

    @property
    def first(self):
        """Returns the first IP address in this set."""
        if len(self.ranges) > 0:
            return self.ranges[0].first
        else:
            return None

    @property
    def last(self):
        """Returns the last IP address in this set."""
        if len(self.ranges) > 0:
            return self.ranges[-1].last
        else:
            return None

    def ip_has_purpose(self, ip, purpose):
        """Returns True if the specified IP address has the specified purpose
        in this set; False otherwise.
        """
        range = self.find(ip)
        if range is None:
            raise ValueError(
                "IP address %s does not exist in range (%s-%s)." % (
                    ip, self.first, self.last))
        return purpose in range.purpose

    def is_unused(self, ip):
        """Returns True if the specified IP address (which must be within the
        ranges in this set) is unused; False otherwise."""
        return self.ip_has_purpose(ip, IPRANGE_TYPE.UNUSED)

    def includes_purpose(self, purpose):
        """Returns True if the specified purpose is found inside any of the
        ranges in this set, otherwise returns False"""
        for item in self.ranges:
            if purpose in item.purpose:
                return True
        return False

    def get_first_unused_ip(self):
        """Returns the integer value of the first unused IP address in the set.
        """
        for item in self.ranges:
            if IPRANGE_TYPE.UNUSED in item.purpose:
                return item.first
        return None

    def get_largest_unused_block(self):
        """Find the largest unused block of addresses in this set."""
        class NullIPRange:
            """Throwaway class to represent an empty IP range."""
            def __init__(self):
                self.size = 0

        largest = NullIPRange()
        for item in self.ranges:
            if IPRANGE_TYPE.UNUSED in item.purpose:
                if item.size >= largest.size:
                    largest = item
        if largest.size == 0:
            return None
        return largest

    def render_json(self, *args, **kwargs):
        return [
            iprange.render_json(*args, **kwargs)
            for iprange in self.ranges
        ]

    def __getitem__(self, item):
        return self.find(item)

    def __contains__(self, item):
        return bool(self.find(item))

    def get_unused_ranges(self, outer_range, comment=IPRANGE_TYPE.UNUSED):
        """Calculates and returns a list of unused IP ranges, based on
        the supplied range of desired addresses.

        :param outer_range: can be an IPNetwork or IPRange of addresses.
            If an IPNetwork is supplied, the network (and broadcast, if
            applicable) addresses will be excluded from the set of
            addresses considered "unused". If an IPRange is supplied,
            all addresses in the range will be considered unused.
        """
        if isinstance(outer_range, (bytes, str)):
            if '/' in outer_range:
                outer_range = IPNetwork(outer_range)
        unused_ranges = []
        if type(outer_range) == IPNetwork:
            # Skip the network address, if this is a network
            prefixlen = outer_range.prefixlen
            if outer_range.version == 4 and prefixlen in (31, 32):
                start = outer_range.first
            elif outer_range.version == 6 and prefixlen in (127, 128):
                start = outer_range.first
            else:
                start = outer_range.first + 1
        else:
            # Otherwise, assume the first address is the start of the range
            start = outer_range.first
        candidate_start = start
        # Note: by now, self.ranges is sorted from lowest
        # to highest IP address.
        for used_range in self.ranges:
            candidate_end = used_range.first - 1
            # Check if there is a gap between the start of the current
            # candidate range, and the address just before the next used
            # range.
            if candidate_end - candidate_start >= 0:
                unused_ranges.append(
                    make_iprange(candidate_start, candidate_end, comment))
            candidate_start = used_range.last + 1
        # Skip the broadcast address, if this is an IPv4 network
        if type(outer_range) == IPNetwork:
            prefixlen = outer_range.prefixlen
            if outer_range.version == 4 and prefixlen not in (31, 32):
                candidate_end = outer_range.last - 1
            else:
                candidate_end = outer_range.last
        else:
            candidate_end = outer_range.last
        # Check if there is a gap between the last used range and the end
        # of the range we're checking against.
        if candidate_end - candidate_start >= 0:
            unused_ranges.append(
                make_iprange(candidate_start, candidate_end, comment))
        return MAASIPSet(unused_ranges)

    def get_full_range(self, outer_range):
        unused_ranges = self.get_unused_ranges(outer_range)
        full_range = MAASIPSet(self | unused_ranges, cidr=outer_range)
        # The full_range should always contain at least one IP address.
        # However, in bug #1570606 we observed a situation where there were
        # no resulting ranges. This assert is just in case the fix didn't cover
        # all cases where this could happen.
        assert len(full_range.ranges) > 0, (
            "get_full_range(): No ranges for CIDR: %s; "
            "self=%r, unused_ranges=%r" % (
                outer_range, self, unused_ranges))
        return full_range

    def __repr__(self):
        item_repr = []
        for item in self.ranges:
            item_repr.append(item)
        return '%s(%s)' % (self.__class__.__name__, item_repr)


def make_ipaddress(input):
    """Returns an `IPAddress` object for the specified input, or `None` if
    `bool(input)` is `False`. Returns `input` if it is already an
    `IPAddress.`"""
    if input:
        if isinstance(input, IPAddress):
            return input
        return IPAddress(input)
    return None


def make_iprange(first, second=None, purpose="unknown"):
    """Returns a MAASIPRange (which is compatible with IPRange) for the
    specified range of addresses.

    :param second: the (inclusive) upper bound of the range. If not supplied,
        uses the lower bound (creating a range of 1 address).
    :param purpose: If supplied, stores a comment in the range object to
        indicate the purpose of this range.
    """
    if isinstance(first, int):
        first = IPAddress(first)
    if second is None:
        second = first
    else:
        if isinstance(second, int):
            second = IPAddress(second)
    iprange = MAASIPRange(inet_ntop(first), inet_ntop(second), purpose=purpose)
    return iprange


def make_network(
        ip_address, netmask_or_bits, cidr=False, **kwargs):
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
    network = IPNetwork("%s/%s" % (ip_address, netmask_or_bits), **kwargs)
    if cidr:
        network = network.cidr
    return network


def find_ip_via_arp(mac):
    """Find the IP address for `mac` by reading the output of arp -n.

    Returns `None` if the MAC is not found.

    We do this because we aren't necessarily the only DHCP server on the
    network, so we can't check our own leases file and be guaranteed to find an
    IP that matches.

    :param mac: The mac address, e.g. '1c:6f:65:d5:56:98'.
    """
    output = call_and_check(['arp', '-n'])
    output = output.decode("ascii").splitlines()

    for line in sorted(output):
        columns = line.split()
        if len(columns) == 5 and columns[2].lower() == mac.lower():
            return columns[0]
    return None


def find_mac_via_arp(ip):
    """Find the MAC address for `ip` by reading the output of arp -n.

    Returns `None` if the IP is not found.

    We do this because we aren't necessarily the only DHCP server on the
    network, so we can't check our own leases file and be guaranteed to find an
    IP that matches.

    :param ip: The ip address, e.g. '192.168.1.1'.
    """
    # Normalise ip.  IPv6 has a wealth of alternate notations, so we can't
    # just look for the string; we have to parse.
    ip = IPAddress(ip)
    # Use "C" locale; we're parsing output so we don't want any translations.
    output = call_and_check(['ip', 'neigh'], env={'LC_ALL': 'C'})
    output = output.decode("ascii").splitlines()

    for line in sorted(output):
        columns = line.split()
        if len(columns) < 4:
            raise Exception(
                "Output line from 'ip neigh' does not look like a neighbour "
                "entry: '%s'" % line)
        # Normal "ip neigh" output lines look like:
        #   <IP> dev <interface> lladdr <MAC> [router] <status>
        #
        # Where <IP> is an IPv4 or IPv6 address, <interface> is a network
        # interface name such as eth0, <MAC> is a MAC address, and status
        # can be REACHABLE, STALE, etc.
        #
        # However sometimes you'll also see lines like:
        #   <IP> dev <interface>  FAILED
        #
        # Note the missing lladdr entry.
        if IPAddress(columns[0]) == ip and columns[3] == 'lladdr':
            # Found matching IP address.  Return MAC.
            return columns[4]
    return None


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


def resolve_hostname(
        hostname, ip_version=4, address_only=True, port=None,
        proto=IPPROTO_TCP):
    """Wrapper around `getaddrinfo`: return addresses for `hostname`.

    :param hostname: Host name (or IP address).
    :param ip_version: Look for addresses of this IP version only: 4 for IPv4,
        or 6 for IPv6, None for both. (Default: 4)
    :param address_only: Only return the addresss, not the full getaddrinfo
        tuple. (Default: true)
    :param port: port number, if any specified.
    :return: A set of `IPAddress`.  Empty if `hostname` does not resolve for
        the requested IP version.
    """
    addr_families = {
        4: AF_INET,
        6: AF_INET6,
        None: None,
        }
    assert ip_version in addr_families
    try:
        if ip_version is None:
            address_info = getaddrinfo(hostname, port, proto=proto)
        else:
            address_info = getaddrinfo(
                hostname, port, family=addr_families[ip_version], proto=proto)
    except gaierror as e:
        if e.errno in (EAI_NONAME, EAI_NODATA):
            # Name does not resolve.
            address_info = []
        else:
            raise

    # The contents of sockaddr differ for IPv6 and IPv4, but the
    # first element is always the address, and that's all we care
    # about.
    if address_only:
        return {
            IPAddress(sockaddr[0])
            for family, socktype, proto, canonname, sockaddr in address_info}
    else:
        return address_info


def intersect_iprange(network, iprange):
    """Return the intersection between two IPNetworks or IPRanges.

    IPSet is notoriously inefficient so we intersect ourselves here.
    """
    if not network or not iprange:
        return None
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


def inet_ntop(value):
    """Convert IPv4 and IPv6 addresses from binary to text form.
    (See also inet_ntop(3), the C function with the same name and function.)"""
    return str(IPAddress(value))


def parse_integer(value_string):
    """Convert the specified `value_string` into a decimal integer.

    Strips whitespace, and handles hexadecimal or binary format strings,
    if the string is prefixed with '0x' or '0b', respectively.

    :raise:ValueError if the conversion to int fails
    :return:int
    """
    value_string = value_string.strip()
    if value_string.lower().startswith('0x'):
        # Hexadecimal.
        base = 16
    elif value_string.lower().startswith('0b'):
        # Binary
        base = 2
    else:
        # When all else fails, assume decimal.
        base = 10
    return int(value_string, base)


def bytes_to_hex(byte_string):
    """Utility function to convert the the specified `bytes` object into
    a string of hex characters."""
    return codecs.encode(byte_string, 'hex')


def bytes_to_int(byte_string):
    """Utility function to convert the specified string of bytes into
    an `int`."""
    return int(bytes_to_hex(byte_string), 16)


def hex_str_to_bytes(data):
    """Strips spaces, '-', and ':' characters out of the specified string,
    and (assuming the characters that remain are hex digits) returns an
    equivalent `bytes` object."""
    data = data.strip()
    if data.startswith('0x'):
        data = data[2:]
    data = data.replace(':', '')
    data = data.replace('-', '')
    data = data.replace(' ', '')
    try:
        return bytes.fromhex(data)
    except ValueError as e:
        # The default execption is not really useful since it doesn't specify
        # the incorrect input.
        raise ValueError("Invalid hex string: '%s'; %s" % (data, str(e)))


def ipv4_to_bytes(ipv4_address):
    return bytes.fromhex("%08x" % IPAddress(ipv4_address).value)


def format_eui(eui):
    """Returns the specified netaddr.EUI object formatted in the MAAS style."""
    return str(eui).replace('-', ':').lower()


def fix_link_addresses(links):
    """Fix the addresses defined in `links`.

    Some address will have a prefixlen of 32 or 128 depending if IPv4 or IPv6.
    Fix those address to fall within a subnet that is already defined in
    another link. The addresses that get fixed will be placed into the smallest
    subnet defined in `links`.
    """
    subnets_v4 = []
    links_v4 = []
    subnets_v6 = []
    links_v6 = []

    # Loop through and build a list of subnets where the prefixlen is not
    # 32 or 128 for IPv4 and IPv6 respectively.
    for link in links:
        ip_addr = IPNetwork(link["address"])
        if ip_addr.version == 4:
            if ip_addr.prefixlen == 32:
                links_v4.append(link)
            else:
                subnets_v4.append(ip_addr.cidr)
        elif ip_addr.version == 6:
            if ip_addr.prefixlen == 128:
                links_v6.append(link)
            else:
                subnets_v6.append(ip_addr.cidr)

    # Sort the subnets so the smallest prefixlen is first.
    subnets_v4 = sorted(subnets_v4, key=attrgetter("prefixlen"), reverse=True)
    subnets_v6 = sorted(subnets_v6, key=attrgetter("prefixlen"), reverse=True)

    # Fix all addresses that have prefixlen of 32 or 128 that fit in inside
    # one of the already defined subnets.
    for link in links_v4:
        ip_addr = IPNetwork(link["address"])
        for subnet in subnets_v4:
            if ip_addr.ip in subnet:
                ip_addr.prefixlen = subnet.prefixlen
                link["address"] = str(ip_addr)
                break
    for link in links_v6:
        ip_addr = IPNetwork(link["address"])
        for subnet in subnets_v6:
            if ip_addr.ip in subnet:
                ip_addr.prefixlen = subnet.prefixlen
                link["address"] = str(ip_addr)
                break


def fix_link_gateways(links, iproute_info):
    """Fix the gateways to be set on each link if a route exists for the subnet
    or if the default gateway is in the subnet.
    """
    for link in links:
        ip_addr = IPNetwork(link["address"])
        cidr = str(ip_addr.cidr)
        if cidr in iproute_info:
            link["gateway"] = iproute_info[cidr]["via"]
        elif ("default" in iproute_info and
                IPAddress(iproute_info["default"]["via"]) in ip_addr):
            link["gateway"] = iproute_info["default"]["via"]


def get_interface_children(interfaces: dict) -> dict:
    """Map each parent interface to a set of its children.

    Interfaces with no children will not be present in the resulting
    dictionary.

    :param interfaces: The output of `get_all_interfaces_definition()`
    :return: dict
    """
    children_map = {}
    for ifname in interfaces:
        for parent in interfaces[ifname]['parents']:
            if parent in children_map:
                children_map[parent].add(ifname)
            else:
                children_map[parent] = {ifname}
    return children_map


InterfaceChild = namedtuple('InterfaceChild', ('name', 'data'))


def interface_children(ifname: str, interfaces: dict, children_map: dict):
    """Yields each child interface for `ifname` given the specified data.

    Each resul will be in the format of a single-item dictionary mapping
    the child interface name to its data in the `interfaces` structure.

    :param ifname: The interface whose children to yield.
    :param interfaces: The output of `get_all_interfaces_definition()`.
    :param children_map: The output of `get_interface_children()`.
    :return: a `namedtuple` with each child's `name` and its `data`.
    """
    if ifname in children_map:
        children = children_map[ifname]
        for child in children:
            yield InterfaceChild._make((child, interfaces[child]))


def get_all_interfaces_definition():
    """Return interfaces definition by parsing "ip addr" and the running
    "dhclient" processes on the machine.

    The interfaces definition is defined as a contract between the region and
    the rack controller. The region controller processes this resulting
    dictionary to update the interfaces model for the rack controller.
    """
    interfaces = {}
    dhclient_info = get_dhclient_info()
    iproute_info = get_ip_route()
    exclude_types = ["loopback", "ipip"]
    if not running_in_container():
        exclude_types.append("ethernet")
    ipaddr_info = {
        name: ipaddr
        for name, ipaddr in get_ip_addr().items()
        if (ipaddr["type"] not in exclude_types and
            not ipaddr["type"].startswith("unknown-"))
    }
    for name, ipaddr in ipaddr_info.items():
        iface_type = "physical"
        parents = []
        mac_address = None
        vid = None
        if ipaddr["type"] == "ethernet.bond":
            iface_type = "bond"
            mac_address = ipaddr["mac"]
            for bond_nic in ipaddr["bonded_interfaces"]:
                if bond_nic in interfaces or bond_nic in ipaddr_info:
                    parents.append(bond_nic)
        elif ipaddr["type"] == "ethernet.vlan":
            iface_type = "vlan"
            parents.append(ipaddr['parent'])
            vid = ipaddr["vid"]
        elif ipaddr["type"] == "ethernet.bridge":
            iface_type = "bridge"
            mac_address = ipaddr["mac"]
            for bridge_nic in ipaddr["bridged_interfaces"]:
                if bridge_nic in interfaces or bridge_nic in ipaddr_info:
                    parents.append(bridge_nic)
        else:
            mac_address = ipaddr["mac"]

        # Create the interface definition will links for both IPv4 and IPv6.
        interface = {
            "type": iface_type,
            "links": [],
            "enabled": True if 'UP' in ipaddr['flags'] else False,
            "parents": parents,
            "source": "ipaddr",
        }
        if mac_address is not None:
            interface["mac_address"] = mac_address
        if vid is not None:
            interface["vid"] = vid
        # Add the static and dynamic IP addresses assigned to the interface.
        dhcp_address = dhclient_info.get(name, None)
        for address in ipaddr.get("inet", []) + ipaddr.get("inet6", []):
            if str(IPNetwork(address).ip) == dhcp_address:
                interface["links"].append({
                    "mode": "dhcp",
                    "address": address,
                })
            else:
                interface["links"].append({
                    "mode": "static",
                    "address": address,
                })
        fix_link_addresses(interface["links"])
        fix_link_gateways(interface["links"], iproute_info)
        interfaces[name] = interface

    return interfaces


def is_loopback_address(hostname):
    """Determine if the given hostname appears to be a loopback address.

    :param hostname: either a hostname or an IP address.  No resolution is
        done, but 'localhost' is considered to be loopback.
    :type hostname: str

    :return: True if the address is a loopback address.
    """

    try:
        ip = IPAddress(hostname)
    except AddrFormatError:
        return hostname.lower() in {"localhost", "localhost."}
    return ip.is_loopback() or (
        ip.is_ipv4_mapped() and ip.ipv4().is_loopback())


@synchronous
def resolves_to_loopback_address(hostname):
    """Determine if the given hostname appears to be a loopback address.

    :param hostname: either a hostname or an IP address, which will be
        resolved.  If any of the returned addresses are loopback addresses,
        then it is considered loopback.
    :type hostname: str

    :return: True if the hostname appears to be a loopback address.
    """
    try:
        addrinfo = socket.getaddrinfo(hostname, None, proto=IPPROTO_TCP)
    except socket.gaierror:
        return hostname.lower() in {"localhost", "localhost."}
    else:
        return any(
            is_loopback_address(sockaddr[0])
            for _, _, _, _, sockaddr in addrinfo)
