# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the region's RPC implementation."""

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

from crochet import wait_for_reactor
from maasserver import eventloop
from maasserver.rpc.regionservice import (
    Region,
    RegionService,
    )
from maastesting.factory import factory
from maastesting.matchers import Provides
from maastesting.testcase import MAASTestCase
from provisioningserver.config import Config
from provisioningserver.rpc.region import ReportBootImages
from provisioningserver.rpc.testing import call_responder
from testtools.matchers import (
    AfterPreprocessing,
    Equals,
    Is,
    IsInstance,
    MatchesListwise,
    )
from twisted.application.service import Service
from twisted.internet import (
    reactor,
    tcp,
    )
from twisted.internet.defer import (
    Deferred,
    fail,
    )
from twisted.internet.interfaces import IStreamServerEndpoint
from twisted.internet.protocol import Factory
from twisted.python import log


class TestRegionProtocol(MAASTestCase):

    def test_report_boot_images_is_registered(self):
        protocol = Region()
        responder = protocol.locateResponder(ReportBootImages.commandName)
        self.assertIsNot(responder, None)

    @wait_for_reactor
    def test_report_boot_images_can_be_called(self):
        uuid = factory.make_name("uuid")
        images = [
            {"architecture": factory.make_name("architecture"),
             "subarchitecture": factory.make_name("subarchitecture"),
             "release": factory.make_name("release"),
             "purpose": factory.make_name("purpose")},
        ]

        d = call_responder(Region(), ReportBootImages, {
            b"uuid": uuid, b"images": images,
        })

        def check(response):
            self.assertEqual({}, response)

        return d.addCallback(check)

    @wait_for_reactor
    def test_report_boot_images_with_real_things_to_report(self):
        # tftppath.report_boot_images()'s return value matches the
        # arguments schema that ReportBootImages declares, and is
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

        # Ensure that report_boot_images() uses the above TFTP file tree.
        load_from_cache = self.patch(Config, "load_from_cache")
        load_from_cache.return_value = {"tftp": {"root": tftpdir}}

        images = [
            {"architecture": arch, "subarchitecture": subarch,
             "release": release, "purpose": purpose}
            for arch, subarch, release, purpose in product(
                archs, subarchs, releases, purposes)
        ]

        d = call_responder(Region(), ReportBootImages, {
            b"uuid": factory.make_name("uuid"), b"images": images,
        })

        def check(response):
            self.assertEqual({}, response)

        return d.addCallback(check)


class TestRegionService(MAASTestCase):

    def test_init_sets_appropriate_instance_attributes(self):
        service = RegionService(reactor)
        self.assertThat(service, IsInstance(Service))
        self.assertThat(service.endpoint, Provides(IStreamServerEndpoint))
        self.assertThat(service.factory, IsInstance(Factory))
        self.assertThat(service.factory.protocol, Equals(Region))

    @wait_for_reactor
    def test_starting_and_stopping_the_service(self):
        service = RegionService(reactor)
        self.assertThat(service.starting, Is(None))
        service.startService()
        self.assertThat(service.starting, IsInstance(Deferred))

        def check_started(port):
            self.assertThat(port, IsInstance(tcp.Port))
            self.assertThat(port.factory, IsInstance(Factory))
            self.assertThat(port.factory.protocol, Equals(Region))
            # The port is saved as a private instance var.
            self.assertThat(service._port, Is(port))
            return service.stopService()

        service.starting.addCallback(check_started)

        def check_stopped(ignore, service=service):
            self.assertTrue(service._port.disconnected)

        service.starting.addCallback(check_stopped)

        return service.starting

    @wait_for_reactor
    def test_start_up_can_be_cancelled(self):
        service = RegionService(reactor)

        # Return an inert Deferred from the listen() call.
        self.patch(service.endpoint, "listen").return_value = Deferred()

        service.startService()
        self.assertThat(service.starting, IsInstance(Deferred))

        service.starting.cancel()

        def check(port):
            self.assertThat(port, Is(None))
            self.assertThat(service._port, Is(None))
            return service.stopService()

        return service.starting.addCallback(check)

    @wait_for_reactor
    def test_start_up_errors_are_logged(self):
        service = RegionService(reactor)

        # Ensure that endpoint.listen fails with a obvious error.
        exception = ValueError("This is not the messiah.")
        self.patch(service.endpoint, "listen").return_value = fail(exception)

        err_calls = []
        self.patch(log, "err", err_calls.append)

        err_calls_expected = [
            AfterPreprocessing(
                (lambda failure: failure.value),
                Is(exception)),
        ]

        service.startService()
        self.assertThat(err_calls, MatchesListwise(err_calls_expected))

    @wait_for_reactor
    def test_stopping_cancels_startup(self):
        service = RegionService(reactor)

        # Return an inert Deferred from the listen() call.
        self.patch(service.endpoint, "listen").return_value = Deferred()

        service.startService()
        service.stopService()

        def check(port):
            # The CancelledError is suppressed.
            self.assertThat(port, Is(None))
            self.assertThat(service._port, Is(None))

        return service.starting.addCallback(check)

    @wait_for_reactor
    def test_stopping_when_start_up_failed(self):
        service = RegionService(reactor)

        # Ensure that endpoint.listen fails with a obvious error.
        exception = ValueError("This is a very naughty boy.")
        self.patch(service.endpoint, "listen").return_value = fail(exception)
        # Suppress logged messages.
        self.patch(log.theLogPublisher, "observers", [])

        service.startService()
        # The test is that stopService() succeeds.
        return service.stopService()
