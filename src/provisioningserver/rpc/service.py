# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""RPC helpers for service monitoring."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "service_action",
    "connect_check",
]


from socket import (
    AF_INET,
    SOCK_STREAM,
    socket,
)
from subprocess import (
    PIPE,
    Popen,
    STDOUT,
)

from provisioningserver.utils.twisted import (
    asynchronous,
    synchronous,
)
from twisted.internet.threads import deferToThread


@synchronous
def _service_action(service_name, action):
    """Check that the given service is running."""
    process = Popen(
        ['service', service_name, action], stdin=PIPE,
        stdout=PIPE,
        stderr=STDOUT, close_fds=True)
    output, _ = process.communicate()
    return process.wait() == 0, output.strip()


@asynchronous
def service_action(service_name, action):
    """Perfom an action on an upstart service.

    Returns a tuple (boolean, error string).
    """
    return deferToThread(_service_action, service_name)


@synchronous
def _connect_check(port, host):
    s = socket(AF_INET, SOCK_STREAM)
    s.settimeout(1)
    try:
        s.connect(("localhost", port))
    except Exception, e:
        return False, unicode(e)
    else:
        return True, ''


@asynchronous
def connect_check(port, host='localhost'):
    """Check if the given port is open.

    Returns a tuple (boolean, error string).
    """
    return deferToThread(_connect_check, port, host)
