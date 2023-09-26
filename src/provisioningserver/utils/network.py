# Copyright 2014-2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Generic helpers for `netaddr` and network-related types."""

import codecs
from collections import namedtuple
import json
from operator import attrgetter, itemgetter
import random
import re
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
import struct
from typing import Iterable, List, Optional, TypeVar
from zlib import crc32

from netaddr import EUI, IPAddress, IPNetwork, IPRange
from netaddr.core import AddrFormatError, NotRegisteredError
import netifaces
from twisted.internet.defer import Deferred, inlineCallbacks
from twisted.internet.interfaces import IResolver
from twisted.names.client import getResolver
from twisted.names.error import (
    AuthoritativeDomainError,
    DNSQueryTimeoutError,
    DomainError,
    ResolverError,
)

from provisioningserver.utils.dhclient import get_dhclient_info
from provisioningserver.utils.ipaddr import get_ip_addr
from provisioningserver.utils.iproute import get_ip_route
from provisioningserver.utils.ps import running_in_container
from provisioningserver.utils.shell import call_and_check, get_env_with_locale
from provisioningserver.utils.twisted import asynchronous, synchronous

# Address families in /etc/network/interfaces that MAAS chooses to parse. All
# other families are ignored.
ENI_PARSED_ADDRESS_FAMILIES = ["inet", "inet6"]

# Interface method in /etc/network/interfaces that MAAS chooses to parse. All
# other methods are ignored.
ENI_PARSED_METHODS = ["static", "manual", "dhcp"]

# Hard-coded loopback interface information, since the loopback interface isn't
# included in `get_all_interfaces_definition()`.
LOOPBACK_INTERFACE_INFO = {
    "enabled": True,
    "links": [{"address": "::1/128"}, {"address": "127.0.0.1/8"}],
}


REVERSE_RESOLVE_RETRIES = (1, 2, 4, 8, 16)


# Type hints for `outer_range` parameter (get_unused_ranges()).
OuterRange = TypeVar("OuterRange", IPRange, IPNetwork, bytes, str)

# Could be an `netaddr.IPAddress`, or something we could convert to one if it
# were passed into the `netaddr.IPAddress` constructor.
MaybeIPAddress = TypeVar("MaybeIPAddress", IPAddress, bytes, str, int)

IPAddressOrNetwork = TypeVar(
    "IPAddressOrNetwork", IPNetwork, IPAddress, bytes, str, int
)


class IPRANGE_TYPE:
    """Well-known purpose types for IP ranges."""

    UNUSED = "unused"
    GATEWAY_IP = "gateway-ip"
    DYNAMIC = "dynamic"
    PROPOSED_DYNAMIC = "proposed-dynamic"
    UNMANAGED = "unmanaged"


class MAASIPRange(IPRange):
    """IPRange object whose default end address is the start address if not
    specified. Capable of storing a string to indicate the purpose of
    the range."""

    def __init__(self, start, end=None, flags=0, purpose=None):
        if purpose is None:
            purpose = set()
        if end is None:
            end = start
        if type(start) == IPRange:
            end = start.last
            start = start.first
        super().__init__(start, end, flags=flags)
        self.flags = flags
        if type(purpose) != set:
            purpose = {purpose}
        self.purpose = purpose

    def __str__(self):
        range_str = str(IPAddress(self.first))
        if not self.first == self.last:
            range_str += "-" + str(IPAddress(self.last))
            range_str += f" num_addresses={self.num_addresses}"
        if self.purpose:
            range_str += " purpose=" + repr(self.purpose)
        return range_str

    def __repr__(self):
        return "{}('{}', '{}'{}{})".format(
            self.__class__.__name__,
            self._start,
            self._end,
            (" flags=%d" % self.flags if self.flags else ""),
            (" purpose=%s" % repr(self.purpose) if self.purpose else ""),
        )

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


def _combine_overlapping_maasipranges(
    ranges: Iterable[MAASIPRange],
) -> List[MAASIPRange]:
    """Returns the specified ranges after combining any overlapping ranges.

    Given a sorted list of `MAASIPRange` objects, returns a new (sorted)
    list where any adjacent overlapping ranges have been combined into a single
    range.
    """
    new_ranges = []
    previous_min = None
    previous_max = None
    for item in ranges:
        if previous_min is not None and previous_max is not None:
            # Check for an overlapping range.
            min_overlaps = previous_min <= item.first <= previous_max
            max_overlaps = previous_min <= item.last <= previous_max
            if min_overlaps or max_overlaps:
                previous = new_ranges.pop()
                item = make_iprange(
                    min(item.first, previous_min),
                    max(item.last, previous_max),
                    previous.purpose | item.purpose,
                )
        previous_min = item.first
        previous_max = item.last
        new_ranges.append(item)
    return new_ranges


