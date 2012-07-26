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
    'change_dns_zones',
    'next_zone_serial',
    'write_full_dns_config',
    ]


import collections

from django.conf import settings
from django.db.models.signals import (
    post_delete,
    post_save,
    )
from django.dispatch import receiver
from maasserver.models import (
    DHCPLease,
    Node,
    NodeGroup,
    )
from maasserver.models.dhcplease import post_updates
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


def is_dns_enabled():
    return settings.DNS_CONNECT


@receiver(post_save, sender=NodeGroup)
def dns_post_save_NodeGroup(sender, instance, created, **kwargs):
    """Create or update DNS zones related to the new nodegroup."""
    if is_dns_enabled():
        if created:
            add_zone(instance)
        else:
            write_full_dns_config()


@receiver(post_delete, sender=NodeGroup)
def dns_post_delete_NodeGroup(sender, instance, **kwargs):
    """Delete DNS zones related to the nodegroup."""
    if is_dns_enabled():
        write_full_dns_config()


@receiver(post_updates, sender=DHCPLease.objects)
def dns_updated_DHCPLeaseManager(sender, **kwargs):
    """Update all the zone files."""
    if is_dns_enabled():
        change_dns_zones(NodeGroup.objects.all())


@receiver(post_delete, sender=Node)
def dns_post_delete_Node(sender, instance, **kwargs):
    """Update the Node's zone file."""
    if is_dns_enabled():
        change_dns_zones(instance.nodegroup)


def get_zone(nodegroup, serial=None):
    """Create a :class:`DNSZoneConfig` object from a nodegroup.

    This method also accepts a serial to reuse the same serial when
    we are creating DNSZoneConfig objects in bulk.
    """
    if serial is None:
        serial = next_zone_serial()
    return DNSZoneConfig(
        zone_name=nodegroup.name, serial=serial,
        subnet_mask=nodegroup.subnet_mask, broadcast_ip=nodegroup.broadcast_ip,
        ip_range_low=nodegroup.ip_range_low,
        ip_range_high=nodegroup.ip_range_high,
        mapping=DHCPLease.objects.get_hostname_ip_mapping(nodegroup))


def change_dns_zones(nodegroups):
    """Update the zone configuration for the given list of Nodegroups.

    :param nodegroups: The list of nodegroups (or the nodegroup) for which the
        zone should be updated.
    :type nodegroups: list (or :class:`NodeGroup`)
    """
    if not isinstance(nodegroups, collections.Iterable):
        nodegroups = [nodegroups]
    serial = next_zone_serial()
    for nodegroup in nodegroups:
        zone = get_zone(nodegroup, serial)
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
