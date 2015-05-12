# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Classes for generating BIND zone config files."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'DNSForwardZoneConfig',
    'DNSReverseZoneConfig',
    ]


from abc import ABCMeta
from datetime import datetime
from itertools import chain
import math

from netaddr import (
    IPAddress,
    IPNetwork,
    spanning_cidr,
)
from netaddr.core import AddrFormatError
from provisioningserver.dns.config import (
    compose_config_path,
    render_dns_template,
    report_missing_config_dir,
)
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
        return target.rstrip('.') + '.'


def enumerate_mapping(mapping):
    """Generate `(hostname, ip)` tuples from `mapping`.

    :param mapping: A dict mapping host names to lists of IP addresses.
    """
    for hostname, ips in mapping.viewitems():
        for ip in ips:
            yield hostname, ip


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

    octet_one = (cidr.value & 0xff000000) >> 24
    octet_two = (cidr.value & 0x00ff0000) >> 16

    # The first two octets of the network range formatted in the
    # usual dotted-quad style. We can precalculate the start of any IP
    # address in the range because we're only ever dealing with /16
    # networks and smaller.
    prefix = "%d.%d" % (octet_one, octet_two)

    # Similarly, we can calculate what the reverse DNS suffix is going
    # to look like.
    rdns_suffix = "%d.%d.in-addr.arpa." % (octet_two, octet_one)
    return intersecting_subnets, prefix, rdns_suffix


class DNSZoneConfigBase:
    """Base class for zone writers."""

    __metaclass__ = ABCMeta

    template_file_name = 'zone.template'

    def __init__(self, domain, zone_name, serial=None):
        """
        :param domain: The domain name of the forward zone.
        :param zone_name: Fully-qualified zone name.
        :param serial: The serial to use in the zone file. This must increment
            on each change.
        """
        self.domain = domain
        self.zone_name = zone_name
        self.serial = serial
        self.target_path = compose_config_path('zone.%s' % self.zone_name)

    def make_parameters(self):
        """Return a dict of the common template parameters."""
        return {
            'domain': self.domain,
            'serial': self.serial,
            'modified': unicode(datetime.today()),
        }

    @classmethod
    def write_zone_file(cls, output_file, *parameters):
        """Write a zone file based on the zone file template.

        There is a subtlety with zone files: their filesystem timestamp must
        increase with every rewrite.  Some filesystems (ext3?) only seem to
        support a resolution of one second, and so this method may set an
        unexpected modification time in order to maintain that property.
        """
        content = render_dns_template(cls.template_file_name, *parameters)
        with report_missing_config_dir():
            incremental_write(content, output_file, mode=0644)


