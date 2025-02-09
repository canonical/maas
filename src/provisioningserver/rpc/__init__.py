# Copyright 2013-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Cluster Controller RPC."""

import provisioningserver
from provisioningserver.rpc import exceptions


def getRegionClient():
    """getRegionClient()

    Get a client with which to make RPCs to the region.

    :raises: :py:class:`~.exceptions.NoConnectionsAvailable` when there
        are no open connections to the region controller.
    """
    # TODO: retry a couple of times before giving up if the service is
    # not running or if exceptions.NoConnectionsAvailable gets raised.
    try:
        rpc_service = provisioningserver.services.getServiceNamed("rpc")
    except KeyError:
        raise exceptions.NoConnectionsAvailable(  # noqa: B904
            "Cluster services are unavailable."
        )
    else:
        # won't scale connections if existing connections are busy, but will always return connection if one exists
        return rpc_service.getClient(busy_ok=True)
