# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""DNS management module."""


from collections import defaultdict

from django.conf import settings
from netaddr import IPAddress

from maasserver.dns.zonegenerator import (
    InternalDomain,
    InternalDomainResourse,
    InternalDomainResourseRecord,
    ZoneGenerator,
)
from maasserver.enum import IPADDRESS_TYPE, RDNS_MODE
from maasserver.models.config import Config
from maasserver.models.dnspublication import DNSPublication
from maasserver.models.domain import Domain
from maasserver.models.node import RackController
from maasserver.models.subnet import Subnet
from provisioningserver.dns.actions import (
    bind_reload,
    bind_reload_with_retries,
    bind_write_configuration,
    bind_write_options,
    bind_write_zones,
)
from provisioningserver.logger import get_maas_logger

maaslog = get_maas_logger("dns")


def current_zone_serial():
    return "%0.10d" % DNSPublication.objects.get_most_recent().serial


def is_dns_enabled():
    """Is MAAS configured to manage DNS?"""
    return settings.DNS_CONNECT


def dns_force_reload():
    """Force the DNS to be regenerated."""
    DNSPublication(source="Force reload").save()


def forward_domains_to_forwarded_zones(forward_domains):
    # converted to a list of tuple to keep model within maasserver code
    return [
        (
            domain.name,
            [
                fwd_dns_srvr.ip_address
                for fwd_dns_srvr in domain.forward_dns_servers
            ],
        )
        for domain in forward_domains
    ]


def dns_update_all_zones(reload_retry=False, reload_timeout=2):
    """Update all zone files for all domains.

    Serving these zone files means updating BIND's configuration to include
    them, then asking it to load the new configuration.

    :param reload_retry: Should the DNS server reload be retried in case
        of failure? Defaults to `False`.
    :type reload_retry: bool
    """
    if not is_dns_enabled():
        return

    domains = Domain.objects.filter(authoritative=True)
    forwarded_zones = forward_domains_to_forwarded_zones(
        Domain.objects.get_forward_domains()
    )
    subnets = Subnet.objects.exclude(rdns_mode=RDNS_MODE.DISABLED)
    default_ttl = Config.objects.get_config("default_dns_ttl")
    serial = current_zone_serial()
    zones = ZoneGenerator(
        domains,
        subnets,
        default_ttl,
        serial,
        internal_domains=[get_internal_domain()],
    ).as_list()
    bind_write_zones(zones)

    # We should not be calling bind_write_options() here; call-sites should be
    # making a separate call. It's a historical legacy, where many sites now
    # expect this side-effect from calling dns_update_all_zones_now(), and
    # some that call it for this side-effect alone. At present all it does is
    # set the upstream DNS servers, nothing to do with serving zones at all!
    bind_write_options(
        upstream_dns=get_upstream_dns(),
        dnssec_validation=get_dnssec_validation(),
    )

    # Nor should we be rewriting ACLs that are related only to allowing
    # recursive queries to the upstream DNS servers. Again, this is legacy,
    # where the "trusted" ACL ended up in the same configuration file as the
    # zone stanzas, and so both need to be rewritten at the same time.
    bind_write_configuration(
        zones,
        trusted_networks=get_trusted_networks(),
        forwarded_zones=forwarded_zones,
    )

    # Reloading with retries may be a legacy from Celery days, or it may be
    # necessary to recover from races during start-up. We're not sure if it is
    # actually needed but it seems safer to maintain this behaviour until we
    # have a better understanding.
    if reload_retry:
        reloaded = bind_reload_with_retries(timeout=reload_timeout)
    else:
        reloaded = bind_reload(timeout=reload_timeout)

    # Return the current serial and list of domain names.
    return serial, reloaded, [domain.name for domain in domains]


def get_upstream_dns():
    """Return the IP addresses of configured upstream DNS servers.

    :return: A list of IP addresses.
    """
    upstream_dns = Config.objects.get_config("upstream_dns")
    return [] if upstream_dns is None else upstream_dns.split()


