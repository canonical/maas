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

# A DNS zone's serial is a 32-bit integer.  Also, we start with the
# value 1 because 0 has special meaning for some DNS servers.  Even if
# we control the DNS server we use, better safe than sorry.
zone_serial = Sequence(
    'maasserver_zone_serial_seq', incr=1, minvalue=1, maxvalue=INT_MAX)


def next_zone_serial():
    return '%0.10d' % zone_serial.nextval()


def change_dns_zone(nodegroup):
    """Update the zone configurtion for the given `nodegroup`.

    :param nodegroup: The nodegroup for which the zone should be cupdated.
    :type nodegroup: :class:`NodeGroup`
    """
    mapping = DHCPLease.objects.get_hostname_ip_mapping(nodegroup)
    zone_name = nodegroup.name
    zone_reload_subtask = tasks.rndc_command.subtask(
        args=['reload', zone_name])
    tasks.write_dns_zone_config.delay(
        zone_name=zone_name, domain=zone_name,
        serial=next_zone_serial(), hostname_ip_mapping=mapping,
        callback=zone_reload_subtask)


def add_zone(nodegroup):
    """Add to the DNS server a new zone for the given `nodegroup`.

    :param nodegroup: The nodegroup for which the zone should be added.
    :type nodegroup: :class:`NodeGroup`
    """
    zone_names = [
        result[0]
        for result in NodeGroup.objects.all().values_list('name')]
    tasks.write_dns_config(zone_names=zone_names)
    mapping = DHCPLease.objects.get_hostname_ip_mapping(nodegroup)
    zone_name = nodegroup.name
    reconfig_subtask = tasks.rndc_command.subtask(args=['reconfig'])
    write_dns_config_subtask = tasks.write_dns_config.subtask(
        zone_names=zone_names, callback=reconfig_subtask)
    tasks.write_dns_zone_config.delay(
        zone_name=zone_name, domain=zone_name,
        serial=next_zone_serial(), hostname_ip_mapping=mapping,
        callback=write_dns_config_subtask)


def write_full_dns_config():
    """Write the DNS configuration for all the nodegroups."""
    groups = NodeGroup.objects.all()
    serial = next_zone_serial()
    zones = {
        group.name: {
            'serial': serial,
            'zone_name': group.name,
            'domain': group.name,
            'hostname_ip_mapping': (
                DHCPLease.objects.get_hostname_ip_mapping(
                    group))
            }
        for group in groups
        }
    tasks.write_full_dns_config(
        zones,  callback=tasks.rndc_command.subtask(args=['reload']))
