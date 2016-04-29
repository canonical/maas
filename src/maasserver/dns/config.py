# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""DNS management module."""

__all__ = [
    'dns_force_reload',
    'dns_update_all_zones',
    ]

from django.conf import settings
from maasserver.dns.zonegenerator import ZoneGenerator
from maasserver.enum import RDNS_MODE
from maasserver.models.config import Config
from maasserver.models.dnspublication import DNSPublication
from maasserver.models.domain import Domain
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
    return '%0.10d' % DNSPublication.objects.get_most_recent().serial


def is_dns_enabled():
    """Is MAAS configured to manage DNS?"""
    return settings.DNS_CONNECT


def dns_force_reload():
    """Force the DNS to be regenerated."""
    DNSPublication(source="Force reload").save()


def dns_update_all_zones(reload_retry=False):
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
    subnets = Subnet.objects.exclude(rdns_mode=RDNS_MODE.DISABLED)
    default_ttl = Config.objects.get_config('default_dns_ttl')
    serial = current_zone_serial()
    zones = ZoneGenerator(
        domains, subnets, default_ttl,
        serial).as_list()
    bind_write_zones(zones)

    # We should not be calling bind_write_options() here; call-sites should be
    # making a separate call. It's a historical legacy, where many sites now
    # expect this side-effect from calling dns_update_all_zones_now(), and
    # some that call it for this side-effect alone. At present all it does is
    # set the upstream DNS servers, nothing to do with serving zones at all!
    bind_write_options(
        upstream_dns=get_upstream_dns(),
        dnssec_validation=get_dnssec_validation())

    # Nor should we be rewriting ACLs that are related only to allowing
    # recursive queries to the upstream DNS servers. Again, this is legacy,
    # where the "trusted" ACL ended up in the same configuration file as the
    # zone stanzas, and so both need to be rewritten at the same time.
    bind_write_configuration(zones, trusted_networks=get_trusted_networks())

    # Reloading with retries may be a legacy from Celery days, or it may be
    # necessary to recover from races during start-up. We're not sure if it is
    # actually needed but it seems safer to maintain this behaviour until we
    # have a better understanding.
    if reload_retry:
        bind_reload_with_retries()
    else:
        bind_reload()


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


def get_trusted_networks():
    """Return the CIDR representation of all the Subnets we know about.

    :return: A list of CIDR-format subnet specifications.
    """
    return [
        str(subnet.cidr)
        for subnet in Subnet.objects.all()
    ]
