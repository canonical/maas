# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""DNS management module."""

__all__ = [
    'dns_add_domains',
    'dns_add_subnets',
    'dns_update_all_zones',
    'dns_update_by_node',
    'dns_update_domains',
    'dns_update_subnets',
    ]

from itertools import chain
import threading

from django.conf import settings
from maasserver import locks
from maasserver.dns.zonegenerator import (
    sequence,
    ZoneGenerator,
)
from maasserver.enum import RDNS_MODE
from maasserver.models.config import Config
from maasserver.models.domain import Domain
from maasserver.models.subnet import Subnet
from maasserver.sequence import (
    INT_MAX,
    Sequence,
)
from maasserver.utils import synchronised
from maasserver.utils.orm import (
    post_commit,
    transactional,
    with_connection,
)
from maasserver.utils.threads import callOutToDatabase
from provisioningserver.dns.actions import (
    bind_reconfigure,
    bind_reload,
    bind_reload_with_retries,
    bind_reload_zones,
    bind_write_configuration,
    bind_write_options,
    bind_write_zones,
)
from provisioningserver.logger import get_maas_logger
from provisioningserver.utils.twisted import callOut


maaslog = get_maas_logger("dns")


# A DNS zone's serial is a 32-bit integer.  Also, we start with the
# value 1 because 0 has special meaning for some DNS servers.  Even if
# we control the DNS server we use, better safe than sorry.
zone_serial = Sequence(
    'maasserver_zone_serial_seq', increment=1, minvalue=1, maxvalue=INT_MAX)


def next_zone_serial():
    return '%0.10d' % next(zone_serial)


def is_dns_enabled():
    """Is MAAS configured to manage DNS?"""
    return settings.DNS_CONNECT


# Whether to defer DNS changes to a post-commit hook or not. In normal use we
# want to defer all DNS changes until after a commit, but for testing it can
# be useful to have immediate feedback.
DNS_DEFER_UPDATES = True


def dns_add_zones_now(domains, subnets):
    """Add zone files for the given domain(s) and subnet(s), and serve them.

    Serving these new zone files means updating BIND's configuration to
    include them, then asking it to load the new configuration.

    :param domains: The domain(s) for which zones should be served.
    :type domains: :py:class:`Domain`, or an iterable thereof.
    :param subnets: The subnet(s) for which zones should be served.
    :type subnets: :py:class:`Subnet`, or an iterable thereof.
    """
    if not is_dns_enabled():
        return

    default_ttl = Config.objects.get_config('default_dns_ttl')
    serial = next_zone_serial()
    zones_to_write = ZoneGenerator(
        domains, subnets, default_ttl,
        serial).as_list()
    if len(zones_to_write) == 0:
        return None
    # Compute non-None zones.
    zones = ZoneGenerator(
        Domain.objects.all(), Subnet.objects.all(),
        default_ttl, serial).as_list()
    bind_write_zones(zones_to_write)
    bind_write_configuration(zones, trusted_networks=get_trusted_networks())
    bind_reconfigure()


def dns_add_subnets(subnets):
    """Arrange for `dns_add_zones_now` to be called post-commit.

    :return: The post-commit `Deferred`.
    """
    if is_dns_enabled():
        subnets = [
            net
            for net in subnets
            if net.rdns_mode != RDNS_MODE.DISABLED]
        if DNS_DEFER_UPDATES:
            return consolidator.add_subnets(subnets)
        else:
            return dns_add_zones_now([], subnets)
    else:
        return None


def dns_add_domains(domains):
    """Arrange for `dns_add_zones_now` to be called post-commit.

    :return: The post-commit `Deferred`.
    """
    if is_dns_enabled():
        auth_domains = [dom for dom in domains if dom.authoritative is True]
        if DNS_DEFER_UPDATES:
            return consolidator.add_domains(auth_domains)
        else:
            return dns_add_zones_now(auth_domains, [])
    else:
        return None


