# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Twisted Application Plugin code for the MAAS provisioning server"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "ProvisioningServiceMaker",
]

from errno import ENOPROTOOPT
import os
import socket
from socket import error as socket_error

from provisioningserver.monkey import force_simplestreams_to_use_urllib2
from provisioningserver.utils.debug import (
    register_sigusr2_thread_dump_handler,
)
from twisted.application.internet import TCPServer
from twisted.application.service import IServiceMaker
from twisted.cred.checkers import ICredentialsChecker
from twisted.cred.credentials import IUsernamePassword
from twisted.cred.error import UnauthorizedLogin
from twisted.cred.portal import IRealm
from twisted.internet import reactor
from twisted.internet.defer import (
    inlineCallbacks,
    returnValue,
)
from twisted.plugin import IPlugin
from twisted.python import usage
from twisted.web.resource import (
    IResource,
    Resource,
)
from twisted.web.server import Site
from zope.interface import implementer


@implementer(ICredentialsChecker)
class SingleUsernamePasswordChecker:
    """An `ICredentialsChecker` for a single username and password."""

    credentialInterfaces = [IUsernamePassword]

    def __init__(self, username, password):
        super(SingleUsernamePasswordChecker, self).__init__()
        self.username = username
        self.password = password

    @inlineCallbacks
    def requestAvatarId(self, credentials):
        """See `ICredentialsChecker`."""
        if credentials.username == self.username:
            matched = yield credentials.checkPassword(self.password)
            if matched:
                returnValue(credentials.username)
        raise UnauthorizedLogin(credentials.username)


@implementer(IRealm)
class ProvisioningRealm:
    """The `IRealm` for the Provisioning API."""

    noop = staticmethod(lambda: None)

    def __init__(self, resource):
        super(ProvisioningRealm, self).__init__()
        self.resource = resource

    def requestAvatar(self, avatarId, mind, *interfaces):
        """See `IRealm`."""
        if IResource in interfaces:
            return (IResource, self.resource, self.noop)
        raise NotImplementedError()


def serverFromString(description):
    """Lazy import from `provisioningserver.utils.introspect`."""
    from provisioningserver.utils import introspect
    return introspect.serverFromString(description)


class Options(usage.Options):
    """Command line options for the provisioning server."""

    optParameters = [
        ["config-file", "c", "pserv.yaml", "Configuration file to load."],
        ["introspect", None, None,
         ("Allow introspection, allowing unhindered access to the internals "
          "of MAAS. This should probably only be used for debugging. Supply "
          "an argument in 'endpoint' form; the document 'Getting Connected "
          "with Endpoints' on the Twisted Wiki may help."),
         serverFromString],
    ]


