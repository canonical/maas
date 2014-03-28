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

from collections import defaultdict
from contextlib import closing
from itertools import product
from operator import attrgetter
import os.path
import random
import threading

from crochet import wait_for_reactor
from django.db import connection
from django.db.utils import ProgrammingError
from maasserver import eventloop
from maasserver.rpc import regionservice
from maasserver.rpc.regionservice import (
    Region,
    RegionAdvertisingService,
    RegionServer,
    RegionService,
    )
from maasserver.rpc.testing.doubles import IdentifyingRegionServer
from maastesting.factory import factory
from maastesting.matchers import (
    MockCalledOnceWith,
    Provides,
    )
from maastesting.testcase import MAASTestCase
from provisioningserver.rpc import (
    cluster,
    common,
    exceptions,
    )
from provisioningserver.rpc.region import (
    Identify,
    ReportBootImages,
    )
from provisioningserver.rpc.testing import (
    are_valid_tls_parameters,
    call_responder,
    TwistedLoggerFixture,
    )
from provisioningserver.rpc.testing.doubles import DummyConnection
from provisioningserver.testing.config import set_tftp_root
from provisioningserver.utils import asynchronous
from testtools.matchers import (
    AfterPreprocessing,
    AllMatch,
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
    succeed,
    )
from twisted.internet.interfaces import IStreamServerEndpoint
from twisted.internet.protocol import Factory
from twisted.internet.threads import deferToThread
from twisted.protocols import amp
from twisted.python import log


class TestRegionProtocol_Identify(MAASTestCase):

    def test_identify_is_registered(self):
        protocol = Region()
        responder = protocol.locateResponder(Identify.commandName)
        self.assertIsNot(responder, None)

    @wait_for_reactor
    def test_identify_reports_event_loop_name(self):
        d = call_responder(Region(), Identify, {})

        def check(response):
            self.assertEqual({"ident": eventloop.loop.name}, response)

        return d.addCallback(check)


class TestRegionProtocol_StartTLS(MAASTestCase):

    def test_StartTLS_is_registered(self):
        protocol = Region()
        responder = protocol.locateResponder(amp.StartTLS.commandName)
        self.assertIsNot(responder, None)

    def test_get_tls_parameters_returns_parameters(self):
        # get_tls_parameters() is the underlying responder function.
        # However, locateResponder() returns a closure, so we have to
        # side-step it.
        protocol = Region()
        cls, func = protocol._commandDispatch[amp.StartTLS.commandName]
        self.assertThat(func(protocol), are_valid_tls_parameters)

    @wait_for_reactor
    def test_StartTLS_returns_nothing(self):
        # The StartTLS command does some funky things - see _TLSBox and
        # _LocalArgument for an idea - so the parameters returned from
        # get_tls_parameters() - the registered responder - don't end up
        # travelling over the wire as part of an AMP message. However,
        # the responder is not aware of this, and is called just like
        # any other.
        d = call_responder(Region(), amp.StartTLS, {})

        def check(response):
            self.assertEqual({}, response)

        return d.addCallback(check)


class TestRegionProtocol_ReportBootImages(MAASTestCase):

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
        self.useFixture(set_tftp_root(tftpdir))

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


from provisioningserver.rpc.interfaces import IConnection
from zope.interface.verify import verifyObject


