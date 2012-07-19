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
    'rndc_command',
    'setup_rndc_configuration',
    'write_dns_config',
    'write_dns_zone_config',
    'write_full_dns_config',
    ]


from celery.task import task
from provisioningserver.dns.config import (
    DNSConfig,
    execute_rndc_command,
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
def rndc_command(arguments, callback=None):
    """Use rndc to execute a command.
    :param callback: Callback subtask.
    :type callback: callable
    """
    execute_rndc_command(arguments)
    if callback is not None:
        callback.delay()


@task
def write_full_dns_config(zones=None, callback=None, **kwargs):
    """Write out the DNS configuration files: the main configuration
    file and the zone files.
    :param zones: List of zones to write.
    :type zones: list of :class:`DNSZoneData`
    :param callback: Callback subtask.
    :type callback: callable
    :param **kwargs: Keyword args passed to DNSConfig.write_config()
    """
    if zones is not None:
        for zone in zones:
            zone.write_config()
            zone.write_reverse_config()
    # Write main config file.
    config = DNSConfig(zones=zones)
    config.write_config(**kwargs)
    if callback is not None:
        callback.delay()


@task
def write_dns_config(zones=(), callback=None, **kwargs):
    """Write out the DNS configuration file.

    :param zones: List of zones to include as part of the main
        config.
    :type zones: list of :class:`DNSZoneData`
    :param callback: Callback subtask.
    :type callback: callable
    :param **kwargs: Keyword args passed to DNSConfig.write_config()
    """
    config = DNSConfig(zones=zones)
    config.write_config(**kwargs)
    if callback is not None:
        callback.delay()


@task
def write_dns_zone_config(zone, callback=None, **kwargs):
    """Write out a DNS zone configuration file.

    :param zone: The zone data to write the configuration for.
    :type zone: :class:`DNSZoneData`
    :param callback: Callback subtask.
    :type callback: callable
    :param **kwargs: Keyword args passed to DNSZoneConfig.write_config()
    """
    zone.write_config()
    zone.write_reverse_config()
    if callback is not None:
        callback.delay()


@task
def setup_rndc_configuration(callback=None):
    """Write out the two rndc configuration files (rndc.conf and
    named.conf.rndc).

    :param callback: Callback subtask.
    :type callback: callable
    """
    setup_rndc()
    if callback is not None:
        callback.delay()
