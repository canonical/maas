# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test doubles for the region's RPC implementation."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "IdentifyingRegionServer",
]

from maasserver.rpc.regionservice import RegionServer
from maastesting.factory import factory
from provisioningserver.rpc import cluster
from twisted.internet.defer import succeed


class IdentifyingRegionServer(RegionServer):
    """A :class:`RegionServer` derivative that stubs ident of the cluster.

    This intercepts remote calls to `cluster.Identify` and returns a
    canned answer.

    :ivar cluster_uuid: When `cluster.Identify` is called for the first
        time, this is populated with a random UUID. That UUID is also
        returned in the stub-response.
    """

    cluster_uuid = None

    def callRemote(self, commandType, *args, **kwargs):
        if commandType is cluster.Identify:
            if self.cluster_uuid is None:
                self.cluster_uuid = factory.getRandomUUID()
            return succeed({b"uuid": self.cluster_uuid})
        else:
            return super(IdentifyingRegionServer, self).callRemote(
                commandType, *args, **kwargs)
