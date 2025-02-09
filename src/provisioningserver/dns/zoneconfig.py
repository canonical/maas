# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Classes for generating BIND zone config files."""

from datetime import datetime
from itertools import chain
import os

from netaddr import IPAddress, IPNetwork, spanning_cidr
from netaddr.core import AddrFormatError

from provisioningserver.dns.actions import freeze_thaw_zone, NSUpdateCommand
from provisioningserver.dns.config import (
    compose_zone_file_config_path,
    DynamicDNSUpdate,
    render_dns_template,
    report_missing_config_dir,
)
from provisioningserver.prometheus.metrics import PROMETHEUS_METRICS
from provisioningserver.utils.fs import incremental_write
from provisioningserver.utils.network import (
    intersect_iprange,
    ip_range_within_network,
)


def get_fqdn_or_ip_address(target):
    """Returns the ip address is target is a valid ip address, otherwise
    returns the target with appended '.' if missing."""
    try:
        return IPAddress(target).format()
    except AddrFormatError:
        return target.rstrip(".") + "."


def enumerate_ip_mapping(mapping):
    """Generate `(hostname, ttl, value)` tuples from `mapping`.

    :param mapping: A dict mapping host names to info about the host:
        .ttl: ttl for the RRset, .ips: list of ip addresses.
    """
    for hostname, info in mapping.items():
        for value in info.ips:
            yield hostname, info.ttl, value


def enumerate_rrset_mapping(mapping):
    """Generate `(hostname, ttl, value)` tuples from `mapping`.

    :param mapping: A dict mapping host names to info about the host:
        .rrset: list of (ttl, rrtype, rrdata) tuples.
    """
    for hostname, info in mapping.items():
        for value in info.rrset:
            yield hostname, value[0], value[1], value[2]


def get_details_for_ip_range(ip_range):
    """For a given IPRange, return all subnets, a useable prefix and the
    reverse DNS suffix calculated from that IP range.

    :return: A tuple of:
        All subnets of /24 (or smaller if there is no /24 subnet to be
        found) in `ip_range`.
        A prefix made from the first two octets in the range.
        A RDNS suffix calculated from the first two octets in the range.
    """
    # Calculate a spanning network for the range above. There are
    # 256 /24 networks in a /16, so that's the most /24s we're going
    # to have to deal with; this matters later on when we iterate
    # through the /24s within this network.
    if ip_range.size == 1:
        cidr = IPNetwork(IPAddress(ip_range.first))
    else:
        cidr = spanning_cidr(ip_range)
    subnets = cidr.subnet(max(24, cidr.prefixlen))

    # Split the spanning network into /24 subnets, then see if they fall
    # entirely within the original network range, partially, or not at
    # all.
    intersecting_subnets = []
    for subnet in subnets:
        intersect = intersect_iprange(subnet, ip_range)
        if intersect is None:
            # The subnet does not fall within the original network.
            pass
        else:
            # The subnet falls partially within the original network, so print
            # out a $GENERATE expression for a subset of the /24.
            intersecting_subnets.append(intersect)

    octet_one = (cidr.value & 0xFF000000) >> 24
    octet_two = (cidr.value & 0x00FF0000) >> 16

    # The first two octets of the network range formatted in the
    # usual dotted-quad style. We can precalculate the start of any IP
    # address in the range because we're only ever dealing with /16
    # networks and smaller.
    prefix = "%d.%d" % (octet_one, octet_two)

    # Similarly, we can calculate what the reverse DNS suffix is going
    # to look like.
    rdns_suffix = "%d.%d.in-addr.arpa." % (octet_two, octet_one)
    return intersecting_subnets, prefix, rdns_suffix


def networks_overlap(net1, net2):
    return net1 in net2 or net2 in net1


def record_for_network(update: DynamicDNSUpdate, network: IPNetwork) -> bool:
    if update.rectype != "PTR":
        return True

    return IPAddress(update.ip) in network


