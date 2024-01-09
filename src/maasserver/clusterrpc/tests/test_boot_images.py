# Copyright 2014-2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the `boot_images` module."""


import os
from typing import Dict, List
from unittest.mock import MagicMock

from twisted.internet.defer import succeed

from maasserver.clusterrpc import boot_images as boot_images_module
from maasserver.clusterrpc.boot_images import (
    get_all_available_boot_images,
    get_boot_images,
    get_boot_images_for,
    get_common_available_boot_images,
)
from maasserver.clusterrpc.testing.boot_images import make_rpc_boot_image
from maasserver.enum import BOOT_RESOURCE_TYPE
from maasserver.rpc import getAllClients
from maasserver.rpc.testing.fixtures import RunningClusterRPCFixture
from maasserver.testing.factory import factory
from maasserver.testing.testcase import (
    MAASServerTestCase,
    MAASTransactionServerTestCase,
)
from maastesting import get_testing_timeout
from maastesting.matchers import MockCalledOnceWith
from provisioningserver.boot.tests import test_tftppath
from provisioningserver.boot.tftppath import compose_image_path
from provisioningserver.rpc import boot_images
from provisioningserver.rpc.cluster import ListBootImages
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
