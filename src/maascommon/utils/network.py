# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from ipaddress import IPv4Address, IPv6Address
import re
from typing import Iterable, List, Optional

from netaddr import IPAddress, IPNetwork, IPRange, IPSet

from maascommon.enums.ipranges import IPRangePurpose


def coerce_to_valid_hostname(
    hostname: str, lowercase: bool = True
) -> str | None:
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


class IPRANGE_PURPOSE:
    """Well-known purpose types for IP ranges."""

    UNUSED = IPRangePurpose.UNUSED.value
    GATEWAY_IP = IPRangePurpose.GATEWAY_IP.value
    RESERVED = IPRangePurpose.RESERVED.value
    DYNAMIC = IPRangePurpose.DYNAMIC.value
    PROPOSED_DYNAMIC = IPRangePurpose.PROPOSED_DYNAMIC.value
    UNMANAGED = IPRangePurpose.UNMANAGED.value
    ASSIGNED_IP = IPRangePurpose.ASSIGNED_IP.value
    DNS_SERVER = IPRangePurpose.DNS_SERVER.value
    EXCLUDED = IPRangePurpose.EXCLUDED.value
    NEIGHBOUR = IPRangePurpose.NEIGHBOUR.value
    RFC_4291 = IPRangePurpose.RFC_4291.value
    UNKNOWN = IPRangePurpose.UNKNOWN.value


class MAASIPRange(IPRange):
    """IPRange object whose default end address is the start address if not
    specified. Capable of storing a string to indicate the purpose of
    the range.

    This class has been moved from `provisioningserver.utils.network` and the
    relevant tests are still there.
    """

    def __init__(
        self,
        start,
        end=None,
        flags=0,
        purpose: set[str] | str = IPRANGE_PURPOSE.UNKNOWN,
    ):
        if end is None:
            end = start
        if isinstance(start, IPRange):
            end = start.last
            start = start.first
        super().__init__(start, end, flags=flags)
        self.flags = flags
        if not isinstance(purpose, set):
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
            self._start,  # pyright: ignore [reportAttributeAccessIssue]
            self._end,  # pyright: ignore [reportAttributeAccessIssue]
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

    @classmethod
    def from_db(
        cls,
        start_ip: IPv4Address | IPv6Address,
        end_ip: IPv4Address | IPv6Address,
        purpose: list[str],
    ):
        # we receive an ipaddress address but we have to translate it to a netaddr one.
        return cls(
            start=IPAddress(str(start_ip)),
            end=IPAddress(str(end_ip)),
            purpose=set(purpose),
        )


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


class MAASIPSet(set):
    """
    This class has been moved from `provisioningserver.utils.network` and the
    relevant tests are still there.
    """

    def __init__(
        self, ranges: list[MAASIPRange], cidr: IPNetwork | None = None
    ):
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
    def first(self) -> Optional[int]:
        """Returns the first IP address in this set."""
        if len(self.ranges) > 0:
            return self.ranges[0].first
        else:
            return None

    @property
    def last(self) -> Optional[int]:
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
        return self.ip_has_purpose(ip, IPRANGE_PURPOSE.UNUSED)

    def includes_purpose(self, purpose) -> bool:
        """Returns True if the specified purpose is found inside any of the
        ranges in this set, otherwise returns False.
        """
        for item in self.ranges:
            if purpose in item.purpose:
                return True
        return False

    def get_first_unused_ip(self) -> Optional[int]:
        """Returns the integer value of the first unused IP address in the set."""
        for item in self.ranges:
            if IPRANGE_PURPOSE.UNUSED in item.purpose:
                return item.first
        return None

    def get_largest_unused_block(self) -> Optional[MAASIPRange]:
        """Find the largest unused block of addresses in this set.

        An IP range is considered unused if it has a purpose of
        `IPRANGE_PURPOSE.UNUSED`.

        :returns: a `MAASIPRange` if the largest unused block was found,
            or None if no IP addresses are unused.
        """

        class NullIPRange:
            """Throwaway class to represent an empty IP range."""

            def __init__(self):
                self.size = 0

        largest = NullIPRange()
        for item in self.ranges:
            if IPRANGE_PURPOSE.UNUSED in item.purpose:
                if item.size >= largest.size:
                    largest = item
        if largest.size == 0:
            return None
        return largest  # pyright: ignore [reportReturnType]

    def render_json(self, *args, **kwargs):
        return [
            iprange.render_json(*args, **kwargs) for iprange in self.ranges
        ]

    def __getitem__(self, item):
        return self.find(item)

    def __contains__(self, item):
        return bool(self.find(item))

    def get_unused_ranges_for_network(
        self, network: IPNetwork, purpose=IPRANGE_PURPOSE.UNUSED
    ) -> "MAASIPSet":
        """Calculates unused ranges with respect to a network.

        Exclude the network (and broadcast, if applicable) addresses from
        the set of addresses considered "unused".
        """
        ip_set = IPSet(network)
        # Skip the network address, if this is a network
        prefixlen = network.prefixlen
        if (
            network.version == 4
            and prefixlen not in (31, 32)
            or network.version == 6
            and prefixlen not in (127, 128)
        ):
            ip_set.remove(network.first)
        # Skip the broadcast address, if this is an IPv4 network
        if network.version == 4 and prefixlen not in (31, 32):
            ip_set.remove(network.last)
        return self._get_unused_ranges(ip_set, purpose)

    def get_unused_ranges_for_range(
        self, ranges: list[MAASIPRange], purpose=IPRANGE_PURPOSE.UNUSED
    ) -> "MAASIPSet":
        """Calculates unused ranges with respect to a list of ranges."""
        ip_set = IPSet(ranges)
        return self._get_unused_ranges(ip_set, purpose)

    def _get_unused_ranges(
        self, ip_set: IPSet, purpose=IPRANGE_PURPOSE.UNUSED
    ) -> "MAASIPSet":
        """Calculates and returns a list of unused IP ranges, based on
        the supplied range of desired addresses.
        """
        used_ip_set = IPSet(self.ranges)
        unused_ip_set = ip_set.difference(used_ip_set)
        unused_ranges = [
            make_iprange(r.first, r.last, purpose)
            for r in unused_ip_set.iter_ipranges()
        ]
        return MAASIPSet(unused_ranges)

    def get_full_range(self, cidr: IPNetwork) -> "MAASIPSet":
        unused_ranges = self.get_unused_ranges_for_network(cidr)
        full_range = MAASIPSet(
            [*self.ranges, *unused_ranges.ranges], cidr=cidr
        )
        # The full_range should always contain at least one IP address.
        # However, in bug #1570606 we observed a situation where there were
        # no resulting ranges. This assert is just in case the fix didn't cover
        # all cases where this could happen.
        assert len(full_range.ranges) > 0, (
            f"get_full_range(): No ranges for CIDR: {cidr}; "
            f"self{self!r}, unused_ranges={unused_ranges!r}"
        )
        return full_range

    def __repr__(self):
        item_repr = []
        for item in self.ranges:
            item_repr.append(item)
        return f"{self.__class__.__name__}({item_repr})"


def inet_ntop(value):
    """Convert IPv4 and IPv6 addresses from integer to text form.
    (See also inet_ntop(3), the C function with the same name and function.)"""
    return str(IPAddress(value))


def make_iprange(
    first, second=None, purpose: set[str] | str = IPRANGE_PURPOSE.UNKNOWN
) -> MAASIPRange:
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