class TestRegionServer(MAASTestCase):

    def test_interfaces(self):
        protocol = RegionServer()
        verifyObject(IConnection, protocol)

    def test_connectionMade_identifies_the_remote_cluster(self):
        service = RegionService()
        service.running = True  # Pretend it's running.
        protocol = service.factory.buildProtocol(addr=None)  # addr is unused.
        example_uuid = factory.getRandomUUID()
        callRemote = self.patch(protocol, "callRemote")
        callRemote.return_value = succeed({b"ident": example_uuid})
        protocol.connectionMade()
        # The Identify command was called on the cluster.
        self.assertThat(callRemote, MockCalledOnceWith(cluster.Identify))
        # The UUID has been saved on the protocol instance.
        self.assertThat(protocol.ident, Equals(example_uuid))

    def test_connectionMade_drops_the_connection_on_ident_failure(self):
        service = RegionService()
        service.running = True  # Pretend it's running.
        protocol = service.factory.buildProtocol(addr=None)  # addr is unused.
        callRemote = self.patch(protocol, "callRemote")
        callRemote.return_value = fail(IOError("no paddle"))
        transport = self.patch(protocol, "transport")
        logger = self.useFixture(TwistedLoggerFixture())
        protocol.connectionMade()
        # The transport is instructed to lose the connection.
        self.assertThat(transport.loseConnection, MockCalledOnceWith())
        # The connection is not in the service's connection map.
        self.assertDictEqual({}, service.connections)
        # The error is logged.
        self.assertDocTestMatches(
            """\
            Unhandled Error
            Traceback (most recent call last):
            Failure: exceptions.IOError: no paddle
            """,
            logger.dump())

    def test_connectionMade_updates_services_connection_set(self):
        service = RegionService()
        service.running = True  # Pretend it's running.
        service.factory.protocol = IdentifyingRegionServer
        protocol = service.factory.buildProtocol(addr=None)  # addr is unused.
        self.assertDictEqual({}, service.connections)
        protocol.connectionMade()
        self.assertDictEqual(
            {protocol.ident: {protocol}},
            service.connections)

    def test_connectionMade_drops_connection_if_service_not_running(self):
        service = RegionService()
        service.running = False  # Pretend it's not running.
        service.factory.protocol = IdentifyingRegionServer
        protocol = service.factory.buildProtocol(addr=None)  # addr is unused.
        transport = self.patch(protocol, "transport")
        self.assertDictEqual({}, service.connections)
        protocol.connectionMade()
        # The protocol is not added to the connection set.
        self.assertDictEqual({}, service.connections)
        # The transport is instructed to lose the connection.
        self.assertThat(transport.loseConnection, MockCalledOnceWith())

    def test_connectionLost_updates_services_connection_set(self):
        service = RegionService()
        service.running = True  # Pretend it's running.
        service.factory.protocol = IdentifyingRegionServer
        protocol = service.factory.buildProtocol(addr=None)  # addr is unused.
        protocol.connectionMade()
        connectionLost_up_call = self.patch(amp.AMP, "connectionLost")
        self.assertDictEqual(
            {protocol.ident: {protocol}},
            service.connections)
        protocol.connectionLost(reason=None)
        # The connection is removed from the set, but the key remains.
        self.assertDictEqual({protocol.ident: set()}, service.connections)
        # connectionLost() is called on the superclass.
        self.assertThat(connectionLost_up_call, MockCalledOnceWith(None))


