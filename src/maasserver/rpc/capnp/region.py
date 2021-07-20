import logging

import capnp

from maasserver.rpc.capnp import handshake, rpc_dir
from maasserver.rpc.regionservice import RegionServer

region = capnp.load(rpc_dir("region.capnp"))
controller = capnp.load(rpc_dir("controller.capnp"))
log = logging.getLogger(__name__)


class RegionController(region.RegionController.Server):
    def __init__(self, rack_controllers, server, *args, **kwargs):
        self.shim = RegionServer()
        self.rack_controllers = rack_controllers
        self.server = server
        super(RegionController, self).__init__()

    def ping(self):
        return

    def reportBootImates(self, req):
        return

    def getBootConfig(self, req):
        return None

    def getBootSources(self, uuid):
        return None

    def getArchiveMirrors(self):
        return None

    def getProxies(self):
        return None

    def markNodeFailed(self, req):
        return

    def listNodePowerParameters(self, uuid):
        return None

    def updateLastImageSync(self, systemId):
        return None

    def updateNodePowerState(self, req):
        return

    def registerEventType(self, req):
        return

    def sendEvent(self, event):
        return

    def sendEventMacAddress(self, msg):
        return

    def sendIPAddress(self, msg):
        return

    def reportForeignDHCPServer(self, msg):
        return

    def reportMDNSEntries(self, msg):
        return

    def reportNeighbours(self, msg):
        return

    def createNode(self, msg):
        return ""

    def commisionNode(self, msg):
        return

    def getDiscoveryState(systemId):
        return None

    def requestNodeInfoByMACAddress(mac_address):
        return None

    def updateLease(self, msg):
        return

    def updateService(self, msg):
        return

    def requestRackRefresh(self, systemId):
        return None

    def getControllerType(self, systemId):
        return None

    def getTimeConfiguration(self, systemId):
        resp = controller.TimeConfiguration()
        prom = capnp.Promise(resp)

        def get_result(cfg):
            resp.servers = cfg.get("servers", [])
            resp.peers = cfg.get("peers", [])
            prom.then(lambda resp: resp)

        self.shim.getTimeConfiguration(systemId).addCallback(get_result)
        return prom

    def getDNSConfiguration(self, systemId):
        return None

    def getProxyConfiguration(self, systemId):
        return None

    def getSyslogConfiguration(self, systemId):
        return None

    def updateControllerState(self, msg):
        return None

    def getAuthenticator(self, *args, **kwargs):
        return handshake.Authenticator(self.shim)

    def getRegisterer(self, *args, **kwargs):
        ctx = kwargs.get("_context")
        return handshake.Registerer(
            self.shim, ctx.params.rackController, self.server
        )
