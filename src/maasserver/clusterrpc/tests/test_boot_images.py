# Copyright 2014-2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the `boot_images` module."""


import os
import random
from typing import Dict, List
from unittest.mock import ANY, MagicMock, sentinel
from urllib.parse import urlparse

from testtools.matchers import (
    Equals,
    Is,
    IsInstance,
    MatchesAll,
    MatchesListwise,
    MatchesStructure,
)
from twisted.internet.defer import DeferredLock, fail, maybeDeferred, succeed
from twisted.internet.task import Clock
from twisted.python.failure import Failure

from maasserver.bootresources import get_simplestream_endpoint
from maasserver.clusterrpc import boot_images as boot_images_module
from maasserver.clusterrpc.boot_images import (
    get_all_available_boot_images,
    get_boot_images,
    get_boot_images_for,
    get_common_available_boot_images,
    is_import_boot_images_running,
    RackControllersImporter,
)
from maasserver.clusterrpc.testing.boot_images import make_rpc_boot_image
from maasserver.enum import BOOT_RESOURCE_TYPE
from maasserver.models.config import Config
from maasserver.models.signals import bootsources
from maasserver.rpc import getAllClients
from maasserver.rpc.testing.fixtures import (
    MockLiveRegionToClusterRPCFixture,
    RunningClusterRPCFixture,
)
from maasserver.testing.eventloop import (
    RegionEventLoopFixture,
    RunningEventLoopFixture,
)
from maasserver.testing.factory import factory
from maasserver.testing.testcase import (
    MAASServerTestCase,
    MAASTransactionServerTestCase,
)
from maastesting import get_testing_timeout
from maastesting.matchers import MockCalledOnceWith, MockNotCalled
from maastesting.twisted import TwistedLoggerFixture
from provisioningserver.boot.tests import test_tftppath
from provisioningserver.boot.tftppath import compose_image_path
from provisioningserver.rpc import boot_images
from provisioningserver.rpc.cluster import ImportBootImages, ListBootImages
from provisioningserver.rpc.exceptions import NoConnectionsAvailable
from provisioningserver.testing.boot_images import (
    make_boot_image_storage_params,
    make_image,
)
from provisioningserver.testing.config import ClusterConfigurationFixture

TIMEOUT = get_testing_timeout()


def make_image_dir(image_params, tftp_root):
    """Fake a boot image matching `image_params` under `tftp_root`."""
    image_dir = os.path.join(
        tftp_root,
        compose_image_path(
            osystem=image_params["osystem"],
            arch=image_params["architecture"],
            subarch=image_params["subarchitecture"],
            release=image_params["release"],
            label=image_params["label"],
        ),
    )
    os.makedirs(image_dir)
    factory.make_file(image_dir, "linux")
    factory.make_file(image_dir, "initrd.gz")


class TestIsImportBootImagesRunning(MAASTransactionServerTestCase):
    """Tests for `is_import_boot_images_running`."""

    def test_returns_True_when_one_cluster_returns_True(self):
        factory.make_RackController()
        factory.make_RackController()
        factory.make_RackController()
        self.useFixture(RunningClusterRPCFixture())

        clients = getAllClients()
        for index, client in enumerate(clients):
            callRemote = self.patch(client._conn, "callRemote")
            if index == 0:
                # The first client returns all False.
                callRemote.return_value = succeed({"running": False})
            else:
                # All clients but the first return True.
                callRemote.return_value = succeed({"running": True})

        self.assertTrue(is_import_boot_images_running())

    def test_returns_False_when_all_clusters_return_False(self):
        factory.make_RackController()
        factory.make_RackController()
        factory.make_RackController()
        self.useFixture(RunningClusterRPCFixture())

        clients = getAllClients()
        for index, client in enumerate(clients):
            callRemote = self.patch(client._conn, "callRemote")
            callRemote.return_value = succeed({"running": False})

        self.assertFalse(is_import_boot_images_running())

    def test_ignores_failures_when_talking_to_clusters(self):
        factory.make_RackController()
        factory.make_RackController()
        factory.make_RackController()
        self.useFixture(RunningClusterRPCFixture())

        clients = getAllClients()
        for index, client in enumerate(clients):
            callRemote = self.patch(client._conn, "callRemote")
            if index == 0:
                # The first client returns True.
                callRemote.return_value = succeed({"running": True})
            else:
                # All clients but the first raise an exception.
                callRemote.side_effect = ZeroDivisionError()

        self.assertTrue(is_import_boot_images_running())


