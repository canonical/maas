import logging
from urllib.parse import urlparse

import capnp

from maasserver.rpc.capnp import rpc_dir

log = logging.getLogger(__name__)

handshake = capnp.load(rpc_dir("handshake.capnp"))
region = capnp.load(rpc_dir("region.capnp"))


class Authenticator(region.RegionController.Authenticator.Server):
    def __init__(self, shim):
        self.shim = shim
        super(Authenticator, self).__init__()

    def authenticate_context(self, context):
        msg = context.params.msg
        self.event = capnp.PromiseFulfillerPair()

        def get_result(creds):
            resp = handshake.AuthResponse()
            resp.salt = creds.get("salt")
            resp.digest = creds.get("digest")
            context.results.resp = resp
            self.event.fulfill()

        self.shim.authenticate(msg).addCallback(get_result)
        return self.event.promise


class Registerer(region.RegionController.Registerer.Server):
    def __init__(self, shim, rack_controller, server):
        self.shim = shim
        self.rack_controller = rack_controller
        self.server = server
        super(Registerer, self).__init__()

    def register_context(self, context):
        self.event = capnp.PromiseFulfillerPair()
        req = context.params.req

        def get_result(res):
            resp = handshake.RegisterResponse()
            resp.systemId = res.get("system_id")
            resp.uuid = res.get("uuid")
            resp.version = res.get("version")
            self.server.register_rack_controller(
                res.get("system_id"), self.rack_controller
            )
            context.results.resp = resp
            self.event.fulfill()

        try:
            ifaces = {e.name: e.iface.to_dict() for e in req.interfaces.ifaces}
            self.shim.register(
                req.systemId,
                req.hostname,
                ifaces,
                urlparse(req.url),
                req.nodegroup,
                req.beaconSupport,
                req.version,
            ).addCallback(get_result)
        except Exception as e:
            log.error(e)
        return self.event.promise