def _coalesce_adjacent_purposes(
    ranges: Iterable[MAASIPRange],
) -> List[MAASIPRange]:
    """Combines and returns adjacent ranges that have an identical purpose.

    Given a sorted list of `MAASIPRange` objects, returns a new (sorted)
    list where any adjacent ranges with identical purposes have been combined
    into a single range.
    """
    new_ranges = []
    previous_first = None
    previous_last = None
    previous_purpose = None
    for item in ranges:
        if previous_purpose is not None and previous_last is not None:
            adjacent_and_identical = (
                item.first == (previous_last + 1)
                and item.purpose == previous_purpose
            )
            if adjacent_and_identical:
                new_ranges.pop()
                item = make_iprange(previous_first, item.last, item.purpose)
        previous_first = item.first
        previous_last = item.last
        previous_purpose = item.purpose
        new_ranges.append(item)
    return new_ranges


def _normalize_ipranges(ranges: Iterable) -> List[MAASIPRange]:
    """Converts each object in the list of ranges to an MAASIPRange, if
    the object is not already a MAASIPRange. Then, returns a sorted list
    of those MAASIPRange objects.
    """
    new_ranges = []
    for item in ranges:
        if not isinstance(item, MAASIPRange):
            item = MAASIPRange(item)
        new_ranges.append(item)
    return sorted(new_ranges)


class IPRangeStatistics:
    """Encapsulates statistics about a MAASIPSet.

    This class calculates statistics about a `MAASIPSet`, which must be a
    set returned from `MAASIPSet.get_full_range()`. That is, the set must
    include a `MAASIPRange` to cover every possible IP address present in the
    desired range.
    """

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
        if self.ip_version == 6 and self.total_addresses <= 2:
            return None
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
            largest_unused.first,
            largest_unused.last,
            purpose=IPRANGE_TYPE.PROPOSED_DYNAMIC,
        )
        # Adjust the largest unused block if it contains the suggested gateway.
        if self.suggested_gateway is not None:
            gateway_value = IPAddress(self.suggested_gateway).value
            if gateway_value in candidate:
                # The suggested gateway is going to be either the first
                # or the last IP address in the range.
                if gateway_value == candidate.first:
                    candidate = MAASIPRange(
                        candidate.first + 1,
                        candidate.last,
                        purpose=IPRANGE_TYPE.PROPOSED_DYNAMIC,
                    )
                else:
                    # Must be the last address.
                    candidate = MAASIPRange(
                        candidate.first,
                        candidate.last - 1,
                        purpose=IPRANGE_TYPE.PROPOSED_DYNAMIC,
                    )
        if candidate is not None:
            first = candidate.first
            one_fourth_range = self.total_addresses >> 2
            half_remaining_space = self.num_available >> 1
            if candidate.size > one_fourth_range:
                # Prevent the proposed range from taking up too much available
                # space in the subnet.
                first = candidate.last - one_fourth_range
            elif candidate.size >= half_remaining_space:
                # Prevent the proposed range from taking up the remainder of
                # the available IP addresses. (take at most half.)
                first = candidate.last - half_remaining_space + 1
            if first >= candidate.last:
                # Calculated an impossible range.
                return None
            candidate = MAASIPRange(
                first, candidate.last, purpose=IPRANGE_TYPE.PROPOSED_DYNAMIC
            )
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
        return f"{self.available_percentage:.0%}"

    @property
    def usage_percentage(self):
        """Returns the utilization percentage for this set of addresses.
        :return:float"""
        return float(self.num_unavailable) / float(self.total_addresses)

    @property
    def usage_percentage_string(self):
        """Returns the utilization percentage for this set of addresses.
        :return:unicode"""
        return f"{self.usage_percentage:.0%}"

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
            "ip_version": self.ip_version,
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
        self.cidr = cidr
        self.ranges = ranges
        self._condense()
        super().__init__(set(self.ranges))

    def _condense(self):
        """Condenses the `ranges` ivar in this `MAASIPSet` by:

        (1) Ensuring range set is is sorted list of MAASIPRange objects.
        (2) De-duplicate set by combining overlapping IP ranges.
        (3) Combining adjacent ranges with an identical purpose.
        """
        self.ranges = _normalize_ipranges(self.ranges)
        self.ranges = _combine_overlapping_maasipranges(self.ranges)
        self.ranges = _coalesce_adjacent_purposes(self.ranges)

    def __ior__(self, other):
        """Return self |= other."""
        self.ranges.extend(list(other.ranges))
        self._condense()
        # Replace the underlying set with the new ranges.
        super().clear()
        super().__ior__(set(self.ranges))
        return self

    def find(self, search) -> Optional[MAASIPRange]:
        """Searches the list of IPRange objects until it finds the specified
        search parameter, and returns the range it belongs to if found.
        (If the search parameter is a range, returns the result based on
        matching the searching for the range containing the first IP address
        within that range.)
        """
        if isinstance(search, IPRange):
            for item in self.ranges:
                if (
                    item.first <= search.first <= item.last
                    and item.first <= search.last <= item.last
                ):
                    return item
        else:
            addr = IPAddress(search)
            addr = int(addr)
            for item in self.ranges:
                if item.first <= addr <= item.last:
                    return item
        return None

    @property
    def first(self) -> Optional[MAASIPRange]:
        """Returns the first IP address in this set."""
        if len(self.ranges) > 0:
            return self.ranges[0].first
        else:
            return None

    @property
    def last(self) -> Optional[MAASIPRange]:
        """Returns the last IP address in this set."""
        if len(self.ranges) > 0:
            return self.ranges[-1].last
        else:
            return None

    def ip_has_purpose(self, ip, purpose) -> bool:
        """Returns True if the specified IP address has the specified purpose
        in this set; False otherwise.

        :raises: ValueError if the IP address is not within this range.
        """
        range = self.find(ip)
        if range is None:
            raise ValueError(
                "IP address %s does not exist in range (%s-%s)."
                % (ip, self.first, self.last)
            )
        return purpose in range.purpose

    def is_unused(self, ip) -> bool:
        """Returns True if the specified IP address (which must be within the
        ranges in this set) is unused; False otherwise.

        :raises: ValueError if the IP address is not within this range.
        """
        return self.ip_has_purpose(ip, IPRANGE_TYPE.UNUSED)

    def includes_purpose(self, purpose) -> bool:
        """Returns True if the specified purpose is found inside any of the
        ranges in this set, otherwise returns False.
        """
        for item in self.ranges:
            if purpose in item.purpose:
                return True
        return False

    def get_first_unused_ip(self) -> int:
        """Returns the integer value of the first unused IP address in the set."""
        for item in self.ranges:
            if IPRANGE_TYPE.UNUSED in item.purpose:
                return item.first
        return None

    def get_largest_unused_block(self) -> Optional[MAASIPRange]:
        """Find the largest unused block of addresses in this set.

        An IP range is considered unused if it has a purpose of
        `IPRANGE_TYPE.UNUSED`.

        :returns: a `MAASIPRange` if the largest unused block was found,
            or None if no IP addresses are unused.
        """

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
            iprange.render_json(*args, **kwargs) for iprange in self.ranges
        ]

    def __getitem__(self, item):
        return self.find(item)

    def __contains__(self, item):
        return bool(self.find(item))

    def get_unused_ranges(
        self, outer_range: OuterRange, purpose=IPRANGE_TYPE.UNUSED
    ) -> "MAASIPSet":
        """Calculates and returns a list of unused IP ranges, based on
        the supplied range of desired addresses.

        :param outer_range: can be an IPNetwork or IPRange of addresses.
            If an IPNetwork is supplied, the network (and broadcast, if
            applicable) addresses will be excluded from the set of
            addresses considered "unused". If an IPRange is supplied,
            all addresses in the range will be considered unused.
        """
        if isinstance(outer_range, (bytes, str)):
            if "/" in outer_range:
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
                    make_iprange(candidate_start, candidate_end, purpose)
                )
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
                make_iprange(candidate_start, candidate_end, purpose)
            )
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
            "self=%r, unused_ranges=%r" % (outer_range, self, unused_ranges)
        )
        return full_range

    def __repr__(self):
        item_repr = []
        for item in self.ranges:
            item_repr.append(item)
        return f"{self.__class__.__name__}({item_repr})"


