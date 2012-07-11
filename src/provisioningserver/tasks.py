# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Provisioning server tasks that are run in Celery workers."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    'power_off',
    'power_on',
    'reload_dns_config',
    'reload_zone_config',
    'write_dns_config',
    'write_dns_zone_config',
    'write_full_dns_config',
    'setup_rndc_configuration',
    ]


from celery.task import task
from celery.task.sets import subtask
from provisioningserver.dns.config import (
    DNSConfig,
    DNSZoneConfig,
    execute_rndc_command,
    InactiveDNSConfig,
    setup_rndc,
    )
from provisioningserver.power.poweraction import (
    PowerAction,
    PowerActionFail,
    )
from provisioningserver.pxe.pxeconfig import PXEConfig


def issue_power_action(power_type, power_change, **kwargs):
    """Issue a power action to a node.

    :param power_type: The node's power type.  Must have a corresponding
        power template.
    :param power_change: The change to request: 'on' or 'off'.
    :param **kwargs: Keyword arguments are passed on to :class:`PowerAction`.
    """
    assert power_change in ('on', 'off'), (
        "Unknown power change keyword: %s" % power_change)
    kwargs['power_change'] = power_change
    try:
        pa = PowerAction(power_type)
        pa.execute(**kwargs)
    except PowerActionFail:
        # TODO: signal to webapp that it failed

        # Re-raise, so the job is marked as failed.  Only currently
        # useful for tests.
        raise

    # TODO: signal to webapp that it worked.


@task
def power_on(power_type, **kwargs):
    """Turn a node on."""
    issue_power_action(power_type, 'on', **kwargs)


@task
def power_off(power_type, **kwargs):
    """Turn a node off."""
    issue_power_action(power_type, 'off', **kwargs)


@task
def write_tftp_config_for_node(arch, macs, subarch="generic",
                               tftproot=None, **kwargs):
    """Write out the TFTP MAC-based config for a node.

    A config file is written for each MAC associated with the node.

    :param arch: Architecture name
    :type arch: string
    :param macs: An iterable of mac addresses
    :type macs: Iterable of strings
    :param subarch: The subarchitecture of the node, defaults to "generic" for
        architectures without sub-architectures.
    :param tftproot: Root TFTP directory.
    :param **kwargs: Keyword args passed to PXEConfig.write_config()
    """
    # TODO: fix subarch when node.py starts modelling sub-architecture for ARM
    for mac in macs:
        pxeconfig = PXEConfig(arch, subarch, mac, tftproot)
        pxeconfig.write_config(**kwargs)


@task
def reload_dns_config():
    """Use rndc to reload the DNS configuration."""
    execute_rndc_command('reload')


@task
def reload_zone_config(zone_name):
    """Use rndc to reload the DNS configuration for a zone."""
    execute_rndc_command('reload', zone_name)


@task
def write_full_dns_config(zones=None, reverse_zones=None,
                          **kwargs):
    """Write out the DNS configuration files: the main configuration
    file and the zone files.
    :param zones: Mapping between zone names and the zone data used
        to write the zone config files.
    :type zones: dict
    :param reverse_zones: Mapping between reverse zone names and the
        reverse zone data used to write the reverse zone config
        files.
    :type reverse_zones: dict
    :param **kwargs: Keyword args passed to DNSConfig.write_config()
    """
    if zones is None:
        zones = {}
    if reverse_zones is None:
        reverse_zones = {}
    # Write zone files.
    for zone_name, zone_data in zones.items():
        DNSZoneConfig(zone_name).write_config(**zone_data)
    # TODO: Write reverse zone files.
    # for zone_name, zone_data in zones.items():
    #    DNSZoneConfig(zone_name).write_config(**zone_data)
    # Write main config file.
    config = DNSConfig(
        zone_names=list(zones),
        reverse_zone_names=list(reverse_zones))
    config.write_config(**kwargs)
    subtask(reload_dns_config.subtask()).delay()


@task
def write_dns_config(inactive=False, zone_names=(),
                     reverse_zone_names=(), **kwargs):
    """Write out the DNS configuration file.

    :param inactive: Whether or not an inactive (i.e. blank)
        configuration should be written. False by default.
    :type inactive: boolean
    :param zone_names: List of zone names to include as part of the
        main config.
    :type zone_names: list
    :param reverse_zone_names: List of reverse zone names to include as part of
        the main config.
    :type reverse_zone_names: list
    :param **kwargs: Keyword args passed to DNSConfig.write_config()
    """
    if inactive:
        InactiveDNSConfig().write_config()
    else:
        config = DNSConfig(
            zone_names=zone_names,
            reverse_zone_names=reverse_zone_names)
        config.write_config(**kwargs)
    subtask(reload_dns_config.subtask()).delay()


@task
def write_dns_zone_config(zone_name, **kwargs):
    """Write out a DNS zone configuration file.

    :param zone_name: The identifier of the zone to write the configuration
        for.
    :type zone_name: basestring
    :param **kwargs: Keyword args passed to DNSZoneConfig.write_config()
    """
    DNSZoneConfig(zone_name).write_config(**kwargs)
    subtask(reload_zone_config.subtask(args=[zone_name])).delay()


@task
def setup_rndc_configuration():
    """Write out the two rndc configuration files (rndc.conf and
    named.conf.rndc).
    """
    setup_rndc()
    subtask(reload_dns_config.subtask()).delay()
