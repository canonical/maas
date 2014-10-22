# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Testing helpers for RPC implementations."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "always_fail_with",
    "always_succeed_with",
    "are_valid_tls_parameters",
    "call_responder",
    "make_amp_protocol_factory",
    "MockClusterToRegionRPCFixture",
    "MockLiveClusterToRegionRPCFixture",
    "TwistedLoggerFixture",
]

from abc import (
    ABCMeta,
    abstractmethod,
    )
import collections
from copy import copy
import itertools
import operator
from os import path

import fixtures
from fixtures import (
    EnvironmentVariable,
    Fixture,
    )
from maastesting.factory import factory
from maastesting.fixtures import TempDirectory
from mock import (
    Mock,
    sentinel,
    )
import provisioningserver
from provisioningserver.rpc import region
from provisioningserver.rpc.clusterservice import (
    Cluster,
    ClusterClient,
    ClusterClientService,
    )
from provisioningserver.rpc.common import RPCProtocol
from provisioningserver.rpc.testing.tls import get_tls_parameters_for_region
from provisioningserver.security import (
    get_shared_secret_from_filesystem,
    set_shared_secret_on_filesystem,
    )
from provisioningserver.utils.twisted import (
    asynchronous,
    callOut,
    )
from testtools.deferredruntest import extract_result
from testtools.matchers import (
    AllMatch,
    IsInstance,
    MatchesAll,
    MatchesDict,
    )
from twisted.internet import (
    defer,
    endpoints,
    reactor,
    ssl,
    )
from twisted.internet.defer import (
    inlineCallbacks,
    returnValue,
    )
from twisted.internet.protocol import Factory
from twisted.internet.task import Clock
from twisted.protocols import amp
from twisted.python import (
    log,
    reflect,
    )
from twisted.python.failure import Failure
from twisted.test import iosim


def call_responder(protocol, command, arguments):
    """Call `command` responder in `protocol` with given `arguments`.

    Serialises the arguments and deserialises the response too.
    """
    responder = protocol.locateResponder(command.commandName)
    arguments = command.makeArguments(arguments, protocol)
    d = responder(arguments)
    d.addCallback(command.parseResponse, protocol)

    def eb_massage_error(error):
        if error.check(amp.RemoteAmpError):
            # Convert remote errors back into local errors using the
            # command's error map if possible.
            error_type = command.reverseErrors.get(
                error.value.errorCode, amp.UnknownRemoteError)
            return Failure(error_type(error.value.description))
        else:
            # Exceptions raised in responders that aren't declared in that
            # responder's schema can get through to here without being wrapped
            # in RemoteAmpError. This is because call_responder() bypasses the
            # network marshall/unmarshall steps, where these exceptions would
            # ordinarily get squashed.
            return Failure(amp.UnknownRemoteError("%s: %s" % (
                reflect.qual(error.type), reflect.safe_str(error.value))))
    d.addErrback(eb_massage_error)

    return d


class TwistedLoggerFixture(Fixture):
    """Capture all Twisted logging.

    Temporarily replaces all log observers.
    """

    def __init__(self):
        super(TwistedLoggerFixture, self).__init__()
        self.logs = []

    def dump(self):
        """Return all logs as a string."""
        return "\n---\n".join(
            log.textFromEventDict(event) for event in self.logs)

    # For compatibility with fixtures.FakeLogger.
    output = property(dump)

    def containsError(self):
        return any(log["isError"] for log in self.logs)

    def setUp(self):
        super(TwistedLoggerFixture, self).setUp()
        self.addCleanup(
            operator.setitem, log.theLogPublisher.observers,
            slice(None), log.theLogPublisher.observers[:])
        log.theLogPublisher.observers[:] = [self.logs.append]


are_valid_tls_parameters = MatchesDict({
    "tls_localCertificate": IsInstance(ssl.PrivateCertificate),
    "tls_verifyAuthorities": MatchesAll(
        IsInstance(collections.Sequence),
        AllMatch(IsInstance(ssl.Certificate)),
    ),
})