def prepare_tftp_root(test):
    """Create a `current` directory and configure its use."""
    test.tftp_root = os.path.join(test.make_dir(), "current")
    os.mkdir(test.tftp_root)
    test.patch(boot_images, "CACHED_BOOT_IMAGES", None)
    config = ClusterConfigurationFixture(tftp_root=test.tftp_root)
    test.useFixture(config)


class TestGetBootImages(MAASServerTestCase):
    """Tests for `get_boot_images`."""

    def setUp(self):
        super().setUp()
        prepare_tftp_root(self)  # Sets self.tftp_root.

    def test_calls_ListBootImages(self):
        rack_controller = factory.make_RackController()
        mock_client = MagicMock()
        self.patch_autospec(
            boot_images_module, "getClientFor"
        ).return_value = mock_client
        get_boot_images(rack_controller)
        self.assertThat(mock_client, MockCalledOnceWith(ListBootImages))


class TestGetBootImagesTxn(MAASTransactionServerTestCase):
    """Transactional tests for `get_boot_images`."""

    def setUp(self):
        super().setUp()
        prepare_tftp_root(self)  # Sets self.tftp_root.

    def test_returns_boot_images(self):
        rack_controller = factory.make_RackController()
        self.useFixture(RunningClusterRPCFixture())

        purposes = ["install", "commissioning", "xinstall"]
        params = [make_boot_image_storage_params() for _ in range(3)]
        for param in params:
            make_image_dir(param, self.tftp_root)
            test_tftppath.make_osystem(self, param["osystem"], purposes)
        self.assertCountEqual(
            [
                make_image(param, purpose)
                for param in params
                for purpose in purposes
            ],
            get_boot_images(rack_controller),
        )


class TestGetAvailableBootImages(MAASTransactionServerTestCase):
    """Tests for `get_common_available_boot_images` and
    `get_all_available_boot_images`."""

    scenarios = (
        (
            "get_common_available_boot_images",
            {"get": get_common_available_boot_images, "all": False},
        ),
        (
            "get_all_available_boot_images",
            {"get": get_all_available_boot_images, "all": True},
        ),
    )

    def setUp(self):
        super().setUp()
        prepare_tftp_root(self)  # Sets self.tftp_root.

    def test_returns_boot_images_for_one_cluster(self):
        factory.make_RackController()
        self.useFixture(RunningClusterRPCFixture())

        purposes = ["install", "commissioning", "xinstall"]
        params = [make_boot_image_storage_params() for _ in range(3)]
        for param in params:
            make_image_dir(param, self.tftp_root)
            test_tftppath.make_osystem(self, param["osystem"], purposes)
        self.assertCountEqual(
            [
                make_image(param, purpose)
                for param in params
                for purpose in purposes
            ],
            self.get(),
        )

    def test_returns_boot_images_on_all_clusters(self):
        factory.make_RackController()
        factory.make_RackController()
        factory.make_RackController()
        self.useFixture(RunningClusterRPCFixture())

        images = [make_rpc_boot_image() for _ in range(3)]
        available_images = list(images)
        available_images.pop()

        clients = getAllClients()
        for index, client in enumerate(clients):
            callRemote = self.patch(client._conn, "callRemote")
            if index == 0:
                # The first client returns all images.
                callRemote.return_value = succeed({"images": images})
            else:
                # All clients but the first return only available images.
                callRemote.return_value = succeed({"images": available_images})

        expected_images = images if self.all else available_images
        self.assertCountEqual(expected_images, self.get())

    def test_ignores_failures_when_talking_to_clusters(self):
        factory.make_RackController()
        factory.make_RackController()
        factory.make_RackController()
        self.useFixture(RunningClusterRPCFixture())

        images = [make_rpc_boot_image() for _ in range(3)]

        clients = getAllClients()
        for index, client in enumerate(clients):
            callRemote = self.patch(client._conn, "callRemote")
            if index == 0:
                # The first client returns correct image information.
                callRemote.return_value = succeed({"images": images})
            else:
                # All clients but the first raise an exception.
                callRemote.side_effect = ZeroDivisionError()

        self.assertCountEqual(images, self.get())

    def test_returns_empty_list_when_all_clusters_fail(self):
        factory.make_RackController()
        factory.make_RackController()
        factory.make_RackController()
        self.useFixture(RunningClusterRPCFixture())

        clients = getAllClients()
        for index, client in enumerate(clients):
            callRemote = self.patch(client._conn, "callRemote")
            callRemote.side_effect = ZeroDivisionError()

        self.assertEqual([], self.get())