class TestRegionService(MAASTestCase):

    def test_init_sets_appropriate_instance_attributes(self):
        service = RegionService()
        self.assertThat(service, IsInstance(Service))
        self.assertThat(service.connections, IsInstance(defaultdict))
        self.assertThat(service.connections.default_factory, Is(set))
        self.assertThat(service.endpoint, Provides(IStreamServerEndpoint))
        self.assertThat(service.factory, IsInstance(Factory))
        self.assertThat(service.factory.protocol, Equals(RegionServer))

    @wait_for_reactor
    def test_starting_and_stopping_the_service(self):
        service = RegionService()
        self.assertThat(service.starting, Is(None))
        service.startService()
        self.assertThat(service.starting, IsInstance(Deferred))

        def check_started(port):
            self.assertThat(port, IsInstance(tcp.Port))
            self.assertThat(port.factory, IsInstance(Factory))
            self.assertThat(port.factory.protocol, Equals(RegionServer))
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
    @inlineCallbacks
    def test_stopping_closes_connections_cleanly(self):
        service = RegionService()
        service.starting = Deferred()
        service.factory.protocol = IdentifyingRegionServer
        connections = {
            service.factory.buildProtocol(None),
            service.factory.buildProtocol(None),
        }
        for conn in connections:
            # Pretend it's already connected.
            service.connections[conn.ident].add(conn)
        transports = {
            self.patch(conn, "transport")
            for conn in connections
        }
        yield service.stopService()
        self.assertThat(
            transports, AllMatch(
                AfterPreprocessing(
                    attrgetter("loseConnection"),
                    MockCalledOnceWith())))

    @wait_for_reactor
    @inlineCallbacks
    def test_stopping_logs_errors_when_closing_connections(self):
        service = RegionService()
        service.starting = Deferred()
        service.factory.protocol = IdentifyingRegionServer
        connections = {
            service.factory.buildProtocol(None),
            service.factory.buildProtocol(None),
        }
        for conn in connections:
            transport = self.patch(conn, "transport")
            transport.loseConnection.side_effect = IOError("broken")
            # Pretend it's already connected.
            service.connections[conn.ident].add(conn)
        logger = self.useFixture(TwistedLoggerFixture())
        # stopService() completes without returning an error.
        yield service.stopService()
        # Connection-specific errors are logged.
        self.assertDocTestMatches(
            """\
            Unhandled Error
            Traceback (most recent call last):
            ...
            exceptions.IOError: broken
            ---
            Unhandled Error
            Traceback (most recent call last):
            ...
            exceptions.IOError: broken
            """,
            logger.dump())

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

    @wait_for_reactor
    def test_getClientFor_errors_when_no_connections(self):
        service = RegionService()
        service.connections.clear()
        self.assertRaises(
            exceptions.NoConnectionsAvailable,
            service.getClientFor, factory.getRandomUUID())

    @wait_for_reactor
    def test_getClientFor_errors_when_no_connections_for_cluster(self):
        service = RegionService()
        uuid = factory.getRandomUUID()
        service.connections[uuid].clear()
        self.assertRaises(
            exceptions.NoConnectionsAvailable,
            service.getClientFor, uuid)

    @wait_for_reactor
    def test_getClientFor_returns_random_connection(self):
        c1 = DummyConnection()
        c2 = DummyConnection()
        chosen = DummyConnection()

        service = RegionService()
        uuid = factory.getRandomUUID()
        conns_for_uuid = service.connections[uuid]
        conns_for_uuid.update({c1, c2})

        def check_choice(choices):
            self.assertItemsEqual(choices, conns_for_uuid)
            return chosen
        self.patch(random, "choice", check_choice)

        self.assertThat(
            service.getClientFor(uuid),
            Equals(common.Client(chosen)))

    @wait_for_reactor
    def test_getAllClients_empty(self):
        service = RegionService()
        service.connections.clear()
        self.assertThat(service.getAllClients(), Equals([]))

    @wait_for_reactor
    def test_getAllClients(self):
        service = RegionService()
        uuid1 = factory.getRandomUUID()
        c1 = DummyConnection()
        c2 = DummyConnection()
        service.connections[uuid1].update({c1, c2})
        uuid2 = factory.getRandomUUID()
        c3 = DummyConnection()
        c4 = DummyConnection()
        service.connections[uuid2].update({c3, c4})
        clients = service.getAllClients()
        self.assertItemsEqual(clients, {
            common.Client(c1), common.Client(c2),
            common.Client(c3), common.Client(c4),
        })


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
        yield deferToThread(service.update)
        yield service.stopService()

        dump = yield deferToThread(service.dump)
        self.assertItemsEqual([], dump)

    def test__get_addresses(self):
        service = RegionAdvertisingService()

        example_port = factory.getRandomPort()
        getServiceNamed = self.patch(eventloop.services, "getServiceNamed")
        getPort = getServiceNamed.return_value.getPort
        getPort.side_effect = asynchronous(lambda: example_port)

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
        getPort = getServiceNamed.return_value.getPort
        getPort.side_effect = asynchronous(lambda: None)

        get_all_interface_addresses = self.patch(
            regionservice, "get_all_interface_addresses")
        get_all_interface_addresses.return_value = [
            factory.getRandomIPAddress(),
            factory.getRandomIPAddress(),
        ]

        # If the RPC service is down, _get_addresses() returns nothing.
        self.assertItemsEqual([], service._get_addresses())
