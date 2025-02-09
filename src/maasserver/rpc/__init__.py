# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Region Controller RPC."""

from maasserver import eventloop
from provisioningserver.rpc import exceptions
from provisioningserver.utils.twisted import asynchronous, deferred, FOREVER


@asynchronous(timeout=FOREVER)  # Handles times-out itself.
@deferred  # Always return a Deferred, no matter what.
def getClientFromIdentifiers(identifiers, timeout=0):
    """Get a client with which to make RPCs to any one of the `identifiers`.

    :param timeout: The number of seconds to wait before giving up on
        getting a connection. By default, `timeout` is 0.
    :raises: :py:class:`~.exceptions.NoConnectionsAvailable` when there
        are no open connections to any rack controllers.
    """
    try:
        service = eventloop.services.getServiceNamed("rpc")
    except KeyError:
        raise exceptions.NoConnectionsAvailable(  # noqa: B904
            "Unable to connect to any rack controller %s; no connections "
            "available." % ",".join(identifiers)
        )
    else:
        return service.getClientFromIdentifiers(identifiers, timeout=timeout)


@asynchronous(timeout=FOREVER)  # Handles times-out itself.
@deferred  # Always return a Deferred, no matter what.
def getClientFor(uuid, timeout=0):
    """Get a client with which to make RPCs to the specified rack controller.

    :param timeout: The number of seconds to wait before giving up on
        getting a connection. By default, `timeout` is 0.
    :raises: :py:class:`~.exceptions.NoConnectionsAvailable` when there
        are no open connections to the specified cluster controller.
    """
    try:
        service = eventloop.services.getServiceNamed("rpc")
    except KeyError:
        raise exceptions.NoConnectionsAvailable(  # noqa: B904
            "Unable to connect to rack controller %s; no connections "
            "available." % uuid,
            uuid=uuid,
        )
    else:
        return service.getClientFor(uuid, timeout=timeout)


@asynchronous(timeout=FOREVER)  # Does not defer work.
def getAllClients():
    """Get all recorded clients ready to make RPCs to rack controllers."""
    try:
        service = eventloop.services.getServiceNamed("rpc")
    except KeyError:
        return []
    else:
        return service.getAllClients()


@asynchronous(timeout=FOREVER)  # Does not defer work.
def getRandomClient():
    """Return a random client to any connected rack controller."""
    try:
        service = eventloop.services.getServiceNamed("rpc")
    except KeyError:
        return []
    else:
        return service.getRandomClient()
