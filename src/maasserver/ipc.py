# Copyright 2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""
Inter-process communication between processes.

This defines the communication between the master regiond process and the
worker regiond processes. All worker regiond process connect to the master
socket.
"""

import os

from provisioningserver.logger import LegacyLogger
from provisioningserver.rpc.common import RPCProtocol
from provisioningserver.utils.twisted import asynchronous
from twisted.application import service
from twisted.internet.defer import (
    CancelledError,
    inlineCallbacks,
)
from twisted.internet.endpoints import (
    connectProtocol,
    UNIXClientEndpoint,
    UNIXServerEndpoint,
)
from twisted.internet.protocol import Factory
from twisted.protocols import amp


log = LegacyLogger()


def get_ipc_socket_path():
    """Return the path to the IPC socket."""
    return os.environ.get(
        'MAAS_IPC_SOCKET_PATH', os.path.join(
            os.environ.get('MAAS_ROOT', '/var/lib/maas'), 'maas-regiond.sock'))


class WorkerIdentify(amp.Command):
    """Register worker with master using PID."""

    arguments = [
        (b"pid", amp.Integer()),
    ]
    response = []
    errors = []


class IPCMaster(RPCProtocol):
    """The IPC master side of the protocol."""

    def connectionLost(self, reason):
        """Client disconnected."""
        self.factory.service.unregisterWorker(self, reason)

    @WorkerIdentify.responder
    def worker_identify(self, pid):
        """Worker identified with master."""
        self.factory.service.registerWorker(pid, self)
        return {}


class IPCMasterService(service.Service, object):
    """
    IPC master service.

    Provides the master side of the IPC communication between the workers.
    """

    connections = None

    def __init__(self, reactor, workers=None, socket_path=None):
        super(IPCMasterService, self).__init__()
        self.reactor = reactor
        self.workers = workers
        self.socket_path = socket_path
        if self.socket_path is None:
            self.socket_path = get_ipc_socket_path()
        if os.path.exists(self.socket_path):
            os.remove(self.socket_path)
        self.endpoint = UNIXServerEndpoint(reactor, self.socket_path)
        self.port = None
        self.connections = {}
        self.factory = Factory.forProtocol(IPCMaster)
        self.factory.service = self

    @asynchronous
    def startService(self):
        """Start listening on UNIX socket."""
        super(IPCMasterService, self).startService()
        self.starting = self.endpoint.listen(self.factory)

        def save_port(port):
            self.port = port

        def log_failure(failure):
            if failure.check(CancelledError):
                log.msg("IPCMasterService start-up has been cancelled.")
            else:
                log.err(failure, "IPCMasterService start-up failed.")

        self.starting.addCallback(save_port)
        self.starting.addErrback(log_failure)

        # Twisted's service framework does not track start-up progress, i.e.
        # it does not check for Deferreds returned by startService(). Here we
        # return a Deferred anyway so that direct callers (esp. those from
        # tests) can easily wait for start-up.
        return self.starting

    @asynchronous
    @inlineCallbacks
    def stopService(self):
        """Stop listening."""
        self.starting.cancel()
        if self.port:
            self.port, port = None, self.port
            yield port.stopListening()
        for conn in self.connections.values():
            try:
                yield conn.transport.loseConnection()
            except:
                log.err(None, "Failure when closing IPC connection.")
        yield super(IPCMasterService, self).stopService()

    def registerWorker(self, pid, conn):
        """Register the worker with `pid` using `conn`."""
        self.connections[pid] = conn
        log.msg("Worker pid:%d IPC connected." % pid)

    def getPIDFromConnection(self, conn):
        """Get the PID from the connection."""
        for pid, reg in self.connections.items():
            if reg == conn:
                return pid

    def unregisterWorker(self, conn, reason):
        """Unregister the worker with `pid` because of `reason`."""
        pid = self.getPIDFromConnection(conn)
        if pid:
            del self.connections[pid]
            log.msg("Worker pid:%d IPC disconnected." % pid)
            if self.workers:
                self.workers.killWorker(pid)


class IPCWorker(RPCProtocol):
    """The IPC client side of the protocol."""

    def connectionMade(self):
        super(IPCWorker, self).connectionMade()
        self.callRemote(WorkerIdentify, pid=os.getpid())


class IPCWorkerService(service.Service, object):
    """
    IPC worker service.

    Provides the worker side of the IPC communication to the master.
    """

    def __init__(self, reactor, socket_path=None):
        super(IPCWorkerService, self).__init__()
        self.reactor = reactor
        self.socket_path = socket_path
        if self.socket_path is None:
            self.socket_path = get_ipc_socket_path()
        self.endpoint = UNIXClientEndpoint(reactor, self.socket_path)
        self.protocol = None

    @asynchronous
    def startService(self):
        """Connect to UNIX socket."""
        super(IPCWorkerService, self).startService()
        self.starting = connectProtocol(self.endpoint, IPCWorker())

        def save_protocol(protocol):
            self.protocol = protocol

        def log_failure(failure):
            if failure.check(CancelledError):
                log.msg("IPCWorkerService start-up has been cancelled.")
            else:
                log.err(failure, "IPCWorkerService start-up failed.")

        self.starting.addCallback(save_protocol)
        self.starting.addErrback(log_failure)

        # Twisted's service framework does not track start-up progress, i.e.
        # it does not check for Deferreds returned by startService(). Here we
        # return a Deferred anyway so that direct callers (esp. those from
        # tests) can easily wait for start-up.
        return self.starting

    @asynchronous
    def stopService(self):
        """Disconnect from UNIX socket."""
        self.starting.cancel()
        if self.protocol:
            self.protocol, protocol = None, self.protocol
            if protocol.transport:
                protocol.transport.loseConnection()
        return super(IPCWorkerService, self).stopService()
