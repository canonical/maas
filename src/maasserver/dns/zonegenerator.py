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
    """Return a mapping {hostnames -> ips} for the allocated nodes in
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

    def __init__(self, domains, subnets, serial=None, serial_generator=None):
        """
        :param serial: A serial number to reuse when creating zones in bulk.
        :param serial_generator: As an alternative to `serial`, a callback
            that returns a fresh serial number on every call.
        """
        self.domains = sequence(domains)
        self.subnets = sequence(subnets)
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
    def _get_srv_mappings():
        """Return list of srv records.

        Each srv record is a dictionary with the following required keys
        srv, port, target. Optional keys are priority and weight.
        """
        # Avoid circular imports.
        from provisioningserver.dns.config import SRVRecord

        # 2015-12-16 lamont This will eventually get replaced by creating a
        # DNSResource record for the windows_kms_host, once we have more than A
        # and AAAA records in that model.
        windows_kms_host = Config.objects.get_config("windows_kms_host")
        if windows_kms_host is None or windows_kms_host == '':
            return
        yield SRVRecord(
            service='_vlmcs._tcp', port=1688, target=windows_kms_host,
            priority=0, weight=0)

    @staticmethod
    def _get_forward_domains(domains):
        """Return the set of managed domains for the given `domains`."""
        return set(
            domain
            for domain in Domain.objects.filter(
                name__in=domains,
                authoritative=True))

    @staticmethod
    def _gen_forward_zones(domains, serial, mappings, srv_mappings):
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
        # 2. node: ip mapping(domain)
        # 3. dnsresource records in this domain
        for domain in domains:
            nodegroups = nodegroup_dict.get(domain.name, [])
            dynamic_ranges = [
                interface.get_dynamic_ip_range()
                for nodegroup in nodegroups
                for interface in nodegroup.get_managed_interfaces()
            ]
            dnsresources = DNSResource.objects.filter(
                domain=domain, ip_addresses__ip__isnull=False)
            # First, map all of the nodes in this domain
            # strip off the domain, since we don't need it in the forward zone.
            mapping = {
                hostname.split('.')[0]: ips
                for hostname, ips in mappings[domain].items()
            }
            # Then, go through and add all of the DNSResource records that are
            # relevant.
            mapping.update({
                dnsrr.name: [ipaddress.ip]
                for dnsrr in dnsresources
                for ipaddress in dnsrr.ip_addresses.exclude(
                    ip__isnull=True)
            })

            yield DNSForwardZoneConfig(
                domain.name, serial=serial, dns_ip=dns_ip,
                mapping=mapping,
                srv_mapping=set(srv_mappings),
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
    def _gen_reverse_zones(subnets, serial, mappings, networks):
        """Generator of reverse zones, sorted by network."""

        subnets = set(subnets)
        # For each of the zones that we are generating (one or more per
        # subnet), compile the zone from:
        # 1. nodegroup dynamic ranges on this subnet
        # 2. node: ip mapping(subnet)
        # 3. dnsresource records for StaticIPAddresses in this subnet
        # 4. interfaces on any node that have IP addresses in this subnet
        for subnet in subnets:
            network = IPNetwork(subnet.cidr)
            nodegroups = set(
                nodegroup
                for nodegroup in NodeGroup.objects.filter(
                    nodegroupinterface__subnet=subnet)
                if len(nodegroup.get_managed_interfaces()) > 0)
            dynamic_ranges = [
                IPRange(iprange[1][0], iprange[1][1])
                for nodegroup in nodegroups
                for iprange in networks[nodegroup]
            ]
            dnsresources = DNSResource.objects.filter(
                ip_addresses__subnet=subnet).exclude(
                ip_addresses__ip__isnull=True)
            ipaddresses = StaticIPAddress.objects.filter(
                subnet=subnet).exclude(ip__isnull=True)

            # First, map all of the nodes on this subnet
            mapping = {
                hostname: [ip]
                for hostname, ips in mappings[subnet].items()
                for ip in ips
            }
            # Next, go through and add all of the relevant DNSResource records.
            mapping.update({
                "%s.%s" % (dnsrr.name, dnsrr.domain.name): [ipaddress.ip]
                for dnsrr in dnsresources
                for ipaddress in dnsrr.ip_addresses.filter(
                    subnet=subnet).exclude(ip__isnull=True)
            })
            # Finally, add all of the interface named records.
            # 2015-12-18 lamont N.B., these are not found in the forward zone,
            # on purpose.  If someone eventually calls this a bug, we can
            # revisit the size increase this would create in the forward zone.
            mapping.update({
                "%s.%s" % (
                    interface.name, interface.node.fqdn): [ip.ip]
                for ip in ipaddresses
                for interface in ip.interface_set.filter(
                    node__isnull=False, node__domain__isnull=False)
            })

            # Use the default_domain as the name for the NS host in the reverse
            # zones.
            yield DNSReverseZoneConfig(
                Domain.objects.get_default_domain().name, serial=serial,
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
        srv_mappings = self._get_srv_mappings()
        serial = self.serial or self.serial_generator()
        return chain(
            self._gen_forward_zones(
                self.domains, serial, mappings,
                srv_mappings),
            self._gen_reverse_zones(
                self.subnets, serial, mappings, networks),
            )

    def as_list(self):
        """Return the zones as a list."""
        return list(self)