@implementer(IServiceMaker, IPlugin)
class ProvisioningServiceMaker:
    """Create a service for the Twisted plugin."""

    options = Options

    def __init__(self, name, description):
        self.tapname = name
        self.description = description

    def _makeSiteService(self, papi_xmlrpc, config):
        """Create the site service."""
        site_root = Resource()
        site_root.putChild("api", papi_xmlrpc)
        site = Site(site_root)
        site_port = config["port"]
        site_interface = config["interface"]
        site_service = TCPServer(site_port, site, interface=site_interface)
        site_service.setName("site")
        return site_service

    def _makeImageService(self):
        from provisioningserver.pserv_services.image import (
            BootImageEndpointService)
        from twisted.internet.endpoints import AdoptedStreamServerEndpoint
        from provisioningserver import config

        port = 5248  # config["port"]
        # Make a socket with SO_REUSEPORT set so that we can run multiple we
        # applications. This is easier to do from outside of Twisted as there's
        # not yet official support for setting socket options.
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except socket_error as e:
            # Python's socket module was compiled using modern headers
            # thus defining SO_REUSEPORT would cause issues as it might
            # running in older kernel that does not support SO_REUSEPORT.

            # XXX andreserl 2015-04-08 bug=1441684: We need to add a warning
            # log message when we see this error, and a test for it.
            if e.errno != ENOPROTOOPT:
                raise e
        s.bind(('0.0.0.0', port))
        # Use a backlog of 50, which seems to be fairly common.
        s.listen(50)
        # Adopt this socket into Twisted's reactor.
        site_endpoint = AdoptedStreamServerEndpoint(
            reactor, s.fileno(), s.family)
        site_endpoint.port = port  # Make it easy to get the port number.
        site_endpoint.socket = s  # Prevent garbage collection.

        image_service = BootImageEndpointService(
            resource_root=os.path.join(
                config.BOOT_RESOURCES_STORAGE, "current"),
            endpoint=site_endpoint)
        image_service.setName("image_service")
        return image_service

    def _makeTFTPService(self, tftp_config):
        """Create the dynamic TFTP service."""
        from provisioningserver.pserv_services.tftp import TFTPService
        tftp_service = TFTPService(
            resource_root=tftp_config['resource_root'],
            port=tftp_config['port'], generator=tftp_config['generator'])
        tftp_service.setName("tftp")
        return tftp_service

    def _makeImageDownloadService(self, rpc_service):
        from provisioningserver.cluster_config import get_cluster_uuid
        from provisioningserver.pserv_services.image_download_service \
            import ImageDownloadService
        image_download_service = ImageDownloadService(
            rpc_service, reactor, get_cluster_uuid())
        image_download_service.setName("image_download")
        return image_download_service

    def _makeLeaseUploadService(self, rpc_service):
        from provisioningserver.cluster_config import get_cluster_uuid
        from provisioningserver.pserv_services.lease_upload_service \
            import LeaseUploadService
        lease_upload_service = LeaseUploadService(
            rpc_service, reactor, get_cluster_uuid())
        lease_upload_service.setName("lease_upload")
        return lease_upload_service

    def _makeNodePowerMonitorService(self):
        from provisioningserver.cluster_config import get_cluster_uuid
        from provisioningserver.pserv_services.node_power_monitor_service \
            import NodePowerMonitorService
        node_monitor = NodePowerMonitorService(get_cluster_uuid(), reactor)
        node_monitor.setName("node_monitor")
        return node_monitor

    def _makeRPCService(self, rpc_config):
        from provisioningserver.rpc.clusterservice import ClusterClientService
        rpc_service = ClusterClientService(reactor)
        rpc_service.setName("rpc")
        return rpc_service

    def _makeDHCPProbeService(self, rpc_service):
        from provisioningserver.cluster_config import get_cluster_uuid
        from provisioningserver.pserv_services.dhcp_probe_service \
            import DHCPProbeService
        dhcp_probe_service = DHCPProbeService(
            rpc_service, reactor, get_cluster_uuid())
        dhcp_probe_service.setName("dhcp_probe")
        return dhcp_probe_service

    def _makeServiceMonitorService(self):
        from provisioningserver.pserv_services.service_monitor_service \
            import ServiceMonitorService
        service_monitor = ServiceMonitorService(reactor)
        service_monitor.setName("service_monitor")
        return service_monitor

    def _makeIntrospectionService(self, endpoint):
        from provisioningserver.utils import introspect
        introspect_service = (
            introspect.IntrospectionShellService(
                location="cluster", endpoint=endpoint, namespace={}))
        introspect_service.setName("introspect")
        return introspect_service

    def makeService(self, options):
        """Construct the MAAS Cluster service."""
        register_sigusr2_thread_dump_handler()
        force_simplestreams_to_use_urllib2()

        from provisioningserver import services
        from provisioningserver.config import Config

        config = Config.load(options["config-file"])

        image_service = self._makeImageService()
        image_service.setServiceParent(services)

        tftp_service = self._makeTFTPService(config["tftp"])
        tftp_service.setServiceParent(services)

        rpc_service = self._makeRPCService(config["rpc"])
        rpc_service.setServiceParent(services)

        node_monitor = self._makeNodePowerMonitorService()
        node_monitor.setServiceParent(services)

        image_download_service = self._makeImageDownloadService(rpc_service)
        image_download_service.setServiceParent(services)

        dhcp_probe_service = self._makeDHCPProbeService(rpc_service)
        dhcp_probe_service.setServiceParent(services)

        lease_upload_service = self._makeLeaseUploadService(rpc_service)
        lease_upload_service.setServiceParent(services)

        service_monitor_service = self._makeServiceMonitorService()
        service_monitor_service.setServiceParent(services)

        if options["introspect"] is not None:
            introspect = self._makeIntrospectionService(options["introspect"])
            introspect.setServiceParent(services)

        return services
