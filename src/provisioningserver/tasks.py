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
    'restart_dhcp_server',
    'write_dhcp_config',
    'write_dns_config',
    'write_dns_zone_config',
    'write_full_dns_config',
    ]

from subprocess import (
    CalledProcessError,
    check_call,
    )

from celery.task import task
from celeryconfig import DHCP_CONFIG_FILE
from provisioningserver.dhcp import config
from provisioningserver.dns.config import (
    DNSConfig,
    execute_rndc_command,
    setup_rndc,
    )
from provisioningserver.omshell import Omshell
from provisioningserver.power.poweraction import (
    PowerAction,
    PowerActionFail,
    )
from provisioningserver.utils import atomic_write

# =====================================================================
# Power-related tasks
# =====================================================================


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


# =====================================================================
# DNS-related tasks
# =====================================================================


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
    dns_config = DNSConfig(zones=zones)
    dns_config.write_config(**kwargs)
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
    dns_config = DNSConfig(zones=zones)
    dns_config.write_config(**kwargs)
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


# =====================================================================
# DHCP-related tasks
# =====================================================================


@task
def add_new_dhcp_host_map(mappings, server_address, shared_key):
    """Add address mappings to the DHCP server.

    :param mappings: A dict of new IP addresses, and the MAC addresses they
        translate to.
    :param server_address: IP or hostname for the DHCP server
    :param shared_key: The HMAC-MD5 key that the DHCP server uses for access
        control.
    """
    omshell = Omshell(server_address, shared_key)
    try:
        for ip_address, mac_address in mappings.items():
            omshell.create(ip_address, mac_address)
    except CalledProcessError:
        # TODO signal to webapp that the job failed.

        # Re-raise, so the job is marked as failed.  Only currently
        # useful for tests.
        raise


@task
def remove_dhcp_host_map(ip_address, server_address, shared_key):
    """Remove an IP to MAC mapping in the DHCP server.

    :param ip_address: Dotted quad string
    :param server_address: IP or hostname for the DHCP server
    :param shared_key: The HMAC-MD5 key that the DHCP server uses for access
        control.
    """
    omshell = Omshell(server_address, shared_key)
    try:
        omshell.remove(ip_address)
    except CalledProcessError:
        # TODO signal to webapp that the job failed.

        # Re-raise, so the job is marked as failed.  Only currently
        # useful for tests.
        raise


@task
def write_dhcp_config(**kwargs):
    """Write out the DHCP configuration file and restart the DHCP server.

    :param **kwargs: Keyword args passed to dhcp.config.get_config()
    """
    output = config.get_config(**kwargs).encode("ascii")
    atomic_write(output, DHCP_CONFIG_FILE)
    restart_dhcp_server()


@task
def restart_dhcp_server():
    """Restart the DHCP server."""
    check_call(['sudo', 'service', 'isc-dhcp-server', 'restart'])
