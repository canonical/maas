# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test fixtures for the region's RPC implementation."""

__all__ = [
    "RunningClusterRPCFixture",
    "MockLiveRegionToClusterRPCFixture",
    "MockRegionToClusterRPCFixture",
]

from collections import defaultdict
from os import path, urandom
from urllib.parse import urlparse

from crochet import run_in_reactor
import fixtures
from testtools.monkey import MonkeyPatcher, patch
from twisted.internet import defer, endpoints, reactor
from twisted.internet.protocol import Factory
from twisted.test import iosim
from zope.interface import implementer

from maasserver import eventloop, security
from maasserver.models.node import RackController
from maasserver.rpc import getClientFor, rackcontrollers
from maasserver.rpc.regionservice import RegionServer
from maasserver.testing.eventloop import (
    RegionEventLoopFixture,
    RunningEventLoopFixture,
)
from maastesting import get_testing_timeout
from provisioningserver.rpc import cluster, clusterservice, region
from provisioningserver.rpc.interfaces import IConnection
from provisioningserver.rpc.testing import (
    call_responder,
    make_amp_protocol_factory,
)
from provisioningserver.security import calculate_digest
from provisioningserver.utils.twisted import asynchronous, synchronous

TIMEOUT = get_testing_timeout()


@run_in_reactor
def get_service_in_eventloop(name):
    """Obtain the named service from the global event-loop."""
    return eventloop.services.getServiceNamed(name)


@implementer(IConnection)
class FakeConnection:
    def __init__(self, ident):
        super().__init__()
        self.protocol = clusterservice.Cluster()
        self.ident = ident

    def callRemote(self, cmd, **arguments):
        return call_responder(self.protocol, cmd, arguments)


class RunningClusterRPCFixture(fixtures.Fixture):
    """Set-up the event-loop with only the RPC service running.

    Layer on a fake cluster RPC implementation.
    """

    def setUp(self):
        super().setUp()
        self.useFixture(RegionEventLoopFixture("rpc"))
        self.useFixture(RunningEventLoopFixture())
        self.useFixture(MockRegionToClusterRPCFixture())


def _get_shared_secret_for_tests():
    """Get the shared secret, but wait longer."""
    wrapped_gss = security.get_shared_secret
    # Undo functools.wraps
    gss = wrapped_gss.__wrapped__
    rewrapped_gss = asynchronous(timeout=TIMEOUT)(gss)
    return rewrapped_gss()


def authenticate_with_secret(secret, message):
    """Patch-in for `Authenticate` calls.

    This ought to always return the correct digest because it'll be using
    the same shared-secret as the region.
    """
    salt = urandom(16)  # 16 bytes of high grade noise.
    digest = calculate_digest(secret, message, salt)
    return defer.succeed({"digest": digest, "salt": salt})


class MockRegionToClusterRPCFixture(fixtures.Fixture):
    """Patch in a stub cluster RPC implementation to enable end-to-end testing.

    Use this in *region* tests.

    Example usage (in this case, for stubbing the `Identify` RPC method)::

      controller = factory.make_RackController()
      fixture = self.useFixture(MockRegionToClusterRPCFixture())
      protocol, io = fixture.makeCluster(controller, region.Identify)
      protocol.Identify.return_value = defer.succeed({"ident": "foobar"})

      client = getClientFor(controller.system_id)
      result = client(region.Identify)
      io.flush()  # Call this in the reactor thread.

      self.assertEqual(result, ...)

    """

    def setUp(self):
        super().setUp()
        # Ensure there's a shared-secret.
        self.secret = _get_shared_secret_for_tests()
        # We need the event-loop up and running.
        if not eventloop.loop.running:
            raise RuntimeError(
                "Please start the event-loop before using this fixture."
            )
        self.rpc = get_service_in_eventloop("rpc").wait(TIMEOUT)
        # The RPC service uses a defaultdict(set) to manage connections, but
        # let's check those assumptions.
        assert isinstance(self.rpc.connections, defaultdict)
        assert self.rpc.connections.default_factory is set
        # Populate a connections mapping with a fake connection for each
        # rack controller known at present.
        fake_connections = defaultdict(set)
        for system_id in RackController.objects.values_list(
            "system_id", flat=True
        ):
            connection = FakeConnection(system_id)
            fake_connections[connection.ident].add(connection)
        # Patch the fake connections into place for this fixture's lifetime.
        self.addCleanup(patch(self.rpc, "connections", fake_connections))

    def addCluster(self, protocol):
        """Add a new stub cluster using the given `protocol`.

        The `protocol` should be an instance of `amp.AMP`.

        :return: py:class:`twisted.test.iosim.IOPump`
        """
        server_factory = Factory.forProtocol(RegionServer)
        server_factory.service = self.rpc
        server = server_factory.buildProtocol(addr=None)
        return iosim.connect(
            server,
            iosim.makeFakeServer(server),
            protocol,
            iosim.makeFakeClient(protocol),
            debug=False,  # Debugging is useful, but too noisy by default.
        )

    def makeCluster(self, controller, *commands):
        """Make and add a new stub cluster connection with the `commands`.

        See `make_amp_protocol_factory` for details.

        Note that if the ``Identify`` call is not amongst `commands`, it will
        be added. In addition, its return value is also set to return the
        system_id of `controller`. There's a good reason: the first thing that
        `RegionServer` does when a connection is made is call `Identify`. This
        has to succeed or the connection will never been added to the RPC
        service's list of connections.

        :return: A 2-tuple of the protocol instance created and the
            py:class:`twisted.test.iosim.IOPump` as returned by `addCluster`.
        """
        if cluster.Identify not in commands:
            commands = commands + (cluster.Identify,)
        if cluster.Authenticate not in commands:
            commands = commands + (cluster.Authenticate,)
        protocol_factory = make_amp_protocol_factory(*commands)
        protocol = protocol_factory()
        ident_response = {"ident": controller.system_id}
        protocol.Identify.side_effect = lambda _: defer.succeed(
            ident_response.copy()
        )
        protocol.Authenticate.side_effect = (
            lambda _, message: authenticate_with_secret(self.secret, message)
        )
        return protocol, self.addCluster(protocol)