class TestGetBootImagesFor(MAASTransactionServerTestCase):
    """Tests for `get_boot_images_for`."""

    def setUp(self):
        super().setUp()
        prepare_tftp_root(self)  # Sets self.tftp_root.

    def make_boot_images(self):
        purposes = ["install", "commissioning", "xinstall"]
        params = [make_boot_image_storage_params() for _ in range(3)]
        for param in params:
            make_image_dir(param, self.tftp_root)
            test_tftppath.make_osystem(self, param["osystem"], purposes)
        return params

    def make_rpc_boot_images(self, param, remove_platform=False) -> List[Dict]:
        purposes = ["install", "commissioning", "xinstall"]
        result = []
        for purpose in purposes:
            image = make_image(param, purpose)
            if remove_platform:
                if "platform" in image:
                    del image["platform"]
                if "supported_platforms" in image:
                    del image["supported_platforms"]
            result.append(image)
        return result

    def test_returns_boot_images_matching_subarchitecture(self):
        rack = factory.make_RackController()
        self.useFixture(RunningClusterRPCFixture())
        params = self.make_boot_images()
        param = params.pop()

        self.assertCountEqual(
            self.make_rpc_boot_images(param, remove_platform=True),
            get_boot_images_for(
                rack,
                param["osystem"],
                param["architecture"],
                param["subarchitecture"],
                param["release"],
            ),
        )

    def test_returns_boot_images_matching_subarches_in_boot_resources(self):
        rack = factory.make_RackController()
        self.useFixture(RunningClusterRPCFixture())
        params = self.make_boot_images()
        param = params.pop()

        subarches = [factory.make_name("subarch") for _ in range(3)]
        resource_name = "{}/{}".format(param["osystem"], param["release"])
        resource_arch = "{}/{}".format(
            param["architecture"],
            param["subarchitecture"],
        )

        resource = factory.make_BootResource(
            rtype=BOOT_RESOURCE_TYPE.SYNCED,
            name=resource_name,
            architecture=resource_arch,
        )
        extra = resource.extra.copy()
        extra["subarches"] = ",".join(subarches)
        resource.extra = extra
        resource.save()

        subarch = subarches.pop()
        expected = self.make_rpc_boot_images(param, remove_platform=True)
        for image in expected:
            image["platform"] = resource.extra["platform"]
            image["supported_platforms"] = resource.extra[
                "supported_platforms"
            ]
        observed = get_boot_images_for(
            rack,
            param["osystem"],
            param["architecture"],
            subarch,
            param["release"],
        )

        self.assertCountEqual(expected, observed)


