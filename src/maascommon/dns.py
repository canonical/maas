#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from ipaddress import IPv4Address, IPv6Address
import re

from netaddr import AddrFormatError, IPAddress, ipv6_full

from maascommon.enums.node import NodeTypeEnum


class HostnameIPMapping:
    """This is used to return address information for a host in a way that
    keeps life simple for the callers."""

    # NOTE: you MUST preserve the order of this arguments, in order not to break
    # v2 API. Make sure the order is always (system_id, ttl, ips, node_type,
    # dnsresource_id, user_id). If you want to add any additional argument, do
    # so after user_id.
    def __init__(
        self,
        system_id: str | None = None,
        ttl: int | None = None,
        ips: set[IPv4Address | IPv6Address] | None = None,
        node_type: NodeTypeEnum | None = None,
        dnsresource_id: int | None = None,
        user_id: int | None = None,
        # Additional arguments
        node_id: int | None = None,
    ):
        self.system_id = system_id
        self.node_type = node_type
        self.ttl = ttl
        self.ips: set[IPv4Address | IPv6Address] = (
            set() if ips is None else ips.copy()
        )
        self.dnsresource_id = dnsresource_id
        self.user_id = user_id
        self.node_id = node_id

    def __repr__(self):
        return "HostnameIPMapping({!r}, {!r}, {!r}, {!r}, {!r}, {!r}, {!r})".format(
            self.system_id,
            self.ttl,
            self.ips,
            self.node_type,
            self.dnsresource_id,
            self.user_id,
            self.node_id,
        )

    def __eq__(self, other):
        return self.__dict__ == other.__dict__


class HostnameRRsetMapping:
    """This is used to return non-address information for a hostname in a way
    that keeps life simple for the callers.  Rrset is a set of (ttl, rrtype,
    rrdata) tuples."""

    # NOTE: you MUST preserve the order of this arguments, in order not to break
    # v2 API. Make sure the order is always (system_id, rrset, node_type,
    # dnsresource_id, user_id). If you want to add any additional argument, do
    # so after user_id.
    def __init__(
        self,
        system_id: str | None = None,
        rrset: set | None = None,
        node_type: NodeTypeEnum | None = None,
        dnsresource_id: int | None = None,
        user_id: int | None = None,
        # Additional arguments
        node_id: int | None = None,
    ):
        self.system_id = system_id
        self.node_type = node_type
        self.dnsresource_id = dnsresource_id
        self.user_id = user_id
        self.rrset = set() if rrset is None else rrset.copy()
        self.node_id = node_id

    def __repr__(self):
        return (
            "HostnameRRSetMapping({!r}, {!r}, {!r}, {!r}, {!r}, {!r})".format(
                self.system_id,
                self.rrset,
                self.node_type,
                self.dnsresource_id,
                self.user_id,
                self.node_id,
            )
        )

    def __eq__(self, other):
        return self.__dict__ == other.__dict__


class DomainDNSRecord:
    """Output of `render_json_for_related_rrdata`.

    `node_id` was added for the v3 api.

    See src/maasservicelayer/services/domains.py"""

    def __init__(
        self,
        name: str,
        rrtype: str,
        rrdata: str,
        system_id: str | None = None,
        node_type: NodeTypeEnum | None = None,
        user_id: int | None = None,
        dnsresource_id: int | None = None,
        node_id: int | None = None,
        ttl: int | None = None,
        dnsdata_id: int | None = None,
    ):
        self.name = name
        self.system_id = system_id
        self.node_type = node_type
        self.user_id = user_id
        self.dnsresource_id = dnsresource_id
        self.node_id = node_id
        self.ttl = ttl
        self.rrtype = rrtype
        self.rrdata = rrdata
        self.dnsdata_id = dnsdata_id

    def to_dict(self, with_node_id: bool = True) -> dict:
        d = {
            "name": self.name,
            "system_id": self.system_id,
            "node_type": self.node_type,
            "user_id": self.user_id,
            "dnsresource_id": self.dnsresource_id,
            "ttl": self.ttl,
            "rrtype": self.rrtype,
            "rrdata": self.rrdata,
            "dnsdata_id": self.dnsdata_id,
        }
        if with_node_id:
            d["node_id"] = self.node_id
        return d


def get_ip_based_hostname(ip) -> str:
    """Given the specified IP address (which must be suitable to convert to
    a netaddr.IPAddress), creates an automatically generated hostname by
    converting the '.' or ':' characters in it to '-' characters.

    For IPv6 address which represent an IPv4-compatible or IPv4-mapped
    address, the IPv4 representation will be used.

    :param ip: The IPv4 or IPv6 address (can be an integer or string)
    """
    try:
        hostname = IPAddress(ip, version=4).format().replace(".", "-")
    except AddrFormatError:
        hostname = IPAddress(ip, version=6).format(ipv6_full).replace(":", "-")  # type: ignore
    return hostname


def get_iface_name_based_hostname(iface_name: str) -> str:
    """Given the specified interface name, creates an automatically generated
    hostname by converting the '_' characters in it to '-' characters, and by
    removing any non-letters in the beginning of the name, and
    non-letters-or-digits from the end.

    Note that according to RFC 952 <http://www.faqs.org/rfcs/rfc952.html> the
    lexical grammar of a name is given by

    <name>  ::= <let>[*[<let-or-digit-or-hyphen>]<let-or-digit>]

    :param iface_name: Input value for the interface name.
    """
    hostname = iface_name.replace("_", "-")
    hostname = re.sub(r"^[^a-zA-Z]+", "", hostname)
    hostname = re.sub(r"[^a-zA-Z0-9]+$", "", hostname)
    return hostname
