# Copyright 2012-2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""DNS management module."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'dns_add_zones',
    'dns_add_zones_now',
    'dns_update_all_zones',
    'dns_update_all_zones_now',
    'dns_update_zones',
    'dns_update_zones_now',
    ]

from itertools import (
    chain,
    imap,
)
import threading

from django.conf import settings
from maasserver import locks
from maasserver.dns.zonegenerator import (
    sequence,
    ZoneGenerator,
)
from maasserver.enum import NODEGROUPINTERFACE_MANAGEMENT
from maasserver.models.config import Config
from maasserver.models.network import Network
from maasserver.models.nodegroup import NodeGroup
from maasserver.models.nodegroupinterface import NodeGroupInterface
from maasserver.sequence import (
    INT_MAX,
    Sequence,
)
from maasserver.utils import synchronised
from maasserver.utils.orm import (
    post_commit,
    transactional,
)
from provisioningserver.dns.actions import (
    bind_reconfigure,
    bind_reload,
    bind_reload_with_retries,
    bind_reload_zone,
    bind_write_configuration,
    bind_write_options,
    bind_write_zones,
)
from provisioningserver.logger import get_maas_logger
from provisioningserver.utils.twisted import (
    callOut,
    callOutToThread,
)


maaslog = get_maas_logger("dns")


# A DNS zone's serial is a 32-bit integer.  Also, we start with the
# value 1 because 0 has special meaning for some DNS servers.  Even if
# we control the DNS server we use, better safe than sorry.
zone_serial = Sequence(
    'maasserver_zone_serial_seq', incr=1, minvalue=1, maxvalue=INT_MAX)


def next_zone_serial():
    return '%0.10d' % zone_serial.nextval()


def is_dns_in_use():
    """Is there at least one interface configured to manage DNS?"""
    interfaces_with_dns = (
        NodeGroupInterface.objects.filter(
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS))
    return interfaces_with_dns.exists()


def is_dns_enabled():
    """Is MAAS configured to manage DNS?"""
    return settings.DNS_CONNECT


# Whether to defer DNS changes to a post-commit hook or not. In normal use we
# want to defer all DNS changes until after a commit, but for testing it can
# be useful to have immediate feedback.
DNS_DEFER_UPDATES = True


@synchronised(locks.dns)
def dns_add_zones_now(clusters):
    """Add zone files for the given cluster(s), and serve them.

    Serving these new zone files means updating BIND's configuration to
    include them, then asking it to load the new configuration.

    :param clusters: The clusters(s) for which zones should be served.
    :type clusters: :py:class:`NodeGroup`, or an iterable thereof.
    """
    if not (is_dns_enabled() and is_dns_in_use()):
        return

    zones_to_write = ZoneGenerator(
        clusters, serial_generator=next_zone_serial).as_list()
    if len(zones_to_write) == 0:
        return None
    serial = next_zone_serial()
    # Compute non-None zones.
    zones = ZoneGenerator(NodeGroup.objects.all(), serial).as_list()
    bind_write_zones(zones_to_write)
    bind_write_configuration(zones, trusted_networks=get_trusted_networks())
    bind_reconfigure()


def dns_add_zones(clusters):
    """Arrange for `dns_add_zones_now` to be called post-commit.

    :return: The post-commit `Deferred`.
    """
    if is_dns_enabled():
        if DNS_DEFER_UPDATES:
            return consolidator.add_zones(clusters)
        else:
            return dns_add_zones_now(clusters)
    else:
        return None


@synchronised(locks.dns)
def dns_update_zones_now(clusters):
    """Update the zone files for the given cluster(s).

    Once the new zone files have been written, BIND is asked to reload them.
    It's assumed that BIND already serves the zones that are being written.

    :param clusters: Those cluster(s) for which the zone should be updated.
    :type clusters: A :py:class:`NodeGroup`, or an iterable thereof.
    """
    if not (is_dns_enabled() and is_dns_in_use()):
        return

    serial = next_zone_serial()
    for zone in ZoneGenerator(clusters, serial):
        maaslog.info("Generating new DNS zone file for %s", zone.zone_name)
        bind_write_zones([zone])
        bind_reload_zone(zone.zone_name)


def dns_update_zones(clusters):
    """Arrange for `dns_update_zones_now` to be called post-commit.

    :return: The post-commit `Deferred`.
    """
    if is_dns_enabled():
        if DNS_DEFER_UPDATES:
            return consolidator.update_zones(clusters)
        else:
            return dns_update_zones_now(clusters)
    else:
        return None


@synchronised(locks.dns)
def dns_update_all_zones_now(reload_retry=False, force=False):
    """Update all zone files for all clusters.

    Serving these zone files means updating BIND's configuration to include
    them, then asking it to load the new configuration.

    :param reload_retry: Should the DNS server reload be retried in case
        of failure? Defaults to `False`.
    :type reload_retry: bool
    :param force: Update the configuration even if no interface is configured
        to manage DNS. This makes sense when deconfiguring an interface.
    :type force: bool
    """
    write_conf = is_dns_enabled() and (force or is_dns_in_use())
    if not write_conf:
        return

    clusters = NodeGroup.objects.all()
    zones = ZoneGenerator(
        clusters, serial_generator=next_zone_serial).as_list()
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
    return chain.from_iterable(imap(sequence, things))


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
        self.zones_to_add = []
        self.zones_to_update = []
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
            self.hook.addCallback(callOutToThread, self.apply)
            self.hook.addBoth(callOut, self.reset)
        return self.hook

    @transactional
    @synchronised(locks.dns)
    def apply(self):
        """Apply all requested changes.

        A request to update all zones will do just that, and ignore any zones
        individually requested for adding or updating, because both those
        things will happen as part of the process.

        Assuming that's not the case, requests to *add* specific zones will be
        acted on next, followed by requests to *update* specific zones. If
        there's a request to add and update a zone, only the add will be done
        because the update will be a wasteful no-op.
        """
        if self.update_all_zones:
            # We've been asked to do the full-monty; just do it and get out.
            dns_update_all_zones_now(
                reload_retry=self.update_all_zones_reload_retry,
                force=self.update_all_zones_force)
        else:
            # Call `dns_add_zones_now` for each zone to add. We consolidate
            # changes into a dict, keyed by ID because Django's ORM does not
            # guarantee the same instance for the same database row.
            zones_to_add = {
                cluster.id: cluster
                for cluster in flatten(self.zones_to_add)
            }
            if len(self.zones_to_add) != 0:
                dns_add_zones_now(zones_to_add.values())

            # Call `dns_update_zones_now` for each zone to update, *excluding*
            # those we've only just added; there's no point doing them again.
            # We consolidate changes into a dict for the same reason as above.
            zones_to_update = {
                cluster.id: cluster
                for cluster in flatten(self.zones_to_update)
                if cluster.id not in zones_to_add
            }
            if len(zones_to_update) != 0:
                dns_update_zones_now(zones_to_update.values())


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

    def add_zones(self, clusters):
        """Request that zones for `clusters` be added."""
        self.changes.zones_to_add.append(clusters)
        return self.changes.activate()

    def update_zones(self, clusters):
        """Request that zones for `clusters` be updated."""
        self.changes.zones_to_update.append(clusters)
        return self.changes.activate()

    def update_all_zones(self, reload_retry=False, force=False):
        """Request that zones for all clusters be updated."""
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
    """Return the CIDR representation of all the Networks we know about.

    :return: A list of CIDR-format network specifications.
    """
    return [
        unicode(net.get_network().cidr)
        for net in Network.objects.all()
    ]
