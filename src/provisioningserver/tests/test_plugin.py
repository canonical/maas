# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the ``maasrackd`` TAP."""

__all__ = []

import crochet
from maastesting.matchers import MockCalledOnceWith
from maastesting.testcase import (
    MAASTestCase,
    MAASTwistedRunTest,
)
import provisioningserver
from provisioningserver import (
    logger,
    plugin as plugin_module,
    settings,
)
from provisioningserver.config import ClusterConfiguration
from provisioningserver.http import EndpointService
from provisioningserver.plugin import (
    Options,
    ProvisioningHTTPServiceMaker,
    ProvisioningServiceMaker,
)
from provisioningserver.rackdservices.dhcp_probe_service import (
    DHCPProbeService,
)
from provisioningserver.rackdservices.dns import RackDNSService
from provisioningserver.rackdservices.http_image_service import (
    HTTPImageService,
)
from provisioningserver.rackdservices.image_download_service import (
    ImageDownloadService,
)
from provisioningserver.rackdservices.lease_socket_service import (
    LeaseSocketService,
)
from provisioningserver.rackdservices.networks_monitoring_service import (
    RackNetworksMonitoringService,
)
from provisioningserver.rackdservices.node_power_monitor_service import (
    NodePowerMonitorService,
)
from provisioningserver.rackdservices.service_monitor_service import (
    ServiceMonitorService,
)
from provisioningserver.rackdservices.tftp import (
    TFTPBackend,
    TFTPService,
)
from provisioningserver.rackdservices.tftp_offload import TFTPOffloadService
from provisioningserver.rpc.clusterservice import ClusterClientCheckerService
from provisioningserver.testing.config import ClusterConfigurationFixture
from provisioningserver.utils.twisted import reducedWebLogFormatter
from testtools.matchers import (
    AfterPreprocessing,
    Contains,
    Equals,
    Is,
    IsInstance,
    KeysEqual,
    MatchesAll,
    MatchesStructure,
    Not,
)
from twisted.application.service import MultiService
from twisted.python.filepath import FilePath
from twisted.web.server import Site


class TestOptions(MAASTestCase):
    """Tests for `provisioningserver.plugin.Options`."""

    def test_defaults(self):
        options = Options()
        self.assertEqual({}, options.defaults)

    def test_parse_minimal_options(self):
        options = Options()
        # The minimal set of options that must be provided.
        arguments = []
        options.parseOptions(arguments)  # No error.


