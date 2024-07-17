# Copyright 2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""
Inter-process communication between processes.

This defines the communication between the master regiond process and the
worker regiond processes. All worker regiond process connect to the master
socket.
"""

from datetime import timedelta
from functools import partial
import os
from socket import gethostname

from netaddr import IPAddress
from twisted.application import service
from twisted.internet.defer import CancelledError, inlineCallbacks
from twisted.internet.endpoints import (
    connectProtocol,
    UNIXClientEndpoint,
    UNIXServerEndpoint,
)
from twisted.internet.protocol import Factory
from twisted.internet.task import LoopingCall
from twisted.protocols import amp

from maasserver import eventloop, workers
from maasserver.enum import SERVICE_STATUS
from maasserver.models.node import RackController, RegionController
from maasserver.models.regioncontrollerprocess import RegionControllerProcess
from maasserver.models.regioncontrollerprocessendpoint import (
    RegionControllerProcessEndpoint,
)
from maasserver.models.regionrackrpcconnection import RegionRackRPCConnection
from maasserver.models.service import Service
from maasserver.models.timestampedmodel import now
from maasserver.utils.orm import transactional
from maasserver.utils.threads import deferToDatabase
from provisioningserver.logger import LegacyLogger
from provisioningserver.path import get_maas_data_path
from provisioningserver.rpc.common import RPCProtocol
from provisioningserver.utils.network import (
    get_all_interface_addresses,
    get_all_interface_source_addresses,
)
from provisioningserver.utils.twisted import (
    asynchronous,
    DeferredValue,
    synchronous,
)

log = LegacyLogger()


def get_ipc_socket_path():
    """Return the path to the IPC socket."""
    return os.environ.get(
        "MAAS_IPC_SOCKET_PATH", get_maas_data_path("maas-regiond.sock")
    )


class WorkerIdentify(amp.Command):
    """Register worker with master using PID."""

    arguments = [(b"pid", amp.Integer())]
    response = [(b"process_id", amp.Integer())]
    errors = []


class RPCEndpointPublish(amp.Command):
    """Publish the RPC endpoint for the process as open."""

    arguments = [(b"pid", amp.Integer()), (b"port", amp.Integer())]
    response = []
    errors = []


class RPCRegisterConnection(amp.Command):
    """Register worker has connection from RPC client."""

    arguments = [
        (b"pid", amp.Integer()),
        (b"connid", amp.Unicode()),
        (b"ident", amp.Unicode()),
        (b"host", amp.Unicode()),
        (b"port", amp.Integer()),
    ]
    response = []
    errors = []


class RPCUnregisterConnection(amp.Command):
    """Unregister worker lost connection from RPC client."""

    arguments = [(b"pid", amp.Integer()), (b"connid", amp.Unicode())]
    response = []
    errors = []


class IPCMaster(RPCProtocol):
    """The IPC master side of the protocol."""

    def connectionLost(self, reason):
        """Client disconnected."""
        return self.factory.service.unregisterWorker(self, reason)

    @WorkerIdentify.responder
    def worker_identify(self, pid):
        """Worker identified with master."""
        return self.factory.service.registerWorker(pid, self)

    @RPCEndpointPublish.responder
    def rpc_endpoint_publish(self, pid, port):
        """Worker informed master RPC is opening and listing on `port`."""
        self.factory.service.registerWorkerRPC(pid, port)
        return {}

    @RPCRegisterConnection.responder
    def rpc_register_connection(self, pid, connid, ident, host, port):
        """Register worker has connection from RPC client."""
        self.factory.service.registerWorkerRPCConnection(
            pid, connid, ident, host, port
        )
        return {}

    @RPCUnregisterConnection.responder
    def rpc_unregister_connection(self, pid, connid):
        """Unregister worker lost connection from RPC client."""
        self.factory.service.unregisterWorkerRPCConnection(pid, connid)
        return {}


class IPCMasterService(service.Service):
    """
    IPC master service.

    Provides the master side of the IPC communication between the workers.
    """

    UPDATE_INTERVAL = 60  # 60 seconds.

    REMOVE_INTERVAL = 90  # 90 seconds.

    connections = None

    def __init__(self, reactor, workers=None, socket_path=None):
        super().__init__()
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
        self.updateLoop = LoopingCall(self.update)

    @asynchronous
    def startService(self):
        """Start listening on UNIX socket and create the region controller."""
        super().startService()
        self.starting = self.endpoint.listen(self.factory)

        def save_port(port):
            self.port = port

        @transactional
        def create_region(result):
            RegionController.objects.get_or_create_running_controller()

        def start_update_loop(result):
            self.updateLoopDone = self.updateLoop.start(self.UPDATE_INTERVAL)

        def log_failure(failure):
            if failure.check(CancelledError):
                log.msg("IPCMasterService start-up has been cancelled.")
            else:
                log.err(failure, "IPCMasterService start-up failed.")

        self.starting.addCallback(save_port)
        self.starting.addCallback(partial(deferToDatabase, create_region))
        self.starting.addCallback(start_update_loop)
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
        for data in self.connections.values():
            try:
                yield data["connection"].transport.loseConnection()
            except Exception:
                log.err(None, "Failure when closing IPC connection.")

        @transactional
        def delete_all_processes():
            region = RegionController.objects.get_running_controller()
            region.processes.all().delete()

        @asynchronous
        def stop_update_loop():
            if self.updateLoop.running:
                self.updateLoop.stop()
                return self.updateLoopDone

        yield deferToDatabase(delete_all_processes)
        yield stop_update_loop()
        yield super().stopService()

    @asynchronous
    def registerWorker(self, pid, conn):
        """Register the worker with `pid` using `conn`."""

        @transactional
        def create_process(pid):
            region = RegionController.objects.get_running_controller()
            process, _ = RegionControllerProcess.objects.get_or_create(
                region=region, pid=pid
            )
            return (pid, process.id)

        def log_connected(result):
            pid, process_id = result
            log.msg("Worker pid:%d IPC connected." % pid)
            return result

        def add_to_connections(result):
            pid, process_id = result
            self.connections[pid] = {
                "process_id": process_id,
                "connection": conn,
                "rpc": {
                    "port": None,
                    "connections": set(),
                    "burst_connections": set(),
                },
            }
            return process_id

        @transactional
        def update_service(process_id):
            region = RegionController.objects.get_running_controller()
            self._updateService(region)
            return process_id

        def return_result(process_id):
            return {"process_id": process_id}

        d = deferToDatabase(create_process, pid)
        d.addCallback(log_connected)
        d.addCallback(add_to_connections)
        d.addCallback(partial(deferToDatabase, update_service))
        d.addCallback(return_result)
        return d

    def getPIDFromConnection(self, conn):
        """Get the PID from the connection."""
        for pid, data in self.connections.items():
            if data["connection"] == conn:
                return pid

    @asynchronous
    def unregisterWorker(self, conn, reason):
        """Unregister the worker with `pid` because of `reason`."""
        pid = self.getPIDFromConnection(conn)
        if pid:

            @transactional
            def delete_process(pid):
                process_id = self.connections[pid]["process_id"]
                RegionControllerProcess.objects.filter(id=process_id).delete()
                return pid

            def remove_conn_kill_worker(pid):
                del self.connections[pid]
                if self.workers:
                    self.workers.killWorker(pid)
                return pid

            def log_disconnected(pid):
                log.msg("Worker pid:%d IPC disconnected." % pid)

            d = deferToDatabase(delete_process, pid)
            d.addCallback(remove_conn_kill_worker)
            d.addCallback(log_disconnected)
            return d

    def _getListenAddresses(self, port):
        """Return list of tuple (address, port) for the addresses the worker
        is listening on."""
        addresses = get_all_interface_source_addresses()
        if addresses:
            return {(addr, port) for addr in addresses}
        # There are no non-loopback addresses, so return loopback
        # address as a fallback.
        loopback_addresses = set()
        for addr in get_all_interface_addresses():
            ipaddr = IPAddress(addr)
            if ipaddr.is_link_local():
                continue  # Don't advertise link-local addresses.
            if ipaddr.is_loopback():
                loopback_addresses.add((addr, port))
        return loopback_addresses

    @synchronous
    @transactional
    def _updateEndpoints(self, process, addresses):
        """Update the endpoints for `pid` and `port`."""
        previous_endpoint_ids = set(
            RegionControllerProcessEndpoint.objects.filter(
                process=process
            ).values_list("id", flat=True)
        )
        if addresses:
            for addr, port in addresses:
                (
                    endpoint,
                    created,
                ) = RegionControllerProcessEndpoint.objects.get_or_create(
                    process=process, address=addr, port=port
                )
                if not created:
                    previous_endpoint_ids.remove(endpoint.id)
        RegionControllerProcessEndpoint.objects.filter(
            id__in=previous_endpoint_ids
        ).delete()

    @synchronous
    def _getProcessObjFor(self, pid):
        """Return `RegionControllerProcess` for `pid`."""
        process_id = self.connections[pid]["process_id"]
        try:
            return RegionControllerProcess.objects.get(id=process_id)
        except RegionControllerProcess.DoesNotExist:
            region_obj = RegionController.objects.get_running_controller()
            return RegionControllerProcess.objects.create(
                id=process_id, region=region_obj, pid=pid
            )

    @asynchronous
    def registerWorkerRPC(self, pid, port):
        """Register the worker with `pid` has RPC `port` open."""
        if pid in self.connections:

            @transactional
            def create_endpoints(result):
                pid, port = result
                process = self._getProcessObjFor(pid)
                self._updateEndpoints(process, self._getListenAddresses(port))
                return result

            def set_result(result):
                pid, port = result
                self.connections[pid]["rpc"]["port"] = port
                self.connections[pid]["rpc"]["connections"] = {}
                self.connections[pid]["rpc"]["burst_connections"] = {}
                return result

            def log_rpc_open(result):
                log.msg(
                    "Worker pid:%d opened RPC listener on port:%s." % result
                )

            d = deferToDatabase(create_endpoints, (pid, port))
            d.addCallback(set_result)
            d.addCallback(log_rpc_open)
            return d

    @synchronous
    def _registerConnection(self, process, ident, host, port, force_save=True):
        rackd = RackController.objects.get(system_id=ident)
        endpoint, _ = RegionControllerProcessEndpoint.objects.get_or_create(
            process=process, address=host, port=port
        )
        connection, created = RegionRackRPCConnection.objects.get_or_create(
            endpoint=endpoint, rack_controller=rackd
        )
        if not created and force_save:
            # Force the save so that signals connected to the
            # RegionRackRPCConnection are performed.
            connection.save(force_update=True)
        return (connection, created)

    def registerWorkerRPCConnection(self, pid, connid, ident, host, port):
        """Register the worker with `pid` has RPC an RPC connection."""
        if pid in self.connections:

            @transactional
            def register_connection(pid, connid, ident, host, port):
                process = self._getProcessObjFor(pid)
                _, created = self._registerConnection(
                    process, ident, host, port
                )
                return (pid, connid, ident, host, port, created)

            def log_connection(result):
                pid, conn = result[0], result[1:]
                log.msg(
                    "Worker pid:%d registered RPC connection to %s."
                    % (pid, conn[1:-1])
                )
                return conn

            def set_result(conn):
                connid, *conn, created = conn
                if created:
                    self.connections[pid]["rpc"]["connections"][connid] = (
                        tuple(conn)
                    )
                else:
                    self.connections[pid]["rpc"]["burst_connections"][
                        connid
                    ] = tuple(conn)

            d = deferToDatabase(
                register_connection, pid, connid, ident, host, port
            )
            d.addCallback(log_connection)
            d.addCallback(set_result)
            return d

    @transactional
    def _unregisterConnection(self, process, ident, host, port):
        """Unregister the connection into the database."""
        try:
            endpoint = RegionControllerProcessEndpoint.objects.get(
                process=process, address=host, port=port
            )
        except RegionControllerProcessEndpoint.DoesNotExist:
            # Endpoint no longer exists, nothing to do.
            pass
        else:
            try:
                rackd = RackController.objects.get(system_id=ident)
            except RackController.DoesNotExist:
                # No rack controller, nothing to do.
                pass
            else:
                RegionRackRPCConnection.objects.filter(
                    endpoint=endpoint, rack_controller=rackd
                ).delete()

    def unregisterWorkerRPCConnection(self, pid, connid):
        """Unregister connection for worker with `pid`."""
        if pid in self.connections:
            connections = self.connections[pid]["rpc"]["connections"]
            conn = connections.get(connid, None)
            if conn is not None:

                @transactional
                def unregister_connection(pid, connid, ident, host, port):
                    process = self._getProcessObjFor(pid)
                    self._unregisterConnection(process, ident, host, port)
                    return (pid, connid, ident, host, port)

                def log_disconnect(result):
                    pid, conn = result[0], result[1:]
                    log.msg(
                        "Worker pid:%d lost RPC connection to %s."
                        % (pid, conn[1:])
                    )
                    return conn

                def set_result(conn):
                    connid = conn[0]
                    connections.pop(connid, None)

                d = deferToDatabase(unregister_connection, pid, connid, *conn)
                d.addCallback(log_disconnect)
                d.addCallback(set_result)
                return d
            else:
                burst_connections = self.connections[pid]["rpc"][
                    "burst_connections"
                ]
                conn = burst_connections.pop(connid, None)
                if conn:
                    log.msg(
                        "Worker pid:%d lost burst connection to %s."
                        % (pid, conn[1:])
                    )

    @synchronous
    def _updateConnections(self, process, connections):
        """Update the existing RPC connections into this region.

        This is needed because the database could get in an incorrect state
        because another process removed its references in the database and
        the existing connections need to be re-created.
        """
        if not connections:
            RegionRackRPCConnection.objects.filter(
                endpoint__process=process
            ).delete()
        else:
            previous_connection_ids = set(
                RegionRackRPCConnection.objects.filter(
                    endpoint__process=process
                ).values_list("id", flat=True)
            )
            for _, (ident, host, port) in connections.items():
                db_conn, _ = self._registerConnection(
                    process, ident, host, port, force_save=False
                )
                previous_connection_ids.discard(db_conn.id)
            if previous_connection_ids:
                RegionRackRPCConnection.objects.filter(
                    id__in=previous_connection_ids
                ).delete()

    @synchronous
    def _updateService(self, region_obj):
        """Update the service status for this region."""
        Service.objects.create_services_for(region_obj)
        number_of_processes = len(self.connections)
        not_running_count = workers.MAX_WORKERS_COUNT - number_of_processes
        if not_running_count > 0:
            if number_of_processes == 1:
                process_text = "process"
            else:
                process_text = "processes"
            Service.objects.update_service_for(
                region_obj,
                "regiond",
                SERVICE_STATUS.DEGRADED,
                "%d %s running but %d were expected."
                % (
                    number_of_processes,
                    process_text,
                    workers.MAX_WORKERS_COUNT,
                ),
            )
        else:
            Service.objects.update_service_for(
                region_obj, "regiond", SERVICE_STATUS.RUNNING, ""
            )

    @synchronous
    @transactional
    def _update(self):
        """Repopulate the database with process, endpoint, and connection
        information."""
        # Get the region controller and update its hostname and last
        # updated time.
        region_obj = RegionController.objects.get_running_controller()
        hostname = gethostname()
        if region_obj.hostname != hostname:
            region_obj.hostname = hostname
            region_obj.save()

        # Get all the existing processes for the region controller. This is
        # used to remove the old processes that we did not update.
        previous_process_ids = set(
            RegionControllerProcess.objects.filter(
                region=region_obj
            ).values_list("id", flat=True)
        )

        # Loop through all the current workers to update the records in the
        # database. Caution is needed because other region controllers can
        # remove expired processes.
        for pid, conn in self.connections.items():
            process = self._getProcessObjFor(pid)
            process.updated = now()
            process.save()
            if conn["rpc"]["port"]:
                # Update the endpoints for the provided port.
                self._updateEndpoints(
                    process, self._getListenAddresses(conn["rpc"]["port"])
                )
            else:
                # RPC is not running, no endpoints.
                self._updateEndpoints(process, [])
            self._updateConnections(process, conn["rpc"]["connections"].copy())
            previous_process_ids.discard(process.id)

        # Delete all the old processes that are dead.
        if previous_process_ids:
            RegionControllerProcess.objects.filter(
                id__in=previous_process_ids
            ).delete()

        # Remove any old processes not owned by this controller. Every
        # controller should update its processes based on the `UPDATE_INTERVAL`
        # any that are older than `REMOVE_INTERVAL` are dropped.
        remove_before_time = now() - timedelta(seconds=self.REMOVE_INTERVAL)
        RegionControllerProcess.objects.exclude(region=region_obj).filter(
            updated__lte=remove_before_time
        ).delete()

        # Update the status of this regiond service for this region based on
        # the number of running processes.
        self._updateService(region_obj)

        # Update the status of all regions that have no processes running.
        for other_region in RegionController.objects.exclude(
            system_id=region_obj.id
        ).prefetch_related("processes"):
            # Use len with `all` so the prefetch cache is used.
            if len(other_region.processes.all()) == 0:
                Service.objects.mark_dead(other_region, dead_region=True)

    @asynchronous
    def update(self):
        def ignore_cancel(failure):
            failure.trap(CancelledError)

        d = deferToDatabase(self._update)
        d.addErrback(ignore_cancel)
        d.addErrback(
            log.err,
            "Failed to update regiond's processes and endpoints; "
            "%s record's may be out of date" % (eventloop.loop.name,),
        )
        return d


class IPCWorker(RPCProtocol):
    """The IPC client side of the protocol."""

    def connectionMade(self):
        super().connectionMade()

        # Identify with the master process.
        d = self.callRemote(WorkerIdentify, pid=os.getpid())

        # Set the values on the service so the worker knows its connected
        # to the master process.
        def set_defers(result):
            self.service.protocol.set(self)
            self.service.processId.set(result["process_id"])

        d.addCallback(set_defers)
        return d


class IPCWorkerService(service.Service):
    """
    IPC worker service.

    Provides the worker side of the IPC communication to the master.
    """

    def __init__(self, reactor, socket_path=None):
        super().__init__()
        self.reactor = reactor
        self.socket_path = socket_path
        if self.socket_path is None:
            self.socket_path = get_ipc_socket_path()
        self.endpoint = UNIXClientEndpoint(reactor, self.socket_path)
        self._protocol = None
        self.protocol = DeferredValue()
        self.processId = DeferredValue()

    @asynchronous
    def startService(self):
        """Connect to UNIX socket."""
        super().startService()
        protocol = IPCWorker()
        protocol.service = self
        self.starting = connectProtocol(self.endpoint, protocol)

        def save_protocol(protocol):
            self._protocol = protocol

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
        if self._protocol:
            self.protocol = DeferredValue()
            self.processId = DeferredValue()
            self._protocol, protocol = None, self._protocol
            if protocol.transport:
                protocol.transport.loseConnection()
        return super().stopService()

    @asynchronous
    def rpcPublish(self, port):
        """Publish the RPC port to the region."""
        d = self.protocol.get()
        d.addCallback(
            lambda protocol: protocol.callRemote(
                RPCEndpointPublish, pid=os.getpid(), port=port
            )
        )
        return d

    @asynchronous
    def rpcRegisterConnection(self, connid, ident, host, port):
        """Register RPC connection on master."""
        d = self.protocol.get()
        d.addCallback(
            lambda protocol: protocol.callRemote(
                RPCRegisterConnection,
                pid=os.getpid(),
                connid=connid,
                ident=ident,
                host=host,
                port=port,
            )
        )
        return d

    @asynchronous
    def rpcUnregisterConnection(self, connid):
        """Unregister RPC connection on master."""
        d = self.protocol.get()
        d.addCallback(
            lambda protocol: protocol.callRemote(
                RPCUnregisterConnection, pid=os.getpid(), connid=connid
            )
        )
        return d
