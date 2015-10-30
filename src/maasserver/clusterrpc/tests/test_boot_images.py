# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the `boot_images` module."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import os
import random

from maasserver.bootresources import get_simplestream_endpoint
from maasserver.clusterrpc import boot_images as boot_images_module
from maasserver.clusterrpc.boot_images import (
    get_all_available_boot_images,
    get_boot_images,
    get_boot_images_for,
    get_common_available_boot_images,
    is_import_boot_images_running,
    is_import_boot_images_running_for,
)
from maasserver.clusterrpc.testing.boot_images import make_rpc_boot_image
from maasserver.enum import (
    BOOT_RESOURCE_TYPE,
    NODEGROUP_STATUS,
)
from maasserver.models.config import Config
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
from maasserver.testing.testcase import MAASServerTestCase
from maastesting.matchers import (
    MockCalledOnceWith,
    MockCallsMatch,
    MockNotCalled,
)
from maastesting.testcase import MAASTestCase
from maastesting.twisted import TwistedLoggerFixture
from mock import (
    ANY,
    call,
    MagicMock,
)
from provisioningserver.boot.tests import test_tftppath
from provisioningserver.boot.tftppath import (
    compose_image_path,
    locate_tftp_path,
)
from provisioningserver.rpc import (
    boot_images,
    clusterservice,
)
from provisioningserver.rpc.cluster import (
    ImportBootImages,
    ListBootImages,
    ListBootImagesV2,
)
from provisioningserver.rpc.exceptions import NoConnectionsAvailable
from provisioningserver.testing.boot_images import (
    make_boot_image_storage_params,
    make_image,
)
from provisioningserver.testing.config import ClusterConfigurationFixture
from testtools.matchers import (
    IsInstance,
    MatchesAll,
    MatchesListwise,
)
from twisted.internet.defer import (
    DeferredLock,
    fail,
    maybeDeferred,
    succeed,
)
from twisted.internet.task import Clock
from twisted.protocols.amp import UnhandledCommand
from twisted.python.failure import Failure


def make_image_dir(image_params, tftp_root):
    """Fake a boot image matching `image_params` under `tftp_root`."""
    image_dir = locate_tftp_path(
        compose_image_path(
            osystem=image_params['osystem'],
            arch=image_params['architecture'],
            subarch=image_params['subarchitecture'],
            release=image_params['release'],
            label=image_params['label']),
        tftp_root)
    os.makedirs(image_dir)
    factory.make_file(image_dir, 'linux')
    factory.make_file(image_dir, 'initrd.gz')


class TestIsImportBootImagesRunning(MAASServerTestCase):
    """Tests for `is_import_boot_images_running`."""

    def test_returns_True_when_one_cluster_returns_True(self):
        factory.make_NodeGroup().accept()
        factory.make_NodeGroup().accept()
        factory.make_NodeGroup().accept()
        self.useFixture(RunningClusterRPCFixture())

        clients = getAllClients()
        for index, client in enumerate(clients):
            callRemote = self.patch(client._conn, "callRemote")
            if index == 0:
                # The first client returns all False.
                callRemote.return_value = succeed({'running': False})
            else:
                # All clients but the first return True.
                callRemote.return_value = succeed({'running': True})

        self.assertTrue(is_import_boot_images_running())

    def test_returns_False_when_all_clusters_return_False(self):
        factory.make_NodeGroup().accept()
        factory.make_NodeGroup().accept()
        factory.make_NodeGroup().accept()
        self.useFixture(RunningClusterRPCFixture())

        clients = getAllClients()
        for index, client in enumerate(clients):
            callRemote = self.patch(client._conn, "callRemote")
            callRemote.return_value = succeed({'running': False})

        self.assertFalse(is_import_boot_images_running())

    def test_ignores_failures_when_talking_to_clusters(self):
        factory.make_NodeGroup().accept()
        factory.make_NodeGroup().accept()
        factory.make_NodeGroup().accept()
        self.useFixture(RunningClusterRPCFixture())

        clients = getAllClients()
        for index, client in enumerate(clients):
            callRemote = self.patch(client._conn, "callRemote")
            if index == 0:
                # The first client returns True.
                callRemote.return_value = succeed({'running': True})
            else:
                # All clients but the first raise an exception.
                callRemote.side_effect = ZeroDivisionError()

        self.assertTrue(is_import_boot_images_running())


