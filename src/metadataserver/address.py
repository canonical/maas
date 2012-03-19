# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Figure out server address for the maas_url setting."""

from __future__ import (
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    'guess_server_address',
    ]

from fcntl import ioctl
from logging import getLogger
from os import environ
import re
import socket
import struct
from subprocess import check_output

# fcntl operation as defined in <ioctls.h>.  This is GNU/Linux-specific!
SIOCGIFADDR = 0x8915


def get_command_output(*command_line):
    """Execute a command line, and return its output.

    Raises an exception if return value is nonzero.

    :param *command_line: Words for the command line.  No shell expansions
        are performed.
    :type *command_line: Sequence of basestring.
    :return: Output from the command.
    :rtype: List of basestring, one per line.
    """
    env = {
        variable: value
        for variable, value in environ.items()
            if not variable.startswith('LC_')}
    env.update({
        'LC_ALL': 'C',
        'LANG': 'en_US.UTF-8',
    })
    return check_output(command_line, env=env).splitlines()


def find_default_interface(ip_route_output):
    """Find the network interface used for the system's default route.

    If no default is found, makes a guess.

    :param ip_route_output: Output lines from "ip route show" output.
    :type ip_route_output: Sequence of basestring.
    :return: basestring, or None.
    """
    route_lines = list(ip_route_output)
    for line in route_lines:
        match = re.match('default\s+.*\sdev\s+(\w+)', line)
        if match is not None:
            return match.groups()[0]

    # Still nothing?  Try the first recognizable interface in the list.
    for line in route_lines:
        match = re.match('\s*(?:\S+\s+)*dev\s+(\w+)', line)
        if match is not None:
            return match.groups()[0]
    return None


def get_ip_address(interface):
    """Get the IP address for a given network interface."""
    # Apparently the netifaces module would do this for us.
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    interface_name = struct.pack(b'256s', interface[:15])
    try:
        info = ioctl(s.fileno(), SIOCGIFADDR, interface_name)
    except IOError as e:
        getLogger('maasserver').warn(
            "Could not determine address for apparent default interface %s "
            "(%s)"
            % (interface, e))
        return None
    return socket.inet_ntoa(info[20:24])


def guess_server_address():
    """Make a guess as to this server's IP address."""
    ip_route_output = get_command_output(
        '/bin/ip', '-oneline', 'route', 'show')
    interface = find_default_interface(ip_route_output)
    if interface is None:
        return socket.gethostname()
    else:
        return get_ip_address(interface)
