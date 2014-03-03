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
from provisioningserver.utils import asynchronous


@asynchronous
def getClientFor(uuid):
    """Get a client with which to make RPCs to the specified cluster."""
    try:
        service = eventloop.services.getServiceNamed("rpc")
    except KeyError:
        raise exceptions.NoConnectionsAvailable()
    else:
        return service.getClientFor(uuid)


@asynchronous
def getAllClients():
    """Get all recorded clients ready to make RPCs to clusters."""
    try:
        service = eventloop.services.getServiceNamed("rpc")
    except KeyError:
        return []
    else:
        return service.getAllClients()