class MockLiveRegionToClusterRPCFixture(fixtures.Fixture):
    """Patch in a stub cluster RPC implementation to enable end-to-end testing.

    This connects up the region's RPC implementation to a stub cluster RPC
    implementation using UNIX sockets. There's no need to pump IO (though
    that's useful in places); as long as the reactor is running this will
    propagate IO between each end.

    Use this in *region* tests.

    Example usage::

      controller = factory.make_RackController()
      fixture = self.useFixture(RegionToClusterRPCFixture())
      protocol = fixture.makeCluster(controller, region.Identify)
      protocol.Identify.return_value = defer.succeed({"ident": "foobar"})

      client = getClientFor(controller.system_id)
      d = client(region.Identify)

      def check(result):
          self.assertEqual(result, ...)
      d.addCallback(check)

    """

    @synchronous
    def start(self):
        # Shutdown the RPC service, switch endpoints, then start again.
        self.rpc.stopService().wait(TIMEOUT)

        # Ensure there's a shared-secret.
        self.secret = _get_shared_secret_for_tests()

        # The RPC service uses a list to manage endpoints, but let's check
        # those assumptions.
        assert isinstance(self.rpc.endpoints, list)
        # Patch a fake UNIX endpoint in to the RPC service.
        endpoint = endpoints.UNIXServerEndpoint(reactor, self.sockfile)
        self.monkey.add_patch(self.rpc, "endpoints", [[endpoint]])

        # The RPC service uses a defaultdict(set) to manage connections, but
        # let's check those assumptions.
        assert isinstance(self.rpc.connections, defaultdict)
        assert self.rpc.connections.default_factory is set
        # Patch a fake connections dict into place for this fixture's lifetime.
        self.monkey.add_patch(self.rpc, "connections", defaultdict(set))

        # Modify the state of the service.
        self.monkey.patch()

        # Start the service back up again.
        self.rpc.startService().wait(TIMEOUT)

    @synchronous
    def stop(self):
        # Shutdown the RPC service, switch endpoints, then start again.
        self.rpc.stopService().wait(TIMEOUT)
        # Restore the state of the service.
        self.monkey.restore()
        # Start the service back up again.
        self.rpc.startService().wait(TIMEOUT)

    def setUp(self):
        super().setUp()
        self.monkey = MonkeyPatcher()
        # We need the event-loop up and running.
        if not eventloop.loop.running:
            raise RuntimeError(
                "Please start the event-loop before using this fixture."
            )
        self.rpc = get_service_in_eventloop("rpc").wait(TIMEOUT)
        # Where we're going to put the UNIX socket files.
        self.sockdir = self.useFixture(fixtures.TempDir()).path
        self.sockfile = path.join(self.sockdir, "sock")
        # Configure the RPC service with a UNIX endpoint.
        self.addCleanup(self.stop)
        self.start()

    @asynchronous
    @defer.inlineCallbacks
    def addCluster(self, protocol, rack_controller):
        """Add a new stub cluster using the given `protocol`.

        The `protocol` should be an instance of `amp.AMP`.

        :return: A `Deferred` that fires with the connected protocol
            instance.
        """
        endpoint = endpoints.UNIXClientEndpoint(reactor, self.sockfile)
        protocol = yield endpoints.connectProtocol(endpoint, protocol)

        # Mock the registration into the database, as the rack controller is
        # already created. We reset this once registration is complete so as
        # to not interfere with other tests.
        registered = rack_controller
        patcher = MonkeyPatcher()
        patcher.add_patch(
            rackcontrollers, "register", (lambda *args, **kwargs: registered)
        )

        # Register the rack controller with the region.
        patcher.patch()
        try:
            yield protocol.callRemote(
                region.RegisterRackController,
                system_id=rack_controller.system_id,
                hostname=rack_controller.hostname,
                interfaces={},
                url=urlparse(""),
            )
        finally:
            patcher.restore()

        defer.returnValue(protocol)

    @synchronous
    def makeCluster(self, rack_controller, *commands):
        """Make and add a new stub cluster connection with the `commands`.

        See `make_amp_protocol_factory` for details.

        Note that if the ``Authenticate`` call is not amongst `commands`,
        it will be added. In addition, its action is to call
        ``RegisterRackController`` so the connction is fully made and the
        connection wil be added to the RPC service's list of connections.

        :return: The protocol instance created.
        """
        if cluster.Authenticate not in commands:
            commands = commands + (cluster.Authenticate,)
        protocol_factory = make_amp_protocol_factory(*commands)
        protocol = protocol_factory()

        protocol.Authenticate.side_effect = (
            lambda _, message: authenticate_with_secret(self.secret, message)
        )
        self.addCluster(protocol, rack_controller).wait(TIMEOUT)
        # The connection is now established, but there is a brief
        # handshake that takes place immediately upon connection.  We
        # wait for that to finish before returning.
        getClientFor(rack_controller.system_id, timeout=TIMEOUT)
        return protocol
