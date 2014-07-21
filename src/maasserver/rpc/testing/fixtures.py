# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test fixtures for the region's RPC implementation."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "ClusterRPCFixture",
]

from collections import defaultdict

from crochet import run_in_reactor
import fixtures
from maasserver import eventloop
from maasserver.enum import NODEGROUP_STATUS
from maasserver.models.nodegroup import NodeGroup
from provisioningserver.rpc import clusterservice
from provisioningserver.rpc.interfaces import IConnection
from provisioningserver.rpc.testing import call_responder
from testtools.monkey import patch
from zope.interface import implementer


@run_in_reactor
def get_service_in_eventloop(name):
    """Obtain the named service from the global event-loop."""
    return eventloop.services.getServiceNamed(name)


@implementer(IConnection)
class FakeConnection:

    def __init__(self, ident):
        super(FakeConnection, self).__init__()
        self.protocol = clusterservice.Cluster()
        self.ident = ident

    def callRemote(self, cmd, **arguments):
        return call_responder(self.protocol, cmd, arguments)


class ClusterRPCFixture(fixtures.Fixture):

    def setUp(self):
        super(ClusterRPCFixture, self).setUp()
        # We need the event-loop up and running.
        if not eventloop.loop.running:
            raise RuntimeError(
                "Please start the event-loop before using this fixture.")
        rpc_service = get_service_in_eventloop("rpc").wait(10)
        # The RPC service uses a defaultdict(set) to manage connections, but
        # let's check those assumptions.
        assert isinstance(rpc_service.connections, defaultdict)
        assert rpc_service.connections.default_factory is set
        # Populate a connections mapping with a fake connection for each
        # node-group known at present.
        fake_connections = defaultdict(set)
        for nodegroup in NodeGroup.objects.all():
            if nodegroup.status == NODEGROUP_STATUS.ACCEPTED:
                connection = FakeConnection(nodegroup.uuid)
                fake_connections[connection.ident].add(connection)
        # Patch the fake connections into place for this fixture's lifetime.
        self.addCleanup(patch(rpc_service, "connections", fake_connections))