def get_dnssec_validation():
    """Return the configuration option for DNSSEC validation.

    :return: "on", "off", or "auto"
    """
    return Config.objects.get_config("dnssec_validation")


def get_trusted_acls():
    """Return the configuration option for trusted ACLs.

    :return: A list of CIDR-format subnet, IPs or names.
    """
    items = Config.objects.get_config("dns_trusted_acl")
    return [] if items is None else items.split()


def get_trusted_networks():
    """Return the CIDR representation of all the subnets we know about
    combined with the list from get_trusted_acls().

    :return: A list of CIDR-format subnet specifications.
    """
    known_subnets = [
        str(subnet.cidr) for subnet in Subnet.objects.filter(allow_dns=True)
    ]
    return list(set(known_subnets + get_trusted_acls()))


def get_resource_name_for_subnet(subnet):
    """Convert the subnet CIDR to the resource name."""
    return subnet.cidr.replace("/", "--").replace(":", "-").replace(".", "-")


def _get_controller_ips_by_resource_name(controller):
    ips_by_resource = defaultdict(set)
    for interface in controller.interface_set.all():
        found_static = False
        # Order by alloc_type here because DHCP and DISCOVERED IP addresses
        # are last in the numeric ordering.
        for ip_address in interface.ip_addresses.all().order_by("alloc_type"):
            is_dhcp = False
            if ip_address.alloc_type in (
                IPADDRESS_TYPE.AUTO,
                IPADDRESS_TYPE.STICKY,
                IPADDRESS_TYPE.USER_RESERVED,
            ):
                # If we find a static IP address, take note of that fact,
                # because that means we'll want to skip adding a DHCP IP
                # address here if we find one on the same interface. DHCP
                # IPs should only be used as a last resort, because errant
                # leases (for example, from a temporarily duplicated MAC)
                # can leak into DNS otherwise.
                found_static = True
            else:
                is_dhcp = True
            if ip_address.ip:
                if not is_dhcp or (not found_static and is_dhcp):
                    resource_name = get_resource_name_for_subnet(
                        ip_address.subnet
                    )
                    ips_by_resource[resource_name].add(ip_address.ip)
    return ips_by_resource


def _get_ips_by_resource_name(controllers):
    # Group the IP addresses on controllers by the connected subnets.
    ips_by_resource = defaultdict(set)
    for controller in controllers:
        controller_ips = _get_controller_ips_by_resource_name(controller)
        for resource, ips in controller_ips.items():
            ips_by_resource[resource].update(ips)
    return ips_by_resource


def get_internal_domain():
    """Calculate the zone description for the internal domain.

    This constructs the zone with a resource per subnet that is connected to
    rack controllers. Each resource gets A and AAAA records for the rack
    controllers that have a connection to that subnet.

    Note: Rack controllers that have no registered RPC connections are not
    included in the calculation. Those rack controllers are dead and no traffic
    should be directed to them.
    """
    # `connections__isnull` verifies that only rack controllers with atleast
    # one connection are used in the calculation.
    controllers = RackController.objects.filter(connections__isnull=False)
    controllers = controllers.prefetch_related(
        "interface_set__ip_addresses__subnet"
    )

    ips_by_resource = _get_ips_by_resource_name(controllers)

    # Map the subnet IP address to the model required for zone generation.
    resources = []
    for resource_name, ip_addresses in ips_by_resource.items():
        records = []
        for ip_address in ip_addresses:
            if IPAddress(ip_address).version == 4:
                records.append(
                    InternalDomainResourseRecord(rrtype="A", rrdata=ip_address)
                )
            else:
                records.append(
                    InternalDomainResourseRecord(
                        rrtype="AAAA", rrdata=ip_address
                    )
                )
        resources.append(
            InternalDomainResourse(name=resource_name, records=records)
        )

    return InternalDomain(
        name=Config.objects.get_config("maas_internal_domain"),
        ttl=15,
        resources=resources,
    )
