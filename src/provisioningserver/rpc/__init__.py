# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Cluster Controller RPC."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "getRegionClient",
]

import provisioningserver
from provisioningserver.rpc import exceptions

# A reference to the cluster's services.  This is initialized
# in ProvisioningServiceMaker.makeServer from
# (src/provisioningserver/plugin.py).
services = None


def getRegionClient():
    """getRegionClient()

    Get a client with which to make RPCs to the region.

    :raises: :py:class:`~.exceptions.NoConnectionsAvailable` when there
        are no open connections to the region controller.
    """
    # TODO: retry a couple of times before giving up if the service is
    # not running or if exceptions.NoConnectionsAvailable gets raised.
    if provisioningserver.services is None:
        raise exceptions.NoConnectionsAvailable(
            "Cluster services are unavailable.")
    rpc_service = provisioningserver.services.getServiceNamed('rpc')
    return rpc_service.getClient()