class DomainInfo:
    """Information about a DNS zone"""

    def __init__(self, subnetwork, zone_name, target_path=None):
        """
        :param subnetwork: IPNetwork that this zone (chunk) is for.  None
            for forward zones.
        :param zone_name: Fully-qualified zone name
        :param target_path: Optional, can be used to override the target path.
        """
        self.subnetwork = subnetwork
        self.zone_name = zone_name
        if target_path is None:
            self.target_path = compose_zone_file_config_path(
                "zone.%s" % zone_name
            )
        else:
            self.target_path = target_path


class DomainConfigBase:
    """Base class for zone writers."""

    template_file_name = "zone.template"

    def __init__(self, domain, zone_info, serial=None, **kwargs):
        """
        :param domain: An iterable list of domain names for the
            forward zone.
        :param ns_host_name: The name of the primary nameserver.
        :param zone_info: list of DomainInfo entries.
        :param serial: The serial to use in the zone file. This must increment
            on each change.
        :param ns_ttl: The TTL for the NS RRset.
        :param default_ttl: The default TTL for the zone.
        """
        self.domain = domain
        self.ns_host_name = kwargs.pop("ns_host_name", None)
        self.serial = serial
        self.zone_info = zone_info
        self.target_base = compose_zone_file_config_path("zone")
        self.default_ttl = kwargs.pop("default_ttl", 30)
        self.ns_ttl = kwargs.pop("ns_ttl", self.default_ttl)
        self.requires_reload = False
        self._dynamic_updates = kwargs.pop("dynamic_updates", [])
        self.force_config_write = kwargs.pop("force_config_write", False)

    def make_parameters(self):
        """Return a dict of the common template parameters."""
        return {
            "domain": self.domain,
            "serial": self.serial,
            "modified": str(datetime.today()),
            "ttl": self.default_ttl,
            "ns_ttl": self.ns_ttl,
            "ns_host_name": self.ns_host_name,
        }

    def zone_file_exists(self, zone_info):
        try:
            os.stat(zone_info.target_path)
        except FileNotFoundError:
            return False
        else:
            return True

    def dynamic_update(self, zone_info, network=None):
        nsupdate = NSUpdateCommand(
            zone_info.zone_name,
            [
                update
                for update in self._dynamic_updates
                if update.zone == zone_info.zone_name
                or (
                    networks_overlap(IPNetwork(update.subnet), network)
                    and record_for_network(update, network)
                    if network
                    else networks_overlap(
                        IPNetwork(update.subnet), zone_info.subnetwork
                    )
                    and record_for_network(update, zone_info.subnetwork)
                )
            ],
            serial=self.serial,
            ttl=self.default_ttl,
        )
        nsupdate.update()

    @classmethod
    def write_zone_file(cls, output_file, *parameters):
        """Write a zone file based on the zone file template.

        There is a subtlety with zone files: their filesystem timestamp must
        increase with every rewrite.  Some filesystems (ext3?) only seem to
        support a resolution of one second, and so this method may set an
        unexpected modification time in order to maintain that property.
        """
        if not isinstance(output_file, list):
            output_file = [output_file]
        for outfile in output_file:
            content = render_dns_template(cls.template_file_name, *parameters)
            with report_missing_config_dir():
                incremental_write(
                    content.encode("utf-8"),
                    outfile,
                    mode=0o644,
                    uid=os.getuid(),
                    gid=os.getgid(),
                )


