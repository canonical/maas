# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""DNS management module."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    'add_zone',
    'change_dns_zone',
    'next_zone_serial',
    'write_full_dns_config',
    ]


from maasserver.models import (
    DHCPLease,
    NodeGroup,
    )
from maasserver.sequence import (
    INT_MAX,
    Sequence,
    )
from provisioningserver import tasks
from provisioningserver.dns.config import DNSZoneConfig

# A DNS zone's serial is a 32-bit integer.  Also, we start with the
# value 1 because 0 has special meaning for some DNS servers.  Even if
# we control the DNS server we use, better safe than sorry.
zone_serial = Sequence(
    'maasserver_zone_serial_seq', incr=1, minvalue=1, maxvalue=INT_MAX)


def next_zone_serial():
    return '%0.10d' % zone_serial.nextval()


def get_zone(nodegroup, serial=None):
    """Create a :class:`DNSZoneConfig` object from a nodegroup.

    This method also accepts a serial to reuse the same serial when
    we are creating DNSZoneConfig objects in bulk.
    """
    if serial is None:
        serial = next_zone_serial()
    return DNSZoneConfig(
        zone_name=nodegroup.name, serial=serial,
        mapping=DHCPLease.objects.get_hostname_ip_mapping(nodegroup),
        bcast=nodegroup.broadcast_ip, mask=nodegroup.subnet_mask)


def change_dns_zone(nodegroup):
    """Update the zone configurtion for the given `nodegroup`.

    :param nodegroup: The nodegroup for which the zone should be cupdated.
    :type nodegroup: :class:`NodeGroup`
    """
    zone = get_zone(nodegroup)
    reverse_zone_reload_subtask = tasks.rndc_command.subtask(
        args=[['reload', zone.reverse_zone_name]])
    zone_reload_subtask = tasks.rndc_command.subtask(
        args=[['reload', zone.zone_name]],
        callback=reverse_zone_reload_subtask)
    tasks.write_dns_zone_config.delay(
        zone=zone, callback=zone_reload_subtask)


def add_zone(nodegroup):
    """Add to the DNS server a new zone for the given `nodegroup`.

    To do this we have to write a new configuration file for the zone
    and update the master config to include this new configuration.
    These are done in turn by chaining Celery subtasks.

    :param nodegroup: The nodegroup for which the zone should be added.
    :type nodegroup: :class:`NodeGroup`
    """
    serial = next_zone_serial()
    zones = [
        get_zone(nodegroup, serial)
        for nodegroup in NodeGroup.objects.all()]
    reconfig_subtask = tasks.rndc_command.subtask(args=[['reconfig']])
    write_dns_config_subtask = tasks.write_dns_config.subtask(
        zones=zones, callback=reconfig_subtask)
    zone = get_zone(nodegroup)
    tasks.write_dns_zone_config.delay(
        zone=zone, callback=write_dns_config_subtask)


def write_full_dns_config():
    """Write the DNS configuration for all the nodegroups."""
    serial = next_zone_serial()
    zones = [
        get_zone(nodegroup, serial)
        for nodegroup in NodeGroup.objects.all()]
    tasks.write_full_dns_config.delay(
        zones=zones,
        callback=tasks.rndc_command.subtask(args=[['reload']]))