class TestProvisioningServiceMaker(MAASTestCase):
    """Tests for `provisioningserver.plugin.ProvisioningServiceMaker`."""

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

    def setUp(self):
        super(TestProvisioningServiceMaker, self).setUp()
        self.useFixture(ClusterConfigurationFixture())
        self.patch(provisioningserver, "services", MultiService())
        self.patch_autospec(crochet, "no_setup")
        self.patch_autospec(logger, "configure")
        self.tempdir = self.make_dir()

    def test_init(self):
        service_maker = ProvisioningServiceMaker("Harry", "Hill")
        self.assertEqual("Harry", service_maker.tapname)
        self.assertEqual("Hill", service_maker.description)

    def test_makeService_not_in_debug(self):
        """
        Only the site service is created when no options are given.
        """
        self.patch(settings, "DEBUG", False)
        options = Options()
        service_maker = ProvisioningServiceMaker("Harry", "Hill")
        self.patch(service_maker, '_loadSettings')
        service = service_maker.makeService(options, clock=None)
        self.assertIsInstance(service, MultiService)
        expected_services = [
            "dhcp_probe", "networks_monitor", "image_download",
            "lease_socket_service", "node_monitor", "ntp", "dns",
            "rpc", "rpc-ping", "tftp", "http_image_service", "service_monitor",
            ]
        self.assertThat(service.namedServices, KeysEqual(*expected_services))
        self.assertEqual(
            len(service.namedServices), len(service.services),
            "Not all services are named.")
        self.assertEqual(service, provisioningserver.services)
        self.assertThat(crochet.no_setup, MockCalledOnceWith())
        self.assertThat(
            logger.configure, MockCalledOnceWith(
                options["verbosity"], logger.LoggingMode.TWISTD))

    def test_makeService_in_debug(self):
        """
        Only the site service is created when no options are given.
        """
        self.patch(settings, "DEBUG", True)
        options = Options()
        service_maker = ProvisioningServiceMaker("Harry", "Hill")
        self.patch(service_maker, '_loadSettings')
        service = service_maker.makeService(options, clock=None)
        self.assertIsInstance(service, MultiService)
        expected_services = [
            "dhcp_probe", "networks_monitor", "image_download",
            "lease_socket_service", "node_monitor", "ntp", "dns",
            "rpc", "rpc-ping", "tftp", "http_image_service", "service_monitor",
            ]
        self.assertThat(service.namedServices, KeysEqual(*expected_services))
        self.assertEqual(
            len(service.namedServices), len(service.services),
            "Not all services are named.")
        self.assertEqual(service, provisioningserver.services)
        self.assertThat(crochet.no_setup, MockCalledOnceWith())
        self.assertThat(
            logger.configure, MockCalledOnceWith(
                3, logger.LoggingMode.TWISTD))

    def test_makeService_with_EXPERIMENTAL_tftp_offload_service(self):
        """
        Only the site service is created when no options are given.
        """
        # Activate the offload service by setting port to 0.
        self.useFixture(ClusterConfigurationFixture(tftp_port=0))

        options = Options()
        service_maker = ProvisioningServiceMaker("Harry", "Hill")
        service = service_maker.makeService(options, clock=None)
        self.assertIsInstance(service, MultiService)
        self.assertThat(service.namedServices, Not(Contains("tftp")))
        self.assertThat(service.namedServices, Contains("tftp-offload"))
        tftp_offload_service = service.getServiceNamed("tftp-offload")
        self.assertThat(tftp_offload_service, IsInstance(TFTPOffloadService))

    def test_makeService_patches_tftp_service(self):
        mock_tftp_patch = (
            self.patch(plugin_module, 'add_patches_to_txtftp'))
        options = Options()
        service_maker = ProvisioningServiceMaker("Harry", "Hill")
        service_maker.makeService(options, clock=None)
        self.assertThat(mock_tftp_patch, MockCalledOnceWith())

    def test_image_download_service(self):
        options = Options()
        service_maker = ProvisioningServiceMaker("Harry", "Hill")
        service = service_maker.makeService(options, clock=None)
        image_service = service.getServiceNamed("image_download")
        self.assertIsInstance(image_service, ImageDownloadService)

    def test_node_monitor_service(self):
        options = Options()
        service_maker = ProvisioningServiceMaker("Harry", "Hill")
        service = service_maker.makeService(options, clock=None)
        node_monitor = service.getServiceNamed("node_monitor")
        self.assertIsInstance(node_monitor, NodePowerMonitorService)

    def test_networks_monitor_service(self):
        options = Options()
        service_maker = ProvisioningServiceMaker("Spike", "Milligan")
        service = service_maker.makeService(options, clock=None)
        networks_monitor = service.getServiceNamed("networks_monitor")
        self.assertIsInstance(networks_monitor, RackNetworksMonitoringService)

    def test_dhcp_probe_service(self):
        options = Options()
        service_maker = ProvisioningServiceMaker("Spike", "Milligan")
        service = service_maker.makeService(options, clock=None)
        dhcp_probe = service.getServiceNamed("dhcp_probe")
        self.assertIsInstance(dhcp_probe, DHCPProbeService)

    def test_service_monitor_service(self):
        options = Options()
        service_maker = ProvisioningServiceMaker("Harry", "Hill")
        service = service_maker.makeService(options, clock=None)
        service_monitor = service.getServiceNamed("service_monitor")
        self.assertIsInstance(service_monitor, ServiceMonitorService)

    def test_rpc_ping_service(self):
        options = Options()
        service_maker = ProvisioningServiceMaker("Harry", "Hill")
        service = service_maker.makeService(options, clock=None)
        rpc_ping = service.getServiceNamed("rpc-ping")
        self.assertIsInstance(rpc_ping, ClusterClientCheckerService)

    def test_dns_service(self):
        options = Options()
        service_maker = ProvisioningServiceMaker("Harry", "Hill")
        service = service_maker.makeService(options, clock=None)
        dns_service = service.getServiceNamed("dns")
        self.assertIsInstance(dns_service, RackDNSService)

    def test_tftp_service(self):
        # A TFTP service is configured and added to the top-level service.
        options = Options()
        service_maker = ProvisioningServiceMaker("Harry", "Hill")
        service = service_maker.makeService(options, clock=None)
        tftp_service = service.getServiceNamed("tftp")
        self.assertIsInstance(tftp_service, TFTPService)

        with ClusterConfiguration.open() as config:
            tftp_root = config.tftp_root
            tftp_port = config.tftp_port

        expected_backend = MatchesAll(
            IsInstance(TFTPBackend),
            AfterPreprocessing(
                lambda backend: backend.base.path,
                Equals(tftp_root)))

        self.assertThat(
            tftp_service, MatchesStructure(
                backend=expected_backend,
                port=Equals(tftp_port),
            ))

    def test_lease_socket_service(self):
        options = Options()
        service_maker = ProvisioningServiceMaker("Harry", "Hill")
        service = service_maker.makeService(options, clock=None)
        lease_socket_service = service.getServiceNamed("lease_socket_service")
        self.assertIsInstance(lease_socket_service, LeaseSocketService)

    def test_http_image_service(self):
        options = Options()
        service_maker = ProvisioningServiceMaker("Harry", "Hill")
        service = service_maker.makeService(options, clock=None)
        lease_socket_service = service.getServiceNamed("http_image_service")
        self.assertIsInstance(lease_socket_service, HTTPImageService)


