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
    "TwistedLoggerFixture",
]

import collections
import operator

from fixtures import Fixture
from testtools.matchers import (
    AllMatch,
    IsInstance,
    MatchesAll,
    MatchesDict,
    )
from twisted.internet import ssl
from twisted.protocols import amp
from twisted.python import log
from twisted.python.failure import Failure


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
