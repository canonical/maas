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
    "are_valid_tls_parameters",
    "call_responder",
    "ClusterToRegionRPCFixture",
    "make_amp_protocol_factory",
    "TwistedLoggerFixture",
]

import collections
import itertools
import operator

import fixtures
from fixtures import Fixture
from maastesting.factory import factory
from mock import (
    Mock,
    sentinel,
    )
import provisioningserver
from provisioningserver.rpc.clusterservice import (
    ClusterClient,
    ClusterClientService,
    )
from testtools.matchers import (
    AllMatch,
    IsInstance,
    MatchesAll,
    MatchesDict,
    )
from testtools.monkey import MonkeyPatcher
from twisted.internet import ssl
from twisted.internet.task import Clock
from twisted.protocols import amp
from twisted.python import log
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
        # Convert remote errors back into local errors using the
        # command's error map if possible.
        error.trap(amp.RemoteAmpError)
        error_type = command.reverseErrors.get(
            error.value.errorCode, amp.UnknownRemoteError)
        return Failure(error_type(error.value.description))
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

    def setUp(self):
        super(TwistedLoggerFixture, self).setUp()
        self.addCleanup(
            operator.setitem, self.logs, slice(None), [])
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


class ClusterToRegionRPCFixture(fixtures.Fixture):
    """Patch in a stub region RPC implementation to enable end-to-end testing.

    Use this in *cluster* tests.

    Example usage::

      fixture = self.useFixture(ClusterToRegionRPCFixture())
      protocol, io = fixture.makeEventLoop(region.Identify)
      protocol.Identify.return_value = defer.succeed({"ident": "foobar"})

      client = getRegionClient()
      result = client(region.Identify)
      io.flush()  # Call this in the reactor thread.

      self.assertThat(result, ...)

    """

    def setUp(self):
        super(ClusterToRegionRPCFixture, self).setUp()
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
        # We're going to be monkeying with a few things.
        patcher = MonkeyPatcher()
        add_patch = patcher.add_patch
        # Use an inert clock with ClusterClientService so it doesn't update
        # itself except when we ask it to.
        service = ClusterClientService(Clock())
        # Patch it into the global services object.
        service.setName("rpc")
        service.setServiceParent(provisioningserver.services)
        self.addCleanup(service.disownServiceParent)
        # Keep a reference to the RPC service here.
        add_patch(self, "service", service)
        # Pretend event-loops only exist for those connections that already
        # exist. The chicken-and-egg will be resolved by injecting a
        # connection later on.
        add_patch(service, "_get_rpc_info_url", self._get_rpc_info_url)
        add_patch(service, "_fetch_rpc_info", self._fetch_rpc_info)
        # Execute those patches, but add the restore first; if it crashes
        # mid-way this will ensure that things are still put straight.
        self.addCleanup(patcher.restore)
        patcher.patch()
        # Finally, start the service. If the clock is advanced, this will do
        # its usual update() calls, but we've patched out _get_rpc_info_url
        # and _fetch_rpc_info so no traffic will result.
        service.startService()
        self.addCleanup(service.stopService)

    def addEventLoop(self, protocol):
        """Add a new stub event-loop using the given `protocol`.

        The `protocol` should be an instance of `amp.AMP`.

        :returns: py:class:`twisted.test.iosim.IOPump`
        """
        eventloop = factory.make_name("eventloop")
        address = factory.getRandomIPAddress(), factory.pick_port()
        client = ClusterClient(address, eventloop, self.service)
        return iosim.connect(
            protocol, iosim.makeFakeServer(protocol),
            client, iosim.makeFakeClient(client),
            debug=False,  # Debugging is useful, but too noisy by default.
        )

    def makeEventLoop(self, *commands):
        """Make and add a new stub event-loop for the given `commands`.

        See `make_amp_protocol_factory` for details.
        """
        protocol_factory = make_amp_protocol_factory(*commands)
        protocol = protocol_factory()
        return protocol, self.addEventLoop(protocol)

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
        connections = self.service.connections.viewitems()
        return {
            "eventloops": {
                eventloop: [client.address]
                for eventloop, client in connections
            },
        }


# An iterable of names for new dynamically-created AMP protocol factories.
amp_protocol_factory_names = (
    "AMPTestProtocol#%d".encode("ascii") % seq
    for seq in itertools.count(1))


def make_amp_protocol_factory(*commands):
    """Make a new AMP protocol factory."""

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
    cls = type(name, (amp.AMP,), {"__init__": __init__})

    return cls