class DNSForwardZoneConfig(DNSZoneConfigBase):
    """Writes forward zone files.

    A forward zone config contains two kinds of mappings: "A" records map all
    possible IP addresses within each of its networks to generated hostnames
    based on those addresses.  "CNAME" records map configured hostnames to the
    matching generated IP hostnames.  An additional "A" record maps the domain
    to the name server itself.
    """

    def __init__(self, domain, **kwargs):
        """See `DNSZoneConfigBase.__init__`.

        :param domain: The domain name of the forward zone.
        :param serial: The serial to use in the zone file. This must increment
            on each change.
        :param dns_ip: The IP address of the DNS server authoritative for this
            zone.
        :param mapping: A hostname:ip-addresses mapping for all known hosts in
            the zone.  They will be mapped as A records.
        :param srv_mapping: Set of SRVRecord mappings.
        """
        self._dns_ip = kwargs.pop('dns_ip', None)
        self._mapping = kwargs.pop('mapping', {})
        self._network = kwargs.pop('network', None)
        self._dynamic_ranges = kwargs.pop('dynamic_ranges', [])
        self._srv_mapping = kwargs.pop('srv_mapping', [])
        super(DNSForwardZoneConfig, self).__init__(
            domain, zone_name=domain, **kwargs)

    @classmethod
    def get_mapping(cls, mapping, domain, dns_ip):
        """Return a generator mapping hostnames to IP addresses.

        This includes the record for the name server's IP.

        :param mapping: A dict mapping host names to lists of IP addresses.
        :param domain: Zone's domain name.
        :param dns_ip: IP address for the zone's authoritative DNS server.
        :return: A generator of tuples: (host name, IP address).
        """
        return chain(
            [('%s.' % domain, dns_ip)],
            enumerate_mapping(mapping))

    @classmethod
    def get_A_mapping(cls, mapping, domain, dns_ip):
        """Return a generator mapping hostnames to IP addresses for all
        the IPv4 addresses in `mapping`.

        The returned mapping is meant to be used to generate A records in
        the forward zone file.

        This includes the A record for the name server's IP.
        :param mapping: A dict mapping host names to lists of IP addresses.
        :param domain: Zone's domain name.
        :param dns_ip: IP address for the zone's authoritative DNS server.
        :return: A generator of tuples: (host name, IP address).
        """
        mapping = cls.get_mapping(mapping, domain, dns_ip)
        return (item for item in mapping if IPAddress(item[1]).version == 4)

    @classmethod
    def get_AAAA_mapping(cls, mapping, domain, dns_ip):
        """Return a generator mapping hostnames to IP addresses for all
        the IPv6 addresses in `mapping`.

        The returned mapping is meant to be used to generate AAAA records
        in the forward zone file.

        :param mapping: A dict mapping host names to lists of IP addresses.
        :param domain: Zone's domain name.
        :param dns_ip: IP address for the zone's authoritative DNS server.
        :return: A generator of tuples: (host name, IP address).
        """
        mapping = cls.get_mapping(mapping, domain, dns_ip)
        return (item for item in mapping if IPAddress(item[1]).version == 6)

    @classmethod
    def get_srv_mapping(cls, mappings):
        """Return a generator mapping srv entries to hostnames.

        :param mappings: Set of SRVRecord.
        :return: A generator of tuples:
            (service, 'priority weight port target').
        """
        for record in mappings:
            target = get_fqdn_or_ip_address(record.target)
            item = '%s %s %s %s' % (
                record.priority,
                record.weight,
                record.port,
                target)
            yield (record.service, item)

    @classmethod
    def get_GENERATE_directives(cls, dynamic_range):
        """Return the GENERATE directives for the forward zone of a network.
        """
        slash_16 = IPNetwork("%s/16" % IPAddress(dynamic_range.first))
        if (dynamic_range.size > 256 ** 2 or
           not ip_range_within_network(dynamic_range, slash_16)):
            # We can't issue a sane set of $GENERATEs for any network
            # larger than a /16, or for one that spans two /16s, so we
            # don't try.
            return []

        generate_directives = set()
        subnets, prefix, _ = get_details_for_ip_range(dynamic_range)
        for subnet in subnets:
            iterator = "%d-%d" % (
                (subnet.first & 0x000000ff),
                (subnet.last & 0x000000ff))

            hostname = "%s-%d-$" % (
                prefix.replace('.', '-'),
                # Calculate what the third quad (i.e. 10.0.X.1) value should
                # be for this subnet.
                (subnet.first & 0x0000ff00) >> 8,
                )

            ip_address = "%s.%d.$" % (
                prefix,
                (subnet.first & 0x0000ff00) >> 8)
            generate_directives.add((iterator, hostname, ip_address))

        return sorted(
            generate_directives, key=lambda directive: directive[2])

    def write_config(self):
        """Write the zone file."""
        # Create GENERATE directives for IPv4 ranges.
        generate_directives = list(
            chain.from_iterable(
                self.get_GENERATE_directives(dynamic_range)
                for dynamic_range in self._dynamic_ranges
                if dynamic_range.version == 4
            ))
        self.write_zone_file(
            self.target_path, self.make_parameters(),
            {
                'mappings': {
                    'SRV': self.get_srv_mapping(
                        self._srv_mapping),
                    'A': self.get_A_mapping(
                        self._mapping, self.domain, self._dns_ip),
                    'AAAA': self.get_AAAA_mapping(
                        self._mapping, self.domain, self._dns_ip),
                },
                'generate_directives': {
                    'A': generate_directives,
                }
            })


