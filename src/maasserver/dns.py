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

from django.conf import settings
from maasserver.exceptions import MAASException
from maasserver.models import (
    Config,
    DHCPLease,
    NodeGroup,
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
    """An error occured when setting up MAAS's DNS server."""


def warn_loopback(ip):
    """Warn if the given IP address is in the loopback network."""
    if IPAddress(ip) in IPNetwork('127.0.0.1/8'):
        logging.getLogger('maas').warn(
            "The DNS server will use the address '%s',  which is inside the "
            "loopback network.  This may not be a problem if you're not using "
            "MAAS's DNS features or if you don't rely on this information.  "
            "Be sure to configure the DEFAULT_MAAS_URL setting in MAAS's "
            "settings.py (or demo.py/development.py if you are running a "
            "development system)."
            % ip)


def get_dns_server_address():
    """Return the DNS server's IP address.

    That address is derived from DEFAULT_MAAS_URL in order to get a sensible
    default and at the same time give a possibility to the user to change this.
    """
    try:
        ip = get_maas_facing_server_address()
    except socket.error as e:
        raise DNSException(
            "Unable to find MAAS server IP address: %s.  "
            "MAAS's DNS server requires this IP address for the NS records "
            "in its zone files.  Make sure that the DEFAULT_MAAS_URL setting "
            "has the correct hostname."
            % e.strerror)

    warn_loopback(ip)
    return ip


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
    if not is_dns_enabled():
        return
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
    if not is_dns_enabled():
        return
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


def write_full_dns_config(active=True, reload_retry=False):
    """Write the DNS configuration.

    :param active: If True, write the DNS config for all the nodegroups.
        Otherwise write an empty DNS config (with no zones).  Defaults
        to `True`.
    :type active: bool
    :param reload_retry: Should the reload rndc command be retried in case
        of failure?  Defaults to `False`.
    :type reload_retry: bool
    """
    if not is_dns_enabled():
        return
    if active:
        serial = next_zone_serial()
        zones = get_zones(NodeGroup.objects.all(), serial)
    else:
        zones = []
    tasks.write_full_dns_config.delay(
        zones=zones,
        callback=tasks.rndc_command.subtask(
            args=[['reload'], reload_retry]))
