import asyncio
import logging
import socket

import capnp
from twisted.application import service
from twisted.internet.defer import Deferred

from maasserver.rpc.capnp.region import RegionController
from provisioningserver.utils.twisted import asynchronous

log = logging.getLogger(__name__)


class Server:
    rpc_interface = None
    rack_controllers = {}
    io_timeout = 0.1
    io_buffer_size = 4096

    def register_rack_controller(self, system_id, rack_controller):
        self.rack_controllers[system_id] = rack_controller

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
            bootstrap=self.rpc_interface(self.rack_controllers, self)
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


class RegionControllerServer(Server):
    rpc_interface = RegionController


def connect(server):
    async def serve(reader, writer):
        srvr = server()
        await srvr.serve(reader, writer)

    return serve


async def run():
    # TODO make these values configurable
    addr = "0.0.0.0"
    port = 5555

    server = await asyncio.start_server(
        connect(RegionControllerServer), addr, str(port), family=socket.AF_INET
    )

    async with server:
        await server.serve_forever()


class RPCShimService(service.Service):
    def __init__(self, ipc_worker):
        self.ipc_worker = ipc_worker
        self.server_deferred = None
        super(RPCShimService, self).__init__()

    @asynchronous
    def startService(self):
        super().startService()
        self.server_deferred = Deferred.fromFuture(
            asyncio.ensure_future(run())
        )
        return self.server_deferred
