# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Generic helpers for `netaddr` and network-related types."""

__all__ = [
    'clean_up_netifaces_address',
    'find_ip_via_arp',
    'find_mac_via_arp',
    'get_all_addresses_for_interface',
    'get_all_interface_addresses',
    'make_network',
    'resolve_hostname',
    'intersect_iprange',
    'ip_range_within_network',
    ]


from socket import (
    AF_INET,
    AF_INET6,
    EAI_NODATA,
    EAI_NONAME,
    gaierror,
    getaddrinfo,
)

from netaddr import (
    IPAddress,
    IPNetwork,
    IPRange,
)
import netifaces
from provisioningserver.utils.shell import call_and_check


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
        self.num_available = 0
        self.num_unavailable = 0
        self.largest_available = 0
        for range in full_maasipset.ranges:
            if 'unused' in range.purpose:
                self.num_available += range.num_addresses
                if range.num_addresses > self.largest_available:
                    self.largest_available = range.num_addresses
            else:
                self.num_unavailable += range.num_addresses
        self.total_addresses = self.num_available + self.num_unavailable

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

    def render_json(self, include_ranges=False):
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
            # XXX LJ 20151004: determine the right calculation, and do it.
            "inefficiency_string": "TBD",
        }
        if include_ranges:
            data["ranges"] = self.ranges.render_json()
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

    def render_json(self, *args, **kwargs):
        return [
            iprange.render_json(*args, **kwargs)
            for iprange in self.ranges
        ]

    def __getitem__(self, item):
        return self.find(item)

    def __contains__(self, item):
        return bool(self.find(item))

    def get_unused_ranges(self, outer_range):
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
                    make_iprange(candidate_start, candidate_end, "unused"))
            candidate_start = used_range.last + 1
        # Skip the broadcast address, if this is an IPv4 network
        if type(outer_range) == IPNetwork and outer_range.version == 4:
            candidate_end = outer_range.last - 1
        else:
            candidate_end = outer_range.last
        # Check if there is a gap between the last used range and the end
        # of the range we're checking against.
        if candidate_end - candidate_start >= 0:
            unused_ranges.append(
                make_iprange(candidate_start, candidate_end, "unused"))
        return MAASIPSet(unused_ranges)

    def get_full_range(self, outer_range):
        unused_ranges = self.get_unused_ranges(outer_range)
        return MAASIPSet(self | unused_ranges, cidr=outer_range)

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