class DNSForwardZoneConfig(DomainConfigBase):
    """Writes forward zone files.

    A forward zone config contains two kinds of mappings: "A" records map all
    possible IP addresses within each of its networks to generated hostnames
    based on those addresses.  "CNAME" records map configured hostnames to the
    matching generated IP hostnames.  An additional "A" record maps the domain
    to the name server itself.
    """

    def __init__(self, domain, **kwargs):
        """See `DomainConfigBase.__init__`.

        :param domain: The forward domain name.
        :param serial: The serial to use in the zone file. This must increment
            on each change.
        :param mapping: A hostname:ip-addresses mapping for all known hosts in
            the zone.  They will be mapped as A records.
        :param default_ttl: The default TTL for the zone.
        """
        self._mapping = kwargs.pop("mapping", {})
        self._network = kwargs.pop("network", None)
        self._dynamic_ranges = kwargs.pop("dynamic_ranges", [])
        self._other_mapping = kwargs.pop("other_mapping", {})
        self._ipv4_ttl = kwargs.pop("ipv4_ttl", None)
        self._ipv6_ttl = kwargs.pop("ipv6_ttl", None)
        super().__init__(
            domain, zone_info=[DomainInfo(None, domain)], **kwargs
        )

    @classmethod
    def get_mapping(cls, mapping, addr_ttl):
        """Return a generator mapping hostnames to IP addresses.

        This includes the record for the name server's IP.
        :param mapping: A dict mapping host names to lists of IP addresses.
        :param addr_ttl: The TTL for the @ address RRset.
        :return: A generator of tuples: (host name, IP address).
        """
        return enumerate_ip_mapping(mapping)

    @classmethod
    def get_A_mapping(cls, mapping, addr_ttl):
        """Return a generator mapping hostnames to IP addresses for all
        the IPv4 addresses in `mapping`.

        The returned mapping is meant to be used to generate A records in
        the forward zone file.

        This includes the A record for the name server's IP.
        :param mapping: A dict mapping host names to lists of IP addresses.
        :param addr_ttl: The TTL for the @ address RRset.
        :return: A generator of tuples: (host name, IP address).
        """
        mapping = cls.get_mapping(mapping, addr_ttl)
        if mapping is None:
            return ()
        return (item for item in mapping if IPAddress(item[2]).version == 4)

    @classmethod
    def get_AAAA_mapping(cls, mapping, addr_ttl):
        """Return a generator mapping hostnames to IP addresses for all
        the IPv6 addresses in `mapping`.

        The returned mapping is meant to be used to generate AAAA records
        in the forward zone file.

        :param mapping: A dict mapping host names to lists of IP addresses.
        :param addr_ttl: The TTL for the @ address RRset.
        :return: A generator of tuples: (host name, IP address).
        """
        mapping = cls.get_mapping(mapping, addr_ttl)
        if mapping is None:
            return ()
        return (item for item in mapping if IPAddress(item[2]).version == 6)

    @classmethod
    def get_GENERATE_directives(cls, dynamic_range):
        """Return the GENERATE directives for the forward zone of a network."""
        slash_16 = IPNetwork("%s/16" % IPAddress(dynamic_range.first))
        if dynamic_range.size > 256**2 or not ip_range_within_network(
            dynamic_range, slash_16
        ):
            # We can't issue a sane set of $GENERATEs for any network
            # larger than a /16, or for one that spans two /16s, so we
            # don't try.
            return []

        generate_directives = set()
        subnets, prefix, rdns_suffix = get_details_for_ip_range(dynamic_range)
        for subnet in subnets:
            iterator = "%d-%d" % (
                (subnet.first & 0x000000FF),
                (subnet.last & 0x000000FF),
            )

            hostname = "%s-%d-$" % (
                prefix.replace(".", "-"),
                # Calculate what the third quad (i.e. 10.0.X.1) value should
                # be for this subnet.
                (subnet.first & 0x0000FF00) >> 8,
            )

            ip_address = "%s.%d.$" % (prefix, (subnet.first & 0x0000FF00) >> 8)
            generate_directives.add((iterator, hostname, ip_address))

        return sorted(generate_directives, key=lambda directive: directive[2])

    def write_config(self):
        """Write the zone file."""
        # Create GENERATE directives for IPv4 ranges.
        for zi in self.zone_info:
            generate_directives = list(
                chain.from_iterable(
                    self.get_GENERATE_directives(dynamic_range)
                    for dynamic_range in self._dynamic_ranges
                    if dynamic_range.version == 4
                )
            )
            if not self.force_config_write and self.zone_file_exists(zi):
                self.dynamic_update(zi)
                PROMETHEUS_METRICS.update(
                    "maas_dns_dynamic_update_count",
                    "inc",
                    labels={"zone": self.domain},
                )
            else:
                self.requires_reload = True
                needs_freeze_thaw = self.zone_file_exists(zi)
                with freeze_thaw_zone(needs_freeze_thaw, zone=zi.zone_name):
                    self.write_zone_file(
                        zi.target_path,
                        self.make_parameters(),
                        {
                            "mappings": {
                                "A": self.get_A_mapping(
                                    self._mapping, self._ipv4_ttl
                                ),
                                "AAAA": self.get_AAAA_mapping(
                                    self._mapping, self._ipv6_ttl
                                ),
                            },
                            "other_mapping": enumerate_rrset_mapping(
                                self._other_mapping
                            ),
                            "generate_directives": {"A": generate_directives},
                        },
                    )
                PROMETHEUS_METRICS.update(
                    "maas_dns_full_zonefile_write_count",
                    "inc",
                    labels={"zone": self.domain},
                )


