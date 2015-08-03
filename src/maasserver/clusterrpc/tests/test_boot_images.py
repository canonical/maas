# Copyright 2014 Canonical Ltd.  This software is licensed under the
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

from maasserver.clusterrpc import boot_images as boot_images_module
from maasserver.clusterrpc.boot_images import (
    get_available_boot_images,
    get_boot_images,
    get_boot_images_for,
    is_import_boot_images_running,
    is_import_boot_images_running_for,
    )
from maasserver.clusterrpc.testing.boot_images import make_rpc_boot_image
from maasserver.enum import (
    BOOT_RESOURCE_TYPE,
    NODEGROUP_STATUS,
    )
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
    )
from mock import (
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
    ListBootImages,
    ListBootImagesV2,
    )
from provisioningserver.testing.boot_images import (
    make_boot_image_storage_params,
    make_image,
    )
from twisted.internet.defer import succeed
from twisted.protocols.amp import UnhandledCommand


def make_image_dir(image_params, tftproot):
    """Fake a boot image matching `image_params` under `tftproot`."""
    image_dir = locate_tftp_path(
        compose_image_path(
            osystem=image_params['osystem'],
            arch=image_params['architecture'],
            subarch=image_params['subarchitecture'],
            release=image_params['release'],
            label=image_params['label']),
        tftproot)
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
        nodegroup = factory.make_NodeGroup(status=NODEGROUP_STATUS.ACCEPTED)
        self.useFixture(RunningClusterRPCFixture())
        self.assertTrue(is_import_boot_images_running_for(nodegroup))

    def test_returns_False(self):
        mock_is_running = self.patch(
            clusterservice, "is_import_boot_images_running")
        mock_is_running.return_value = False
        nodegroup = factory.make_NodeGroup(status=NODEGROUP_STATUS.ACCEPTED)
        self.useFixture(RunningClusterRPCFixture())
        self.assertFalse(is_import_boot_images_running_for(nodegroup))


class TestGetBootImages(MAASServerTestCase):
    """Tests for `get_boot_images`."""

    def setUp(self):
        super(TestGetBootImages, self).setUp()
        resource_dir = self.make_dir()
        self.tftproot = os.path.join(resource_dir, 'current')
        os.mkdir(self.tftproot)
        self.patch(boot_images, 'CACHED_BOOT_IMAGES', None)
        self.patch(boot_images, 'BOOT_RESOURCES_STORAGE', resource_dir)

    def test_returns_boot_images(self):
        nodegroup = factory.make_NodeGroup(status=NODEGROUP_STATUS.ACCEPTED)
        self.useFixture(RunningClusterRPCFixture())

        purposes = ['install', 'commissioning', 'xinstall']
        params = [make_boot_image_storage_params() for _ in range(3)]
        for param in params:
            make_image_dir(param, self.tftproot)
            test_tftppath.make_osystem(self, param['osystem'], purposes)
        self.assertItemsEqual(
            [
                make_image(param, purpose)
                for param in params
                for purpose in purposes
            ],
            get_boot_images(nodegroup))

    def test_calls_ListBootImagesV2_before_ListBootImages(self):
        nodegroup = factory.make_NodeGroup(status=NODEGROUP_STATUS.ACCEPTED)
        mock_client = MagicMock()
        self.patch_autospec(
            boot_images_module, "getClientFor").return_value = mock_client
        get_boot_images(nodegroup)
        self.assertThat(mock_client, MockCalledOnceWith(ListBootImagesV2))

    def test_calls_ListBootImages_if_raised_UnhandledCommand(self):
        nodegroup = factory.make_NodeGroup(status=NODEGROUP_STATUS.ACCEPTED)
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
    """Tests for `get_available_boot_images`."""

    def setUp(self):
        super(TestGetAvailableBootImages, self).setUp()
        resource_dir = self.make_dir()
        self.tftproot = os.path.join(resource_dir, 'current')
        os.mkdir(self.tftproot)
        self.patch(boot_images, 'CACHED_BOOT_IMAGES', None)
        self.patch(boot_images, 'BOOT_RESOURCES_STORAGE', resource_dir)

    def test_returns_boot_images_for_one_cluster(self):
        factory.make_NodeGroup().accept()
        self.useFixture(RunningClusterRPCFixture())

        purposes = ['install', 'commissioning', 'xinstall']
        params = [make_boot_image_storage_params() for _ in range(3)]
        for param in params:
            make_image_dir(param, self.tftproot)
            test_tftppath.make_osystem(self, param['osystem'], purposes)
        self.assertItemsEqual(
            [
                make_image(param, purpose)
                for param in params
                for purpose in purposes
            ],
            get_available_boot_images())

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

        self.assertItemsEqual(
            available_images,
            get_available_boot_images())

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

        self.assertItemsEqual(
            images,
            get_available_boot_images())

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

        self.assertItemsEqual(images, get_available_boot_images())

    def test_returns_empty_list_when_all_clusters_fail(self):
        factory.make_NodeGroup().accept()
        factory.make_NodeGroup().accept()
        factory.make_NodeGroup().accept()
        self.useFixture(RunningClusterRPCFixture())

        clients = getAllClients()
        for index, client in enumerate(clients):
            callRemote = self.patch(client._conn, "callRemote")
            callRemote.side_effect = ZeroDivisionError()

        self.assertItemsEqual(
            [],
            get_available_boot_images())


class TestGetBootImagesFor(MAASServerTestCase):
    """Tests for `get_boot_images_for`."""

    def setUp(self):
        super(TestGetBootImagesFor, self).setUp()
        resource_dir = self.make_dir()
        self.tftproot = os.path.join(resource_dir, 'current')
        os.mkdir(self.tftproot)
        self.patch(boot_images, 'CACHED_BOOT_IMAGES', None)
        self.patch(boot_images, 'BOOT_RESOURCES_STORAGE', resource_dir)

    def make_boot_images(self):
        purposes = ['install', 'commissioning', 'xinstall']
        params = [make_boot_image_storage_params() for _ in range(3)]
        for param in params:
            make_image_dir(param, self.tftproot)
            test_tftppath.make_osystem(self, param['osystem'], purposes)
        return params

    def make_rpc_boot_images(self, param):
        purposes = ['install', 'commissioning', 'xinstall']
        return [
            make_image(param, purpose)
            for purpose in purposes
            ]

    def test_returns_boot_images_matching_subarchitecture(self):
        nodegroup = factory.make_NodeGroup(status=NODEGROUP_STATUS.ACCEPTED)
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
        nodegroup = factory.make_NodeGroup(status=NODEGROUP_STATUS.ACCEPTED)
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
