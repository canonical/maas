# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Figure out server address for the maas_url setting."""

import re
import socket
from subprocess import check_output

from metadataserver import logger
from provisioningserver.utils.network import get_all_addresses_for_interface
from provisioningserver.utils.shell import get_env_with_locale

# fcntl operation as defined in <ioctls.h>.  This is GNU/Linux-specific!
SIOCGIFADDR = 0x8915


def get_command_output(*command_line):
    """Execute a command line, and return its output.

    Raises an exception if return value is nonzero.

    :param *command_line: Words for the command line.  No shell expansions
        are performed.
    :type *command_line: Sequence of unicode.
    :return: Output from the command.
    :rtype: List of unicode, one per line.
    """
    env = get_env_with_locale()
    output = check_output(command_line, env=env)
    return output.decode("utf-8").splitlines()


def find_default_interface(ip_route_output):
    """Find the network interface used for the system's default route.

    If no default is found, makes a guess.

    :param ip_route_output: Output lines from "ip route show" output.
    :type ip_route_output: Sequence of unicode.
    :return: unicode, or None.
    """
    route_lines = list(ip_route_output)
    for line in route_lines:
        match = re.match(r"default\s+.*\sdev\s+([^\s]+)", line)
        if match is not None:
            return match.groups()[0]

    # Still nothing?  Try the first recognizable interface in the list.
    for line in route_lines:
        match = re.match(r"\s*(?:\S+\s+)*dev\s+([^\s]+)", line)
        if match is not None:
            return match.groups()[0]
    return None


def get_ip_address(interface):
    """Get the first IP address for a given network interface.

    :return: The IP address, as a string, for the first address on the
        interface. If the interface has both IPv4 and IPv6 addresses, the IPv4
        address will be preferred. Otherwise the returned address will be the
        first result of a sort on the set of addresses on the interface.
    """
    try:
        # get_all_addresses_for_interface yields IPAddress instances.
        # When sorted, IPAddress guarantees that IPv4 addresses will
        # sort before IPv6, so we just return the first address that
        # we've found.
        all_addresses = sorted(get_all_addresses_for_interface(interface))
        return all_addresses[0]
    except Exception as e:
        logger.warning(
            "Could not determine address for apparent default interface "
            "%s (%s)" % (interface, e)
        )
        return None


def guess_server_host():
    """Make a guess as to this server's IP address or hostname.

    :return: IP address or hostname.
    :rtype: unicode
    """
    ip_route_output = get_command_output(
        "/bin/ip", "-oneline", "route", "show"
    )
    interface = find_default_interface(ip_route_output)
    if interface is None:
        return socket.gethostname()
    else:
        return get_ip_address(interface)