class TestIsImportBootImagesRunningFor(MAASServerTestCase):
    """Tests for `is_import_boot_images_running_for`."""

    def test_returns_True(self):
        mock_is_running = self.patch(
            clusterservice, "is_import_boot_images_running")
        mock_is_running.return_value = True
        nodegroup = factory.make_NodeGroup(status=NODEGROUP_STATUS.ENABLED)
        self.useFixture(RunningClusterRPCFixture())
        self.assertTrue(is_import_boot_images_running_for(nodegroup))

    def test_returns_False(self):
        mock_is_running = self.patch(
            clusterservice, "is_import_boot_images_running")
        mock_is_running.return_value = False
        nodegroup = factory.make_NodeGroup(status=NODEGROUP_STATUS.ENABLED)
        self.useFixture(RunningClusterRPCFixture())
        self.assertFalse(is_import_boot_images_running_for(nodegroup))


def prepare_tftp_root(test):
    """Create a `current` directory and configure its use."""
    test.tftp_root = os.path.join(test.make_dir(), 'current')
    os.mkdir(test.tftp_root)
    test.patch(boot_images, 'CACHED_BOOT_IMAGES', None)
    config = ClusterConfigurationFixture(tftp_root=test.tftp_root)
    test.useFixture(config)


class TestGetBootImages(MAASServerTestCase):
    """Tests for `get_boot_images`."""

    def setUp(self):
        super(TestGetBootImages, self).setUp()
        prepare_tftp_root(self)  # Sets self.tftp_root.

    def test_returns_boot_images(self):
        nodegroup = factory.make_NodeGroup(status=NODEGROUP_STATUS.ENABLED)
        self.useFixture(RunningClusterRPCFixture())

        purposes = ['install', 'commissioning', 'xinstall']
        params = [make_boot_image_storage_params() for _ in range(3)]
        for param in params:
            make_image_dir(param, self.tftp_root)
            test_tftppath.make_osystem(self, param['osystem'], purposes)
        self.assertItemsEqual(
            [
                make_image(param, purpose)
                for param in params
                for purpose in purposes
            ],
            get_boot_images(nodegroup))

    def test_calls_ListBootImagesV2_before_ListBootImages(self):
        nodegroup = factory.make_NodeGroup(status=NODEGROUP_STATUS.ENABLED)
        mock_client = MagicMock()
        self.patch_autospec(
            boot_images_module, "getClientFor").return_value = mock_client
        get_boot_images(nodegroup)
        self.assertThat(mock_client, MockCalledOnceWith(ListBootImagesV2))

    def test_calls_ListBootImages_if_raised_UnhandledCommand(self):
        nodegroup = factory.make_NodeGroup(status=NODEGROUP_STATUS.ENABLED)
        mock_client = MagicMock()
        self.patch_autospec(
            boot_images_module, "getClientFor").return_value = mock_client
        mock_client.return_value.wait.side_effect = [
            UnhandledCommand(),
            {"images": []},
            ]
        get_boot_images(nodegroup)
        self.assertThat(mock_client, MockCallsMatch(
            call(ListBootImagesV2),
            call(ListBootImages)))


