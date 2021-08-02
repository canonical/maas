import asyncio
from collections import defaultdict
import logging
import random
import socket

import capnp
from twisted.application import service
from twisted.internet.defer import (
    CancelledError,
    Deferred,
    inlineCallbacks,
    succeed,
)

from maasserver.rpc.capnp.region import RegionController
from provisioningserver.rpc import exceptions
from provisioningserver.utils.events import EventGroup
from provisioningserver.utils.twisted import (
    asynchronous,
    callOut,
    deferWithTimeout,
    FOREVER,
)

log = logging.getLogger(__name__)


class CapnpService:
    rpc_interface = None
    io_timeout = 0.1
    io_buffer_size = 4096

    def __init__(self, service):
        self.service = service
        self.ident = None

    async def run_reader(self):
        while self.retry:
            try:
                data = await asyncio.wait_for(
                    self.reader.read(self.io_buffer_size),
                    timeout=self.io_timeout,
                )
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                log.error(e)
                return False
            await self.server.write(data)
        return True

    async def run_writer(self):
        while self.retry:
            try:
                data = await asyncio.wait_for(
                    self.server.read(self.io_buffer_size),
                    timeout=self.io_timeout,
                )
                self.writer.write(data.tobytes())
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                log.error(e)
                return False
        return True

    async def serve(self, reader, writer):
        self.server = capnp.TwoPartyServer(
            bootstrap=self.rpc_interface(self, self.service)
        )
        self.reader = reader
        self.writer = writer
        self.retry = True

        coroutines = [self.run_reader(), self.run_writer()]
        tasks = asyncio.gather(*coroutines, return_exceptions=True)

        while True:
            self.server.poll_once()
            if self.reader.at_eof():
                self.retry = False
                break
            await asyncio.sleep(0.1)

        await tasks

        if self.ident is not None:
            self.service._removeConnectionFor(self.ident, self.server)


class RegionCapnpService(CapnpService):
    rpc_interface = RegionController


def connect(service, server):
    async def serve(reader, writer):
        srvr = server(service)
        await srvr.serve(reader, writer)

    return serve


async def run(service, addr, port):
    server = await asyncio.start_server(
        connect(service, RegionCapnpService),
        addr,
        str(port),
        family=socket.AF_INET,
    )

    async with server:
        await server.serve_forever()


class CapnpRPCService(service.Service):
    connections = None

    def __init__(self, ipc_worker):
        self.ipc_worker = ipc_worker
        self.server_deferred = None
        self.addr = "0.0.0.0"
        self.port = 5555
        self.connections = {}
        self.waiters = defaultdict(set)
        self.events = EventGroup("connected", "disconnected")

        super(CapnpRPCService, self).__init__()

    @asynchronous
    def startService(self):
        super().startService()
        self.server_deferred = Deferred.fromFuture(
            asyncio.ensure_future(run(self, self.addr, self.port))
        )
        return self.server_deferred

    @asynchronous
    @inlineCallbacks
    def stopService(self):
        """TODO Stop listening."""
        self.server_deferred.cancel()
        yield super().stopService()

    @asynchronous(timeout=FOREVER)
    def getPort(self):
        return self.port

    @asynchronous(timeout=FOREVER)
    def getClientFor(self, system_id, timeout=30):
        log.info("get client {}".format(system_id))
        d = self._getConnectionFor(system_id, timeout)

        def cancelled(failure):
            failure.trap(CancelledError)
            raise exceptions.NoConnectionsAvailable(
                "Unable to connect to rack controller %s; no connections "
                "available." % system_id,
                uuid=system_id,
            )

        def cb_client(connection):
            return CapnpRackClient(connection)

        return d.addCallbacks(cb_client, cancelled)

    @asynchronous(timeout=FOREVER)
    def getClientFromIdentifiers(self, identifiers, timeout=30):
        log.info("get clients for {}".format(identifiers))
        d = self._getConnectionFromIdentifiers(identifiers, timeout)

        def cancelled(failure):
            failure.trap(CancelledError)
            raise exceptions.NoConnectionsAvailable(
                "Unable to connect to any rack controller %s; no connections "
                "available." % ",".join(identifiers)
            )

        def cb_client(conns):
            connection = random.choice(conns)
            return CapnpRackClient(connection)

        return d.addCallbacks(cb_client, cancelled)

    @asynchronous(timeout=FOREVER)
    def getAllClients(self):
        return [CapnpRackClient(conn) for conn in self.connections.values()]

    @asynchronous(timeout=FOREVER)
    def getRandomClient(self):
        """Return a random connected :class:`RackClient`."""
        if len(self.connections) == 0:
            raise exceptions.NoConnectionsAvailable(
                "Unable to connect to any rack controller; no connections "
                "available."
            )
        else:
            conn = random.choice(self.connections.values())
            return CapnpRackClient(conn)

    def _addConnectionFor(self, ident, connection):
        """Adds `connection` to the set of connections for `ident`."""
        log.info("add conn {} on {}".format(connection, ident))
        self.connections[ident] = connection
        self.events.connected.fire(ident)
        pass

    def _removeConnectionFor(self, ident, connection):
        """Removes `connection` from the set of connections for `ident`."""
        log.info("remove conn {} on {}".format(connection, ident))
        self.connections.pop(ident)
        self.events.disconnected.fire(ident)

    def _getConnectionFor(self, ident, timeout):
        """Wait up to `timeout` seconds for a connection for `ident`."""
        conn = self.connections.get(ident)
        if conn is None:
            waiters = self.waiters[ident]
            d = deferWithTimeout(timeout)
            d.addBoth(callOut, waiters.discard, d)
            waiters.add(d)
            return d
        else:
            return succeed(conn)

    def _getConnectionFromIdentifiers(self, identifiers, timeout):
        """Wait up to `timeout` seconds for at least one connection from
        `identifiers`.
        """
        matched_connections = [
            self.connections[k]
            for k in self.connections.keys()
            if k in identifiers
        ]
        if len(matched_connections) > 0:
            return succeed(matched_connections)
        else:
            # No connections for any of the identifiers. Wait for at least one
            # connection to appear during the timeout.

            def discard_all(waiters, identifiers, d):
                """Discard all defers in the waiters for all identifiers."""
                for ident in identifiers:
                    waiters[ident].discard(d)

            def cb_conn_list(conn):
                """Convert connection into a list."""
                return [conn]

            d = deferWithTimeout(timeout)
            d.addBoth(callOut, discard_all, self.waiters, identifiers, d)
            d.addCallback(cb_conn_list)
            for ident in identifiers:
                self.waiters[ident].add(d)
            return d


class CapnpRackClient:
    def __init__(self, connection=None):
        self._conn = connection
        self.ident = None

    @asynchronous
    def __call__(self, cmd, *args, **kwargs):
        """Call a remote RPC method."""
        # must return a deferred
        log.info("called {}".format(cmd))
        # TODO wire this to the capnp interface
        return succeed(None)
