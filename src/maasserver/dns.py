# Copyright 2012 Canonical Ltd.  This software is licensed under the
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
    'add_zone',
    'change_dns_zones',
    'is_dns_enabled',
    'is_dns_managed',
    'next_zone_serial',
    'write_full_dns_config',
    ]


import collections
from itertools import (
    chain,
    groupby,
    )
import socket

from django.conf import settings
from maasserver import logger
from maasserver.enum import (
    NODEGROUP_STATUS,
    NODEGROUPINTERFACE_MANAGEMENT,
    )
from maasserver.exceptions import MAASException
from maasserver.models import (
    Config,
    DHCPLease,
    NodeGroup,
    NodeGroupInterface,
    )
from maasserver.sequence import (
    INT_MAX,
    Sequence,
    )
from maasserver.server_address import get_maas_facing_server_address
from netaddr import (
    IPAddress,
    IPNetwork,
    )
from provisioningserver import tasks
from provisioningserver.dns.config import (
    DNSForwardZoneConfig,
    DNSReverseZoneConfig,
    )

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


class DNSException(MAASException):
    """An error occured when setting up MAAS's DNS server."""


def is_dns_managed(nodegroup):
    """Does MAAS manage a DNS zone for this Nodegroup?"""
    interface = nodegroup.get_managed_interface()
    return (
        nodegroup.status == NODEGROUP_STATUS.ACCEPTED and
        interface is not None and
        interface.management == NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS)


WARNING_MESSAGE = (
    "The DNS server will use the address '%s',  which is inside the "
    "loopback network.  This may not be a problem if you're not using "
    "MAAS's DNS features or if you don't rely on this information.  "
    "Be sure to configure the DEFAULT_MAAS_URL setting in MAAS's "
    "/etc/maas/maas_local_settings.py.")


def warn_loopback(ip):
    """Warn if the given IP address is in the loopback network."""
    if IPAddress(ip) in IPNetwork('127.0.0.1/8'):
        logger.warn(WARNING_MESSAGE % ip)


def get_dns_server_address(nodegroup=None):
    """Return the DNS server's IP address.

    That address is derived from DEFAULT_MAAS_URL or nodegroup.maas_url.
    """
    try:
        ip = get_maas_facing_server_address(nodegroup)
    except socket.error as e:
        raise DNSException(
            "Unable to find MAAS server IP address: %s.  "
            "MAAS's DNS server requires this IP address for the NS records "
            "in its zone files.  Make sure that the DEFAULT_MAAS_URL setting "
            "has the correct hostname."
            % e.strerror)

    warn_loopback(ip)
    return ip


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


