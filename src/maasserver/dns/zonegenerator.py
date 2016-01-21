# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""DNS zone generator."""

__all__ = [
    'ZoneGenerator',
    ]


import collections
from itertools import (
    chain,
    groupby,
)
import socket

from maasserver import logger
from maasserver.enum import NODEGROUP_STATUS
from maasserver.exceptions import MAASException
from maasserver.models.config import Config
from maasserver.models.dnsresource import DNSResource
from maasserver.models.domain import Domain
from maasserver.models.node import Node
from maasserver.models.nodegroup import NodeGroup
from maasserver.models.staticipaddress import StaticIPAddress
from maasserver.server_address import get_maas_facing_server_address
from netaddr import (
    IPAddress,
    IPNetwork,
    IPRange,
)
from provisioningserver.dns.zoneconfig import (
    DNSForwardZoneConfig,
    DNSReverseZoneConfig,
)


class lazydict(dict):
    """A `dict` that lazily populates itself.

    Somewhat like a :class:`collections.defaultdict`, but that the factory
    function is called with the missing key, and the value returned is saved.
    """

    __slots__ = ("factory", )

    def __init__(self, factory):
        super(lazydict, self).__init__()
        self.factory = factory

    def __missing__(self, key):
        value = self[key] = self.factory(key)
        return value


def sequence(thing):
    """Make a sequence from `thing`.

    If `thing` is a sequence, return it unaltered. If it's iterable, return a
    list of its elements. Otherwise, return `thing` as the sole element in a
    new list.
    """
    if isinstance(thing, collections.Sequence):
        return thing
    elif isinstance(thing, collections.Iterable):
        return list(thing)
    else:
        return [thing]


def get_hostname_ip_mapping(domain_or_subnet):
    """Return a mapping {hostnames -> (ttl, ips)} for the allocated nodes in
    `domain` or `subnet`.
    """
    # Circular imports.
    if isinstance(domain_or_subnet, NodeGroup):
        raise DNSException(
            "get_hostname_ip_mapping no longer takes NodeGroup")
    return StaticIPAddress.objects.get_hostname_ip_mapping(domain_or_subnet)


class DNSException(MAASException):
    """An error occured when setting up MAAS's DNS server."""


WARNING_MESSAGE = (
    "The DNS server will use the address '%s',  which is inside the "
    "loopback network.  This may not be a problem if you're not using "
    "MAAS's DNS features or if you don't rely on this information. "
    "Consult the 'maas-region-admin local_config_set --maas-url' command "
    "for details on how to set the MAAS URL.")


def warn_loopback(ip):
    """Warn if the given IP address is in the loopback network."""
    if IPAddress(ip).is_loopback():
        logger.warning(WARNING_MESSAGE % ip)


def get_dns_server_address(nodegroup=None, ipv4=True, ipv6=True):
    """Return the DNS server's IP address.

    That address is derived from the config maas_url or nodegroup.maas_url.
    Consult the 'maas-region-admin local_config_set --maas-url' command for
    details on how to set the MAAS URL.

    :param nodegroup: Optional cluster to which the DNS server should be
        accessible.  If given, the server address will be taken from the
        cluster's `maas_url` setting.  Otherwise, it will be taken from the
        globally configured default MAAS URL.
    :param ipv4: Include IPv4 server addresses?
    :param ipv6: Include IPv6 server addresses?

    """
    try:
        ip = get_maas_facing_server_address(nodegroup, ipv4=ipv4, ipv6=ipv6)
    except socket.error as e:
        raise DNSException(
            "Unable to find MAAS server IP address: %s. MAAS's DNS server "
            "requires this IP address for the NS records in its zone files. "
            "Make sure that the configuration setting for the MAAS URL has "
            "the correct hostname. Consult the 'maas-region-admin "
            "local_config_set --maas-url' command."
            % e.strerror)

    warn_loopback(ip)
    return ip


def get_dns_search_paths():
    """Return all the search paths for the DNS server."""
    return set(
        name
        for name in NodeGroup.objects.filter(
            status=NODEGROUP_STATUS.ENABLED).values_list("name", flat=True)
        if name
    )