def make_ipaddress(input: Optional[MaybeIPAddress]) -> Optional[IPAddress]:
    """Returns an `IPAddress` object for the specified input.

    This method should often be used in place of `netaddr.IPAddress(input)`,
    if the input could be `None`.

    :return: an IPAddress, or or `None` if `bool(input)` is None.
    """
    if input:
        if isinstance(input, IPAddress):
            return input
        return IPAddress(input)
    return None


def make_iprange(first, second=None, purpose="unknown") -> MAASIPRange:
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
    ip_address: MaybeIPAddress, netmask_or_bits: int, cidr=False, **kwargs
) -> IPNetwork:
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
    network = IPNetwork(f"{ip_address}/{netmask_or_bits}", **kwargs)
    if cidr:
        network = network.cidr
    return network


def find_ip_via_arp(mac: str) -> str:
    """Find the IP address for `mac` by reading the output of arp -n.

    Returns `None` if the MAC is not found.

    We do this because we aren't necessarily the only DHCP server on the
    network, so we can't check our own leases file and be guaranteed to find an
    IP that matches.

    :param mac: The mac address, e.g. '1c:6f:65:d5:56:98'.
    """
    output = call_and_check(["arp", "-n"])
    output = output.decode("ascii").splitlines()

    for line in sorted(output):
        columns = line.split()
        if len(columns) == 5 and columns[2].lower() == mac.lower():
            return columns[0]
    return None


def find_mac_via_arp(ip: str) -> str:
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
    output = call_and_check(
        ["ip", "--json", "neigh"], env=get_env_with_locale(locale="C")
    )
    if not output:
        return None

    # skip failed entries (with no MAC) and ensure consistent sorting in case
    # multiple entries are present for the same IP
    entries = sorted(
        (entry for entry in json.loads(output) if entry.get("lladdr")),
        key=itemgetter("lladdr"),
    )
    for entry in entries:
        if IPAddress(entry["dst"]) == ip:
            return entry.get("lladdr")