class TestGetAvailableBootImages(MAASServerTestCase):
    """Tests for `get_common_available_boot_images` and
    `get_all_available_boot_images`."""

    scenarios = (
        ("get_common_available_boot_images", {
            "get": get_common_available_boot_images,
            "all": False,
        }),
        ("get_all_available_boot_images", {
            "get": get_all_available_boot_images,
            "all": True,
        }),
    )

    def setUp(self):
        super(TestGetAvailableBootImages, self).setUp()
        prepare_tftp_root(self)  # Sets self.tftp_root.

    def test_returns_boot_images_for_one_cluster(self):
        factory.make_NodeGroup().accept()
        self.useFixture(RunningClusterRPCFixture())

        purposes = ['install', 'commissioning', 'xinstall']
        params = [make_boot_image_storage_params() for _ in range(3)]
        for param in params:
            make_image_dir(param, self.tftp_root)
            test_tftppath.make_osystem(self, param['osystem'], purposes)
        self.assertItemsEqual(
            [
                make_image(param, purpose)
                for param in params
                for purpose in purposes
            ],
            self.get())

    def test_returns_boot_images_on_all_clusters(self):
        factory.make_NodeGroup().accept()
        factory.make_NodeGroup().accept()
        factory.make_NodeGroup().accept()
        self.useFixture(RunningClusterRPCFixture())

        images = [make_rpc_boot_image() for _ in range(3)]
        available_images = list(images)
        available_images.pop()

        clients = getAllClients()
        for index, client in enumerate(clients):
            callRemote = self.patch(client._conn, "callRemote")
            if index == 0:
                # The first client returns all images.
                callRemote.return_value = succeed({'images': images})
            else:
                # All clients but the first return only available images.
                callRemote.return_value = succeed({'images': available_images})

        expected_images = images if self.all else available_images
        self.assertItemsEqual(expected_images, self.get())

    def test_ignores_failures_when_talking_to_clusters(self):
        factory.make_NodeGroup().accept()
        factory.make_NodeGroup().accept()
        factory.make_NodeGroup().accept()
        self.useFixture(RunningClusterRPCFixture())

        images = [make_rpc_boot_image() for _ in range(3)]

        clients = getAllClients()
        for index, client in enumerate(clients):
            callRemote = self.patch(client._conn, "callRemote")
            if index == 0:
                # The first client returns correct image information.
                callRemote.return_value = succeed({'images': images})
            else:
                # All clients but the first raise an exception.
                callRemote.side_effect = ZeroDivisionError()

        self.assertItemsEqual(images, self.get())

    def test_fallback_to_ListBootImages_on_old_clusters(self):
        nodegroup_1 = factory.make_NodeGroup()
        nodegroup_1.accept()
        nodegroup_2 = factory.make_NodeGroup()
        nodegroup_2.accept()
        nodegroup_3 = factory.make_NodeGroup()
        nodegroup_3.accept()

        images = [make_rpc_boot_image() for _ in range(3)]

        # Limit the region's event loop to only the "rpc" service.
        self.useFixture(RegionEventLoopFixture("rpc"))
        # Now start the region's event loop.
        self.useFixture(RunningEventLoopFixture())
        # This fixture allows us to simulate mock clusters.
        rpc = self.useFixture(MockLiveRegionToClusterRPCFixture())

        # This simulates an older cluster, one without ListBootImagesV2.
        cluster_1 = rpc.makeCluster(nodegroup_1, ListBootImages)
        cluster_1.ListBootImages.return_value = succeed({'images': images})

        # This simulates a newer cluster, one with ListBootImagesV2.
        cluster_2 = rpc.makeCluster(nodegroup_2, ListBootImagesV2)
        cluster_2.ListBootImagesV2.return_value = succeed({'images': images})

        # This simulates a broken cluster.
        cluster_3 = rpc.makeCluster(nodegroup_3, ListBootImagesV2)
        cluster_3.ListBootImagesV2.side_effect = ZeroDivisionError

        self.assertItemsEqual(images, self.get())

    def test_returns_empty_list_when_all_clusters_fail(self):
        factory.make_NodeGroup().accept()
        factory.make_NodeGroup().accept()
        factory.make_NodeGroup().accept()
        self.useFixture(RunningClusterRPCFixture())

        clients = getAllClients()
        for index, client in enumerate(clients):
            callRemote = self.patch(client._conn, "callRemote")
            callRemote.side_effect = ZeroDivisionError()

        self.assertItemsEqual([], self.get())


class TestGetBootImagesFor(MAASServerTestCase):
    """Tests for `get_boot_images_for`."""

    def setUp(self):
        super(TestGetBootImagesFor, self).setUp()
        prepare_tftp_root(self)  # Sets self.tftp_root.

    def make_boot_images(self):
        purposes = ['install', 'commissioning', 'xinstall']
        params = [make_boot_image_storage_params() for _ in range(3)]
        for param in params:
            make_image_dir(param, self.tftp_root)
            test_tftppath.make_osystem(self, param['osystem'], purposes)
        return params

    def make_rpc_boot_images(self, param):
        purposes = ['install', 'commissioning', 'xinstall']
        return [
            make_image(param, purpose)
            for purpose in purposes
            ]

    def test_returns_boot_images_matching_subarchitecture(self):
        nodegroup = factory.make_NodeGroup(status=NODEGROUP_STATUS.ENABLED)
        self.useFixture(RunningClusterRPCFixture())
        params = self.make_boot_images()
        param = params.pop()

        self.assertItemsEqual(
            self.make_rpc_boot_images(param),
            get_boot_images_for(
                nodegroup,
                param['osystem'],
                param['architecture'],
                param['subarchitecture'],
                param['release']))

    def test_returns_boot_images_matching_subarches_in_boot_resources(self):
        nodegroup = factory.make_NodeGroup(status=NODEGROUP_STATUS.ENABLED)
        self.useFixture(RunningClusterRPCFixture())
        params = self.make_boot_images()
        param = params.pop()

        subarches = [factory.make_name('subarch') for _ in range(3)]
        resource_name = '%s/%s' % (param['osystem'], param['release'])
        resource_arch = '%s/%s' % (
            param['architecture'], param['subarchitecture'])

        resource = factory.make_BootResource(
            rtype=BOOT_RESOURCE_TYPE.SYNCED,
            name=resource_name, architecture=resource_arch)
        resource.extra['subarches'] = ','.join(subarches)
        resource.save()

        subarch = subarches.pop()
        self.assertItemsEqual(
            self.make_rpc_boot_images(param),
            get_boot_images_for(
                nodegroup,
                param['osystem'],
                param['architecture'],
                subarch,
                param['release']))


