# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Common RPC classes and utilties."""
from os import getpid
from socket import gethostname

from twisted.internet.defer import Deferred
from twisted.protocols import amp
from twisted.python.failure import Failure

from provisioningserver.logger import LegacyLogger
from provisioningserver.prometheus.metrics import PROMETHEUS_METRICS
from provisioningserver.rpc.interfaces import IConnection, IConnectionToRegion
from provisioningserver.utils.twisted import (
    asynchronous,
    callOut,
    deferWithTimeout,
)

log = LegacyLogger()

undefined = object()


class Identify(amp.Command):
    """Request the identity of the remote side, e.g. its UUID.

    :since: 1.5
    """

    response = [(b"ident", amp.Unicode())]


class Authenticate(amp.Command):
    """Authenticate the remote side.

    The procedure is as follows:

    - When establishing a new connection, the region and the cluster call
      `Authenticate` on each other, passing a random chunk of data in
      `message`. This message must be unique to avoid replay attacks.

    - The remote side adds some salt to the message, and calculates an HMAC
      digest, keyed with the shared secret.

      The salt is intended to prevent replay attacks: it prevents an intruder
      from authenticating itself by calling `Authenticate` on the caller (or
      another endpoint in the same MAAS installation) and sending the same
      message, receiving the digest and passing it back to the caller.

    - The remote side returns this digest and the salt. The caller performs
      the same calculation, and compares the digests.

    - If the digests match, the connection is put into rotation.

    - If the digests do not match, the connection is closed immediately, and
      an error is logged.

    :since: 1.7
    """

    arguments = [(b"message", amp.String())]
    response = [
        (b"digest", amp.String()),
        (b"salt", amp.String()),  # Is 'salt' the right term here?
    ]
    errors = []


class Ping(amp.Command):
    """Ensure the connection is still good.

    :since: 2.4
    """

    arguments = []
    response = []
    errors = []


class Client:
    """Wrapper around an :class:`amp.AMP` instance.

    Limits the API to a subset of the behaviour of :class:`amp.AMP`'s,
    with alterations to make it suitable for use from a thread outside
    of the reactor.
    """

    def __init__(self, conn):
        super().__init__()
        assert IConnection.providedBy(
            conn
        ), f"{conn!r} does not provide IConnection"
        self._conn = conn

    @property
    def ident(self):
        """Something that identifies the far end of the connection."""
        return self._conn.ident

    @property
    def localIdent(self):
        """Something that identifies this end of the connection."""
        # Testing the interface here is a wart. There should be a separate
        # client for the rack, but that's too much like work right now. Well,
        # it's complicated: ideally the client in the region should actually
        # provide the same interface, and have a `localIdent` property.
        if IConnectionToRegion.providedBy(self._conn):
            return self._conn.localIdent
        else:
            raise NotImplementedError(
                "Client localIdent is only available in the rack."
            )

    @property
    def address(self):
        """Return the address of the far end of the connection."""
        # Testing the interface here is a wart. There should be a separate
        # client for the rack, but that's too much like work right now. Well,
        # it's complicated: ideally the client in the region should actually
        # provide the same interface, and have an `address` property.
        if IConnectionToRegion.providedBy(self._conn):
            return self._conn.address
        else:
            raise NotImplementedError(
                "Client address is only available in the rack."
            )

    def _global_intercept_errback(self, failure):
        """Intercept exceptions for every call and take actions."""
        # Due to https://bugs.launchpad.net/maas/+bug/2029417 it might be that a connection is actually
        # closed, but we still try to use it. In such case, we close the connection here as soon as we detect it.
        if (
            failure.check(RuntimeError)
            and "the handler is closed" in failure.getErrorMessage()
        ):
            log.err(
                f"Closed handler detected! Dropping the connection '{self.ident}' and forwarding the exception."
            )
            if self._conn.transport:
                self._conn.transport.loseConnection()

        # re-raise always!
        failure.raiseException()

    @PROMETHEUS_METRICS.record_call_latency(
        "maas_rack_region_rpc_call_latency",
        get_labels=lambda args, kwargs, retval: {"call": args[1].__name__},
    )
    @asynchronous
    def __call__(self, cmd, *args, **kwargs):
        """Call a remote RPC method.

        This is how the client is normally used.

        :note:
            Though the call signature shows positional arguments, their use is
            an error. They're in the signature is so this method can detect
            them and provide a better error message than that from Python.
            Python's error message when arguments don't match the call's
            signature is not great at best, but it also makes it hard to
            figure out the receiver when the `TypeError` is raised in a
            different stack from the caller's, e.g. when calling into the
            Twisted reactor from a thread.

        :param cmd: The `amp.Command` child class representing the remote
            method to be invoked.
        :param kwargs: Any parameters to the remote method.  Only keyword
            arguments are accepted.
        :return: A deferred result.  Call its `wait` method (with a timeout
            in seconds) to block on the call's completion.
        """
        self._conn.in_use = True

        def _free_conn():
            self._conn.in_use = False

        if len(args) != 0:
            receiver_name = "{}.{}".format(
                self.__module__,
                self.__class__.__name__,
            )
            raise TypeError(
                "%s called with %d positional arguments, %r, but positional "
                "arguments are not supported. Usage: client(command, arg1="
                "value1, ...)" % (receiver_name, len(args), args)
            )

        timeout = kwargs.pop("_timeout", undefined)
        if timeout is undefined:
            timeout = 120  # 2 minutes
        if timeout is None or timeout <= 0:
            d = self._conn.callRemote(cmd, **kwargs)
            if isinstance(d, Deferred):
                d.addErrback(self._global_intercept_errback)
                d.addBoth(lambda x: callOut(x, _free_conn))
            else:
                _free_conn()
            return d
        else:
            d = deferWithTimeout(timeout, self._conn.callRemote, cmd, **kwargs)
            if isinstance(d, Deferred):
                d.addErrback(self._global_intercept_errback)
                d.addBoth(lambda x: callOut(x, _free_conn))
            else:
                _free_conn()
            return d

    @asynchronous
    def getHostCertificate(self):
        return self._conn.hostCertificate

    @asynchronous
    def getPeerCertificate(self):
        return self._conn.peerCertificate

    @asynchronous
    def isSecure(self):
        return self._conn.peerCertificate is not None

    def __eq__(self, other):
        return type(other) is type(self) and other._conn is self._conn

    def __hash__(self):
        return hash(self._conn)