def clean_up_netifaces_address(address: str, interface: str):
    """Strip extraneous matter from `netifaces` IPv6 address.

    Each link-local IPv6 address we get from `netifaces` has a "zone index": a
    suffix consisting of a percent sign and a network interface name, e.g.
    `eth0` in GNU/Linux or `0` in Windows.  These are normally used to
    disambiguate link-local addresses (which have the same network prefix on
    each link, but may not actually be connected).  `IPAddress` doesn't parse
    that suffix, so we strip it off.
    """
    return address.replace("%" + interface, "")


def get_all_addresses_for_interface(interface: str) -> Iterable[str]:
    """Yield all IPv4 and IPv6 addresses for an interface as `IPAddress`es.

    IPv4 addresses will be yielded first, followed by IPv6 addresses.

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
                # We know the interface name, so we don't care to keep the
                # interface name on link-local addresses.  Strip those off
                # here.
                yield clean_up_netifaces_address(
                    inet6_address["addr"], interface
                )


def get_all_interface_addresses() -> Iterable[str]:
    """For each network interface, yield its addresses."""
    for interface in netifaces.interfaces():
        yield from get_all_addresses_for_interface(interface)


def safe_getaddrinfo(
    hostname, port, family=AF_INET, proto=IPPROTO_TCP, timeout=10
):
    if family in (
        AF_INET,
        0,
    ):  # IPv6-only hosts currently error when using getaddrinfo
        return getaddrinfo(hostname, port, family=family, proto=proto)

    # TODO use getaddrinfo for all versions once fixed in the stdlib
    # see (see python/cpython issue #82082)
    sock_type = (
        socket.SOCK_STREAM if proto == IPPROTO_TCP else socket.SOCK_DGRAM
    )

    @asynchronous(timeout=timeout)
    @inlineCallbacks
    def _v6_lookup():
        resolver = getResolver()
        answers = yield resolver.lookupIPV6Address(hostname)
        return [
            (AF_INET6, sock_type, proto, "", (ans._address, port, 0, 0))
            for ans in answers[0]
        ]

    try:
        addr = IPAddress(hostname)
    except AddrFormatError:
        result = _v6_lookup()
        # this should only happen in tests where twisted is in the thread,
        # but this is called from a synchronous context
        if isinstance(result, Deferred) and result.result:
            return result.result
        # synchronous contexts should use sync_safe_getaddrinfo to ensure
        # this is not a Deferred
        return result
    else:
        return [(AF_INET6, sock_type, proto, "", (str(addr), port, 0, 0))]


@synchronous
def sync_safe_getaddrinfo(*args, **kwargs):
    return safe_getaddrinfo(*args, **kwargs)


def resolve_host_to_addrinfo(
    hostname, ip_version=4, port=0, proto=IPPROTO_TCP
):
    """Wrapper around `getaddrinfo`: return address information for `hostname`.

    :param hostname: Host name (or IP address).
    :param ip_version: Look for addresses of this IP version only: 4 for IPv4,
        6 for IPv6, or 0 for both. (Default: 4)
    :param port: port number, if any specified. (Default: 0)
    :return: a list of 5-tuples (family, type, proto, canonname, sockaddr)
        suitable for creating sockets and connecting.  If `hostname` does not
        resolve (for that `ip_version`), then the list is empty.
    """
    addr_families = {4: AF_INET, 6: AF_INET6, 0: 0}
    assert ip_version in addr_families
    try:
        address_info = safe_getaddrinfo(
            hostname, port, family=addr_families[ip_version], proto=proto
        )
    except gaierror as e:
        if e.errno in (EAI_NONAME, EAI_NODATA):
            # Name does not resolve.
            address_info = []
        else:
            raise
    return address_info


def resolve_hostname(hostname, ip_version=4):
    """Wrapper around `resolve_host_to_addrinfo`: return just the addresses.

    :param hostname: Host name (or IP address).
    :param ip_version: Look for addresses of this IP version only: 4 for IPv4,
        or 6 for IPv6, 0 for both. (Default: 4)
    :return: A set of `IPAddress`.  Empty if `hostname` does not resolve for
        the requested IP version.
    """
    address_info = resolve_host_to_addrinfo(hostname, ip_version)
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
        ip_range = IPRange(IPAddress(network.first), IPAddress(network.last))
    return all([intersect_iprange(cidr, network) for cidr in ip_range.cidrs()])


def inet_ntop(value):
    """Convert IPv4 and IPv6 addresses from integer to text form.
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
    if value_string.lower().startswith("0x"):
        # Hexadecimal.
        base = 16
    elif value_string.lower().startswith("0b"):
        # Binary
        base = 2
    else:
        # When all else fails, assume decimal.
        base = 10
    return int(value_string, base)


