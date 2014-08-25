# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Control the MAAS DHCP daemons."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'restart_dhcpv4',
    'restart_dhcpv6',
    'stop_dhcpv4',
    'stop_dhcpv6',
    ]

from provisioningserver.utils.shell import call_and_check


def call_service_script(ip_version, subcommand):
    """Issue a subcommand to one of the DHCP daemon services.

    Shells out using `sudo`, and with the `C` locale.

    :raise ExternalProcessError: if the restart command fails.
    """
    service_names = {
        4: 'maas-dhcp-server',
        6: 'maas-dhcpv6-server',
        }
    name = service_names[ip_version]
    call_and_check(
        ['sudo', '-n', 'service', name, subcommand],
        env={'LC_ALL': 'C'})


def restart_dhcpv4():
    """Restart the (IPv4) DHCP daemon.

    Shells out using `sudo`, and with the `C` locale.

    :raise ExternalProcessError: if the restart command fails.
    """
    call_service_script(4, 'restart')


def restart_dhcpv6():
    """Restart the DHCPv6 daemon.

    Shells out using `sudo`, and with the `C` locale.

    :raise ExternalProcessError: if the restart command fails.
    """
    call_service_script(6, 'restart')


def stop_dhcpv4():
    """Stop the (IPv4) DHCP daemon.

    Shells out using `sudo`, and with the `C` locale.

    :raise ExternalProcessError: if the restart command fails.
    """
    call_service_script(4, 'stop')


def stop_dhcpv6():
    """Stop the DHCPv6 daemon.

    Shells out using `sudo`, and with the `C` locale.

    :raise ExternalProcessError: if the restart command fails.
    """
    call_service_script(6, 'stop')
