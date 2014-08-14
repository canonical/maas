# Copyright 2014 Canonical Ltd.  This software is licensed under the
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

from netaddr import IPAddress
from netaddr.core import AddrFormatError
from provisioningserver.dns.config import (
    compose_config_path,
    render_dns_template,
    report_missing_config_dir,
    )
from provisioningserver.utils.fs import incremental_write


def get_fqdn_or_ip_address(target):
    """Returns the ip address is target is a valid ip address, otherwise
    returns the target with appended '.' if missing."""
    try:
        return IPAddress(target).format()
    except AddrFormatError:
        return target.rstrip('.') + '.'


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
        :param mapping: A hostname:ip-address mapping for all known hosts in
            the zone.  They will be mapped as A records.
        :param srv_mapping: Set of SRVRecord mappings.
        """
        self._dns_ip = kwargs.pop('dns_ip', None)
        self._mapping = kwargs.pop('mapping', {})
        self._network = None
        self._srv_mapping = kwargs.pop('srv_mapping', [])
        super(DNSForwardZoneConfig, self).__init__(
            domain, zone_name=domain, **kwargs)

    @classmethod
    def get_mapping(cls, mapping, domain, dns_ip):
        """Return a generator mapping hostnames to IP addresses.

        This includes the record for the name server's IP.
        :param mapping: A dict mapping host names to IP addresses.
        :param domain: Zone's domain name.
        :param dns_ip: IP address for the zone's authoritative DNS server.
        :return: A generator of tuples: (host name, IP addresses).
        """
        return chain([('%s.' % domain, dns_ip)], mapping.items())

    @classmethod
    def get_A_mapping(cls, mapping, domain, dns_ip):
        """Return a generator mapping hostnames to IP addresses for all
        the IPv4 addresses in `mapping`.

        The returned mapping is meant to be used to generate A records in
        the forward zone file.

        This includes the A record for the name server's IP.
        :param mapping: A dict mapping host names to IP addresses.
        :param domain: Zone's domain name.
        :param dns_ip: IP address for the zone's authoritative DNS server.
        :return: A generator of tuples: (host name, IP addresses).
        """
        mapping = cls.get_mapping(mapping, domain, dns_ip)
        return (item for item in mapping if IPAddress(item[1]).version == 4)

    @classmethod
    def get_AAAA_mapping(cls, mapping, domain, dns_ip):
        """Return a generator mapping hostnames to IP addresses for all
        the IPv6 addresses in `mapping`.

        The returned mapping is meant to be used to generate AAAA records
        in the forward zone file.

        :param mapping: A dict mapping host names to IP addresses.
        :param domain: Zone's domain name.
        :param dns_ip: IP address for the zone's authoritative DNS server.
        :return: A generator of tuples: (host name, IP addresses).
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

    def write_config(self):
        """Write the zone file."""
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
        :param mapping: A hostname:ip mapping for all known hosts in
            the reverse zone.  They will be mapped as PTR records.  IP
            addresses not in `network` will be dropped.
        :param network: The network that the mapping exists within.
        :type network: :class:`netaddr.IPNetwork`
        """
        self._mapping = kwargs.pop('mapping', {})
        self._network = kwargs.pop("network", None)
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

        :param mapping: A hostname:ip-address mapping for all known hosts in
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
            for hostname, ip in mapping.items()
            # Filter out the IP addresses that are not in `network`.
            if IPAddress(ip) in network
        )

    def write_config(self):
        """Write the zone file."""
        self.write_zone_file(
            self.target_path, self.make_parameters(),
            {
                'mappings': {
                    'PTR': self.get_PTR_mapping(
                        self._mapping, self.domain, self._network),
                },
            }
        )