class TestRackControllersImporter(MAASServerTestCase):
    """Tests for `RackControllersImporter`."""

    def test_init_with_single_system_id(self):
        system_id = factory.make_name("system_id")
        sources = [sentinel.source]
        proxy = factory.make_simple_http_url()

        importer = RackControllersImporter(system_id, sources, proxy)

        self.assertThat(
            importer,
            MatchesStructure(
                system_ids=Equals((system_id,)),
                sources=Is(sources),
                proxy=Equals(urlparse(proxy)),
            ),
        )

    def test_init_with_multiple_ssytem_ids(self):
        system_ids = [factory.make_name("system_id") for _ in range(3)]
        sources = [sentinel.source]
        proxy = factory.make_simple_http_url()

        importer = RackControllersImporter(system_ids, sources, proxy)

        self.assertThat(
            importer,
            MatchesStructure(
                system_ids=Equals(tuple(system_ids)),
                sources=Is(sources),
                proxy=Equals(urlparse(proxy)),
            ),
        )

    def test_init_also_accepts_already_parsed_proxy(self):
        proxy = urlparse(factory.make_simple_http_url())
        importer = RackControllersImporter(
            sentinel.system_id, [sentinel.source], proxy
        )
        self.assertThat(importer, MatchesStructure(proxy=Is(proxy)))

    def test_init_also_accepts_no_proxy(self):
        importer = RackControllersImporter(
            sentinel.system_id, [sentinel.source]
        )
        self.assertThat(importer, MatchesStructure(proxy=Is(None)))

    def test_schedule_arranges_for_later_run(self):
        # Avoid deferring to the database.
        self.patch(boot_images_module, "deferToDatabase", maybeDeferred)
        # Avoid actually initiating a run.
        self.patch_autospec(RackControllersImporter, "run")

        system_ids = [factory.make_name("system_id") for _ in range(3)]
        sources = [sentinel.source]
        proxy = factory.make_simple_http_url()

        conc = random.randint(1, 9)
        delay = random.randint(1, 9)

        clock = Clock()
        delayed_call = RackControllersImporter.schedule(
            system_ids=system_ids,
            sources=sources,
            proxy=proxy,
            delay=delay,
            concurrency=conc,
            clock=clock,
        )

        # The call is scheduled for `delay` seconds from now.
        self.assertThat(delayed_call, MatchesStructure(time=Equals(delay)))
        self.assertThat(RackControllersImporter.run, MockNotCalled())
        clock.advance(delay)
        self.assertThat(
            RackControllersImporter.run, MockCalledOnceWith(ANY, conc)
        )

        # The system_ids, sources, and proxy were all passed through.
        [importer, _] = RackControllersImporter.run.call_args[0]
        self.assertThat(
            importer,
            MatchesStructure(
                system_ids=Equals(tuple(system_ids)),
                sources=Is(sources),
                proxy=Equals(urlparse(proxy)),
            ),
        )

    def test_run_will_not_error_instead_it_logs(self):
        call = self.patch(RackControllersImporter, "__call__")
        call.return_value = fail(ZeroDivisionError())

        with TwistedLoggerFixture() as logger:
            RackControllersImporter([], []).run().wait(TIMEOUT)

        self.assertThat(call, MockCalledOnceWith(ANY))
        self.assertDocTestMatches(
            """\
            General failure syncing boot resources.
            Traceback (most recent call last):
            ...
            """,
            logger.output,
        )