class TestProvisioningHTTPServiceMaker(MAASTestCase):
    """Tests for `provisioningserver.plugin.ProvisioningHTTPServiceMaker`."""

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

    def setUp(self):
        super(TestProvisioningHTTPServiceMaker, self).setUp()
        self.useFixture(ClusterConfigurationFixture())
        self.patch_autospec(logger, "configure")

    def test_init(self):
        service_maker = ProvisioningHTTPServiceMaker("Harry", "Hill")
        self.assertEqual("Harry", service_maker.tapname)
        self.assertEqual("Hill", service_maker.description)

    def test_makeService_not_in_debug(self):
        self.patch(settings, "DEBUG", False)
        options = Options()
        service_maker = ProvisioningHTTPServiceMaker("Harry", "Hill")
        self.patch(service_maker, '_loadSettings')
        service = service_maker.makeService(options, clock=None)
        self.assertIsInstance(service, EndpointService)
        self.assertThat(
            logger.configure, MockCalledOnceWith(
                options["verbosity"], logger.LoggingMode.TWISTD))

    def test_makeService_in_debug(self):
        self.patch(settings, "DEBUG", True)
        options = Options()
        service_maker = ProvisioningHTTPServiceMaker("Harry", "Hill")
        self.patch(service_maker, '_loadSettings')
        service = service_maker.makeService(options, clock=None)
        self.assertIsInstance(service, EndpointService)
        self.assertThat(
            logger.configure, MockCalledOnceWith(
                3, logger.LoggingMode.TWISTD))

    def test__makeHTTPImageService(self):
        options = Options()
        service_maker = ProvisioningHTTPServiceMaker("Harry", "Hill")
        service = service_maker.makeService(options, clock=None)
        self.assertIsInstance(service, EndpointService)
        self.assertIsInstance(service.site, Site)
        self.assertThat(service.site, MatchesStructure(
            _logFormatter=Is(reducedWebLogFormatter)))
        resource = service.site.resource
        root = resource.getChildWithDefault(b"images", request=None)
        self.assertThat(root, IsInstance(FilePath))

        with ClusterConfiguration.open() as config:
            resource_root = FilePath(config.tftp_root)

        self.assertEqual(resource_root, root)
