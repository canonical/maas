# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""DNS zone generator."""

__all__ = [
    'ZoneGenerator',
    ]


import collections
from itertools import chain
import socket

from maasserver import logger
from maasserver.enum import (
    IPRANGE_TYPE,
    RDNS_MODE,
)
from maasserver.exceptions import MAASException
from maasserver.models.config import Config
from maasserver.models.dnsdata import DNSData
from maasserver.models.dnsresource import separate_fqdn
from maasserver.models.domain import Domain
from maasserver.models.node import Node
from maasserver.models.staticipaddress import (
    HostnameIPMapping,
    StaticIPAddress,
)
from maasserver.models.subnet import Subnet
from maasserver.server_address import get_maas_facing_server_address
from netaddr import (
    IPAddress,
    IPNetwork,
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
    """Return a mapping {hostnames -> info} for the allocated nodes in
    `domain` or `subnet`.  Info contains: ttl, ips, system_id.
    """
    return StaticIPAddress.objects.get_hostname_ip_mapping(domain_or_subnet)


def get_hostname_dnsdata_mapping(domain):
    """Return a mapping {hostnames -> info} for the allocated nodes in
    `domain`.  Info contains: system_id and rrsets (which contain (ttl, rrtype,
    rrdata) tuples.
    """
    return DNSData.objects.get_hostname_dnsdata_mapping(domain)


class DNSException(MAASException):
    """An error occured when setting up MAAS's DNS server."""


WARNING_MESSAGE = (
    "The DNS server will use the address '%s',  which is inside the "
    "loopback network.  This may not be a problem if you're not using "
    "MAAS's DNS features or if you don't rely on this information. "
    "Consult the 'maas-region local_config_set --maas-url' command "
    "for details on how to set the MAAS URL.")


def warn_loopback(ip):
    """Warn if the given IP address is in the loopback network."""
    if IPAddress(ip).is_loopback():
        logger.warning(WARNING_MESSAGE % ip)


def get_dns_server_address(rack_controller=None, ipv4=True, ipv6=True):
    """Return the DNS server's IP address.

    That address is derived from the config maas_url or rack_controller.url.
    Consult the 'maas-region local_config_set --maas-url' command for
    details on how to set the MAAS URL.

    :param rack_controller: Optional rack controller to which the DNS server
        should be accessible.  If given, the server address will be taken from
        the rack controller's `maas_url` setting.  Otherwise, it will be taken
        from the globally configured default MAAS URL.
    :param ipv4: Include IPv4 server addresses?
    :param ipv6: Include IPv6 server addresses?

    """
    try:
        ip = get_maas_facing_server_address(
            rack_controller, ipv4=ipv4, ipv6=ipv6)
    except socket.error as e:
        raise DNSException(
            "Unable to find MAAS server IP address: %s. MAAS's DNS server "
            "requires this IP address for the NS records in its zone files. "
            "Make sure that the configuration setting for the MAAS URL has "
            "the correct hostname. Consult the 'maas-region "
            "local_config_set --maas-url' command."
            % e.strerror)

    warn_loopback(ip)
    return ip


def get_dns_search_paths():
    """Return all the search paths for the DNS server."""
    return set(
        name
        for name in Domain.objects.filter(
            authoritative=True).values_list("name", flat=True)
        if name
    )


class ZoneGenerator:
    """Generate zones describing those relating to the given domains and
    subnets.

    We generate zones for the domains (forward), and subnets (reverse) passed.
    """

    def __init__(self, domains, subnets, default_ttl=None, serial=None):
        """
        :param serial: A serial number to reuse when creating zones in bulk.
        """
        self.domains = sequence(domains)
        self.subnets = sequence(subnets)
        if default_ttl is None:
            self.default_ttl = Config.objects.get_config('default_dns_ttl')
        else:
            self.default_ttl = default_ttl
        self.serial = serial

    @staticmethod
    def _get_mappings():
        """Return a lazily evaluated mapping dict."""
        return lazydict(get_hostname_ip_mapping)

    @staticmethod
    def _get_rrset_mappings():
        """Return a lazily evaluated mapping dict."""
        return lazydict(get_hostname_dnsdata_mapping)

    @staticmethod
    def _gen_forward_zones(
            domains, serial, mappings, rrset_mappings, default_ttl):
        """Generator of forward zones, collated by domain name."""
        dns_ip = get_dns_server_address()
        domains = set(domains)

        # For each of the domains that we are generating, create the zone from:
        # 1. Node: ip mapping(domain) (which includes dnsresource addresses).
        # 2. Dnsresource non-address records in this domain.
        # 3. For the default domain all forward look ups for the managed and
        #    unmanaged dynamic ranges.
        for domain in domains:
            # 1. node: ip mapping(domain)
            # Map all of the nodes in this domain, including the user-reserved
            # ip addresses.  Separate_fqdn handles top-of-domain names needing
            # to have the name '@', and we already know the domain name, so we
            # discard that part of the return.
            mapping = {
                separate_fqdn(hostname, domainname=domain.name)[0]: info
                for hostname, info in mappings[domain].items()
            }
            # 2a. Create non-address records.  Specifically ignore any CNAME
            # records that collide with addresses in mapping.
            other_mapping = rrset_mappings[domain]

            # 2b. Capture NS RRsets for anything that is a child of this domain
            domain.add_delegations(other_mapping, dns_ip, default_ttl)

            # 3. All forward entries for the managed and unmanaged dynamic
            # ranges go into the default domain.
            dynamic_ranges = []
            if domain.is_default():
                subnets = Subnet.objects.all().prefetch_related("iprange_set")
                for subnet in subnets:
                    # We loop through the whole set so the prefetch above works
                    # in one query.
                    for ip_range in subnet.iprange_set.all():
                        if ip_range.type == IPRANGE_TYPE.DYNAMIC:
                            dynamic_ranges.append(ip_range.get_MAASIPRange())

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
    def _gen_reverse_zones(subnets, serial, mappings, default_ttl):
        """Generator of reverse zones, sorted by network."""

        subnets = set(subnets)
        # Generate the list of parent networks for rfc2317 glue.  Note that we
        # need to handle the case where we are controlling both the small net
        # and a bigger network containing the /24, not just a /24 network.
        rfc2317_glue = {}
        for subnet in subnets:
            network = IPNetwork(subnet.cidr)
            if subnet.rdns_mode == RDNS_MODE.RFC2317:
                # If this is a small subnet and  we are doing RFC2317 glue for
                # it, then we need to combine that with any other such subnets
                # We need to know this before we start creating reverse DNS
                # zones.
                if network.version == 4 and network.prefixlen > 24:
                    # Turn 192.168.99.32/29 into 192.168.99.0/24
                    basenet = IPNetwork(
                        "%s/24" %
                        IPNetwork("%s/24" % network.network).network)
                    rfc2317_glue.setdefault(basenet, set()).add(network)
                elif network.version == 6 and network.prefixlen > 124:
                    basenet = IPNetwork(
                        "%s/124" %
                        IPNetwork("%s/124" % network.network).network)
                    rfc2317_glue.setdefault(basenet, set()).add(network)

        # For each of the zones that we are generating (one or more per
        # subnet), compile the zone from:
        # 1. Dynamic ranges on this subnet.
        # 2. Node: ip mapping(subnet), including DNSResource records for
        #    StaticIPAddresses in this subnet.
        # 3. Interfaces on any node that have IP addresses in this subnet.
        # All of this needs to be done smallest to largest so that we can
        # correctly gather the rfc2317 glue that we need.  Failure to sort
        # means that we wind up grabbing (and deleting) the rfc2317 glue info
        # while processing the wrong network.
        for subnet in sorted(
                subnets,
                key=lambda subnet: IPNetwork(subnet.cidr).prefixlen,
                reverse=True):
            network = IPNetwork(subnet.cidr)
            if subnet.rdns_mode == RDNS_MODE.DISABLED:
                # If we are not doing reverse dns for this subnet, then just
                # skip to the next subnet.
                logger.debug(
                    "%s disabled subnet in DNS config list" % subnet.cidr)
                continue

            # 1. Figure out the dynamic ranges.
            dynamic_ranges = [
                ip_range.netaddr_iprange
                for ip_range in subnet.get_dynamic_ranges()
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
                interface__ip_addresses__subnet_id=subnet.id,
                interface__ip_addresses__ip__isnull=False).prefetch_related(
                "interface_set__ip_addresses")
            for node in nodes:
                if node.address_ttl is not None:
                    ttl = node.address_ttl
                elif node.domain.ttl is not None:
                    ttl = node.domain.ttl
                else:
                    ttl = default_ttl
                for iface in node.interface_set.all():
                    ips_in_subnet = {
                        ip.ip
                        for ip in iface.ip_addresses.all()
                        if (ip.ip is not None and ip.subnet_id == subnet.id)}
                    if len(ips_in_subnet) > 0:
                        iface_map = HostnameIPMapping(
                            node.system_id, ttl, ips_in_subnet, node.node_type)
                        mapping.update({
                            "%s.%s" % (iface.name, iface.node.fqdn): iface_map
                        })

            # Use the default_domain as the name for the NS host in the reverse
            # zones.  If this network is actually a parent rfc2317 glue
            # network, then we need to generate the glue records.
            # We need to detect the need for glue in our networks that are
            # big.
            if ((network.version == 6 and network.prefixlen < 124) or
                    network.prefixlen < 24):
                glue = set()
                # This is the reason for needing the subnets sorted in
                # increasing order of size.
                for net in rfc2317_glue.copy().keys():
                    if net in network:
                        glue.update(rfc2317_glue[net])
                        del(rfc2317_glue[net])
            elif network in rfc2317_glue:
                glue = rfc2317_glue[network]
                del(rfc2317_glue[network])
            else:
                glue = set()
            yield DNSReverseZoneConfig(
                Domain.objects.get_default_domain().name, serial=serial,
                default_ttl=default_ttl,
                mapping=mapping, network=IPNetwork(subnet.cidr),
                dynamic_ranges=dynamic_ranges,
                rfc2317_ranges=glue,
            )
        # Now provide any remaining rfc2317 glue networks.
        for network, ranges in rfc2317_glue.items():
            yield DNSReverseZoneConfig(
                Domain.objects.get_default_domain().name, serial=serial,
                default_ttl=default_ttl,
                network=network,
                rfc2317_ranges=ranges,
            )

    def __iter__(self):
        """Iterate over zone configs.

        Yields `DNSForwardZoneConfig` and `DNSReverseZoneConfig` configs.
        """
        # For testing and such it's fine if we don't have a serial, but once
        # we get to this point, we really need one.
        assert not (self.serial is None), ("No serial number specified.")

        mappings = self._get_mappings()
        rrset_mappings = self._get_rrset_mappings()
        serial = self.serial
        default_ttl = self.default_ttl
        return chain(
            self._gen_forward_zones(
                self.domains, serial, mappings, rrset_mappings, default_ttl),
            self._gen_reverse_zones(
                self.subnets, serial, mappings, default_ttl),
            )

    def as_list(self):
        """Return the zones as a list."""
        return list(self)