def bytes_to_hex(byte_string):
    """Utility function to convert the the specified `bytes` object into
    a string of hex characters."""
    return codecs.encode(byte_string, "hex")


def bytes_to_int(byte_string):
    """Utility function to convert the specified string of bytes into
    an `int`."""
    return int(bytes_to_hex(byte_string), 16)


def hex_str_to_bytes(data):
    """Strips spaces, '-', and ':' characters out of the specified string,
    and (assuming the characters that remain are hex digits) returns an
    equivalent `bytes` object."""
    data = data.strip()
    if data.startswith("0x"):
        data = data[2:]
    data = data.replace(":", "")
    data = data.replace("-", "")
    data = data.replace(" ", "")
    try:
        return bytes.fromhex(data)
    except ValueError as e:
        # The default execption is not really useful since it doesn't specify
        # the incorrect input.
        raise ValueError(f"Invalid hex string: '{data}'; {str(e)}")


def ipv4_to_bytes(ipv4_address):
    """Converts the specified IPv4 address (in text or integer form) to bytes."""
    return bytes.fromhex("%08x" % IPAddress(ipv4_address).value)


def bytes_to_ipaddress(ip_address_bytes):
    if len(ip_address_bytes) == 4:
        return IPAddress(struct.unpack("!L", ip_address_bytes)[0])
    if len(ip_address_bytes) == 16:
        most_significant, least_significant = struct.unpack(
            "!QQ", ip_address_bytes
        )
        return IPAddress((most_significant << 64) | least_significant)
    else:
        raise ValueError("Invalid IP address size: expected 4 or 16 bytes.")


def format_eui(eui):
    """Returns the specified netaddr.EUI object formatted in the MAAS style."""
    return str(eui).replace("-", ":").lower()


def is_mac(mac: str) -> bool:
    """Return whether or not the string is a MAC address."""
    m = re.search(r"^([0-9a-f]{2}[-:]){5}[0-9a-f]{2}$", str(mac), re.I)
    return m is not None


def get_eui_organization(eui):
    """Returns the registered organization for the specified EUI, if it can be
    determined. Otherwise, returns None.

    :param eui:A `netaddr.EUI` object.
    """
    try:
        registration = eui.oui.registration()
        # Note that `registration` is not a dictionary, so we can't use .get().
        return registration["org"]
    except UnicodeError:
        # See bug #1628761. Due to corrupt data in the OUI database, and/or
        # the fact that netaddr assumes all the data is ASCII, sometimes
        # netaddr will raise an exception during this process.
        return None
    except IndexError:
        # See bug #1748031; this is another way netaddr can fail.
        return None
    except NotRegisteredError:
        # This could happen for locally-administered MACs.
        return None


def get_mac_organization(mac):
    """Returns the registered organization for the specified EUI, if it can be
    determined. Otherwise, returns None.

    :param mac:String representing a MAC address.
    :raises:netaddr.core.AddrFormatError if `mac` is invalid.
    """
    return get_eui_organization(EUI(mac))


