# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Twisted Application Plugin code for the MAAS provisioning server"""

__all__ = [
    "ProvisioningServiceMaker",
]

from errno import ENOPROTOOPT
import socket
from socket import error as socket_error

from provisioningserver.config import ClusterConfiguration
from provisioningserver.monkey import (
    add_term_error_code_to_tftp,
    force_simplestreams_to_use_urllib2,
)
from provisioningserver.utils.debug import (
    register_sigusr2_thread_dump_handler,
)
from twisted.application.internet import TCPServer
from twisted.application.service import IServiceMaker
from twisted.internet import reactor
from twisted.plugin import IPlugin
from twisted.python import usage
from twisted.web.resource import Resource
from twisted.web.server import Site
from zope.interface import implementer


class Options(usage.Options):
    """Command line options for the provisioning server."""


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

    def _makeImageService(self, resource_root):
        from provisioningserver.pserv_services.image import (
            BootImageEndpointService)
        from twisted.internet.endpoints import AdoptedStreamServerEndpoint
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
            resource_root=resource_root, endpoint=site_endpoint)
        image_service.setName("image_service")
        return image_service

    def _makeTFTPService(
            self, cluster_uuid, tftp_root, tftp_port, tftp_generator):
        """Create the dynamic TFTP service."""
        from provisioningserver.pserv_services.tftp import TFTPService
        tftp_service = TFTPService(
            resource_root=tftp_root, port=tftp_port, generator=tftp_generator,
            uuid=cluster_uuid)
        tftp_service.setName("tftp")
        return tftp_service

    def _makeImageDownloadService(self, rpc_service, cluster_uuid, tftp_root):
        from provisioningserver.pserv_services.image_download_service \
            import ImageDownloadService
        image_download_service = ImageDownloadService(
            rpc_service, cluster_uuid, tftp_root, reactor)
        image_download_service.setName("image_download")
        return image_download_service

    def _makeLeaseUploadService(self, rpc_service, cluster_uuid):
        from provisioningserver.pserv_services.lease_upload_service \
            import LeaseUploadService
        lease_upload_service = LeaseUploadService(
            rpc_service, reactor, cluster_uuid)
        lease_upload_service.setName("lease_upload")
        return lease_upload_service

    def _makeNodePowerMonitorService(self, cluster_uuid):
        from provisioningserver.pserv_services.node_power_monitor_service \
            import NodePowerMonitorService
        node_monitor = NodePowerMonitorService(cluster_uuid, reactor)
        node_monitor.setName("node_monitor")
        return node_monitor

    def _makeRPCService(self):
        from provisioningserver.rpc.clusterservice import ClusterClientService
        rpc_service = ClusterClientService(reactor)
        rpc_service.setName("rpc")
        return rpc_service

    def _makeDHCPProbeService(self, rpc_service, cluster_uuid):
        from provisioningserver.pserv_services.dhcp_probe_service \
            import DHCPProbeService
        dhcp_probe_service = DHCPProbeService(
            rpc_service, reactor, cluster_uuid)
        dhcp_probe_service.setName("dhcp_probe")
        return dhcp_probe_service

    def _makeServiceMonitorService(self):
        from provisioningserver.pserv_services.service_monitor_service \
            import ServiceMonitorService
        service_monitor = ServiceMonitorService(reactor)
        service_monitor.setName("service_monitor")
        return service_monitor

    def _makeServices(self, config):
        # Several services need to make use of the RPC service.
        rpc_service = self._makeRPCService()
        yield rpc_service
        # Other services that make up the MAAS Region Controller.
        yield self._makeDHCPProbeService(rpc_service, config.cluster_uuid)
        yield self._makeLeaseUploadService(rpc_service, config.cluster_uuid)
        yield self._makeNodePowerMonitorService(config.cluster_uuid)
        yield self._makeServiceMonitorService()
        yield self._makeImageDownloadService(
            rpc_service, config.cluster_uuid, config.tftp_root)
        # The following are network-accessible services.
        yield self._makeImageService(config.tftp_root)
        yield self._makeTFTPService(
            config.cluster_uuid, config.tftp_root, config.tftp_port,
            config.tftp_generator_url)

    def makeService(self, options):
        """Construct the MAAS Cluster service."""
        register_sigusr2_thread_dump_handler()
        force_simplestreams_to_use_urllib2()
        add_term_error_code_to_tftp()

        from provisioningserver import services
        with ClusterConfiguration.open() as config:
            for service in self._makeServices(config):
                service.setServiceParent(services)

        return services
