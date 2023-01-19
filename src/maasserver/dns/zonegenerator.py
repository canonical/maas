# Copyright 2014-2019 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""DNS zone generator."""


from collections import defaultdict
from collections.abc import Iterable, Sequence
from itertools import chain

import attr
from netaddr import IPAddress, IPNetwork

from maasserver import logger
from maasserver.enum import IPRANGE_TYPE, RDNS_MODE
from maasserver.exceptions import UnresolvableHost
from maasserver.models.config import Config
from maasserver.models.dnsdata import DNSData, HostnameRRsetMapping
from maasserver.models.dnsresource import separate_fqdn
from maasserver.models.domain import Domain
from maasserver.models.staticipaddress import StaticIPAddress
from maasserver.models.subnet import Subnet
from maasserver.server_address import get_maas_facing_server_addresses
from provisioningserver.dns.config import DynamicDNSUpdate
from provisioningserver.dns.zoneconfig import (
    DNSForwardZoneConfig,
    DNSReverseZoneConfig,
)


class lazydict(dict):
    """A `dict` that lazily populates itself.

    Somewhat like a :class:`collections.defaultdict`, but that the factory
    function is called with the missing key, and the value returned is saved.
    """

    __slots__ = ("factory",)

    def __init__(self, factory):
        super().__init__()
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
    if isinstance(thing, Sequence):
        return thing
    elif isinstance(thing, Iterable):
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
    return DNSData.objects.get_hostname_dnsdata_mapping(domain, with_ids=False)


WARNING_MESSAGE = (
    "The DNS server will use the address '%s',  which is inside the "
    "loopback network.  This may not be a problem if you're not using "
    "MAAS's DNS features or if you don't rely on this information. "
    "Consult the 'maas-region local_config_set --maas-url' command "
    "for details on how to set the MAAS URL."
)


def warn_loopback(ip):
    """Warn if the given IP address is in the loopback network."""
    if IPAddress(ip).is_loopback():
        logger.warning(WARNING_MESSAGE % ip)


