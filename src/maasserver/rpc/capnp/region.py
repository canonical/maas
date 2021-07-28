import logging

import capnp
from twisted.internet.defer import inlineCallbacks

from maasserver.rpc import rackcontrollers
from maasserver.rpc.capnp import handshake, rpc_dir
from maasserver.rpc.regionservice import isLoopbackURL, Region
from maasserver.utils.threads import deferToDatabase
from provisioningserver.prometheus.metrics import GLOBAL_LABELS
from provisioningserver.rpc import exceptions
from provisioningserver.utils.version import get_running_version

region = capnp.load(rpc_dir("region.capnp"))
controller = capnp.load(rpc_dir("controller.capnp"))
log = logging.getLogger(__name__)


class RegionServer(Region):
    connid = None
    ident = None
    host = None
    hostIsRemote = False

    @inlineCallbacks
    def register(
        self,
        system_id,
        hostname,
        interfaces,
        url,
        nodegroup_uuid=None,
        beacon_support=False,
        version=None,
    ):
        result = yield self._register(
            system_id,
            hostname,
            interfaces,
            url,
            nodegroup_uuid=nodegroup_uuid,
            version=version,
        )
        if beacon_support:
            # The remote supports beaconing, so acknowledge that.
            result["beacon_support"] = True
        if version:
            # The remote supports version checking, so reply to that.
            result["version"] = str(get_running_version())
        return result

    @inlineCallbacks
    def _register(
        self,
        system_id,
        hostname,
        interfaces,
        url,
        nodegroup_uuid=None,
        version=None,
    ):
        try:
            # Register, which includes updating interfaces.
            is_loopback = yield isLoopbackURL(url)
            rack_controller = yield deferToDatabase(
                rackcontrollers.register,
                system_id=system_id,
                hostname=hostname,
                interfaces=interfaces,
                url=url,
                is_loopback=is_loopback,
                version=version,
            )

            # Check for upgrade.
            if nodegroup_uuid is not None:
                yield deferToDatabase(
                    rackcontrollers.handle_upgrade,
                    rack_controller,
                    nodegroup_uuid,
                )
            self.ident = rack_controller.system_id
            # yield self.initResponder(rack_controller)
        except Exception:
            # Ensure we're not hanging onto this connection.
            # self.factory.service._removeConnectionFor(self.ident, self)
            # Tell the logs about it.
            msg = (
                "Failed to register rack controller '%s' with the "
                "master. Connection will be dropped." % self.ident
            )
            log.err(None, msg)
            # Finally, tell the callers.
            raise exceptions.CannotRegisterRackController(msg)
        else:
            # Done registering the rack controller and connection.
            return {
                "system_id": self.ident,
                "uuid": GLOBAL_LABELS["maas_uuid"],
            }


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

    def getTimeConfiguration_context(self, context):
        self.event = capnp.PromiseFulfillerPair()
        systemId = context.params.systemId

        def get_result(cfg):
            resp = controller.TimeConfiguration()

            srv_list = cfg.get("servers", [])
            lst = resp.init("servers", len(srv_list))
            for i, s in enumerate(srv_list):
                lst[i] = s

            peer_list = cfg.get("peers", [])
            lst = resp.init("peers", len(peer_list))
            for i, s in enumerate(peer_list):
                lst[i] = s

            context.results.resp = resp
            self.event.fulfill()

        self.shim.get_time_configuration(systemId).addCallback(get_result)
        return self.event.promise

    def getDNSConfiguration(self, systemId, _context, **kwargs):
        resp = controller.DNSConfiguration()
        prom = capnp.Promise(resp)

        def get_result(cfg):
            resp.trustedNetworks = cfg.get("trusted_networks", [])
            prom.then(lambda resp: resp)

        self.shim.get_dns_configuration(systemId).addCallback(get_result)
        return prom

    def getProxyConfiguration(self, systemId):
        return None

    def getSyslogConfiguration(self, systemId):
        return None

    def updateControllerState(self, msg):
        return None

    def getAuthenticator_context(self, context):
        context.results.auth = handshake.Authenticator(self.shim)
        return None

    def getRegisterer_context(self, context):
        context.results.reg = handshake.Registerer(
            self.shim, context.params.rackController, self.server
        )
        return None