def make_command_ref(box):
    """Make a textual description of an AMP command box.

    This is intended to help correlating exceptions between distributed parts
    of MAAS. The reference takes the form::

      $hostname:pid=$pid:cmd=$command_name:ask=$ask_sequence

    where:

      * ``hostname`` is the hostname of the machine on which the error
        occurred.

      * ``pid`` is the process ID of where the error originated.

      * ``command_name`` is the AMP command name.

      * ``ask_sequence`` is the sequence number used for RPC calls that expect
        a reply; see http://amp-protocol.net/ for details.

    An extended variant might be valuable: a ``make_box_ref`` function that
    returns unambiguous references for command, answer, and errors boxes.
    """
    return "%s:pid=%d:cmd=%s:ask=%s" % (
        gethostname(),
        getpid(),
        box[amp.COMMAND].decode("ascii"),
        box.get(amp.ASK, b"none").decode("ascii"),
    )


class RPCProtocol(amp.AMP):
    """A specialisation of `amp.AMP`.

    It's hard to track exactly when an `amp.AMP` protocol is connected to its
    transport, or disconnected, from the "outside". It's necessary to subclass
    and override `connectionMade` and `connectionLost` and signal from there,
    which is what this class does.

    :ivar onConnectionMade: A `Deferred` that fires when `connectionMade` has
        been called, i.e. this protocol is now connected.
    :ivar onConnectionLost: A `Deferred` that fires when `connectionLost` has
        been called, i.e. this protocol is no longer connected.
    """

    def __init__(self):
        super().__init__()
        self.onConnectionMade = Deferred()
        self.onConnectionLost = Deferred()

    def connectionMade(self):
        super().connectionMade()
        self.onConnectionMade.callback(None)

    def connectionLost(self, reason):
        super().connectionLost(reason)
        self.onConnectionLost.callback(None)

    def _sendBoxCommand(self, command, box, requiresAnswer=True):
        """Override `_sendBoxCommand` to log the sent RPC message."""
        box[amp.COMMAND] = command
        return super()._sendBoxCommand(
            command, box, requiresAnswer=requiresAnswer
        )

    def dispatchCommand(self, box):
        """Call up, but coerce errors into non-fatal failures.

        This is called by `_commandReceived`, which is responsible for
        capturing unhandled errors and transmitting them back to the remote
        side. It does this within a :class:`amp.QuitBox` which immediately
        disconnects the transport after being transmitted.

        Here we capture all errors before `_commandReceived` sees them and
        wrap them with :class:`amp.RemoteAmpError`. This prevents the
        disconnecting behaviour.
        """
        d = super().dispatchCommand(box)

        def coerce_error(failure):
            if failure.check(amp.RemoteAmpError):
                return failure
            else:
                command = box[amp.COMMAND]
                command_ref = make_command_ref(box)
                log.err(
                    failure,
                    (
                        "Unhandled failure dispatching AMP command. This is "
                        "probably a bug. Please ensure that this error is handled "
                        "within application code or declared in the signature of "
                        "the %s command. [%s]"
                    )
                    % (command, command_ref),
                )
                return Failure(
                    amp.RemoteAmpError(
                        amp.UNHANDLED_ERROR_CODE,
                        b"Unknown Error [%s]" % command_ref.encode("ascii"),
                        fatal=False,
                        local=failure,
                    )
                )

        return d.addErrback(coerce_error)

    def unhandledError(self, failure):
        """Terminal errback, after application code has seen the failure.

        `amp.BoxDispatcher.unhandledError` calls the `amp.IBoxSender`'s
        `unhandledError`. In the default implementation this disconnects the
        transport.

        Here we instead log the failure but do *not* disconnect because it's
        too disruptive to the running of MAAS.
        In case of https://bugs.launchpad.net/maas/+bug/2029417, we drop the connection instead.
        """
        if (
            failure.check(RuntimeError)
            and "the handler is closed" in failure.getErrorMessage()
        ):
            super().unhandledError(failure)
            log.err(
                "The handler is closed and the exception was unhandled. The connection is dropped."
            )
        else:
            log.err(
                failure,
                (
                    "Unhandled failure during AMP request. This is probably a bug. "
                    "Please ensure that this error is handled within application "
                    "code."
                ),
            )

    @Ping.responder
    def ping(self):
        """ping()

        Implementation of
        :py:class:`~provisioningserver.rpc.common.Ping`.
        """
        return {}