from mock import sentinel
from maasserver.clusterrpc.boot_images import ClustersImporter
from testtools.matchers import MatchesStructure, Is, Equals
from urlparse import urlparse


class TestClustersImporter(MAASTestCase):
    """Tests for `ClustersImporter`."""

    def test__init_with_single_UUIDs(self):
        uuid = factory.make_UUID()
        sources = [sentinel.source]
        proxy = factory.make_simple_http_url()

        importer = ClustersImporter(uuid, sources, proxy)

        self.assertThat(importer, MatchesStructure(
            uuids=Equals((uuid, )), sources=Is(sources),
            proxy=Equals(urlparse(proxy)),
        ))

    def test__init_with_multiple_UUIDs(self):
        uuids = [factory.make_UUID() for _ in xrange(3)]
        sources = [sentinel.source]
        proxy = factory.make_simple_http_url()

        importer = ClustersImporter(uuids, sources, proxy)

        self.assertThat(importer, MatchesStructure(
            uuids=Equals(tuple(uuids)), sources=Is(sources),
            proxy=Equals(urlparse(proxy)),
        ))

    def test__init_also_accepts_already_parsed_proxy(self):
        proxy = urlparse(factory.make_simple_http_url())
        importer = ClustersImporter(sentinel.uuid, [sentinel.source], proxy)
        self.assertThat(importer, MatchesStructure(proxy=Is(proxy)))

    def test__init_also_accepts_no_proxy(self):
        importer = ClustersImporter(sentinel.uuid, [sentinel.source])
        self.assertThat(importer, MatchesStructure(proxy=Is(None)))

    def test__schedule_arranges_for_later_run(self):
        # Avoid deferring to the database.
        self.patch(boot_images_module, "deferToDatabase", maybeDeferred)
        # Avoid actually initiating a run.
        self.patch_autospec(ClustersImporter, "run")

        uuids = [factory.make_UUID() for _ in xrange(3)]
        sources = [sentinel.source]
        proxy = factory.make_simple_http_url()

        conc = random.randint(1, 9)
        delay = random.randint(1, 9)

        clock = Clock()
        delayed_call = ClustersImporter.schedule(
            uuids=uuids, sources=sources, proxy=proxy, delay=delay,
            concurrency=conc, clock=clock)

        # The call is scheduled for `delay` seconds from now.
        self.assertThat(delayed_call, MatchesStructure(time=Equals(delay)))
        self.assertThat(ClustersImporter.run, MockNotCalled())
        clock.advance(delay)
        self.assertThat(ClustersImporter.run, MockCalledOnceWith(ANY, conc))

        # The UUIDs, sources, and proxy were all passed through.
        [importer, _] = ClustersImporter.run.call_args[0]
        self.assertThat(importer, MatchesStructure(
            uuids=Equals(tuple(uuids)), sources=Is(sources),
            proxy=Equals(urlparse(proxy)),
        ))

    def test__run_will_not_error_instead_it_logs(self):
        call = self.patch(ClustersImporter, "__call__")
        call.return_value = fail(ZeroDivisionError)

        with TwistedLoggerFixture() as logger:
            ClustersImporter([], []).run().wait(5)

        self.assertThat(call, MockCalledOnceWith(ANY))
        self.assertDocTestMatches(
            """\
            General failure syncing boot resources.
            Traceback (most recent call last):
            ...
            """,
            logger.output)