class DNSReverseZoneConfig(DNSZoneConfigBase):
    """Writes reverse zone files.

    A reverse zone mapping contains "PTR" records, each mapping
    reverse-notation IP addresses within a network to the matching generated
    hostname.
    """

    def __init__(self, domain, **kwargs):
        """See `DNSZoneConfigBase.__init__`.

        :param domain: The domain name of the forward zone.
        :param serial: The serial to use in the zone file. This must increment
            on each change.
        :param mapping: A hostname:ips mapping for all known hosts in
            the reverse zone.  They will be mapped as PTR records.  IP
            addresses not in `network` will be dropped.
        :param network: The network that the mapping exists within.
        :type network: :class:`netaddr.IPNetwork`
        """
        self._mapping = kwargs.pop('mapping', {})
        self._network = kwargs.pop("network", None)
        self._dynamic_ranges = kwargs.pop('dynamic_ranges', [])
        zone_name = self.compose_zone_name(self._network)
        super(DNSReverseZoneConfig, self).__init__(
            domain, zone_name=zone_name, **kwargs)

    @classmethod
    def compose_zone_name(cls, network):
        """Return the name of the reverse zone."""
        # Generate the name of the reverse zone file:
        # Use netaddr's reverse_dns() to get the reverse IP name
        # of the first IP address in the network and then drop the first
        # octets of that name (i.e. drop the octets that will be specified in
        # the zone file).
        first = IPAddress(network.first)
        if first.version == 6:
            # IPv6.
            # Use float division and ceil to cope with network sizes that
            # are not divisible by 4.
            rest_limit = int(math.ceil((128 - network.prefixlen) / 4.))
        else:
            # IPv4.
            # Use float division and ceil to cope with splits not done on
            # octets boundaries.
            rest_limit = int(math.ceil((32 - network.prefixlen) / 8.))
        reverse_name = first.reverse_dns.split('.', rest_limit)[-1]
        # Strip off trailing '.'.
        return reverse_name[:-1]

    @classmethod
    def get_PTR_mapping(cls, mapping, domain, network):
        """Return reverse mapping: reverse IPs to hostnames.

        The reverse generated mapping is the mapping between the reverse
        IP addresses and the hostnames for all the IP addresses in the given
        `mapping`.

        The returned mapping is meant to be used to generate PTR records in
        the reverse zone file.

        :param mapping: A hostname:ip-addresses mapping for all known hosts in
            the reverse zone.
        :param domain: Zone's domain name.
        :param network: Zone's network.
        :type network: :class:`netaddr.IPNetwork`
        """
        return (
            (
                IPAddress(ip).reverse_dns,
                '%s.%s.' % (hostname, domain),
            )
            for hostname, ip in enumerate_mapping(mapping)
            # Filter out the IP addresses that are not in `network`.
            if IPAddress(ip) in network
        )

    @classmethod
    def get_GENERATE_directives(cls, dynamic_range, domain):
        """Return the GENERATE directives for the reverse zone of a network."""
        slash_16 = IPNetwork("%s/16" % IPAddress(dynamic_range.first))
        if (dynamic_range.size > 256 ** 2 or
           not ip_range_within_network(dynamic_range, slash_16)):
            # We can't issue a sane set of $GENERATEs for any network
            # larger than a /16, or for one that spans two /16s, so we
            # don't try.
            return []

        generate_directives = set()
        subnets, prefix, rdns_suffix = get_details_for_ip_range(dynamic_range)
        for subnet in subnets:
            iterator = "%d-%d" % (
                (subnet.first & 0x000000ff),
                (subnet.last & 0x000000ff))
            hostname = "%s-%d-$" % (
                prefix.replace('.', '-'),
                (subnet.first & 0x0000ff00) >> 8)
            rdns = "$.%d.%s" % (
                (subnet.first & 0x0000ff00) >> 8,
                rdns_suffix)
            generate_directives.add(
                (iterator, rdns, "%s.%s." % (hostname, domain)))

        return sorted(
            generate_directives, key=lambda directive: directive[2])

    def write_config(self):
        """Write the zone file."""
        # Create GENERATE directives for IPv4 ranges.
        generate_directives = list(
            chain.from_iterable(
                self.get_GENERATE_directives(dynamic_range, self.domain)
                for dynamic_range in self._dynamic_ranges
                if dynamic_range.version == 4
            ))
        self.write_zone_file(
            self.target_path, self.make_parameters(),
            {
                'mappings': {
                    'PTR': self.get_PTR_mapping(
                        self._mapping, self.domain, self._network),
                },
                'generate_directives': {
                    'PTR': generate_directives,
                }
            }
        )