def dns_update_zones_now(domains, subnets):
    """Update the zone files for the given subnet(s).

    Once the new zone files have been written, BIND is asked to reload them.
    It's assumed that BIND already serves the zones that are being written.

    :param subnets: Those subnet(s) for which the zone should be updated.
    :type subnets: A :py:class:`Domain`, or an iterable thereof.
    """
    if not is_dns_enabled():
        return

    serial = next_zone_serial()
    bind_reconfigure()
    default_ttl = Config.objects.get_config('default_dns_ttl')
    for zone in ZoneGenerator(domains, subnets, default_ttl, serial):
        names = [zi.zone_name for zi in zone.zone_info]
        maaslog.info("Generating new DNS zone file for %s", " ".join(names))
        bind_write_zones([zone])
        bind_reload_zones(names)


def dns_update_subnets(subnets):
    """Arrange for `dns_update_zones_now` to be called post-commit.

    :return: The post-commit `Deferred`.
    """
    if is_dns_enabled():
        subnets = [
            net
            for net in subnets
            if net.rdns_mode != RDNS_MODE.DISABLED]
        if DNS_DEFER_UPDATES:
            return consolidator.update_subnets(subnets)
        else:
            return dns_update_zones_now([], subnets)
    else:
        return None


def dns_update_domains(domains):
    """Arrange for `dns_update_zones_now` to be called post-commit.

    :return: The post-commit `Deferred`.
    """
    if is_dns_enabled():
        auth_domains = [dom for dom in domains if dom.authoritative is True]
        if DNS_DEFER_UPDATES:
            return consolidator.update_domains(auth_domains)
        else:
            return dns_update_zones_now(auth_domains, [])
    else:
        return None


def dns_update_by_node(node):
    """Arrange for `dns_update_zones_now` to be called post-commit.

    :return: The post-commit `Deferred`.
    """
    if is_dns_enabled():
        auth_domains = []
        if node.domain.authoritative is True:
            auth_domains.append(node.domain)
        # What subnets may be affected by this node being updated?
        subnets = Subnet.objects.filter(
            staticipaddress__interface__node=node).exclude(
            rdns_mode=RDNS_MODE.DISABLED)
        if DNS_DEFER_UPDATES:
            return consolidator.update_zones(auth_domains, subnets)
        else:
            return dns_update_zones_now(auth_domains, subnets)
    else:
        return None


def dns_update_all_zones_now(reload_retry=False, force=False):
    """Update all zone files for all domains.

    Serving these zone files means updating BIND's configuration to include
    them, then asking it to load the new configuration.

    :param reload_retry: Should the DNS server reload be retried in case
        of failure? Defaults to `False`.
    :type reload_retry: bool
    :param force: Update the configuration even if no interface is configured
        to manage DNS. This makes sense when deconfiguring an interface.
    :type force: bool
    """
    if not is_dns_enabled():
        return

    domains = Domain.objects.filter(authoritative=True)
    subnets = Subnet.objects.exclude(rdns_mode=RDNS_MODE.DISABLED)
    default_ttl = Config.objects.get_config('default_dns_ttl')
    serial = next_zone_serial()
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


def dns_update_all_zones(reload_retry=False, force=False):
    """Arrange for `dns_update_all_zones_now` to be called post-commit.

    :return: The post-commit `Deferred`.
    """
    if is_dns_enabled():
        if DNS_DEFER_UPDATES:
            return consolidator.update_all_zones(
                reload_retry=reload_retry, force=force)
        else:
            return dns_update_all_zones_now(
                reload_retry=reload_retry, force=force)
    else:
        return None


def flatten(things):
    return chain.from_iterable(map(sequence, things))


