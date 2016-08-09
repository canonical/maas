# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Helpers for testing network code."""

__all__ = [
    "does_HOSTALIASES_work_here",
]

import random
import socket
from tempfile import NamedTemporaryFile

from fixtures import EnvironmentVariable
from netaddr import (
    IPAddress,
    IPRange,
)


def does_HOSTALIASES_work_here():
    """Does the `HOSTALIASES` mechanism work fully on this host?

    Some hosts — and it's not clear why — do not work when the result of
    resolving a name in the file pointed to by `HOSTALIASES` is an IP address.
    """
    hostname = "host%d" % random.randrange(999999, 99999999)
    addresses = IPRange("127.1.0.1", "127.1.255.254")
    address = IPAddress(random.randint(addresses.first, addresses.last))
    with NamedTemporaryFile("w", encoding="ascii", prefix="hosts.") as hosts:
        print(hostname, address, file=hosts, flush=True)
        with EnvironmentVariable("HOSTALIASES", hosts.name):
            try:
                resolved = socket.gethostbyname(hostname)
            except socket.gaierror:
                return False
            else:
                return IPAddress(resolved) == address
