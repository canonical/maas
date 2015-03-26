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

from provisioningserver.utils import in_develop_mode
from provisioningserver.utils.shell import (
    call_and_check,
    ExternalProcessError,
)
from twisted.python import log


def call_service_script(ip_version, subcommand):
    """Issue a subcommand to one of the DHCP daemon services.

    Shells out using `sudo`, and with the `C` locale.

    :raise ExternalProcessError: if the restart command fails.
    """
    service_names = {
        4: 'maas-dhcpd',
        6: 'maas-dhcpd6',
        }
    name = service_names[ip_version]
    if in_develop_mode():
        log.msg("Service control of %s is skipped in DEVELOP mode." % name)
    else:
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


def stop_dhcp_server(ip_version):
    """Stop a DHCP daemon, but treat "not running" as success.

    Upstart reports an attempt to stop a service while it isn't running as an
    error.  We don't want that.  Other errors are still propagated as normal.
    """
    # This relies on the C locale being used: it looks for the specific error
    # message we get in the situation where the DHCP server was not running.
    try:
        call_service_script(ip_version, 'stop')
    except ExternalProcessError as e:
        if e.returncode == 1 and e.output.strip() == "stop: Unknown instance:":
            # The server wasn't running.  This is success.
            pass
        else:
            # Other error.  This is still failure.
            raise


def stop_dhcpv4():
    """Stop the (IPv4) DHCP daemon.

    Shells out using `sudo`, and with the `C` locale.

    :raise ExternalProcessError: if the restart command fails.
    """
    stop_dhcp_server(4)


def stop_dhcpv6():
    """Stop the DHCPv6 daemon.

    Shells out using `sudo`, and with the `C` locale.

    :raise ExternalProcessError: if the restart command fails.
    """
    stop_dhcp_server(6)