class MockClusterToRegionRPCFixtureBase(fixtures.Fixture):
    """Patch in a stub region RPC implementation to enable end-to-end testing.

    This is an abstract base class. Derive concrete fixtures from this by
    implementing the `connect` method.
    """

    __metaclass__ = ABCMeta

    starting = None
    stopping = None

    def checkServicesClean(self):
        # If services are running, what do we do with any existing RPC
        # service? Do we shut it down and patch in? Do we just patch in and
        # move the running service aside? If it's not running, do we patch
        # into it without moving it aside? For now, keep it simple and avoid
        # these questions by requiring that services are stopped and that no
        # RPC service is globally registered.
        if provisioningserver.services.running:
            raise AssertionError(
                "Please ensure that cluster services are *not* running "
                "before using this fixture.")
        if "rpc" in provisioningserver.services.namedServices:
            raise AssertionError(
                "Please ensure that no RPC service is registered globally "
                "before using this fixture.")

    def asyncStart(self):
        # Check that no cluster services are running and that there's no RPC
        # service already registered.
        self.checkServicesClean()
        # Patch it into the global services object.
        self.rpc_service.setName("rpc")
        self.rpc_service.setServiceParent(provisioningserver.services)
        # Pretend event-loops only exist for those connections that already
        # exist. The chicken-and-egg will be resolved by injecting a
        # connection later on.
        self.rpc_service._get_rpc_info_url = self._get_rpc_info_url
        self.rpc_service._fetch_rpc_info = self._fetch_rpc_info
        # Finally, start the service. If the clock is advanced, this will do
        # its usual update() calls, but we've patched out _get_rpc_info_url
        # and _fetch_rpc_info so no traffic will result.
        self.starting = defer.maybeDeferred(self.rpc_service.startService)

    def asyncStop(self):
        if self.starting is None:
            # Nothing to do; it never started.
            self.stopping = defer.succeed(None)
        else:
            self.starting.cancel()
            self.stopping = defer.maybeDeferred(
                self.rpc_service.disownServiceParent)
        # Ensure the cluster's services will be left in a consistent state.
        self.stopping.addCallback(callOut(self.checkServicesClean))

    @asynchronous(timeout=15)
    def setUp(self):
        super(MockClusterToRegionRPCFixtureBase, self).setUp()
        # Ensure that we have MAAS_URL and CLUSTER_UUID set.
        self.useFixture(EnvironmentVariable(
            "MAAS_URL", factory.make_simple_http_url()))
        self.useFixture(EnvironmentVariable(
            "CLUSTER_UUID", factory.make_UUID().encode("ascii")))
        # Use an inert clock with ClusterClientService so it doesn't update
        # itself except when we ask it to.
        self.rpc_service = ClusterClientService(Clock())
        # Start up, but schedule stop first.
        self.addCleanup(self.asyncStop)
        self.asyncStart()
        # Return the Deferred so that callers from threads outside of the
        # reactor will block. In the reactor thread, a supporting test
        # framework may know how to handle this sanely.
        return self.starting

    @asynchronous(timeout=15)
    def cleanUp(self):
        super(MockClusterToRegionRPCFixtureBase, self).cleanUp()
        # Return the Deferred so that callers from threads outside of the
        # reactor will block. In the reactor thread, a supporting test
        # framework may know how to handle this sanely.
        return self.stopping

    def getEventLoopName(self, protocol):
        """Return `protocol`'s event-loop name.

        If one has not been set already, one is generated and saved as
        `protocol.ident`.
        """
        try:
            return protocol.ident
        except AttributeError:
            protocol.ident = factory.make_name("eventloop")
            return protocol.ident

    def ensureSharedSecret(self):
        """Make sure the shared-secret is set."""
        if get_shared_secret_from_filesystem() is None:
            set_shared_secret_on_filesystem(factory.make_bytes())

    @asynchronous(timeout=5)
    def addEventLoop(self, protocol):
        """Add a new stub event-loop using the given `protocol`.

        The `protocol` should be an instance of `amp.AMP`.

        :returns: py:class:`twisted.test.iosim.IOPump`
        """
        eventloop = self.getEventLoopName(protocol)
        address = factory.make_ipv4_address(), factory.pick_port()
        client = ClusterClient(address, eventloop, self.rpc_service)
        return self.connect(client, protocol)

    def makeEventLoop(self, *commands):
        """Make and add a new stub event-loop for the given `commands`.

        See `make_amp_protocol_factory` for details.
        """
        if region.Identify not in commands:
            commands = commands + (region.Identify,)
        if region.Authenticate not in commands:
            commands = commands + (region.Authenticate,)
        if region.Register not in commands:
            commands = commands + (region.Register,)
        if amp.StartTLS not in commands:
            commands = commands + (amp.StartTLS,)
        protocol_factory = make_amp_protocol_factory(*commands)
        protocol = protocol_factory()
        eventloop = self.getEventLoopName(protocol)
        protocol.Identify.return_value = {"ident": eventloop}
        protocol.Authenticate.side_effect = self._authenticate_with_cluster_key
        protocol.Register.side_effect = always_succeed_with({})
        protocol.StartTLS.return_value = get_tls_parameters_for_region()
        return protocol, self.addEventLoop(protocol)

    @abstractmethod
    def connect(self, cluster, region):
        """Wire up a connection between cluster and region.

        :type cluster: `twisted.internet.interfaces.IProtocol`
        :type region: `twisted.internet.interfaces.IProtocol`
        :returns: ...
        """

    def _get_rpc_info_url(self):
        """Patch-in for `ClusterClientService._get_rpc_info_url`.

        Returns a dummy value.
        """
        return sentinel.url

    def _fetch_rpc_info(self, url):
        """Patch-in for `ClusterClientService._fetch_rpc_info`.

        Describes event-loops only for those event-loops already known to the
        service, thus new connections must be injected into the service.
        """
        connections = self.rpc_service.connections.viewitems()
        return {
            "eventloops": {
                eventloop: [client.address]
                for eventloop, client in connections
            },
        }

    def _authenticate_with_cluster_key(self, protocol, message):
        """Patch-in for `Authenticate` calls.

        This ought to always return the correct digest because it'll be using
        the same shared-secret as the cluster.
        """
        self.ensureSharedSecret()
        return Cluster().authenticate(message)


