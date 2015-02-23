# Copyright 2012-2014 Canonical Ltd.  This software is licensed under the
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

import os
import socket

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


class Options(usage.Options):
    """Command line options for the provisioning server."""

    optParameters = [
        ["config-file", "c", "clusterd.db", "Configuration file to load."],
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
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        s.bind(('0.0.0.0', port))
        # Use a backlog of 50, which seems to be fairly common.
        s.listen(50)
        # Adopt this socket into Twisted's reactor.
        site_endpoint = AdoptedStreamServerEndpoint(
            reactor, s.fileno(), s.family)
        site_endpoint.port = port  # Make it easy to get the port number.
        site_endpoint.socket = s  # Prevent garbage collection.

        from provisioningserver.cluster_config import get_boot_resources_storage
        
        print("_makeImageService tftp storage: ", get_boot_resources_storage())
        image_service = BootImageEndpointService(
            resource_root=get_boot_resources_storage(),
            endpoint=site_endpoint)
        image_service.setName("image_service")
        return image_service

    def _makeTFTPService(self, tftp_root, tftp_port, tftp_generator):
        """Create the dynamic TFTP service."""
        print("tftp_root: %s tftp_port: %i tftp_generator: %s" % (tftp_root, tftp_port, tftp_generator))
        from provisioningserver.pserv_services.tftp import TFTPService
        tftp_service = TFTPService(
            resource_root=tftp_root, port=tftp_port, generator=tftp_generator)
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

    def _makeRPCService(self):
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

    def makeService(self, options):
        """Construct a service."""
        from provisioningserver import services
        from provisioningserver.cluster_config import get_tftp_resource_root
        from provisioningserver.cluster_config import get_tftp_port
        from provisioningserver.cluster_config import get_tftp_generator

        image_service = self._makeImageService()
        image_service.setServiceParent(services)

        tftp_service = self._makeTFTPService(get_tftp_resource_root(), get_tftp_port(), get_tftp_generator())
        tftp_service.setServiceParent(services)

        rpc_service = self._makeRPCService()
        rpc_service.setServiceParent(services)

        node_monitor = self._makeNodePowerMonitorService()
        node_monitor.setServiceParent(services)

        image_download_service = self._makeImageDownloadService(rpc_service)
        image_download_service.setServiceParent(services)

        dhcp_probe_service = self._makeDHCPProbeService(rpc_service)
        dhcp_probe_service.setServiceParent(services)

        lease_upload_service = self._makeLeaseUploadService(rpc_service)
        lease_upload_service.setServiceParent(services)

        return services
