from enum import StrEnum


class IPRangeType(StrEnum):
    """The vocabulary of possible types of `IPRange` objects."""

    # Dynamic IP Range.
    DYNAMIC = "dynamic"

    # Reserved for exclusive use by MAAS (and possibly a particular user).
    RESERVED = "reserved"

    def __str__(self):
        return str(self.value)


class IPRangePurpose(StrEnum):
    """Well-known purpose types for IP ranges."""

    UNUSED = "unused"
    GATEWAY_IP = "gateway-ip"
    RESERVED = "reserved"
    DYNAMIC = "dynamic"
    PROPOSED_DYNAMIC = "proposed-dynamic"
    UNMANAGED = "unmanaged"
    ASSIGNED_IP = "assigned-ip"
    DNS_SERVER = "dns-server"
    EXCLUDED = "excluded"
    NEIGHBOUR = "neighbour"
    RFC_4291 = "rfc-4291-2.6.1"
    UNKNOWN = "unknown"

    def __str__(self) -> str:
        return str(self.value)