class MockClusterToRegionRPCFixture(MockClusterToRegionRPCFixtureBase):
    """Patch in a stub region RPC implementation to enable end-to-end testing.

    Use this in *cluster* tests when you're not running with a reactor, or
    when you need fine-grained control over IO. This has low overhead and is
    useful for writing tests where there are obvious points where you can pump
    IO "by hand".

    Example usage (assuming `inlineCallbacks`)::

      fixture = self.useFixture(MockClusterToRegionRPCFixture())
      yield fixture.starting  # Wait for the fixture to start.

      protocol, io = fixture.makeEventLoop(region.Identify)
      protocol.Identify.return_value = defer.succeed({"ident": "foobar"})

      client = getRegionClient()
      result = client(region.Identify)
      io.flush()  # Call this in the reactor thread.

      self.assertThat(result, ...)

    """

    def connect(self, cluster, region):
        """Wire up a connection between cluster and region.

        :type cluster: `twisted.internet.interfaces.IProtocol`
        :type region: `twisted.internet.interfaces.IProtocol`
        :returns: py:class:`twisted.test.iosim.IOPump`
        """
        return iosim.connect(
            region, iosim.makeFakeServer(region),
            cluster, iosim.makeFakeClient(cluster),
            debug=False,  # Debugging is useful, but too noisy by default.
        )