class TestClustersImporterNew(MAASServerTestCase):
    """Tests for the `ClustersImporter.new` function."""

    def test__new_obtains_uuids_if_not_given(self):
        importer = ClustersImporter.new(sources=[], proxy=None)
        self.assertThat(importer, MatchesStructure(uuids=Equals(())))

    def test__new_obtains_uuids_for_accepted_clusters_if_not_given(self):
        cluster_accepted = factory.make_NodeGroup()
        cluster_accepted.accept()
        cluster_rejected = factory.make_NodeGroup()
        cluster_rejected.reject()

        importer = ClustersImporter.new(sources=[], proxy=None)

        self.assertThat(importer, MatchesStructure(
            uuids=Equals((cluster_accepted.uuid, ))))

    def test__new_obtains_sources_if_not_given(self):
        importer = ClustersImporter.new(uuids=[], proxy=None)
        self.assertThat(importer, MatchesStructure(
            sources=Equals([get_simplestream_endpoint()])))

    def test__new_obtains_proxy_if_not_given(self):
        proxy = factory.make_simple_http_url()
        Config.objects.set_config("http_proxy", proxy)
        importer = ClustersImporter.new(uuids=[], sources=[])
        self.assertThat(importer, MatchesStructure(
            proxy=Equals(urlparse(proxy))))

    def test__new_obtains_None_proxy_if_disabled(self):
        proxy = factory.make_simple_http_url()
        Config.objects.set_config("http_proxy", proxy)
        Config.objects.set_config("enable_http_proxy", False)
        importer = ClustersImporter.new(uuids=[], sources=[])
        self.assertThat(importer, MatchesStructure(
            proxy=Equals(None)))


class TestClustersImporterInAction(MAASServerTestCase):
    """Live tests for `ClustersImporter`."""

    def setUp(self):
        super(TestClustersImporterInAction, self).setUp()
        # Limit the region's event loop to only the "rpc" service.
        self.useFixture(RegionEventLoopFixture("rpc"))
        # Now start the region's event loop.
        self.useFixture(RunningEventLoopFixture())
        # This fixture allows us to simulate mock clusters.
        self.rpc = self.useFixture(MockLiveRegionToClusterRPCFixture())

    def test__calling_importer_issues_rpc_calls_to_clusters(self):
        # Some clusters that we'll ask to import resources.
        nodegroup_1 = factory.make_NodeGroup()
        nodegroup_1.accept()
        nodegroup_2 = factory.make_NodeGroup()
        nodegroup_2.accept()

        # Connect only cluster #1.
        cluster_1 = self.rpc.makeCluster(nodegroup_1, ImportBootImages)
        cluster_1.ImportBootImages.return_value = succeed({})

        # Do the import.
        importer = ClustersImporter.new([nodegroup_1.uuid, nodegroup_2.uuid])
        results = importer(lock=DeferredLock()).wait(5)

        # The results are a list (it's from a DeferredList).
        self.assertThat(results, MatchesListwise((
            # Success when calling nodegroup_1.
            Equals((True, {})),
            # Failure when calling nodegroup_2: no connection.
            MatchesListwise((
                Is(False), MatchesAll(
                    IsInstance(Failure), MatchesStructure(
                        value=IsInstance(NoConnectionsAvailable)),
                ),
            )),
        )))

    def test__run_calls_importer_and_reports_results(self):
        # Some clusters that we'll ask to import resources.
        nodegroup_1 = factory.make_NodeGroup(uuid="cluster-1")
        nodegroup_1.accept()
        nodegroup_2 = factory.make_NodeGroup(uuid="cluster-2")
        nodegroup_2.accept()
        nodegroup_3 = factory.make_NodeGroup(uuid="cluster-3")
        nodegroup_3.accept()

        # Cluster #1 will work fine.
        cluster_1 = self.rpc.makeCluster(nodegroup_1, ImportBootImages)
        cluster_1.ImportBootImages.return_value = succeed({})

        # Cluster #2 will break.
        cluster_2 = self.rpc.makeCluster(nodegroup_2, ImportBootImages)
        cluster_2.ImportBootImages.return_value = fail(ZeroDivisionError)

        # Cluster #3 is not connected.

        # Do the import with reporting.
        importer = ClustersImporter.new(
            [nodegroup_1.uuid, nodegroup_2.uuid, nodegroup_3.uuid])

        with TwistedLoggerFixture() as logger:
            importer.run().wait(5)

        self.assertDocTestMatches(
            """\
            ...
            ---
            Cluster (cluster-1) has imported boot resources.
            ---
            Cluster (cluster-2) failed to import boot resources.
            Traceback (most recent call last):
            ...
            ---
            Cluster (cluster-3) did not import boot resources; it is not
            connected to the region at this time.
            """,
            logger.output)