def fix_link_addresses(links):
    """Fix the addresses defined in `links`.

    Each link entry can contain addresses in the form:
       {"address": "1.2.3.4/24", ...}
    or
       {"address": "1.2.3.4", "netmask": 24, ...}

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
        if "netmask" in link:
            ip_addr = IPNetwork(f"{link['address']}/{link['netmask']}")
        else:
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

    for links, subnets in ((links_v4, subnets_v4), (links_v6, subnets_v6)):
        subnets = sorted(subnets, key=attrgetter("prefixlen"), reverse=True)
        # Fix all addresses that have prefixlen of 32 or 128 that fit in inside
        # one of the already defined subnets.
        for link in links:
            has_separate_netmask = "netmask" in link
            if has_separate_netmask:
                ip_addr = IPNetwork(f"{link['address']}/{link['netmask']}")
            else:
                ip_addr = IPNetwork(link["address"])

            for subnet in subnets:
                if ip_addr.ip in subnet:
                    if has_separate_netmask:
                        link["netmask"] = subnet.prefixlen
                    else:
                        ip_addr.prefixlen = subnet.prefixlen
                        link["address"] = str(ip_addr)
                    break


def fix_link_gateways(links, iproute_info):
    """Fix the gateways to be set on each link if a route exists for the subnet
    or if the default gateway is in the subnet.
    """
    for link in links:
        network = IPNetwork(link["address"])
        cidr = str(network.cidr)
        if cidr in iproute_info:
            link["gateway"] = iproute_info[cidr]["gateway"]
        elif (
            "default" in iproute_info
            and IPAddress(iproute_info["default"]["gateway"]) in network
        ):
            link["gateway"] = iproute_info["default"]["gateway"]


def get_interface_children(interfaces: dict) -> dict:
    """Map each parent interface to a set of its children.

    Interfaces with no children will not be present in the resulting
    dictionary.

    :param interfaces: The output of `get_all_interfaces_definition()`
    :return: dict
    """
    children_map = {}
    for ifname in interfaces:
        for parent in interfaces[ifname]["parents"]:
            if parent in children_map:
                children_map[parent].add(ifname)
            else:
                children_map[parent] = {ifname}
    return children_map


InterfaceChild = namedtuple("InterfaceChild", ("name", "data"))


def interface_children(ifname: str, interfaces: dict, children_map: dict):
    """Yields each child interface for `ifname` given the specified data.

    Each result will be in the format of a single-item dictionary mapping
    the child interface name to its data in the `interfaces` structure.

    :param ifname: The interface whose children to yield.
    :param interfaces: The output of `get_all_interfaces_definition()`.
    :param children_map: The output of `get_interface_children()`.
    :return: a `namedtuple` with each child's `name` and its `data`.
    """
    if ifname in children_map:
        children = children_map[ifname]
        for child in children:
            yield InterfaceChild(child, interfaces[child])


def get_default_monitored_interfaces(interfaces: dict) -> list:
    """Return a list of interfaces that should be monitored by default.

    This function takes the interface map and filters out VLANs,
    bond parents, and disabled interfaces.
    """
    children_map = get_interface_children(interfaces)
    monitored_interfaces = []
    # By default, monitor physical interfaces (without children that are
    # bonds), bond interfaces, and bridge interfaces without parents.
    for ifname in interfaces:
        interface = interfaces[ifname]
        if not interface["enabled"]:
            # Skip interfaces which are not link-up.
            continue
        iftype = interface.get("type", None)
        if iftype == "physical":
            should_monitor = True
            for child in interface_children(ifname, interfaces, children_map):
                if child.data["type"] == "bond":
                    # This interface is a bond member. Skip it, since would
                    # rather just monitor the bond interface.
                    should_monitor = False
                    break
            if should_monitor:
                monitored_interfaces.append(ifname)
        elif iftype == "bond":
            monitored_interfaces.append(ifname)
        elif iftype == "bridge":
            # If the bridge has parents, that means a physical, bond, or
            # VLAN interface on the host is a member of the bridge. (Which
            # means we're already monitoring the fabric by virtue of the
            # fact that we are monitoring the parent.) Only bridges that
            # stand alone (are not connected to any interfaces MAAS cares
            # about) should therefore be monitored. (In other words, if
            # the bridge has zero parents, it is a virtual network, which
            # MAAS may be managing virtual machines on.)
            if len(interface["parents"]) == 0:
                monitored_interfaces.append(ifname)
    return monitored_interfaces


def annotate_with_default_monitored_interfaces(interfaces: dict) -> None:
    """Annotates the given interfaces definition dictionary with
    the set of interfaces that should be monitored by default.

    For each interface in the dictionary, sets a `monitored` bool to
    True if it should be monitored by default; False otherwise.
    """
    # Annotate each interface with whether or not it should be monitored
    # by default.
    monitored = set(get_default_monitored_interfaces(interfaces))
    for interface in interfaces:
        interfaces[interface]["monitored"] = interface in monitored


def get_all_interfaces_definition(
    annotate_with_monitored: bool = True,
) -> dict:
    """Return details for all network interfaces.

    The interfaces definition is defined as a contract between the region and
    the rack controller. The region controller processes this resulting
    dictionary to update the interfaces model for the rack controller.

    :param annotate_with_monitored: If True, annotates the given interfaces
        with whether or not they should be monitored. (Default: True)

    """
    interfaces = {}
    dhclient_info = get_dhclient_info()
    iproute_info = get_ip_route()
    exclude_types = [
        # It doesn't make sense for MAAS to manage loopback interfaces.
        "loopback",
        # IPv4-in-IPv4 tunnels aren't useful for MAAS to manage.
        "ipip",
        # This type of interface is created when hypervisors create virtual
        # interfaces for guests. By themselves, they're not useful for MAAS to
        # manage.
        "tunnel",
    ]
    if not running_in_container():
        # When not running in a container, we should be able to identify
        # any Ethernet-variant interfaces that are specific enough to be used
        # with MAAS. So we can throw away any that can't be classified.
        exclude_types.append("ethernet")
    ipaddr_info = {
        name: ipaddr
        for name, ipaddr in get_ip_addr().items()
        if (
            ipaddr["mac"]
            and ipaddr["type"] not in exclude_types
            and not ipaddr["type"].startswith("unknown-")
        )
    }
    for name, details in ipaddr_info.items():
        if_type = details["type"]
        if if_type not in ("vlan", "bridge", "bond"):
            if_type = "physical"
        interface = {
            "type": if_type,
            "mac_address": details["mac"],
            "links": [],
            "enabled": details["enabled"],
            "parents": [
                iface for iface in details["parents"] if iface in ipaddr_info
            ],
            "source": "machine-resources",
        }
        if "vid" in details:
            interface["vid"] = details["vid"]
        # Add the static and dynamic IP addresses assigned to the interface.
        dhcp_address = dhclient_info.get(name, None)
        for address in details["addresses"]:
            if str(IPNetwork(address).ip) == dhcp_address:
                interface["links"].append({"mode": "dhcp", "address": address})
            else:
                interface["links"].append(
                    {"mode": "static", "address": address}
                )
        fix_link_addresses(interface["links"])
        fix_link_gateways(interface["links"], iproute_info)
        interfaces[name] = interface

        if annotate_with_monitored:
            annotate_with_default_monitored_interfaces(interfaces)

    return interfaces


def get_all_interface_subnets():
    """Returns all subnets that this machine has access to.

    Uses the `get_all_interfaces_definition` to get the available interfaces,
    and returns a set of subnets for the machine.

    :return: set of IP networks
    :rtype: set of `IPNetwork`
    """
    return {
        IPNetwork(link["address"])
        for interface in get_all_interfaces_definition().values()
        for link in interface["links"]
    }


def get_all_interface_source_addresses():
    """Return one source address per subnets defined on this machine.

    Uses the `get_all_interface_subnets` and `get_source_address` to determine
    the best source addresses for this machine.

    :return: set of IP addresses
    :rtype: set of `str`
    """
    source_addresses = set()
    for network in get_all_interface_subnets():
        src = get_source_address(network)
        if src is not None:
            source_addresses.add(src)
    return source_addresses


def enumerate_assigned_ips(ifdata):
    """Yields each IP address assigned to an interface.

    :param ifdata: The value of the interface data returned from
        `get_all_interfaces_definition()`.
    :return: generator yielding each IP address as a string.
    """
    links = ifdata["links"]
    return (link["address"].split("/")[0] for link in links)


def get_ifname_ifdata_for_destination(
    destination_ip: IPAddressOrNetwork, interfaces: dict
):
    """Returns an (ifname, ifdata) tuple for the given destination.

    :param destination_ip: The destination IP address.
    :param interfaces: The output of `get_all_interfaces_definition()`.
    :returns: tuple of (ifname, ifdata)
    :raise: ValueError if not found
    """
    source_ip = get_source_address(destination_ip)
    if source_ip is None:
        raise ValueError("No route to host: %s" % destination_ip)
    if source_ip == "::1" or source_ip == "127.0.0.1":
        return "lo", LOOPBACK_INTERFACE_INFO
    for ifname, ifdata in interfaces.items():
        for candidate in enumerate_assigned_ips(ifdata):
            if candidate == source_ip:
                return ifname, ifdata
    raise ValueError("Source IP not found in interface links: %s" % source_ip)


def enumerate_ipv4_addresses(ifdata):
    """Yields each IPv4 address assigned to an interface.

    :param ifdata: The value of the interface data returned from
        `get_all_interfaces_definition()`.
    :return: generator yielding each IPv4 address as a string.
    """
    return (
        ip
        for ip in enumerate_assigned_ips(ifdata)
        if IPAddress(ip).version == 4
    )


def has_ipv4_address(interface: dict) -> bool:
    """Returns True if the specified interface has an IPv4 address assigned.

    If no addresses are assigned, or only addresses with other address families
    are assigned (IPv6), returns False.

    :param interface: interface details for an interface fom `get_all_interfaces_definition()`.
    """
    address_families = {
        IPAddress(ip).version for ip in enumerate_assigned_ips(interface)
    }
    return 4 in address_families


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
        ip.is_ipv4_mapped() and ip.ipv4().is_loopback()
    )


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
        addrinfo = sync_safe_getaddrinfo(hostname, None, proto=IPPROTO_TCP)
    except socket.gaierror:
        return hostname.lower() in {"localhost", "localhost."}
    else:
        return any(
            is_loopback_address(sockaddr[0])
            for _, _, _, _, sockaddr in addrinfo
        )


def preferred_hostnames_sort_key(fqdn: str):
    """Return the sort key for the given FQDN, to sort in "preferred" order."""
    fqdn = fqdn.rstrip(".")
    subdomains = fqdn.split(".")
    # Sort by TLDs first.
    subdomains.reverse()
    key = (
        # First, prefer "more qualified" hostnames. (Since the sort will be
        # ascending, we need to negate this.) For example, if a reverse lookup
        # returns `[www.ubuntu.com, ubuntu.com]`, we prefer `www.ubuntu.com`,
        # even though 'w' sorts after 'u'.
        -len(subdomains),
        # Second, sort by domain components.
        subdomains,
    )
    return key


@inlineCallbacks
def reverseResolve(
    ip: MaybeIPAddress, resolver: IResolver = None
) -> Optional[List[str]]:
    """Using the specified IResolver, reverse-resolves the specifed `ip`.

    :return: a sorted list of resolved hostnames (which the specified IP
        address reverse-resolves to). If the DNS lookup appeared to succeed,
        but no hostnames were found, returns an empty list. If the DNS lookup
        timed out or an error occurred, returns None.
    """
    if resolver is None:
        resolver = getResolver()
    ip = IPAddress(ip)
    try:
        data = yield resolver.lookupPointer(
            ip.reverse_dns, timeout=REVERSE_RESOLVE_RETRIES
        )
        # I love the concise way in which I can ask the Twisted data structure
        # what the list of hostnames is. This is great.
        results = sorted(
            (rr.payload.name.name.decode("idna") for rr in data[0]),
            key=preferred_hostnames_sort_key,
        )
    except AuthoritativeDomainError:
        # "Failed to reverse-resolve '%s': authoritative failure." % ip
        # This means the name didn't resolve, so return an empty list.
        return []
    except DomainError:
        # "Failed to reverse-resolve '%s': no records found." % ip
        # This means the name didn't resolve, so return an empty list.
        return []
    except DNSQueryTimeoutError:
        # "Failed to reverse-resolve '%s': timed out." % ip
        # Don't return an empty list since this implies a temporary failure.
        pass
    except ResolverError:
        # "Failed to reverse-resolve '%s': rejected by local resolver." % ip
        # Don't return an empty list since this could be temporary (unclear).
        pass
    else:
        return results
    return None


def coerce_to_valid_hostname(hostname, lowercase: bool = True):
    """Given a server name that may contain spaces and special characters,
    attempts to derive a valid hostname.

    :param hostname: the specified (possibly invalid) hostname
    :param lowercase: whether to coerce to lowercase chars
    :return: the resulting string, or None if the hostname could not be coerced
    """
    if lowercase:
        hostname = hostname.lower()
    hostname = re.sub(r"[^a-zA-Z0-9-]+", "-", hostname)
    hostname = hostname.strip("-")
    if hostname == "" or len(hostname) > 64:
        return None
    return hostname


def get_source_address(destination: IPAddressOrNetwork):
    """Returns the local source address for the specified destination.

    :param destination: Can be an IP address in string format, an IPNetwork,
        or an IPAddress object.
    :return: the string representation of the local IP address that would be
        used for communication with the specified destination.
    """
    if isinstance(destination, IPNetwork):
        if destination.prefixlen == 128:
            # LP: #1789721 - netaddr raises an exception when using
            # iter_hosts() with a /128 address.
            destination = destination.ip
        else:
            # Make sure to return a host (not a network) if possible.
            # Using iter_hosts() here is a general way to accomplish that.
            destination = IPAddress(next(destination.iter_hosts()))
    else:
        destination = make_ipaddress(destination)
    if destination.is_ipv4_mapped():
        destination = destination.ipv4()
    return get_source_address_for_ipaddress(destination)


def get_source_address_for_ipaddress(destination_ip: IPAddress):
    """Returns the local source address for the specified IPAddress.

    Callers should generally use the `get_source_address()` utility instead;
    it is more flexible about the type of the input parameter.

    :param destination_ip: Can be an IP address in string format, an IPNetwork,
        or an IPAddress object.
    :return: the string representation of the local IP address that would be
        used for communication with the specified destination.
    """
    af = AF_INET if destination_ip.version == 4 else AF_INET6
    with socket.socket(af, socket.SOCK_DGRAM) as sock:
        peername = str(destination_ip)
        local_address = "0.0.0.0" if af == socket.AF_INET else "::"
        try:
            # Note: this sets up the socket *just enough* to get the source
            # address. No network traffic will be transmitted.
            sock.bind((local_address, 0))
            sock.connect((peername, 7))
            sockname = sock.getsockname()
            own_ip = sockname[0]
            return own_ip
        except OSError:
            # Probably "can't assign requested address", which probably means
            # we tried to connect to an IPv6 address, but IPv6 is not
            # configured. Could also happen if a network or broadcast address
            # is passed in, or we otherwise cannot route to the destination.
            return None


def generate_mac_address():
    """Generate a random MAC address."""
    mac = [
        0x52,
        0x54,
        0x00,
        random.randint(0x00, 0xFF),
        random.randint(0x00, 0xFF),
        random.randint(0x00, 0xFF),
    ]
    return ":".join(map(lambda byte: "%02x" % byte, mac))


def convert_host_to_uri_str(host):
    """Convert host to a string that can be used in a URI."""
    try:
        ip = IPAddress(host)
    except AddrFormatError:
        return host
    else:
        if ip.is_ipv4_mapped():
            return str(ip.ipv4())
        elif ip.version == 4:
            return str(ip)
        else:
            return "[%s]" % str(ip)


def get_ifname_for_label(label: str) -> str:
    """Given a generic interface label, return a suitable interface name.

    If the label is numeric, appends 'eth' to the beginning.

    If the name is more than 15 characters, shortens it using a hash algorithm.
    """
    if label.isnumeric():
        label = "eth%d" % int(label)
    # Need to measure the length of the interface name in bytes, not
    # characters, since that is how it's represented in the kernel.
    label = label.encode("utf-8")
    if len(label) > 15:
        ifname_hash = (b"%05x" % (crc32(label) & 0xFFFFFFFF))[-5:]
        label = b"eth-%s-%s" % (ifname_hash, label[len(label) - 5 :])
    return label.decode("utf-8")
