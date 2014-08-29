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
    'add_zone',
    'change_dns_zones',
    'get_trusted_networks',
    'is_dns_enabled',
    'next_zone_serial',
    'write_full_dns_config',
    ]


from django.conf import settings
from maasserver.dns.zonegenerator import ZoneGenerator
from maasserver.enum import NODEGROUPINTERFACE_MANAGEMENT
from maasserver.models.config import Config
from maasserver.models.network import Network
from maasserver.models.nodegroup import NodeGroup
from maasserver.models.nodegroupinterface import NodeGroupInterface
from maasserver.sequence import (
    INT_MAX,
    Sequence,
    )
from provisioningserver import tasks
from provisioningserver.logger import get_maas_logger


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
        maaslog.info("Generating new DNS zone file for %s", zone.zone_name)
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
    zones_to_write = ZoneGenerator(
        nodegroup, serial_generator=next_zone_serial
        ).as_list()
    if len(zones_to_write) == 0:
        return None
    serial = next_zone_serial()
    # Compute non-None zones.
    zones = ZoneGenerator(NodeGroup.objects.all(), serial).as_list()
    reconfig_subtask = tasks.rndc_command.subtask(args=[['reconfig']])
    write_dns_config_subtask = tasks.write_dns_config.subtask(
        kwargs={
            'zones': zones, 'callback': reconfig_subtask,
            'trusted_networks': get_trusted_networks()})
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
    zones = ZoneGenerator(
        NodeGroup.objects.all(), serial_generator=next_zone_serial
        ).as_list()
    upstream_dns = Config.objects.get_config("upstream_dns")
    tasks.write_full_dns_config.delay(
        zones=zones,
        callback=tasks.rndc_command.subtask(
            args=[['reload'], reload_retry]),
        upstream_dns=upstream_dns,
        trusted_networks=get_trusted_networks())


def get_trusted_networks():
    """Return the CIDR representation of all the Networks we know about.

    This must be a whitespace separated list, where each item ends in a
    semicolon, or blank if there's no networks.
    """
    networks = " ".join(
        "%s;" % net.get_network().cidr
        for net in Network.objects.all())
    return networks
