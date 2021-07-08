import logging

import capnp

from maasserver.rpc.capnp import rpc_dir

log = logging.getLogger(__name__)


handshake = capnp.load(rpc_dir("handshake.capnp"))
region = capnp.load(rpc_dir("region.capnp"))


class Authenticator(region.RegionController.Authenticator.Server):
    def __init__(self, shim):
        self.shim = shim
        super(Authenticator, self).__init__()

    def authenticate(self, msg, _context, **kwargs):
        resp = handshake.AuthResponse()
        prom = capnp.Promise(resp)

        def get_result(creds):
            resp.salt = creds.get("salt")
            resp.digest = creds.get("digest")
            prom.then(lambda resp: resp)

        self.shim.authenticate(msg).addCallback(get_result)
        return prom


class Registerer(region.RegionController.Registerer.Server):
    def __init__(self, shim, rack_controller, server):
        self.shim = shim
        self.rack_controller = rack_controller
        self.server = server
        super(Registerer, self).__init__()

    def register(self, req, *args, **kwargs):
        resp = handshake.RegisterResponse()
        prom = capnp.Promise(resp)

        def get_result(res):
            resp.systemId = res.get("system_id")
            resp.uuid = res.get("uuid")
            resp.version = res.get("version")
            self.server.register_rack_controller(
                res.get("system_id"), self.rack_controller
            )
            prom.then(lambda resp: resp)

        try:
            self.shim.register(
                req.systemId,
                req.hostname,
                req.interfaces,
                req.url,
                req.nodegroup,
                req.beaconSupport,
                req.version,
            ).addCallback(get_result)
        except Exception as e:
            log.error(e)
        return prom
