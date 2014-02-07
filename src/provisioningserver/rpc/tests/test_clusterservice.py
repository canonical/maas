# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the cluster's RPC implementation."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from itertools import product
import os.path

from maastesting.matchers import Provides
from maastesting.testcase import MAASTestCase
from provisioningserver.config import Config
from provisioningserver.pxe import tftppath
from provisioningserver.rpc.cluster import ListBootImages
from provisioningserver.rpc.clusterservice import (
    Cluster,
    ClusterFactory,
    ClusterService,
    )
from provisioningserver.rpc.testing import call_responder
from testtools.deferredruntest import AsynchronousDeferredRunTest
from testtools.matchers import (
    IsInstance,
    KeysEqual,
    )
from twisted.application.internet import StreamServerEndpointService
from twisted.internet import reactor
from twisted.internet.interfaces import IStreamServerEndpoint


class TestClusterProtocol(MAASTestCase):

    run_tests_with = AsynchronousDeferredRunTest.make_factory(timeout=5)

    def test_list_boot_images_is_registered(self):
        protocol = Cluster()
        responder = protocol.locateResponder(ListBootImages.commandName)
        self.assertIsNot(responder, None)

    def test_list_boot_images_can_be_called(self):
        list_boot_images = self.patch(tftppath, "list_boot_images")
        list_boot_images.return_value = []

        d = call_responder(Cluster(), ListBootImages, {})

        def check(response):
            self.assertEqual({"images": []}, response)

        return d.addCallback(check)

    def test_list_boot_images_with_things_to_report(self):
        # tftppath.list_boot_images()'s return value matches the
        # response schema that ListBootImages declares, and is
        # serialised correctly.

        # Example boot image definitions.
        archs = "i386", "amd64"
        subarchs = "generic", "special"
        releases = "precise", "trusty"
        purposes = "commission", "install"

        # Create a TFTP file tree with a variety of subdirectories.
        tftpdir = self.make_dir()
        for options in product(archs, subarchs, releases, purposes):
            os.makedirs(os.path.join(tftpdir, *options))

        # Ensure that list_boot_images() uses the above TFTP file tree.
        load_from_cache = self.patch(Config, "load_from_cache")
        load_from_cache.return_value = {"tftp": {"root": tftpdir}}

        expected_images = [
            {"architecture": arch, "subarchitecture": subarch,
             "release": release, "purpose": purpose}
            for arch, subarch, release, purpose in product(
                archs, subarchs, releases, purposes)
        ]

        d = call_responder(Cluster(), ListBootImages, {})

        def check(response):
            self.assertThat(response, KeysEqual("images"))
            self.assertItemsEqual(expected_images, response["images"])

        return d.addCallback(check)


class TestClusterService(MAASTestCase):

    def test_init_sets_appropriate_instance_attributes(self):
        # ClusterService is a convenience wrapper around
        # StreamServerEndpointService. There's not much to demonstrate
        # other than it has been initialised correctly.
        service = ClusterService(reactor, 0)
        self.assertThat(service, IsInstance(StreamServerEndpointService))
        self.assertThat(service.endpoint, Provides(IStreamServerEndpoint))
        self.assertThat(service.factory, IsInstance(ClusterFactory))
