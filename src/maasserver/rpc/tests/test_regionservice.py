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

from contextlib import closing
from itertools import product
import os.path
import threading

from crochet import wait_for_reactor
from django.db import connection
from django.db.utils import ProgrammingError
from maasserver import eventloop
from maasserver.rpc import regionservice
from maasserver.rpc.regionservice import (
    Region,
    RegionAdvertisingService,
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
from twisted.internet import tcp
from twisted.internet.defer import (
    Deferred,
    fail,
    inlineCallbacks,
    )
from twisted.internet.interfaces import IStreamServerEndpoint
from twisted.internet.protocol import Factory
from twisted.internet.threads import deferToThread
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
        service = RegionService()
        self.assertThat(service, IsInstance(Service))
        self.assertThat(service.endpoint, Provides(IStreamServerEndpoint))
        self.assertThat(service.factory, IsInstance(Factory))
        self.assertThat(service.factory.protocol, Equals(Region))

    @wait_for_reactor
    def test_starting_and_stopping_the_service(self):
        service = RegionService()
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
        service = RegionService()

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
        service = RegionService()

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
        service = RegionService()

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
        service = RegionService()

        # Ensure that endpoint.listen fails with a obvious error.
        exception = ValueError("This is a very naughty boy.")
        self.patch(service.endpoint, "listen").return_value = fail(exception)
        # Suppress logged messages.
        self.patch(log.theLogPublisher, "observers", [])

        service.startService()
        # The test is that stopService() succeeds.
        return service.stopService()


class TestRegionAdvertisingService(MAASTestCase):

    def tearDown(self):
        super(TestRegionAdvertisingService, self).tearDown()
        # Django doesn't notice that the database needs to be reset.
        with closing(connection):
            with closing(connection.cursor()) as cursor:
                cursor.execute("DROP TABLE IF EXISTS eventloops")

    def test_init(self):
        ras = RegionAdvertisingService()
        self.assertEqual(60, ras.step)
        self.assertEqual((deferToThread, (ras.update,), {}), ras.call)

    @wait_for_reactor
    def test_starting_and_stopping_the_service(self):
        service = RegionAdvertisingService()
        self.assertThat(service.starting, Is(None))
        service.startService()
        self.assertThat(service.starting, IsInstance(Deferred))

        def check_started(ignore):
            self.assertTrue(service.running)
            with closing(connection):
                with closing(connection.cursor()) as cursor:
                    cursor.execute("SELECT * FROM eventloops")
            return service.stopService()

        service.starting.addCallback(check_started)

        def check_stopped(ignore, service=service):
            self.assertFalse(service.running)

        service.starting.addCallback(check_stopped)

        return service.starting

    @wait_for_reactor
    def test_start_up_can_be_cancelled(self):
        service = RegionAdvertisingService()

        lock = threading.Lock()
        with lock:
            # Prevent prepare - which is deferred to a thread - from
            # completing while we hold the lock.
            service.prepare = lock.acquire
            # Start the service, but cancel it before prepare is able to
            # complete.
            service.startService()
            self.assertThat(service.starting, IsInstance(Deferred))
            service.starting.cancel()

        def check(ignore):
            # The service never started.
            self.assertFalse(service.running)

        return service.starting.addCallback(check)

    @wait_for_reactor
    def test_start_up_errors_are_logged(self):
        service = RegionAdvertisingService()

        # Ensure that service.prepare fails with a obvious error.
        exception = ValueError("You don't vote for kings!")
        self.patch(service, "prepare").side_effect = exception

        err_calls = []
        self.patch(log, "err", err_calls.append)

        err_calls_expected = [
            AfterPreprocessing(
                (lambda failure: failure.value),
                Is(exception)),
        ]

        def check(ignore):
            self.assertThat(err_calls, MatchesListwise(err_calls_expected))

        service.startService()
        service.starting.addCallback(check)
        return service.starting

    @wait_for_reactor
    def test_stopping_cancels_startup(self):
        service = RegionAdvertisingService()

        lock = threading.Lock()
        with lock:
            # Prevent prepare - which is deferred to a thread - from
            # completing while we hold the lock.
            service.prepare = lock.acquire
            # Start the service, but stop it again before prepare is
            # able to complete.
            service.startService()
            service.stopService()

        def check(ignore):
            self.assertTrue(service.starting.called)
            self.assertFalse(service.running)

        return service.starting.addCallback(check)

    @wait_for_reactor
    def test_stopping_when_start_up_failed(self):
        service = RegionAdvertisingService()

        # Ensure that service.prepare fails with a obvious error.
        exception = ValueError("First, shalt thou take out the holy pin.")
        self.patch(service, "prepare").side_effect = exception
        # Suppress logged messages.
        self.patch(log.theLogPublisher, "observers", [])

        service.startService()
        # The test is that stopService() succeeds.
        return service.stopService()

    def test_prepare(self):
        service = RegionAdvertisingService()

        with closing(connection):
            # Before service.prepare is called, there's not eventloops
            # table, and selecting from it elicits an error.
            with closing(connection.cursor()) as cursor:
                self.assertRaises(
                    ProgrammingError, cursor.execute,
                    "SELECT * FROM eventloops")

        service.prepare()

        with closing(connection):
            # After service.prepare is called, the eventloops table
            # exists, and selecting from it works fine, though it is
            # empty.
            with closing(connection.cursor()) as cursor:
                cursor.execute("SELECT * FROM eventloops")
                self.assertEqual([], list(cursor))

    def test_update(self):
        example_addresses = [
            (factory.getRandomIPAddress(), factory.getRandomPort()),
            (factory.getRandomIPAddress(), factory.getRandomPort()),
        ]

        service = RegionAdvertisingService()
        service._get_addresses = lambda: example_addresses
        service.prepare()
        service.update()

        with closing(connection):
            with closing(connection.cursor()) as cursor:
                cursor.execute("SELECT address, port FROM eventloops")
                self.assertItemsEqual(example_addresses, list(cursor))

    def test_update_does_not_insert_when_nothings_listening(self):
        service = RegionAdvertisingService()
        service._get_addresses = lambda: []
        service.prepare()
        service.update()

        with closing(connection):
            with closing(connection.cursor()) as cursor:
                cursor.execute("SELECT address, port FROM eventloops")
                self.assertItemsEqual([], list(cursor))

    def test_update_deletes_old_records(self):
        service = RegionAdvertisingService()
        service.prepare()
        # Populate the eventloops table by hand with two records, one
        # fresh ("vic") and one old ("bob").
        with closing(connection):
            with closing(connection.cursor()) as cursor:
                cursor.execute("""\
                  INSERT INTO eventloops
                    (name, address, port, updated)
                  VALUES
                    ('vic', '192.168.1.1', 1111, DEFAULT),
                    ('bob', '192.168.1.2', 2222, NOW() - INTERVAL '6 mins')
                """)
        # Both event-loops, vic and bob, are visible.
        self.assertItemsEqual(
            [("vic", "192.168.1.1", 1111),
             ("bob", "192.168.1.2", 2222)],
            service.dump())
        # Updating also garbage-collects old event-loop records.
        service.update()
        self.assertItemsEqual(
            [("vic", "192.168.1.1", 1111)],
            service.dump())

    def test_dump(self):
        example_addresses = [
            (factory.getRandomIPAddress(), factory.getRandomPort()),
            (factory.getRandomIPAddress(), factory.getRandomPort()),
        ]

        service = RegionAdvertisingService()
        service._get_addresses = lambda: example_addresses
        service.prepare()
        service.update()

        expected = [
            (eventloop.loop.name, addr, port)
            for (addr, port) in example_addresses
        ]

        self.assertItemsEqual(expected, service.dump())

    def test_remove(self):
        service = RegionAdvertisingService()
        service._get_addresses = lambda: [("192.168.0.1", 9876)]
        service.prepare()
        service.update()
        service.remove()

        self.assertItemsEqual([], service.dump())

    @wait_for_reactor
    @inlineCallbacks
    def test_stopping_calls_remove(self):
        service = RegionAdvertisingService()
        service._get_addresses = lambda: [("192.168.0.1", 9876)]

        # It's hard to no guarantee that the timed call will run at
        # least once while the service is started, so we neuter it here
        # and call service.update() explicitly.
        service.call = (lambda: None), (), {}

        yield service.startService()
        service.update()
        yield service.stopService()

        self.assertItemsEqual([], service.dump())

    def test__get_addresses(self):
        service = RegionAdvertisingService()

        example_port = factory.getRandomPort()
        getServiceNamed = self.patch(eventloop.services, "getServiceNamed")
        getServiceNamed.return_value.getPort.return_value = example_port

        example_addrs = [
            factory.getRandomIPAddress(),
            factory.getRandomIPAddress(),
        ]
        get_all_interface_addresses = self.patch(
            regionservice, "get_all_interface_addresses")
        get_all_interface_addresses.return_value = example_addrs

        self.assertItemsEqual(
            [(addr, example_port) for addr in example_addrs],
            service._get_addresses())

        getServiceNamed.assert_called_once_with("rpc")
        get_all_interface_addresses.assert_called_once_with()

    def test__get_addresses_when_rpc_down(self):
        service = RegionAdvertisingService()

        getServiceNamed = self.patch(eventloop.services, "getServiceNamed")
        # getPort() returns None when the RPC service is not running or
        # not able to bind a port.
        getServiceNamed.return_value.getPort.return_value = None

        get_all_interface_addresses = self.patch(
            regionservice, "get_all_interface_addresses")
        get_all_interface_addresses.return_value = [
            factory.getRandomIPAddress(),
            factory.getRandomIPAddress(),
        ]

        # If the RPC service is down, _get_addresses() returns nothing.
        self.assertItemsEqual([], service._get_addresses())
