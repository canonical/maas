# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Network utilities."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    'int_to_dotted_quad',
    'dotted_quad_to_int',
    'ip_range',
    ]

import socket
import struct
from itertools import imap


def int_to_dotted_quad(n):
    """Convert int to dotted quad string.

    >>> int_to_dotted_quad(3232235521)
    '192.168.0.1'
    """
    return socket.inet_ntoa(struct.pack(str('>L'), n))


def dotted_quad_to_int(ip):
    """Convert decimal dotted quad string to integer.

    >>> dotted_quad_to_int('192.168.0.1')
    3232235521L
    """
    return struct.unpack(str('>L'), socket.inet_aton(ip))[0]


def ip_range(ip_low, ip_high):
    """Return an Iterator over the IP Addresses between the two provided IPs.

    >>> ip_range('192.168.0.1', '192.168.0.3')
    ['192.168.0.1', '192.168.0.2', '192.168.0.3']
    """
    ip_low_int = dotted_quad_to_int(ip_low)
    ip_high_int = dotted_quad_to_int(ip_high)
    ip_range = range(ip_low_int, ip_high_int + 1)
    return imap(int_to_dotted_quad, ip_range)