class MockLiveClusterToRegionRPCFixture(MockClusterToRegionRPCFixtureBase):
    """Patch in a stub region RPC implementation to enable end-to-end testing.

    This differs from `MockClusterToRegionRPCFixture` in that the connections
    between the region and the cluster are _live_, by which I mean that
    they're connected by reactor-managed IO, rather than by an `IOPump`. This
    means that the reactor must be running in order to use this fixture.

    Use this in *cluster* tests where the reactor is running, for example when
    using `MAASTwistedRunTest` or its siblings. There's a slightly greater
    overhead than when using `MockClusterToRegionRPCFixture`, but it's not
    huge. You must be careful to follow the usage instructions otherwise
    you'll be plagued by dirty reactor errors.

    Example usage (assuming `inlineCallbacks`)::

      fixture = self.useFixture(MockLiveClusterToRegionRPCFixture())
      protocol, connecting = fixture.makeEventLoop(region.Identify)
      protocol.Identify.return_value = defer.succeed({"ident": "foobar"})

      # This allows the connections to get established via IO through the
      # reactor. The result of `connecting` is a callable that arranges for
      # the correct shutdown of the connections being established.
      self.addCleanup((yield connecting))

      client = getRegionClient()
      result = yield client(region.Identify)
      self.assertThat(result, ...)

    """

    def setUp(self):
        self.sockdir = TempDirectory()  # Place for UNIX sockets.
        self.socknames = itertools.imap(unicode, itertools.count(1))
        return super(MockLiveClusterToRegionRPCFixture, self).setUp()

    def asyncStart(self):
        super(MockLiveClusterToRegionRPCFixture, self).asyncStart()

        def started(result):
            self.sockdir.setUp()
            return result

        self.starting.addCallback(started)

    def asyncStop(self):
        super(MockLiveClusterToRegionRPCFixture, self).asyncStop()

        def stopped(result):
            self.sockdir.cleanUp()
            return result

        self.stopping.addCallback(stopped)

    @inlineCallbacks
    def connect(self, cluster, region):
        """Wire up a connection between cluster and region.

        Uses a UNIX socket to very rapidly connect the two ends.

        :type cluster: `twisted.internet.interfaces.IProtocol`
        :type region: `twisted.internet.interfaces.IProtocol`
        """
        # Wire up the region and cluster protocols via the sockfile.
        sockfile = path.join(self.sockdir.path, next(self.socknames))

        class RegionFactory(Factory):
            def buildProtocol(self, addr):
                return region

        endpoint_region = endpoints.UNIXServerEndpoint(reactor, sockfile)
        port = yield endpoint_region.listen(RegionFactory())

        endpoint_cluster = endpoints.UNIXClientEndpoint(reactor, sockfile)
        client = yield endpoints.connectProtocol(endpoint_cluster, cluster)

        # Wait for the client to be fully connected. Because onReady will have
        # been capped-off by now (see ClusterClient.connectionMade) this will
        # not raise any exceptions. In some ways this is convenient because it
        # allows the resulting issues to be encountered within test code.
        yield client.ready.get()

        @inlineCallbacks
        def shutdown():
            # We need to make sure that everything is shutdown correctly. TLS
            # seems to make this even more important: it complains loudly if
            # connections are not closed cleanly. An interesting article to
            # read now is Jono Lange's "How to Disconnect in Twisted, Really"
            # <http://mumak.net/stuff/twisted-disconnect.html>.
            yield port.loseConnection()
            yield port.deferred
            if region.transport is not None:
                yield region.transport.loseConnection()
                yield region.onConnectionLost
            if client.transport is not None:
                yield client.transport.loseConnection()
                yield client.onConnectionLost

        # Fixtures don't wait for deferred work in clean-up tasks (or anywhere
        # else), so we can't use `self.addCleanup(shutdown)` here. We need to
        # get the user to add `shutdown` to the clean-up tasks for the *test*,
        # on the assumption they're using a test framework that accommodates
        # deferred work (like testtools with `MAASTwistedRunTest`).
        returnValue(shutdown)


# An iterable of names for new dynamically-created AMP protocol factories.
amp_protocol_factory_names = (
    "AMPTestProtocol#%d".encode("ascii") % seq
    for seq in itertools.count(1))


def make_amp_protocol_factory(*commands):
    """Make a new protocol factory based on `RPCProtocol`."""

    def __init__(self):
        super(cls, self).__init__()
        self._commandDispatch = self._commandDispatch.copy()
        for command in commands:
            # Get a class-level responder, if set.
            responder = getattr(self, command.commandName, None)
            if responder is None:
                # There's no class-level responder, so create an
                # instance-level responder using a Mock.
                responder = Mock(name=command.commandName)
                setattr(self, command.commandName, responder)
            # Register whichever responder we've found.
            self._commandDispatch[command.commandName] = (command, responder)

    name = next(amp_protocol_factory_names)
    cls = type(name, (RPCProtocol,), {"__init__": __init__})

    return cls


def always_succeed_with(result):
    """Return a callable that always returns a successful Deferred.

    The callable allows (and ignores) all arguments, and returns a shallow
    `copy` of `result`.
    """
    def always_succeed(*args, **kwargs):
        return defer.succeed(copy(result))
    return always_succeed


def always_fail_with(result):
    """Return a callable that always returns a failed Deferred.

    The callable allows (and ignores) all arguments, and returns a shallow
    `copy` of `result`.
    """
    def always_fail(*args, **kwargs):
        return defer.fail(copy(result))
    return always_fail


def capture_result(d):
    """Capture a result from a `Deferred` mid-flight.

    Rather than at the end of a callback chain.

    :type d: :py:class:`defer.Deferred`.
    :returns: A no-argument callable that will extract the current result from
        the given `Deferred`, or raise an exception if it has not yet fired.
        See py:func:`extract_result`.
    """
    # We don't need to use a Deferred here, but it's convenient because it
    # pairs well with extract_result().
    dest = defer.Deferred()

    def capture(result):
        dest.callback(result)
        return result
    d.addBoth(capture)

    return lambda: extract_result(dest)