class ZoneGenerator:
    """Generate zones describing those relating to the given domains and
    subnets.

    We generate zones for the domains (forward), and subnets (reverse) passed.
    """

    def __init__(self, domains, subnets, default_ttl=None,
                 serial=None, serial_generator=None):
        """
        :param serial: A serial number to reuse when creating zones in bulk.
        :param serial_generator: As an alternative to `serial`, a callback
            that returns a fresh serial number on every call.
        """
        self.domains = sequence(domains)
        self.subnets = sequence(subnets)
        if default_ttl is None:
            self.default_ttl = Config.objects.get_config('default_dns_ttl')
        else:
            self.default_ttl = default_ttl
        self.serial = serial
        self.serial_generator = serial_generator

    @staticmethod
    def _get_mappings():
        """Return a lazily evaluated nodegroup:mapping dict."""
        return lazydict(get_hostname_ip_mapping)

    @staticmethod
    def _get_networks():
        """Return a lazily evaluated nodegroup:network_details dict.

        network_details takes the form of a tuple of (network,
        (network.ip_range_low, network.ip_range_high)).
        """

        def get_network(nodegroup):
            return [
                (iface.network, (iface.ip_range_low, iface.ip_range_high))
                for iface in nodegroup.get_managed_interfaces()
            ]
        return lazydict(get_network)

    @staticmethod
    def _get_forward_domains(domains):
        """Return the set of managed domains for the given `domains`."""
        return set(
            domain
            for domain in Domain.objects.filter(
                name__in=domains,
                authoritative=True))

    @staticmethod
    def _gen_forward_zones(domains, serial, mappings, default_ttl):
        """Generator of forward zones, collated by domain name."""
        dns_ip = get_dns_server_address()
        domains = set(domains)

        # We need to collect the dynamic ranges for all nodegroups where
        # nodegroup.name == domain.name, so that we can generate mappings for
        # them.
        get_domain = lambda nodegroup: nodegroup.name
        nodegroups = set(
            nodegroup
            for nodegroup in NodeGroup.objects.filter(
                name__in=[domain.name for domain in domains]))
        forward_nodegroups = set(sorted(nodegroups, key=get_domain))
        nodegroup_dict = {}
        for domainname, nodegroups in groupby(forward_nodegroups, get_domain):
            # dynamic ranges come from nodegroups (still)
            # addresses come from Node and StaticIPAddress with no regard for
            # nodegroup, since it could be any with the name overrides.
            nodegroup_dict[domainname] = list(nodegroups)

        # For each of the domains that we are generating, create the zone from:
        # 1. nodegroup dynamic ranges
        # 2. node: ip mapping(domain) (which includes dnsresource addresses)
        # 4. dnsresource non-address records in this domain
        for domain in domains:
            # 1. nodegroup dynamic ranges
            nodegroups = nodegroup_dict.get(domain.name, [])
            dynamic_ranges = [
                interface.get_dynamic_ip_range()
                for nodegroup in nodegroups
                for interface in nodegroup.get_managed_interfaces()
            ]
            dnsresources = DNSResource.objects.filter(domain=domain)
            # 2. node: ip mapping(domain)
            # Map all of the nodes in this domain, including the user-reserved
            # ip addresses.
            mapping = {
                hostname.split('.')[0]: (ttl, ips)
                for hostname, (ttl, ips) in mappings[domain].items()
            }
            # 3. Create non-address records.  Specifically ignore any CNAME
            # records that collide with addresses in mapping.
            other_mapping = {}
            for dnsrr in dnsresources:
                dataset = dnsrr.dnsdata_set.all()
                for rrtype in set(data.resource_type for data in dataset):
                    # Start at 2^31-1, and then select the minimum ttl found in
                    # the RRset.
                    ttl = (1 << 31) - 1
                    if rrtype != 'CNAME' or dnsrr.name not in mapping:
                        values = [
                            str(data)
                            for data in dataset
                            if data.resource_type == rrtype]
                        if dataset.first().ttl is not None:
                            ttl = min(ttl, dataset.first().ttl)
                        elif dnsrr.domain.ttl is not None:
                            ttl = min(ttl, dnsrr.domain.ttl)
                        else:
                            ttl = min(ttl, default_ttl)
                        other_mapping[dnsrr.name] = (ttl, values)

            yield DNSForwardZoneConfig(
                domain.name, serial=serial, dns_ip=dns_ip,
                default_ttl=default_ttl,
                ns_ttl=domain.get_base_ttl('NS', default_ttl),
                ipv4_ttl=domain.get_base_ttl('A', default_ttl),
                ipv6_ttl=domain.get_base_ttl('AAAA', default_ttl),
                mapping=mapping,
                other_mapping=other_mapping,
                dynamic_ranges=dynamic_ranges,
                )

    @staticmethod
    def _get_reverse_nodegroups(nodegroups):
        """Return the set of reverse nodegroups among `nodegroups`.

        This is the subset of the given nodegroups that are managed.
        """
        return set(
            nodegroup
            for nodegroup in nodegroups
            if nodegroup.manages_dns())

    @staticmethod
    def _gen_reverse_zones(subnets, serial, mappings, networks, default_ttl):
        """Generator of reverse zones, sorted by network."""

        subnets = set(subnets)
        # For each of the zones that we are generating (one or more per
        # subnet), compile the zone from:
        # 1. nodegroup dynamic ranges on this subnet
        # 2. node: ip mapping(subnet), including DNSResource records for
        #    StaticIPAddresses in this subnet
        # 3. interfaces on any node that have IP addresses in this subnet
        for subnet in subnets:
            network = IPNetwork(subnet.cidr)
            nodegroups = set(
                nodegroup
                for nodegroup in NodeGroup.objects.filter(
                    nodegroupinterface__subnet=subnet)
                if len(nodegroup.get_managed_interfaces()) > 0)
            # 1. Figure out the dynamic ranges.
            dynamic_ranges = [
                IPRange(iprange[1][0], iprange[1][1])
                for nodegroup in nodegroups
                for iprange in networks[nodegroup]
            ]

            # 2. Start with the map of all of the nodes on this subnet,
            # including all DNSResource-associated addresses.
            mapping = mappings[subnet]

            # 3. Add all of the interface named records.
            # 2015-12-18 lamont N.B., these are not found in the forward zone,
            # on purpose.  If someone eventually calls this a bug, we can
            # revisit the size increase this would create in the forward zone.
            # This will also include any discovered addresses on such
            # interfaces.
            nodes = Node.objects.filter(
                interface__ip_addresses__subnet=subnet,
                interface__ip_addresses__ip__isnull=False)
            for node in nodes:
                if node.address_ttl is not None:
                    ttl = node.address_ttl
                elif node.domain.ttl is not None:
                    ttl = node.domain.ttl
                else:
                    ttl = default_ttl
                interfaces = node.interface_set.filter(
                    ip_addresses__subnet=subnet,
                    ip_addresses__ip__isnull=False)
                mapping.update({
                    "%s.%s" % (
                        interface.name, interface.node.fqdn): (ttl, [
                        ip.ip for ip in interface.ip_addresses.exclude(
                            ip__isnull=True)])
                    for interface in interfaces
                })

            # Use the default_domain as the name for the NS host in the reverse
            # zones.
            yield DNSReverseZoneConfig(
                Domain.objects.get_default_domain().name, serial=serial,
                default_ttl=default_ttl,
                mapping=mapping, network=network,
                dynamic_ranges=dynamic_ranges,
            )

    def __iter__(self):
        """Iterate over zone configs.

        Yields `DNSForwardZoneConfig` and `DNSReverseZoneConfig` configs.
        """
        # For testing and such it's fine if we don't have a serial, but once
        # we get to this point, we really need one.
        assert not (self.serial is None and self.serial_generator is None), (
            "No serial number or serial number generator specified.")

        mappings = self._get_mappings()
        networks = self._get_networks()
        serial = self.serial or self.serial_generator()
        default_ttl = self.default_ttl
        return chain(
            self._gen_forward_zones(
                self.domains, serial, mappings, default_ttl),
            self._gen_reverse_zones(
                self.subnets, serial, mappings, networks, default_ttl),
            )

    def as_list(self):
        """Return the zones as a list."""
        return list(self)
