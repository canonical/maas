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
    "MockRegionToClusterRPCFixture",
]

from collections import defaultdict
from warnings import warn

from crochet import run_in_reactor
import fixtures
from maasserver import eventloop
from maasserver.enum import NODEGROUP_STATUS
from maasserver.models.nodegroup import NodeGroup
from maasserver.rpc.regionservice import RegionServer
from provisioningserver.rpc import (
    cluster,
    clusterservice,
    )
from provisioningserver.rpc.interfaces import IConnection
from provisioningserver.rpc.testing import (
    call_responder,
    make_amp_protocol_factory,
    )
from testtools.monkey import patch
from twisted.internet import defer
from twisted.internet.protocol import Factory
from twisted.test import iosim
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
    """Deprecated: use :py:class:`MockRegionToClusterRPCFixture` instead.

    This creates connections to the "real" cluster RPC implementation,
    but this relies on real data. This makes tests fragile, and, as time
    progresses, will result in ever more elaborate test fixtures to get
    that data into place.

    Instead, use :py:class:`MockRegionToClusterRPCFixture`, which helps you
    stub out those RPC calls that you're testing against, and verifies each
    call's arguments *and* response against the RPC schema.
    """

    def __init__(self):
        super(ClusterRPCFixture, self).__init__()
        warn(
            ("ClusterRPCFixture is deprecated; use "
             "MockRegionToClusterRPCFixture instead."),
            DeprecationWarning)

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


class MockRegionToClusterRPCFixture(fixtures.Fixture):
    """Patch in a stub cluster RPC implementation to enable end-to-end testing.

    Use this in *region* tests.

    Example usage::

      nodegroup = factory.make_node_group()
      fixture = self.useFixture(MockRegionToClusterRPCFixture())
      protocol, io = fixture.makeCluster(nodegroup, region.Identify)
      protocol.Identify.return_value = defer.succeed({"ident": "foobar"})

      client = getClientFor(nodegroup.uuid)
      result = client(region.Identify)
      io.flush()  # Call this in the reactor thread.

      self.assertThat(result, ...)

    """

    def setUp(self):
        super(MockRegionToClusterRPCFixture, self).setUp()
        # We need the event-loop up and running.
        if not eventloop.loop.running:
            raise RuntimeError(
                "Please start the event-loop before using this fixture.")
        self.rpc = get_service_in_eventloop("rpc").wait(10)
        # The RPC service uses a defaultdict(set) to manage connections, but
        # let's check those assumptions.
        assert isinstance(self.rpc.connections, defaultdict)
        assert self.rpc.connections.default_factory is set
        # Patch a fake connections dict into place for this fixture's lifetime.
        self.addCleanup(patch(self.rpc, "connections", defaultdict(set)))

    def addCluster(self, protocol):
        """Add a new stub cluster using the given `protocol`.

        The `protocol` should be an instance of `amp.AMP`.

        :returns: py:class:`twisted.test.iosim.IOPump`
        """
        server_factory = Factory.forProtocol(RegionServer)
        server_factory.service = self.rpc
        server = server_factory.buildProtocol(addr=None)
        return iosim.connect(
            server, iosim.makeFakeServer(server),
            protocol, iosim.makeFakeClient(protocol),
            debug=False,  # Debugging is useful, but too noisy by default.
        )

    def makeCluster(self, nodegroup, *commands):
        """Make and add a new stub cluster connection with the `commands`.

        See `make_amp_protocol_factory` for details.

        Note that if the ``Identify`` call is not amongst `commands`, it will
        be added. In addition, its return value is also set to return the UUID
        of `nodegroup`. There's a good reason: the first thing that
        `RegionServer` does when a connection is made is call `Identify`. This
        has to succeed or the connection will never been added to the RPC
        service's list of connections.

        :returns: A 2-tuple of the protocol instance created and the
            py:class:`twisted.test.iosim.IOPump` as returned by `addCluster`.
        """
        if cluster.Identify not in commands:
            commands = commands + (cluster.Identify,)
        protocol_factory = make_amp_protocol_factory(*commands)
        protocol = protocol_factory()
        ident_response = {"ident": nodegroup.uuid.decode("ascii")}
        protocol.Identify.side_effect = (
            lambda protocol: defer.succeed(ident_response.copy()))
        return protocol, self.addCluster(protocol)
