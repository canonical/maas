# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Region Controller RPC."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "getClientFor",
    "getAllClients",
]

from maasserver import eventloop
from provisioningserver.rpc import exceptions
from provisioningserver.utils.twisted import (
    asynchronous,
    deferred,
    FOREVER,
)


@asynchronous(timeout=FOREVER)  # getClientFor handles times-out itself.
@deferred  # Always return a Deferred, no matter what.
def getClientFor(uuid, timeout=0):
    """Get a client with which to make RPCs to the specified cluster.

    :param timeout: The number of seconds to wait before giving up on
        getting a connection. By default, `timeout` is 0.
    :raises: :py:class:`~.exceptions.NoConnectionsAvailable` when there
        are no open connections to the specified cluster controller.
    """
    try:
        service = eventloop.services.getServiceNamed("rpc")
    except KeyError:
        raise exceptions.NoConnectionsAvailable(
            "Unable to connect to cluster %s; no connections available." %
            uuid, uuid=uuid)
    else:
        return service.getClientFor(uuid, timeout=timeout)


@asynchronous(timeout=FOREVER)  # getAllClients does not defer work.
def getAllClients():
    """Get all recorded clients ready to make RPCs to clusters."""
    try:
        service = eventloop.services.getServiceNamed("rpc")
    except KeyError:
        return []
    else:
        return service.getAllClients()