class ZoneGenerator:
    """Generate zones describing those relating to the given node groups."""

    def __init__(self, nodegroups, serial=None):
        """
        :param serial: A serial to reuse when creating zones in bulk.
        """
        self.nodegroups = sequence(nodegroups)
        self.serial = serial

    @staticmethod
    def _get_forward_nodegroups(nodegroups):
        """Return a set of all forward nodegroups.

        This is the set of all managed nodegroups with the same domain as the
        domain of any of the given nodegroups.
        """
        forward_domains = {nodegroup.name for nodegroup in nodegroups}
        forward_nodegroups = NodeGroup.objects.filter(name__in=forward_domains)
        return {
            nodegroup for nodegroup in forward_nodegroups
            if is_dns_managed(nodegroup)
            }

    @staticmethod
    def _get_reverse_nodegroups(nodegroups):
        """Return a set of all reverse nodegroups.

        This is the subset of the given nodegroups that are managed.
        """
        return {
            nodegroup for nodegroup in nodegroups
            if is_dns_managed(nodegroup)
            }

    @staticmethod
    def _get_mappings():
        """Return a lazily evaluated nodegroup:mapping dict."""
        return lazydict(DHCPLease.objects.get_hostname_ip_mapping)

    @staticmethod
    def _get_networks():
        """Return a lazily evaluated nodegroup:network dict."""
        return lazydict(lambda ng: ng.get_managed_interface().network)

    @staticmethod
    def _gen_forward_zones(nodegroups, serial, mappings, networks):
        """Generator of forward zones, collated by domain name."""
        get_domain = lambda nodegroup: nodegroup.name
        dns_ip = get_dns_server_address()
        forward_nodegroups = sorted(nodegroups, key=get_domain)
        for domain, nodegroups in groupby(forward_nodegroups, get_domain):
            nodegroups = list(nodegroups)
            # A forward zone encompassing all nodes in the same domain.
            yield DNSForwardZoneConfig(
                domain, serial=serial, dns_ip=dns_ip,
                mapping={
                    hostname: ip
                    for nodegroup in nodegroups
                    for hostname, ip in mappings[nodegroup].items()
                    },
                networks={
                    networks[nodegroup]
                    for nodegroup in nodegroups
                    },
                )

    @staticmethod
    def _gen_reverse_zones(nodegroups, serial, mappings, networks):
        """Generator of reverse zones, sorted by network."""
        get_domain = lambda nodegroup: nodegroup.name
        dns_ip = get_dns_server_address()
        reverse_nodegroups = sorted(nodegroups, key=networks.get)
        for nodegroup in reverse_nodegroups:
            yield DNSReverseZoneConfig(
                get_domain(nodegroup), serial=serial, dns_ip=dns_ip,
                mapping=mappings[nodegroup], network=networks[nodegroup])

    def __iter__(self):
        forward_nodegroups = self._get_forward_nodegroups(self.nodegroups)
        reverse_nodegroups = self._get_reverse_nodegroups(self.nodegroups)
        mappings = self._get_mappings()
        networks = self._get_networks()
        serial = self.serial or next_zone_serial()
        return chain(
            self._gen_forward_zones(
                forward_nodegroups, serial, mappings, networks),
            self._gen_reverse_zones(
                reverse_nodegroups, serial, mappings, networks),
            )

    def as_list(self):
        """Return the zones as a list."""
        return list(self)


def change_dns_zones(nodegroups):
    """Update the zone configuration for the given list of Nodegroups.

    :param nodegroups: The list of nodegroups (or the nodegroup) for which the
        zone should be updated.
    :type nodegroups: list (or :class:`NodeGroup`)
    """
    if not (is_dns_enabled() and is_dns_in_use()):
        return
    serial = next_zone_serial()
    for zone in ZoneGenerator(nodegroups, serial):
        zone_reload_subtask = tasks.rndc_command.subtask(
            args=[['reload', zone.zone_name]])
        tasks.write_dns_zone_config.delay(
            zones=[zone], callback=zone_reload_subtask)


def add_zone(nodegroup):
    """Add to the DNS server a new zone for the given `nodegroup`.

    To do this we have to write a new configuration file for the zone
    and update the master config to include this new configuration.
    These are done in turn by chaining Celery subtasks.

    :param nodegroup: The nodegroup for which the zone should be added.
    :type nodegroup: :class:`NodeGroup`
    """
    if not (is_dns_enabled() and is_dns_in_use()):
        return
    zones_to_write = ZoneGenerator(nodegroup).as_list()
    if len(zones_to_write) == 0:
        return None
    serial = next_zone_serial()
    # Compute non-None zones.
    zones = ZoneGenerator(NodeGroup.objects.all(), serial).as_list()
    reconfig_subtask = tasks.rndc_command.subtask(args=[['reconfig']])
    write_dns_config_subtask = tasks.write_dns_config.subtask(
        zones=zones, callback=reconfig_subtask)
    tasks.write_dns_zone_config.delay(
        zones=zones_to_write, callback=write_dns_config_subtask)


def write_full_dns_config(reload_retry=False, force=False):
    """Write the DNS configuration.

    :param reload_retry: Should the reload rndc command be retried in case
        of failure?  Defaults to `False`.
    :type reload_retry: bool
    :param force: Write the configuration even if no interface is
        configured to manage DNS.
    :type force: bool
    """
    write_conf = (
        is_dns_enabled() and (force or is_dns_in_use()))
    if not write_conf:
        return
    zones = ZoneGenerator(NodeGroup.objects.all()).as_list()
    upstream_dns = Config.objects.get_config("upstream_dns")
    tasks.write_full_dns_config.delay(
        zones=zones,
        callback=tasks.rndc_command.subtask(
            args=[['reload'], reload_retry]),
        upstream_dns=upstream_dns)