def get_dns_server_address(rack_controller=None, ipv4=True, ipv6=True):
    """Return a single DNS server IP address (based on address family).

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
    iplist = get_dns_server_addresses(rack_controller, ipv4, ipv6)
    if iplist:
        return min(iplist).format()
    else:
        return None


def get_dns_server_addresses(
    rack_controller=None,
    ipv4=True,
    ipv6=True,
    include_alternates=False,
    default_region_ip=None,
    filter_allowed_dns=True,
):
    """Return the DNS server's IP addresses.

    That address is derived from the config maas_url or rack_controller.url.
    Consult the 'maas-region local_config_set --maas-url' command for
    details on how to set the MAAS URL.

    :param rack_controller: Optional rack controller to which the DNS server
        should be accessible.  If given, the server addresses will be taken
        from the rack controller's `maas_url` setting.  Otherwise, it will be
        taken from the globally configured default MAAS URL.
    :param ipv4: Include IPv4 server addresses?
    :param ipv6: Include IPv6 server addresses?
    :param include_alternates: Include IP addresses from other regions?
    :param default_region_ip: The default source IP address to be used, if a
        specific URL is not defined.
    :param filter_allowed_dns: If true, only include addresses for subnets
        with allow_dns=True.
    :return: List of IPAddress to use.  Loopback addresses are removed from the
        list, unless there are no non-loopback addresses.

    """
    try:
        ips = get_maas_facing_server_addresses(
            rack_controller=rack_controller,
            ipv4=ipv4,
            ipv6=ipv6,
            include_alternates=include_alternates,
            default_region_ip=default_region_ip,
        )
    except OSError as e:
        raise UnresolvableHost(
            "Unable to find MAAS server IP address: %s. MAAS's DNS server "
            "requires this IP address for the NS records in its zone files. "
            "Make sure that the configuration setting for the MAAS URL has "
            "the correct hostname. Consult the 'maas-region "
            "local_config_set --maas-url' command." % e.strerror
        )

    if filter_allowed_dns:
        ips = [
            ip
            for ip in ips
            if getattr(
                Subnet.objects.get_best_subnet_for_ip(ip), "allow_dns", True
            )
        ]
    non_loop = [ip for ip in ips if not ip.is_loopback()]
    if non_loop:
        return non_loop
    else:
        for ip in ips:
            warn_loopback(ip)
        return ips


def get_dns_search_paths():
    """Return all the search paths for the DNS server."""
    return {
        name
        for name in Domain.objects.filter(authoritative=True).values_list(
            "name", flat=True
        )
        if name
    }


class ZoneGenerator:
    """Generate zones describing those relating to the given domains and
    subnets.

    We generate zones for the domains (forward), and subnets (reverse) passed.
    """

    def __init__(
        self,
        domains,
        subnets,
        default_ttl=None,
        serial=None,
        internal_domains=None,
        dynamic_updates=None,
        force_config_write=False,
    ):
        """
        :param serial: A serial number to reuse when creating zones in bulk.
        """
        self.domains = sequence(domains)
        self.subnets = sequence(subnets)
        if default_ttl is None:
            self.default_ttl = Config.objects.get_config("default_dns_ttl")
        else:
            self.default_ttl = default_ttl
        self.default_domain = Domain.objects.get_default_domain()
        self.serial = serial
        self.internal_domains = internal_domains
        if self.internal_domains is None:
            self.internal_domains = []
        self._dynamic_updates = dynamic_updates
        if self._dynamic_updates is None:
            self._dynamic_updates = []
        self.force_config_write = force_config_write  # some data changed that nsupdate cannot update if true

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
        domains,
        serial,
        ns_host_name,
        mappings,
        rrset_mappings,
        default_ttl,
        internal_domains,
        dynamic_updates,
        force_config_write,
    ):
        """Generator of forward zones, collated by domain name."""
        dns_ip_list = get_dns_server_addresses(filter_allowed_dns=False)
        domains = set(domains)

        # For each of the domains that we are generating, create the zone from:
        # 1. Node: ip mapping(domain) (which includes dnsresource addresses).
        # 2. Dnsresource non-address records in this domain.
        # 3. For the default domain all forward look ups for the managed and
        #    unmanaged dynamic ranges.
        for domain in domains:
            zone_ttl = default_ttl if domain.ttl is None else domain.ttl
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
            domain.add_delegations(
                other_mapping, ns_host_name, dns_ip_list, default_ttl
            )

            # 3. All of the special handling for the default domain.
            dynamic_ranges = []
            if domain.is_default():
                # 3a. All forward entries for the managed and unmanaged dynamic
                # ranges go into the default domain.
                subnets = Subnet.objects.all().prefetch_related("iprange_set")
                for subnet in subnets:
                    # We loop through the whole set so the prefetch above works
                    # in one query.
                    for ip_range in subnet.iprange_set.all():
                        if ip_range.type == IPRANGE_TYPE.DYNAMIC:
                            dynamic_ranges.append(ip_range.get_MAASIPRange())
                # 3b. Add A/AAAA RRset for @.  If glue is needed for any other
                # domain, adding the glue is the responsibility of the admin.
                ttl = domain.get_base_ttl("A", default_ttl)
                for dns_ip in dns_ip_list:
                    if dns_ip.version == 4:
                        other_mapping["@"].rrset.add(
                            (ttl, "A", dns_ip.format())
                        )
                    else:
                        other_mapping["@"].rrset.add(
                            (ttl, "AAAA", dns_ip.format())
                        )

            domain_updates = [
                update
                for update in dynamic_updates
                if update.zone == domain.name
            ]

            yield DNSForwardZoneConfig(
                domain.name,
                serial=serial,
                default_ttl=zone_ttl,
                ns_ttl=domain.get_base_ttl("NS", default_ttl),
                ipv4_ttl=domain.get_base_ttl("A", default_ttl),
                ipv6_ttl=domain.get_base_ttl("AAAA", default_ttl),
                mapping=mapping,
                ns_host_name=ns_host_name,
                other_mapping=other_mapping,
                dynamic_ranges=dynamic_ranges,
                dynamic_updates=domain_updates,
                force_config_write=force_config_write,
            )

        # Create the forward zone config for the internal domains.
        for internal_domain in internal_domains:
            # Use other_mapping to create the domain resources.
            other_mapping = defaultdict(HostnameRRsetMapping)
            for resource in internal_domain.resources:
                resource_mapping = other_mapping[resource.name]
                for record in resource.records:
                    resource_mapping.rrset.add(
                        (internal_domain.ttl, record.rrtype, record.rrdata)
                    )

            domain_updates = [
                update
                for update in dynamic_updates
                if update.zone == internal_domain.name
            ]

            yield DNSForwardZoneConfig(
                internal_domain.name,
                serial=serial,
                default_ttl=internal_domain.ttl,
                ns_ttl=internal_domain.ttl,
                ipv4_ttl=internal_domain.ttl,
                ipv6_ttl=internal_domain.ttl,
                mapping={},
                ns_host_name=ns_host_name,
                other_mapping=other_mapping,
                dynamic_ranges=[],
                dynamic_updates=domain_updates,
                force_config_write=force_config_write,
            )

    @staticmethod
    def _gen_reverse_zones(
        subnets,
        serial,
        ns_host_name,
        mappings,
        default_ttl,
        dynamic_updates,
        force_config_write,
    ):
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
                        "%s/24" % IPNetwork("%s/24" % network.network).network
                    )
                    rfc2317_glue.setdefault(basenet, set()).add(network)
                elif network.version == 6 and network.prefixlen > 124:
                    basenet = IPNetwork(
                        "%s/124"
                        % IPNetwork("%s/124" % network.network).network
                    )
                    rfc2317_glue.setdefault(basenet, set()).add(network)

        # Since get_hostname_ip_mapping(Subnet) ignores Subnet.id, so we can
        # just do it once and be happy.  LP#1600259
        if len(subnets):
            mappings["reverse"] = mappings[Subnet.objects.first()]

        # For each of the zones that we are generating (one or more per
        # subnet), compile the zone from:
        # 1. Dynamic ranges on this subnet.
        # 2. Node: ip mapping(subnet), including DNSResource records for
        #    StaticIPAddresses in this subnet.
        # All of this needs to be done smallest to largest so that we can
        # correctly gather the rfc2317 glue that we need.  Failure to sort
        # means that we wind up grabbing (and deleting) the rfc2317 glue info
        # while processing the wrong network.
        for subnet in sorted(
            subnets,
            key=lambda subnet: IPNetwork(subnet.cidr).prefixlen,
            reverse=True,
        ):
            network = IPNetwork(subnet.cidr)
            if subnet.rdns_mode == RDNS_MODE.DISABLED:
                # If we are not doing reverse dns for this subnet, then just
                # skip to the next subnet.
                logger.debug(
                    "%s disabled subnet in DNS config list" % subnet.cidr
                )
                continue

            # 1. Figure out the dynamic ranges.
            dynamic_ranges = [
                ip_range.netaddr_iprange
                for ip_range in subnet.get_dynamic_ranges()
            ]

            # 2. Start with the map of all of the nodes, including all
            # DNSResource-associated addresses.  We will prune this to just
            # entries for the subnet when we actually generate the zonefile.
            # If we get here, then we have subnets, so we noticed that above
            # and created mappings['reverse'].  LP#1600259
            mapping = mappings["reverse"]

            # Use the default_domain as the name for the NS host in the reverse
            # zones.  If this network is actually a parent rfc2317 glue
            # network, then we need to generate the glue records.
            # We need to detect the need for glue in our networks that are
            # big.
            if (
                network.version == 6 and network.prefixlen < 124
            ) or network.prefixlen < 24:
                glue = set()
                # This is the reason for needing the subnets sorted in
                # increasing order of size.
                for net in rfc2317_glue.copy().keys():
                    if net in network:
                        glue.update(rfc2317_glue[net])
                        del rfc2317_glue[net]
            elif network in rfc2317_glue:
                glue = rfc2317_glue[network]
                del rfc2317_glue[network]
            else:
                glue = set()

            domain_updates = [
                DynamicDNSUpdate.as_reverse_record_update(
                    update, str(subnet.cidr)
                )
                for update in dynamic_updates
                if update.answer
                and update.answer_is_ip
                and (update.answer_as_ip in IPNetwork(subnet.cidr))
            ]

            yield DNSReverseZoneConfig(
                ns_host_name,
                serial=serial,
                default_ttl=default_ttl,
                ns_host_name=ns_host_name,
                mapping=mapping,
                network=IPNetwork(subnet.cidr),
                dynamic_ranges=dynamic_ranges,
                rfc2317_ranges=glue,
                exclude={
                    IPNetwork(s.cidr) for s in subnets if s is not subnet
                },
                dynamic_updates=domain_updates,
                force_config_write=force_config_write,
            )
        # Now provide any remaining rfc2317 glue networks.
        for network, ranges in rfc2317_glue.items():
            exclude_set = {
                IPNetwork(s.cidr)
                for s in subnets
                if network in IPNetwork(s.cidr)
            }
            domain_updates = []
            for update in dynamic_updates:
                glue_update = True
                for exclude_net in exclude_set:
                    if (
                        update.answer
                        and update.answer_is_ip
                        and update.answer_as_ip in exclude_net
                    ):
                        glue_update = False
                        break
                if (
                    glue_update
                    and update.answer
                    and update.answer_is_ip
                    and update.answer_as_ip in network
                ):
                    domain_updates.append(
                        DynamicDNSUpdate.as_reverse_record_update(
                            update, str(network)
                        )
                    )
            yield DNSReverseZoneConfig(
                ns_host_name,
                serial=serial,
                default_ttl=default_ttl,
                network=network,
                ns_host_name=ns_host_name,
                rfc2317_ranges=ranges,
                exclude=exclude_set,
                dynamic_updates=domain_updates,
                force_config_write=force_config_write,
            )

    def __iter__(self):
        """Iterate over zone configs.

        Yields `DNSForwardZoneConfig` and `DNSReverseZoneConfig` configs.
        """
        # For testing and such it's fine if we don't have a serial, but once
        # we get to this point, we really need one.
        assert not (self.serial is None), "No serial number specified."

        mappings = self._get_mappings()
        ns_host_name = self.default_domain.name
        rrset_mappings = self._get_rrset_mappings()
        serial = self.serial
        default_ttl = self.default_ttl
        return chain(
            self._gen_forward_zones(
                self.domains,
                serial,
                ns_host_name,
                mappings,
                rrset_mappings,
                default_ttl,
                self.internal_domains,
                self._dynamic_updates,
                self.force_config_write,
            ),
            self._gen_reverse_zones(
                self.subnets,
                serial,
                ns_host_name,
                mappings,
                default_ttl,
                self._dynamic_updates,
                self.force_config_write,
            ),
        )

    def as_list(self):
        """Return the zones as a list."""
        return list(self)


@attr.s
class InternalDomain:
    """Configuration for the internal domain."""

    # Name of the domain.
    name = attr.ib(converter=str)

    # TTL for the domain.
    ttl = attr.ib(converter=int)

    # Resources for this domain.
    resources = attr.ib(converter=list)


@attr.s
class InternalDomainResourse:
    """Resource inside the internal domain."""

    # Name of the resource.
    name = attr.ib(converter=str)

    # Records for this resource.
    records = attr.ib(converter=list)


@attr.s
class InternalDomainResourseRecord:
    """Record inside an internal domain resource."""

    # Type of the resource record.
    rrtype = attr.ib(converter=str)

    # Data inside resource record.
    rrdata = attr.ib(converter=str)
