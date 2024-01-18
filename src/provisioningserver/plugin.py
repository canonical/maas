# Copyright 2012-2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Twisted Application Plugin code for the MAAS provisioning server"""


from errno import ENOPROTOOPT
import socket
from socket import error as socket_error
from time import sleep

from twisted.application.service import IServiceMaker
from twisted.internet import reactor
from twisted.plugin import IPlugin
from zope.interface import implementer

from provisioningserver import logger, settings
from provisioningserver.config import ClusterConfiguration, is_dev_environment
from provisioningserver.monkey import (
    add_patches_to_twisted,
    add_patches_to_txtftp,
)
from provisioningserver.prometheus.utils import clean_prometheus_dir
from provisioningserver.security import to_bin
from provisioningserver.utils.debug import (
    register_sigusr1_toggle_cprofile,
    register_sigusr2_thread_dump_handler,
)
from provisioningserver.utils.env import MAAS_SECRET, MAAS_SHARED_SECRET
from provisioningserver.utils.twisted import retries


class Options(logger.VerbosityOptions):
    """Command line options for `rackd`."""


@implementer(IServiceMaker, IPlugin)
class ProvisioningServiceMaker:
    """Create a service for the Twisted plugin."""

    options = Options

    def __init__(self, name, description):
        self.tapname = name
        self.description = description

    def _makeHTTPService(self):
        """Create the HTTP service."""
        from twisted.application.internet import StreamServerEndpointService
        from twisted.internet.endpoints import AdoptedStreamServerEndpoint

        from provisioningserver.rackdservices.http import HTTPResource
        from provisioningserver.utils.twisted import SiteNoLog

        port = 5249
        s = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except socket_error as e:
            if e.errno != ENOPROTOOPT:
                raise e
        s.bind(("::", port))
        # Use a backlog of 50, which seems to be fairly common.
        s.listen(50)
        # Adopt this socket into Twisted's reactor.
        site_endpoint = AdoptedStreamServerEndpoint(
            reactor, s.fileno(), s.family
        )
        site_endpoint.port = port  # Make it easy to get the port number.
        site_endpoint.socket = s  # Prevent garbage collection.

        http_service = StreamServerEndpointService(
            site_endpoint, SiteNoLog(HTTPResource())
        )
        http_service.setName("http_service")
        return http_service

    def _makeTFTPService(self, tftp_root, tftp_port, rpc_service):
        """Create the dynamic TFTP service."""
        from provisioningserver.rackdservices.tftp import TFTPService

        tftp_service = TFTPService(
            resource_root=tftp_root, port=tftp_port, client_service=rpc_service
        )
        tftp_service.setName("tftp")

        return tftp_service

    def _makeLeaseSocketService(self, rpc_service):
        from provisioningserver.rackdservices.lease_socket_service import (
            LeaseSocketService,
        )

        lease_socket_service = LeaseSocketService(rpc_service, reactor)
        lease_socket_service.setName("lease_socket_service")
        return lease_socket_service

    def _makeNodePowerMonitorService(self):
        from provisioningserver.rackdservices.node_power_monitor_service import (
            NodePowerMonitorService,
        )

        node_monitor = NodePowerMonitorService(reactor)
        node_monitor.setName("node_monitor")
        return node_monitor

    def _makeRPCService(self):
        from provisioningserver.rpc.clusterservice import ClusterClientService

        with ClusterConfiguration.open() as config:
            rpc_service = ClusterClientService(
                reactor,
                config.max_idle_rpc_connections,
                config.max_rpc_connections,
                config.rpc_keepalive,
            )
        rpc_service.setName("rpc")
        return rpc_service

    def _makeRPCPingService(self, rpc_service, clock=reactor):
        from provisioningserver.rpc.clusterservice import (
            ClusterClientCheckerService,
        )

        service = ClusterClientCheckerService(rpc_service, reactor)
        service.setName("rpc-ping")
        return service

    def _makeNetworksMonitoringService(self, rpc_service, clock=reactor):
        from provisioningserver.rackdservices.networks_monitoring_service import (
            RackNetworksMonitoringService,
        )

        networks_monitor = RackNetworksMonitoringService(rpc_service, clock)
        networks_monitor.setName("networks_monitor")
        return networks_monitor

    def _makeDHCPProbeService(self, rpc_service):
        from provisioningserver.rackdservices.dhcp_probe_service import (
            DHCPProbeService,
        )

        dhcp_probe_service = DHCPProbeService(rpc_service, reactor)
        dhcp_probe_service.setName("dhcp_probe")
        return dhcp_probe_service

    def _makeServiceMonitorService(self, rpc_service):
        from provisioningserver.rackdservices.service_monitor_service import (
            ServiceMonitorService,
        )

        service_monitor = ServiceMonitorService(rpc_service, reactor)
        service_monitor.setName("service_monitor")
        return service_monitor

    def _makeRackHTTPService(self, resource_root, rpc_service):
        from provisioningserver.rackdservices import http

        http_service = http.RackHTTPService(
            resource_root, rpc_service, reactor
        )
        http_service.setName("http")
        return http_service

    def _makeExternalService(self, rpc_service):
        from provisioningserver.rackdservices import external

        external_service = external.RackExternalService(rpc_service, reactor)
        external_service.setName("external")
        return external_service

    def _makeSnapUpdateCheckService(self, rpc_service):
        from provisioningserver.rackdservices.version_update_check import (
            RackVersionUpdateCheckService,
        )

        update_check_service = RackVersionUpdateCheckService(rpc_service)
        update_check_service.setName("version_update_check")
        return update_check_service

    def _makeServices(self, tftp_root, tftp_port, clock=reactor):
        # Several services need to make use of the RPC service.
        rpc_service = self._makeRPCService()
        yield rpc_service
        # Other services that make up the MAAS Region Controller.
        yield self._makeRPCPingService(rpc_service, clock=clock)
        yield self._makeNetworksMonitoringService(rpc_service, clock=clock)
        yield self._makeDHCPProbeService(rpc_service)
        yield self._makeLeaseSocketService(rpc_service)
        yield self._makeNodePowerMonitorService()
        yield self._makeServiceMonitorService(rpc_service)
        yield self._makeRackHTTPService(tftp_root, rpc_service)
        yield self._makeExternalService(rpc_service)
        yield self._makeSnapUpdateCheckService(rpc_service)
        # The following are network-accessible services.
        yield self._makeHTTPService()
        yield self._makeTFTPService(tftp_root, tftp_port, rpc_service)

    def _loadSettings(self):
        # Load the settings from rackd.conf.
        with ClusterConfiguration.open() as config:
            settings.DEBUG = config.debug
        # Debug mode is always on in the development environment.
        if is_dev_environment():
            settings.DEBUG = True

    def _configureCrochet(self):
        # Prevent other libraries from starting the reactor via crochet.
        # In other words, this makes crochet.setup() a no-op.
        import crochet

        crochet.no_setup()

    def _configureLogging(self, verbosity: int):
        # Get something going with the logs.
        logger.configure(verbosity, logger.LoggingMode.TWISTD)

    def makeService(self, options, clock=reactor, sleep=sleep):
        """Construct the MAAS Cluster service."""
        register_sigusr1_toggle_cprofile("rackd")
        register_sigusr2_thread_dump_handler()
        clean_prometheus_dir()
        add_patches_to_txtftp()
        add_patches_to_twisted()

        self._loadSettings()
        self._configureCrochet()
        if settings.DEBUG:
            # Always log at debug level in debug mode.
            self._configureLogging(3)
        else:
            self._configureLogging(options["verbosity"])

        with ClusterConfiguration.open() as config:
            tftp_root = config.tftp_root
            tftp_port = config.tftp_port

        from provisioningserver.boot import (
            clean_old_boot_resources,
            install_boot_method_templates,
        )

        clean_old_boot_resources(tftp_root)
        install_boot_method_templates(tftp_root)

        from provisioningserver import services

        secret = None
        for elapsed, remaining, wait in retries(timeout=5 * 60, clock=clock):
            secret = MAAS_SHARED_SECRET.get()
            if secret is not None:
                MAAS_SECRET.set(to_bin(secret))
                break
            sleep(wait)
        if secret is not None:
            # only setup services if the shared secret is configured
            for service in self._makeServices(
                tftp_root, tftp_port, clock=clock
            ):
                service.setServiceParent(services)

        return services
