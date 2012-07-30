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
import logging
import socket
from urlparse import urlparse

from django.conf import settings
from django.db.models.signals import (
    post_delete,
    post_save,
    )
from django.dispatch import receiver
from maasserver.exceptions import MAASException
from maasserver.models import (
    Config,
    DHCPLease,
    Node,
    NodeGroup,
    )
from maasserver.models.dhcplease import post_updates
from maasserver.sequence import (
    INT_MAX,
    Sequence,
    )
from netaddr import (
    IPAddress,
    IPNetwork,
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
    return settings.DNS_CONNECT and Config.objects.get_config('enable_dns')


class DNSException(MAASException):
    """An error occured when setting up MAAS' DNS server."""


def warn_loopback(ip):
    """Warn if the given IP address is in the loopback network."""
    if IPAddress(ip) in IPNetwork('127.0.0.1/8'):
        logging.getLogger('maas').warn(
            "The DNS server address used will be '%s'.  That address is "
            "in the loopback network.  This might not be a problem "
            "if you're not using MAAS' DNS features or if "
            "you don't rely on this information.  Be sure to set the "
            "setting DEFAULT_MAAS_URL." % ip)


def get_dns_server_address():
    """Return the DNS server's IP address.

    That address is derived from DEFAULT_MAAS_URL in order to get a sensible
    default and at the same time give a possibility to the user to change this.
    """
    host = urlparse(settings.DEFAULT_MAAS_URL).netloc.split(':')[0]

    # Try to resolve the hostname, if `host` is alread an IP address, it
    # will simpply be returned by `socket.gethostbyname`.
    try:
        ip = socket.gethostbyname(host)
        warn_loopback(ip)
        return ip
    except socket.error:
        pass

    # No suitable address has been found.
    raise DNSException(
        "Unable to find a suitable IP for the MAAS server.  Such an IP "
        "is required for MAAS' DNS features to work.  Make sure that the "
        "setting DEFAULT_MAAS_URL is defined properly.  The IP in "
        "DEFAULT_MAAS_URL is the one which will be used for the NS record "
        "in MAAS' zone files.")


def dns_config_changed(sender, config, created, **kwargs):
    """Signal callback called when the DNS config changed."""
    if is_dns_enabled():
        write_full_dns_config(active=config.value)


Config.objects.config_changed_connect('enable_dns', dns_config_changed)


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

    Return a :class:`DNSZoneConfig` if DHCP is enabled on the
    nodegroup or None if it is not the case.

    This method also accepts a serial to reuse the same serial when
    we are creating DNSZoneConfig objects in bulk.
    """
    if not nodegroup.is_dhcp_enabled():
        return None

    if serial is None:
        serial = next_zone_serial()
    dns_ip = get_dns_server_address()
    return DNSZoneConfig(
        zone_name=nodegroup.name, serial=serial, dns_ip=dns_ip,
        subnet_mask=nodegroup.subnet_mask,
        broadcast_ip=nodegroup.broadcast_ip,
        ip_range_low=nodegroup.ip_range_low,
        ip_range_high=nodegroup.ip_range_high,
        mapping=DHCPLease.objects.get_hostname_ip_mapping(nodegroup))


def get_zones(nodegroups, serial):
    """Return a list of non-None :class:`DNSZoneConfig` from nodegroups."""
    return filter(
        None,
        [
            get_zone(nodegroup, serial)
            for nodegroup in nodegroups
        ])


def change_dns_zones(nodegroups):
    """Update the zone configuration for the given list of Nodegroups.

    :param nodegroups: The list of nodegroups (or the nodegroup) for which the
        zone should be updated.
    :type nodegroups: list (or :class:`NodeGroup`)
    """
    if not isinstance(nodegroups, collections.Iterable):
        nodegroups = [nodegroups]
    serial = next_zone_serial()
    zones = get_zones(nodegroups, serial)
    for zone in zones:
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
    zone = get_zone(nodegroup)
    if zone is None:
        return None
    serial = next_zone_serial()
    # Compute non-None zones.
    zones = get_zones(NodeGroup.objects.all(), serial)
    reconfig_subtask = tasks.rndc_command.subtask(args=[['reconfig']])
    write_dns_config_subtask = tasks.write_dns_config.subtask(
        zones=zones, callback=reconfig_subtask)
    tasks.write_dns_zone_config.delay(
        zone=zone, callback=write_dns_config_subtask)


def write_full_dns_config(active=True):
    """Write the DNS configuration.

    If active is True, write the DNS config for all the nodegroups.
    If active is False, write an empty DNS config (with no zones).
    """
    if active:
        serial = next_zone_serial()
        zones = get_zones(NodeGroup.objects.all(), serial)
    else:
        zones = []
    tasks.write_full_dns_config.delay(
        zones=zones,
        callback=tasks.rndc_command.subtask(args=[['reload']]))