class Changes:
    """A record of pending DNS changes, and the means to apply them."""

    # FIXME: This has elements in common with the Changes class in
    # maasserver.dhcp. Consider extracting the common parts into a shared
    # superclass.

    def __init__(self):
        super(Changes, self).__init__()
        self.reset()

    def reset(self):
        self.hook = None
        self.domains_to_add = []
        self.domains_to_update = []
        self.subnets_to_add = []
        self.subnets_to_update = []
        self.update_all_zones = False
        self.update_all_zones_reload_retry = False
        self.update_all_zones_force = False

    def activate(self):
        """Arrange for a post-commit hook to be called.

        The hook will apply any pending changes and reset this object to a
        pristine state.

        Can be called multiple times; only one hook will be added.
        """
        if self.hook is None:
            self.hook = post_commit()
            self.hook.addCallback(callOutToDatabase, self.apply)
            self.hook.addBoth(callOut, self.reset)
        return self.hook

    @with_connection  # Needed by the following lock.
    @synchronised(locks.dns)  # Lock before beginning transaction.
    @transactional
    def apply(self):
        """Apply all requested changes.

        A request to update all zones will do just that, and ignore any zones
        individually requested for adding or updating, because both those
        things will happen as part of the process.

        Assuming that's not the case, requests to *add* specific subnets and/or
        domains will be acted on next, followed by requests to *update*
        specific domains and/or subnets. If there's a request to add and update
        a domain or subnet, only the add will be done because the update will
        be a wasteful no-op.
        """
        if self.update_all_zones:
            # We've been asked to do the full-monty; just do it and get out.
            dns_update_all_zones_now(
                reload_retry=self.update_all_zones_reload_retry,
                force=self.update_all_zones_force)
        else:
            # Call `dns_add_zones_now` for each subnet/domain to add. We
            # consolidate changes into a dict, keyed by ID because Django's ORM
            # does not guarantee the same instance for the same database row.
            domains_to_add = {
                domain.id: domain
                for domain in flatten(self.domains_to_add)
            }
            subnets_to_add = {
                subnet.id: subnet
                for subnet in flatten(self.subnets_to_add)
            }
            if len(domains_to_add) > 0 or len(subnets_to_add) > 0:
                dns_add_zones_now(
                    list(domains_to_add.values()),
                    list(subnets_to_add.values()))

            # Call `dns_update_zones_now` for each subnet/domain to update,
            # *excluding* those we've only just added; there's no point doing
            # them again.  We consolidate changes into a dict for the same
            # reason as above.
            domains_to_update = {
                domain.id: domain
                for domain in flatten(self.domains_to_update)
                if domain.id not in domains_to_add
            }
            subnets_to_update = {
                subnet.id: subnet
                for subnet in flatten(self.subnets_to_update)
                if subnet.id not in subnets_to_add
            }
            if len(domains_to_update) > 0 or len(subnets_to_update) > 0:
                dns_update_zones_now(
                    list(domains_to_update.values()),
                    list(subnets_to_update.values()))


class ChangeConsolidator(threading.local):
    """A singleton used to consolidate DNS changes.

    Maintains a thread-local `Changes` instance into which changes are
    written. Requesting any change within a transaction automatically arranges
    a post-commit call to apply those changes, after consolidation.
    """

    # FIXME: This has elements in common with the ChangeConsolidator class in
    # maasserver.dhcp. Consider extracting the common parts into a shared
    # superclass.

    def __init__(self):
        super(ChangeConsolidator, self).__init__()
        self.changes = Changes()

    def add_domains(self, domains):
        """Request that zones for `domains` be added."""
        if isinstance(domains, Domain):
            self.changes.domains_to_add.append(domains)
        elif domains is not None:
            self.changes.domains_to_add += domains
        return self.changes.activate()

    def update_zones(self, domains, subnets):
        if isinstance(domains, Domain):
            self.changes.domains_to_update.append(domains)
        else:
            self.changes.domains_to_update += domains
        if isinstance(subnets, Subnet):
            self.changes.subnets_to_update.append(subnets)
        else:
            self.changes.subnets_to_update += subnets
        return self.changes.activate()

    def update_domains(self, domains):
        """Request that zones for `domains` be updated."""
        if isinstance(domains, Domain):
            self.changes.domains_to_update.append(domains)
        else:
            self.changes.domains_to_update += domains
        return self.changes.activate()

    def add_subnets(self, subnets):
        """Request that zones for `subnets` be added."""
        if isinstance(subnets, Subnet):
            self.changes.subnets_to_add.append(subnets)
        elif subnets is not None:
            self.changes.subnets_to_add += subnets
        return self.changes.activate()

    def update_subnets(self, subnets):
        """Request that zones for `subnets` be updated."""
        if isinstance(subnets, Subnet):
            self.changes.subnets_to_update.append(subnets)
        else:
            self.changes.subnets_to_update += subnets
        return self.changes.activate()

    def update_all_zones(self, reload_retry=False, force=False):
        """Request that zones for all domains be updated."""
        self.changes.update_all_zones = True
        self.changes.update_all_zones_reload_retry |= reload_retry
        self.changes.update_all_zones_force |= force
        return self.changes.activate()


# Singleton, for internal use only.
consolidator = ChangeConsolidator()


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