class TestRackControllersImporterNew(MAASServerTestCase):
    """Tests for the `RackControllersImporter.new` function."""

    def test_new_obtains_system_ids_if_not_given(self):
        importer = RackControllersImporter.new(sources=[], proxy=None)
        self.assertThat(importer, MatchesStructure(system_ids=Equals(())))

    def test_new_obtains_system_ids_for_accepted_clusters_if_not_given(self):
        rack = factory.make_RackController()

        importer = RackControllersImporter.new(sources=[], proxy=None)

        self.assertThat(
            importer, MatchesStructure(system_ids=Equals((rack.system_id,)))
        )

    def test_new_obtains_sources_if_not_given(self):
        importer = RackControllersImporter.new(system_ids=[], proxy=None)
        self.assertThat(
            importer,
            MatchesStructure(sources=Equals([get_simplestream_endpoint()])),
        )

    def test_new_obtains_proxy_if_not_given(self):
        # Disable boot source cache signals.
        self.addCleanup(bootsources.signals.enable)
        bootsources.signals.disable()

        proxy = factory.make_simple_http_url()
        Config.objects.set_config("http_proxy", proxy)
        importer = RackControllersImporter.new(system_ids=[], sources=[])
        self.assertThat(
            importer, MatchesStructure(proxy=Equals(urlparse(proxy)))
        )

    def test_new_obtains_None_proxy_if_disabled(self):
        # Disable boot source cache signals.
        self.addCleanup(bootsources.signals.enable)
        bootsources.signals.disable()

        proxy = factory.make_simple_http_url()
        Config.objects.set_config("http_proxy", proxy)
        Config.objects.set_config("enable_http_proxy", False)
        importer = RackControllersImporter.new(system_ids=[], sources=[])
        self.assertThat(importer, MatchesStructure(proxy=Equals(None)))


class TestRackControllersImporterInAction(MAASTransactionServerTestCase):
    """Live tests for `RackControllersImporter`."""

    def setUp(self):
        super().setUp()
        # Limit the region's event loop to only the "rpc" service.
        self.useFixture(RegionEventLoopFixture("rpc"))
        # Now start the region's event loop.
        self.useFixture(RunningEventLoopFixture())
        # This fixture allows us to simulate mock clusters.
        self.rpc = self.useFixture(MockLiveRegionToClusterRPCFixture())

    def test_calling_importer_issues_rpc_calls_to_clusters(self):
        # Some clusters that we'll ask to import resources.
        rack_1 = factory.make_RackController()
        rack_2 = factory.make_RackController()

        # Connect only cluster #1.
        rack_1_conn = self.rpc.makeCluster(rack_1, ImportBootImages)
        rack_1_conn.ImportBootImages.return_value = succeed({})

        # Do the import.
        importer = RackControllersImporter.new(
            [rack_1.system_id, rack_2.system_id]
        )
        results = importer(lock=DeferredLock()).wait(TIMEOUT)

        # The results are a list (it's from a DeferredList).
        self.assertThat(
            results,
            MatchesListwise(
                (
                    # Success when calling rack_1.
                    Equals((True, {})),
                    # Failure when calling rack_1: no connection.
                    MatchesListwise(
                        (
                            Is(False),
                            MatchesAll(
                                IsInstance(Failure),
                                MatchesStructure(
                                    value=IsInstance(NoConnectionsAvailable)
                                ),
                            ),
                        )
                    ),
                )
            ),
        )

    def test_run_calls_importer_and_reports_results(self):
        # Some clusters that we'll ask to import resources.
        rack_1 = factory.make_RackController()
        rack_2 = factory.make_RackController()
        rack_3 = factory.make_RackController()

        # Cluster #1 will work fine.
        cluster_1 = self.rpc.makeCluster(rack_1, ImportBootImages)
        cluster_1.ImportBootImages.return_value = succeed({})

        # Cluster #2 will break.
        cluster_2 = self.rpc.makeCluster(rack_2, ImportBootImages)
        cluster_2.ImportBootImages.return_value = fail(ZeroDivisionError())

        # Cluster #3 is not connected.

        # Do the import with reporting.
        importer = RackControllersImporter.new(
            [rack_1.system_id, rack_2.system_id, rack_3.system_id]
        )

        with TwistedLoggerFixture() as logger:
            importer.run().wait(TIMEOUT)

        self.assertDocTestMatches(
            """\
            ...
            ---
            Rack controller (%s) has imported boot resources.
            ---
            Rack controller (%s) failed to import boot resources.
            Traceback (most recent call last):
            ...
            ---
            Rack controller (%s) did not import boot resources; it is not
            connected to the region at this time.
            """
            % (rack_1.system_id, rack_2.system_id, rack_3.system_id),
            logger.output,
        )