class DNSReverseZoneConfig(DomainConfigBase):
    """Writes reverse zone files.

    A reverse zone mapping contains "PTR" records, each mapping
    reverse-notation IP addresses within a network to the matching generated
    hostname.
    """

    def __init__(self, domain, **kwargs):
        """See `DomainConfigBase.__init__`.

        :param domain: Default zone name.
        :param serial: The serial to use in the zone file. This must increment
            on each change.
        :param mapping: A hostname:ips mapping for all known hosts in
            the reverse zone.  They will be mapped as PTR records.  IP
            addresses not in `network` will be dropped.
        :param default_ttl: The default TTL for the zone.
        :param network: The network that the mapping exists within.
        :type network: :class:`netaddr.IPNetwork`
        :param rfc2317_ranges: List of ranges to generate RFC2317 CNAMEs for
        :type rfc2317_ranges: [:class:`netaddr.IPNetwork`]
        :param exclude: Set of IPNetworks to exclude from reverse zone generation
        :type exclude: {:class: `netaddr.IPNetwork`}
        """
        self._mapping = kwargs.pop("mapping", {})
        self._network = kwargs.pop("network", None)
        self._dynamic_ranges = kwargs.pop("dynamic_ranges", [])
        self._rfc2317_ranges = kwargs.pop("rfc2317_ranges", [])
        zone_info = self.compose_zone_info(self._network)
        super().__init__(domain, zone_info=zone_info, **kwargs)

    @classmethod
    def compose_zone_info(cls, network):
        """Return the names of the reverse zones."""
        # Generate the name of the reverse zone file:
        # Use netaddr's reverse_dns() to get the reverse IP name
        # of the first IP address in the network and then drop the first
        # octets of that name (i.e. drop the octets that will be specified in
        # the zone file).
        # returns a list of (IPNetwork, zone_name, zonefile_path) tuples
        first = IPAddress(network.first)
        if first.version == 6:
            # IPv6.
            # 2001:89ab::/19 yields 8.1.0.0.2.ip6.arpa, and the full list
            # is 8.1.0.0.2.ip6.arpa, 9.1.0.0.2.ip6.arpa
            # The ipv6 reverse dns form is 32 elements of 1 hex digit each.
            # How many elements of the reverse DNS name to we throw away?
            # Prefixlen of 0-3 gives us 1, 4-7 gives us 2, etc.
            # While this seems wrong, we always _add_ a base label back in,
            # so it's correct.
            rest_limit = (132 - network.prefixlen) // 4
            # What is the prefix for each inner subnet (It will be the next
            # smaller multiple of 4.)  If it's the smallest one, then RFC2317
            # tells us that we're adding an extra blob to the front of the
            # reverse zone name, and we want the entire prefixlen.
            subnet_prefix = (network.prefixlen + 3) // 4 * 4
            if subnet_prefix == 128:
                subnet_prefix = network.prefixlen
            # How big is the step between subnets?  Again, special case for
            # extra small subnets.
            step = 1 << ((128 - network.prefixlen) // 4 * 4)
            if step < 16:
                step = 16
            # Grab the base (hex) and trailing labels for our reverse zone.
            split_zone = first.reverse_dns.split(".")
            zone_rest = ".".join(split_zone[rest_limit:-1])
            base = int(split_zone[rest_limit - 1], 16)
        else:
            # IPv4.
            # The logic here is the same as for IPv6, but with 8 instead of 4.
            rest_limit = (40 - network.prefixlen) // 8
            subnet_prefix = (network.prefixlen + 7) // 8 * 8
            if subnet_prefix == 32:
                subnet_prefix = network.prefixlen
            step = 1 << ((32 - network.prefixlen) // 8 * 8)
            if step < 256:
                step = 256
            # Grab the base (decimal) and trailing labels for our reverse
            # zone.
            split_zone = first.reverse_dns.split(".")
            zone_rest = ".".join(split_zone[rest_limit:-1])
            base = int(split_zone[rest_limit - 1])

        # Rest_limit has bounds of 1..labelcount+1 (5 or 33).
        # If we're stripping any elements, then we just want base.name.
        if rest_limit > 1:
            if first.version == 6:
                new_zone = f"{base:x}.{zone_rest}"
            else:
                new_zone = f"{base:d}.{zone_rest}"
        # We didn't actually strip any elemnts, so base goes back with
        # the prefixlen attached.
        elif first.version == 6:
            new_zone = f"{base:x}-{network.prefixlen:d}.{zone_rest}"
        else:
            new_zone = f"{base:d}-{network.prefixlen:d}.{zone_rest}"
        return [
            DomainInfo(IPNetwork(f"{first}/{subnet_prefix:d}"), new_zone),
        ]

    @classmethod
    def get_PTR_mapping(cls, mapping, network):
        """Return reverse mapping: reverse IPs to hostnames.

        The reverse generated mapping is the mapping between the reverse
        IP addresses and all the hostnames for all the IP addresses in the
        given `mapping`.

        The returned mapping is meant to be used to generate PTR records in
        the reverse zone file.

        :param mapping: A hostname: info mapping for all
            known hosts in the reverse zone, to their FQDN (without trailing
            dot). Info has ttl, and ips.
        :param network: DNS Zone's network. (Not a supernet.)
        :type network: :class:`netaddr.IPNetwork`
        """

        def short_name(ip, network):
            long_name = IPAddress(ip).reverse_dns
            if network.version == 4:
                short_name = ".".join(
                    long_name.split(".")[: (31 - network.prefixlen) // 8 + 1]
                )
            else:
                short_name = ".".join(
                    long_name.split(".")[: (127 - network.prefixlen) // 4 + 1]
                )
            return short_name

        if mapping is None:
            return ()
        return (
            (short_name(ip, network), ttl, "%s." % hostname)
            for hostname, ttl, ip in enumerate_ip_mapping(mapping)
            # Filter out the IP addresses that are not in `network`.
            if IPAddress(ip) in network
        )

    @classmethod
    def get_GENERATE_directives(cls, dynamic_range, domain, zone_info):
        """Return the GENERATE directives for the reverse zone of a network."""
        slash_16 = IPNetwork("%s/16" % IPAddress(dynamic_range.first))
        if dynamic_range.size > 256**2 or not ip_range_within_network(
            dynamic_range, slash_16
        ):
            # We can't issue a sane set of $GENERATEs for any network
            # larger than a /16, or for one that spans two /16s, so we
            # don't try.
            return []

        generate_directives = set()
        # The largest subnet returned is a /24.
        subnets, prefix, rdns_suffix = get_details_for_ip_range(dynamic_range)
        for subnet in subnets:
            if IPAddress(subnet.first) in zone_info.subnetwork:
                iterator = "%d-%d" % (
                    (subnet.first & 0x000000FF),
                    (subnet.last & 0x000000FF),
                )
                hostname = "%s-%d-$" % (
                    prefix.replace(".", "-"),
                    (subnet.first & 0x0000FF00) >> 8,
                )
                # If we're at least a /24, then fully specify the name,
                # rather than trying to figure out how much of the name
                # is in the zone name.
                if zone_info.subnetwork.prefixlen <= 24:
                    rdns = "$.%d.%s" % (
                        (subnet.first & 0x0000FF00) >> 8,
                        rdns_suffix,
                    )
                else:
                    # Let the zone declaration provide the suffix.
                    # rather than trying to calculate it.
                    rdns = "$"
                generate_directives.add(
                    (iterator, rdns, f"{hostname}.{domain}.")
                )

        return sorted(generate_directives, key=lambda directive: directive[2])

    @classmethod
    def get_rfc2317_GENERATE_directives(cls, network, rfc2317_ranges, domain):
        """Return the GENERATE directives for any needed rfc2317 glue."""
        # A non-empty rfc2317_ranges means that the network is the most
        # specific that it can be (IPv4/24 or IPv6/124), so we can make some
        # simplifications in the GENERATE directives.
        generate_directives = set()
        for subnet in rfc2317_ranges:
            if network.version == 4:
                iterator = "%d-%d" % (
                    (subnet.first & 0x000000FF),
                    (subnet.last & 0x000000FF),
                )
                hostname = "$.%d-%d" % (
                    (subnet.first & 0x000000FF),
                    subnet.prefixlen,
                )
                generate_directives.add((iterator, "$", hostname))
            else:
                iterator = "%x-%d" % (
                    (subnet.first & 0x0000000F),
                    (subnet.last & 0x0000000F),
                )
                hostname = "${0,1,x}.%x-%d" % (
                    (subnet.first & 0x0000000F),
                    subnet.prefixlen,
                )
                generate_directives.add((iterator, "${0,1,x}", hostname))
        return sorted(generate_directives)

    def write_config(self):
        """Write the zone file."""
        # Create GENERATE directives for IPv4 ranges.
        for zi in self.zone_info:
            generate_directives = list(
                chain.from_iterable(
                    self.get_GENERATE_directives(
                        dynamic_range, self.domain, zi
                    )
                    for dynamic_range in self._dynamic_ranges
                    if dynamic_range.version == 4
                )
            )
            if not self.force_config_write and self.zone_file_exists(zi):
                self.dynamic_update(zi, network=zi.subnetwork)
                PROMETHEUS_METRICS.update(
                    "maas_dns_dynamic_update_count",
                    "inc",
                    labels={"zone": self.domain},
                )
            else:
                self.requires_reload = True
                needs_freeze_thaw = self.zone_file_exists(zi)
                with freeze_thaw_zone(needs_freeze_thaw, zone=zi.zone_name):
                    self.write_zone_file(
                        zi.target_path,
                        self.make_parameters(),
                        {
                            "mappings": {
                                "PTR": self.get_PTR_mapping(
                                    self._mapping, zi.subnetwork
                                )
                            },
                            "other_mapping": [],
                            "generate_directives": {
                                "PTR": generate_directives,
                                "CNAME": self.get_rfc2317_GENERATE_directives(
                                    zi.subnetwork,
                                    self._rfc2317_ranges,
                                    self.domain,
                                ),
                            },
                        },
                    )
                PROMETHEUS_METRICS.update(
                    "maas_dns_full_zonefile_write_count",
                    "inc",
                    labels={"zone": self.domain},
                )
