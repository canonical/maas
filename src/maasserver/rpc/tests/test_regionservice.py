# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the region's RPC implementation."""

__all__ = []

from collections import defaultdict
from datetime import (
    datetime,
    timedelta,
)
from hashlib import sha256
from hmac import HMAC
from itertools import product
from json import dumps
from operator import attrgetter
import os.path
import random
from random import randint
from socket import gethostname
import threading
import time
from unittest import skip
from unittest.mock import (
    ANY,
    call,
    MagicMock,
    Mock,
    sentinel,
)
from urllib.parse import urlparse

from crochet import wait_for
from django.db import IntegrityError
from maasserver import (
    eventloop,
    locks,
)
from maasserver.bootresources import get_simplestream_endpoint
from maasserver.enum import (
    INTERFACE_TYPE,
    NODE_STATUS,
    NODE_TYPE,
    POWER_STATE,
    SERVICE_STATUS,
)
from maasserver.models import (
    Config,
    Event,
    EventType,
    Node,
    RackController,
    RegionController,
    RegionControllerProcess,
    RegionRackRPCConnection,
    Service as ServiceModel,
    timestampedmodel,
)
from maasserver.models.interface import PhysicalInterface
from maasserver.models.timestampedmodel import now
from maasserver.rpc import (
    events as events_module,
    leases as leases_module,
    regionservice,
)
from maasserver.rpc.regionservice import (
    Region,
    RegionAdvertising,
    RegionAdvertisingService,
    RegionServer,
    RegionService,
    registerConnection,
    unregisterConnection,
)
from maasserver.rpc.services import update_services
from maasserver.rpc.testing.doubles import HandshakingRegionServer
from maasserver.security import get_shared_secret
from maasserver.testing.architecture import make_usable_architecture
from maasserver.testing.eventloop import RegionEventLoopFixture
from maasserver.testing.factory import factory
from maasserver.testing.testcase import (
    MAASServerTestCase,
    MAASTransactionServerTestCase,
)
from maasserver.utils import ignore_unused
from maasserver.utils.orm import (
    reload_object,
    transactional,
)
from maasserver.utils.threads import deferToDatabase
from maastesting.matchers import (
    MockAnyCall,
    MockCalledOnce,
    MockCalledOnceWith,
    MockCalledWith,
    MockCallsMatch,
    Provides,
)
from maastesting.runtest import MAASCrochetRunTest
from maastesting.testcase import MAASTestCase
from maastesting.twisted import (
    always_fail_with,
    always_succeed_with,
    extract_result,
    TwistedLoggerFixture,
)
import netaddr
from provisioningserver.rpc import (
    common,
    exceptions,
)
from provisioningserver.rpc.exceptions import (
    CannotRegisterRackController,
    NoSuchCluster,
    NoSuchNode,
)
from provisioningserver.rpc.interfaces import IConnection
from provisioningserver.rpc.region import (
    Authenticate,
    CommissionNode,
    CreateNode,
    GetArchiveMirrors,
    GetBootConfig,
    GetBootSources,
    GetBootSourcesV2,
    GetProxies,
    Identify,
    ListNodePowerParameters,
    MarkNodeFailed,
    RegisterEventType,
    RegisterRackController,
    ReportBootImages,
    ReportForeignDHCPServer,
    RequestNodeInfoByMACAddress,
    SendEvent,
    SendEventMACAddress,
    UpdateInterfaces,
    UpdateLease,
    UpdateNodePowerState,
    UpdateServices,
)
from provisioningserver.rpc.testing import (
    are_valid_tls_parameters,
    call_responder,
)
from provisioningserver.rpc.testing.doubles import DummyConnection
from provisioningserver.testing.config import ClusterConfigurationFixture
from provisioningserver.utils import events
from provisioningserver.utils.twisted import (
    callInReactorWithTimeout,
    DeferredValue,
)
from testtools.deferredruntest import assert_fails_with
from testtools.matchers import (
    AfterPreprocessing,
    AllMatch,
    ContainsAll,
    Equals,
    HasLength,
    Is,
    IsInstance,
    MatchesAll,
    MatchesListwise,
    MatchesStructure,
    Not,
)
from twisted.application.service import Service
from twisted.internet import (
    reactor,
    tcp,
)
from twisted.internet.address import IPv4Address
from twisted.internet.defer import (
    CancelledError,
    Deferred,
    DeferredList,
    fail,
    inlineCallbacks,
    succeed,
)
from twisted.internet.endpoints import TCP4ServerEndpoint
from twisted.internet.error import ConnectionClosed
from twisted.internet.interfaces import IStreamServerEndpoint
from twisted.internet.protocol import Factory
from twisted.internet.task import LoopingCall
from twisted.logger import globalLogPublisher
from twisted.protocols import amp
from twisted.python import log
from twisted.python.failure import Failure
from twisted.python.reflect import fullyQualifiedName
from zope.interface.verify import verifyObject


wait_for_reactor = wait_for(30)  # 30 seconds.


class SkipAll:

    skipReason = "XXX: GavinPanella 2016-04-12 bug=1572646: Fails spuriously."

    def setUp(self):
        super(SkipAll, self).setUp()
        self.skipTest(self.skipReason)

    @classmethod
    def make(cls, base):
        return type(base.__name__, (cls, base), {})


MAASTestCase = SkipAll.make(MAASTestCase)
MAASServerTestCase = SkipAll.make(MAASServerTestCase)
MAASTransactionServerTestCase = SkipAll.make(MAASTransactionServerTestCase)


@transactional
def transactional_reload_object(obj):
    return reload_object(obj)


class TestRegionProtocol_Identify(MAASTestCase):

    def test_identify_is_registered(self):
        protocol = Region()
        responder = protocol.locateResponder(Identify.commandName)
        self.assertIsNotNone(responder)

    @wait_for_reactor
    def test_identify_reports_event_loop_name(self):
        d = call_responder(Region(), Identify, {})

        def check(response):
            self.assertEqual({"ident": eventloop.loop.name}, response)

        return d.addCallback(check)


class TestRegionProtocol_Authenticate(MAASServerTestCase):

    def test_authenticate_is_registered(self):
        protocol = Region()
        responder = protocol.locateResponder(Authenticate.commandName)
        self.assertIsNotNone(responder)

    @wait_for_reactor
    @inlineCallbacks
    def test_authenticate_calculates_digest_with_salt(self):
        message = factory.make_bytes()
        secret = yield get_shared_secret()

        args = {"message": message}
        response = yield call_responder(Region(), Authenticate, args)
        digest = response["digest"]
        salt = response["salt"]

        expected_digest = HMAC(secret, message + salt, sha256).digest()
        self.assertEqual(expected_digest, digest)
        self.assertThat(salt, HasLength(16))


class TestRegionProtocol_StartTLS(MAASTestCase):

    def test_StartTLS_is_registered(self):
        protocol = Region()
        responder = protocol.locateResponder(amp.StartTLS.commandName)
        self.assertIsNotNone(responder)

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
        self.assertIsNotNone(responder)

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
            "uuid": uuid, "images": images,
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
        self.useFixture(ClusterConfigurationFixture(tftp_root=tftpdir))

        images = [
            {"architecture": arch, "subarchitecture": subarch,
             "release": release, "purpose": purpose}
            for arch, subarch, release, purpose in product(
                archs, subarchs, releases, purposes)
        ]

        d = call_responder(Region(), ReportBootImages, {
            "uuid": factory.make_name("uuid"), "images": images,
        })

        def check(response):
            self.assertEqual({}, response)

        return d.addCallback(check)


class TestRegionProtocol_UpdateLease(MAASTransactionServerTestCase):

    def setUp(self):
        super(TestRegionProtocol_UpdateLease, self).setUp()
        self.useFixture(RegionEventLoopFixture("database-tasks"))

    def test_update_lease_is_registered(self):
        protocol = Region()
        responder = protocol.locateResponder(UpdateLease.commandName)
        self.assertIsNotNone(responder)

    @wait_for_reactor
    @inlineCallbacks
    def test__doesnt_raises_other_errors(self):
        uuid = factory.make_name("uuid")

        # Cause a random exception
        self.patch(leases_module, "update_lease").side_effect = (
            factory.make_exception())

        yield eventloop.start()
        try:
            yield call_responder(
                Region(), UpdateLease, {
                    "cluster_uuid": uuid,
                    "action": "expiry",
                    "mac": factory.make_mac_address(),
                    "ip_family": "ipv4",
                    "ip": factory.make_ipv4_address(),
                    "timestamp": int(time.time()),
                    })
        finally:
            yield eventloop.reset()

        # Test is that no exceptions are raised. If this test passes then all
        # works as expected.


class TestRegionProtocol_GetBootConfig(MAASTransactionServerTestCase):

    def test_get_boot_config_is_registered(self):
        protocol = Region()
        responder = protocol.locateResponder(GetBootConfig.commandName)
        self.assertIsNotNone(responder)

    @wait_for_reactor
    @inlineCallbacks
    def test_get_boot_config_returns_expected_result(self):
        rack_controller = yield deferToDatabase(
            transactional(factory.make_RackController))
        local_ip = factory.make_ip_address()
        remote_ip = factory.make_ip_address()

        response = yield call_responder(
            Region(), GetBootConfig, {
                "system_id": rack_controller.system_id,
                "local_ip": local_ip,
                "remote_ip": remote_ip,
            })

        self.assertThat(
            response,
            ContainsAll([
                "arch",
                "subarch",
                "osystem",
                "release",
                "purpose",
                "hostname",
                "domain",
                "preseed_url",
                "fs_host",
                "log_host",
                "extra_opts",
            ]))


class TestRegionProtocol_GetBootSources(MAASTransactionServerTestCase):

    def test_get_boot_sources_is_registered(self):
        protocol = Region()
        responder = protocol.locateResponder(GetBootSources.commandName)
        self.assertIsNotNone(responder)

    @wait_for_reactor
    def test_get_boot_sources_returns_simplestreams_endpoint(self):
        uuid = factory.make_name("uuid")

        d = call_responder(Region(), GetBootSources, {"uuid": uuid})

        def check(response):
            self.assertEqual(
                {"sources": [get_simplestream_endpoint()]},
                response)

        return d.addCallback(check)


class TestRegionProtocol_GetBootSourcesV2(MAASTransactionServerTestCase):

    def test_get_boot_sources_v2_is_registered(self):
        protocol = Region()
        responder = protocol.locateResponder(GetBootSourcesV2.commandName)
        self.assertIsNotNone(responder)

    @wait_for_reactor
    def test_get_boot_sources_v2_returns_simplestreams_endpoint(self):
        uuid = factory.make_name("uuid")

        d = call_responder(Region(), GetBootSourcesV2, {"uuid": uuid})

        def check(response):
            self.assertEqual(
                {"sources": [get_simplestream_endpoint()]},
                response)

        return d.addCallback(check)


class TestRegionProtocol_GetArchiveMirrors(MAASTransactionServerTestCase):

    def test_get_archive_mirrors_is_registered(self):
        protocol = Region()
        responder = protocol.locateResponder(GetArchiveMirrors.commandName)
        self.assertIsNotNone(responder)

    @transactional
    def set_main_archive(self, url):
        Config.objects.set_config("main_archive", url)

    @transactional
    def set_ports_archive(self, url):
        Config.objects.set_config("ports_archive", url)

    @wait_for_reactor
    @inlineCallbacks
    def test_get_archive_mirrors_with_main_archive_port_archive_default(self):
        yield deferToDatabase(
            self.set_main_archive, "http://archive.ubuntu.com/ubuntu")
        yield deferToDatabase(
            self.set_ports_archive, "http://ports.ubuntu.com/ubuntu-ports")

        response = yield call_responder(Region(), GetArchiveMirrors, {})

        self.assertEqual(
            {"main": urlparse("http://archive.ubuntu.com/ubuntu"),
             "ports": urlparse("http://ports.ubuntu.com/ubuntu-ports")},
            response)

    @wait_for_reactor
    @inlineCallbacks
    def test_get_archive_mirrors_with_main_archive_set(self):
        url = factory.make_parsed_url()
        yield deferToDatabase(self.set_main_archive, url.geturl())

        response = yield call_responder(Region(), GetArchiveMirrors, {})

        self.assertEqual(
            {"main": url,
             "ports": urlparse("http://ports.ubuntu.com/ubuntu-ports")},
            response)

    @inlineCallbacks
    def test_get_archive_mirrors_with_ports_archive_set(self):
        url = factory.make_parsed_url()
        yield deferToDatabase(self.set_ports_archive, url.geturl())

        response = yield call_responder(Region(), GetArchiveMirrors, {})

        self.assertEqual(
            {"main": urlparse("http://arhive.ubuntu.com/ubuntu"),
             "ports": url},
            response)


class TestRegionProtocol_GetProxies(MAASTransactionServerTestCase):

    def test_get_proxies_is_registered(self):
        protocol = Region()
        responder = protocol.locateResponder(GetProxies.commandName)
        self.assertIsNotNone(responder)

    @transactional
    def set_http_proxy(self, url):
        Config.objects.set_config("http_proxy", url)

    @wait_for_reactor
    @inlineCallbacks
    def test_get_proxies_with_http_proxy_not_set(self):
        yield deferToDatabase(self.set_http_proxy, None)

        response = yield call_responder(Region(), GetProxies, {})

        self.assertEqual(
            {"http": None, "https": None},
            response)

    @wait_for_reactor
    @inlineCallbacks
    def test_get_proxies_with_http_proxy_set(self):
        url = factory.make_parsed_url()
        yield deferToDatabase(self.set_http_proxy, url.geturl())

        response = yield call_responder(Region(), GetProxies, {})

        self.assertEqual(
            {"http": url, "https": url},
            response)


class TestRegionProtocol_MarkNodeFailed(MAASTransactionServerTestCase):

    def test_mark_failed_is_registered(self):
        protocol = Region()
        responder = protocol.locateResponder(MarkNodeFailed.commandName)
        self.assertIsNotNone(responder)

    @transactional
    def create_deploying_node(self):
        node = factory.make_Node(status=NODE_STATUS.DEPLOYING)
        return node.system_id

    @transactional
    def get_node_status(self, system_id):
        node = Node.objects.get(system_id=system_id)
        return node.status

    @transactional
    def get_node_error_description(self, system_id):
        node = Node.objects.get(system_id=system_id)
        return node.error_description

    @wait_for_reactor
    @inlineCallbacks
    def test_mark_node_failed_changes_status_and_updates_error_msg(self):
        system_id = yield deferToDatabase(self.create_deploying_node)

        error_description = factory.make_name('error-description')
        response = yield call_responder(
            Region(), MarkNodeFailed,
            {'system_id': system_id, 'error_description': error_description})

        self.assertEqual({}, response)
        new_status = yield deferToDatabase(self.get_node_status, system_id)
        new_error_description = yield deferToDatabase(
            self.get_node_error_description, system_id)
        self.assertEqual(
            (NODE_STATUS.FAILED_DEPLOYMENT, error_description),
            (new_status, new_error_description))

    @wait_for_reactor
    def test_mark_node_failed_errors_if_node_cannot_be_found(self):
        system_id = factory.make_name('unknown-system-id')
        error_description = factory.make_name('error-description')

        d = call_responder(
            Region(), MarkNodeFailed,
            {'system_id': system_id, 'error_description': error_description})

        def check(error):
            self.assertIsInstance(error, Failure)
            self.assertIsInstance(error.value, NoSuchNode)
            # The error message contains a reference to system_id.
            self.assertIn(system_id, str(error.value))

        return d.addErrback(check)


class TestRegionProtocol_ListNodePowerParameters(
        MAASTransactionServerTestCase):

    @transactional
    def create_node(self, **kwargs):
        node = factory.make_Node(**kwargs)
        return node

    @transactional
    def create_rack_controller(self, **kwargs):
        rack = factory.make_RackController(**kwargs)
        return rack

    @transactional
    def get_node_power_parameters(self, node):
        return node.get_effective_power_parameters()

    def test__is_registered(self):
        protocol = Region()
        responder = protocol.locateResponder(
            ListNodePowerParameters.commandName)
        self.assertIsNotNone(responder)

    @wait_for_reactor
    @inlineCallbacks
    def test__returns_correct_arguments(self):
        rack = yield deferToDatabase(
            self.create_rack_controller, power_type='')

        nodes = []
        for _ in range(3):
            node = yield deferToDatabase(
                self.create_node,
                power_type="virsh",
                power_state_updated=None,
                bmc_connected_to=rack)
            power_params = yield deferToDatabase(
                self.get_node_power_parameters, node)
            nodes.append({
                'system_id': node.system_id,
                'hostname': node.hostname,
                'power_state': node.power_state,
                'power_type': node.get_effective_power_type(),
                'context': power_params,
                })

        # Create a node with an invalid power type (i.e. the empty string).
        # This will not be reported by the call to ListNodePowerParameters.
        yield deferToDatabase(
            self.create_node, power_type="", power_state_updated=None)

        response = yield call_responder(
            Region(), ListNodePowerParameters,
            {'uuid': rack.system_id})

        self.maxDiff = None
        self.assertItemsEqual(nodes, response['nodes'])

    @wait_for_reactor
    def test__raises_exception_if_nodegroup_doesnt_exist(self):
        uuid = factory.make_UUID()

        d = call_responder(
            Region(), ListNodePowerParameters,
            {'uuid': uuid})

        return assert_fails_with(d, NoSuchCluster)


class TestRegionProtocol_UpdateNodePowerState(MAASTransactionServerTestCase):

    @transactional
    def create_node(self, power_state):
        node = factory.make_Node(power_state=power_state)
        return node

    @transactional
    def get_node_power_state(self, system_id):
        node = Node.objects.get(system_id=system_id)
        return node.power_state

    def test__is_registered(self):
        protocol = Region()
        responder = protocol.locateResponder(UpdateNodePowerState.commandName)
        self.assertIsNotNone(responder)

    @wait_for_reactor
    @inlineCallbacks
    def test__changes_power_state(self):
        power_state = factory.pick_enum(POWER_STATE)
        node = yield deferToDatabase(self.create_node, power_state)

        new_state = factory.pick_enum(POWER_STATE, but_not=power_state)
        yield call_responder(
            Region(), UpdateNodePowerState,
            {'system_id': node.system_id, 'power_state': new_state})

        db_state = yield deferToDatabase(
            self.get_node_power_state, node.system_id)
        self.assertEqual(new_state, db_state)

    @wait_for_reactor
    def test__errors_if_node_cannot_be_found(self):
        system_id = factory.make_name('unknown-system-id')
        power_state = factory.pick_enum(POWER_STATE)

        d = call_responder(
            Region(), UpdateNodePowerState,
            {'system_id': system_id, 'power_state': power_state})

        def check(error):
            self.assertIsInstance(error, Failure)
            self.assertIsInstance(error.value, NoSuchNode)
            # The error message contains a reference to system_id.
            self.assertIn(system_id, str(error.value))

        return d.addErrback(check)


class TestRegionProtocol_RegisterEventType(MAASTransactionServerTestCase):

    def test_register_event_type_is_registered(self):
        protocol = Region()
        responder = protocol.locateResponder(RegisterEventType.commandName)
        self.assertIsNotNone(responder)

    @transactional
    def get_event_type(self, name):
        return EventType.objects.get(name=name)

    @wait_for_reactor
    @inlineCallbacks
    def test_register_event_type_creates_object(self):
        name = factory.make_name('name')
        description = factory.make_name('description')
        level = random.randint(0, 100)
        response = yield call_responder(
            Region(), RegisterEventType,
            {'name': name, 'description': description, 'level': level})

        self.assertEqual({}, response)
        event_type = yield deferToDatabase(self.get_event_type, name)
        self.assertThat(
            event_type,
            MatchesStructure.byEquality(
                name=name, description=description, level=level)
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_register_event_type_does_not_error_for_existing_event_types(self):
        # This is a regression test for bug 1373357.
        name = factory.make_name('name')
        old_description = factory.make_name('old-description')
        level = random.randint(0, 100)
        response = yield call_responder(
            Region(), RegisterEventType,
            {'name': name, 'description': old_description, 'level': level})
        self.assertEqual({}, response)

        new_description = factory.make_name('new-description')
        response = yield call_responder(
            Region(), RegisterEventType,
            {'name': name, 'description': new_description, 'level': level})
        # If we get this far, no error has been raised, even though we
        # sent a duplicate request for registration.
        self.assertEqual({}, response)


class TestRegionProtocol_SendEvent(MAASTransactionServerTestCase):

    def setUp(self):
        super(TestRegionProtocol_SendEvent, self).setUp()
        self.useFixture(RegionEventLoopFixture("database-tasks"))

    def test_send_event_is_registered(self):
        protocol = Region()
        responder = protocol.locateResponder(SendEvent.commandName)
        self.assertIsNotNone(responder)

    @transactional
    def get_event(self, system_id, type_name):
        # Pre-fetch the related 'node' and 'type' because the caller
        # runs in the event-loop and this can't dereference related
        # objects (unless they have been prefetched).
        all_events_qs = Event.objects.all().select_related(
            'node', 'type')
        event = all_events_qs.get(
            node__system_id=system_id, type__name=type_name)
        return event

    @transactional
    def create_event_type(self, name, description, level):
        EventType.objects.create(
            name=name, description=description, level=level)

    @transactional
    def create_node(self):
        return factory.make_Node().system_id

    @wait_for_reactor
    @inlineCallbacks
    def test_send_event_stores_event(self):
        name = factory.make_name('type_name')
        description = factory.make_name('description')
        level = random.randint(0, 100)
        yield deferToDatabase(self.create_event_type, name, description, level)
        system_id = yield deferToDatabase(self.create_node)

        event_description = factory.make_name('description')

        yield eventloop.start()
        try:
            response = yield call_responder(
                Region(), SendEvent, {
                    'system_id': system_id,
                    'type_name': name,
                    'description': event_description,
                })
        finally:
            yield eventloop.reset()

        self.assertEqual({}, response)
        event = yield deferToDatabase(self.get_event, system_id, name)
        self.expectThat(event.node.system_id, Equals(system_id))
        self.expectThat(event.description, Equals(event_description))
        self.expectThat(event.type.name, Equals(name))

    @wait_for_reactor
    @inlineCallbacks
    def test_send_event_stores_event_with_timestamp_received(self):
        # Use a random time in the recent past and coerce the responder to use
        # it as the time-stamp for the event. We'll check this later on.
        timestamp = datetime.now() - timedelta(seconds=randint(99, 99999))
        self.patch(regionservice, "datetime").now.return_value = timestamp

        event_type = factory.make_name('type_name')
        yield deferToDatabase(self.create_event_type, event_type, "", 0)
        system_id = yield deferToDatabase(self.create_node)

        yield eventloop.start()
        try:
            yield call_responder(
                Region(), SendEvent, {
                    'system_id': system_id, 'type_name': event_type,
                    'description': factory.make_name('description'),
                })
        finally:
            yield eventloop.reset()

        event = yield deferToDatabase(self.get_event, system_id, event_type)
        self.expectThat(event.created, Equals(timestamp))

    @skip("XXX: GavinPanella 2016-03-11 bug=1556188: Fails spuriously.")
    @wait_for_reactor
    @inlineCallbacks
    def test_send_event_does_not_fail_if_unknown_type(self):
        name = factory.make_name('type_name')
        system_id = factory.make_name('system_id')
        description = factory.make_name('description')

        logger = self.useFixture(TwistedLoggerFixture())

        yield eventloop.start()
        try:
            yield call_responder(
                Region(), SendEvent, {
                    'system_id': system_id,
                    'type_name': name,
                    'description': description,
                })
        finally:
            yield eventloop.reset()

        # The log records the issue. FIXME: Why reject logs if the type is not
        # registered? Seems like the region should record all logs and figure
        # out how to present them.
        self.assertDocTestMatches(
            """\
            Unhandled failure in database task.
            Traceback (most recent call last):
            ...
            provisioningserver.rpc.exceptions.NoSuchEventType:
            ...
            """, logger.output)

    @wait_for_reactor
    @inlineCallbacks
    def test_send_event_logs_if_unknown_node(self):
        maaslog = self.patch(events_module, 'maaslog')
        name = factory.make_name('type_name')
        description = factory.make_name('description')
        level = random.randint(0, 100)
        yield deferToDatabase(self.create_event_type, name, description, level)

        system_id = factory.make_name('system_id')
        event_description = factory.make_name('event-description')

        yield eventloop.start()
        try:
            yield call_responder(
                Region(), SendEvent, {
                    'system_id': system_id,
                    'type_name': name,
                    'description': event_description,
                })
        finally:
            yield eventloop.reset()

        self.assertThat(
            maaslog.debug, MockCalledOnceWith(
                "Event '%s: %s' sent for non-existent node '%s'.",
                name, event_description, system_id))


class TestRegionProtocol_SendEventMACAddress(MAASTransactionServerTestCase):

    def setUp(self):
        super(TestRegionProtocol_SendEventMACAddress, self).setUp()
        self.useFixture(RegionEventLoopFixture("database-tasks"))

    def test_send_event_mac_address_is_registered(self):
        protocol = Region()
        responder = protocol.locateResponder(
            SendEventMACAddress.commandName)
        self.assertIsNotNone(responder)

    @transactional
    def get_event(self, mac_address, type_name):
        # Pre-fetch the related 'node' and 'type' because the caller
        # runs in the event-loop and this can't dereference related
        # objects (unless they have been prefetched).
        all_events_qs = Event.objects.all().select_related(
            'node', 'type')
        node = PhysicalInterface.objects.get(mac_address=mac_address).node
        event = all_events_qs.get(node=node, type__name=type_name)
        return event

    @transactional
    def create_event_type(self, name, description, level):
        EventType.objects.create(
            name=name, description=description, level=level)

    @transactional
    def make_interface(self):
        # Precache the node. So a database query is not made in the event-loop.
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        node = interface.node
        ignore_unused(node)
        return interface

    @wait_for_reactor
    @inlineCallbacks
    def test_send_event_mac_address_stores_event(self):
        name = factory.make_name('type_name')
        description = factory.make_name('description')
        level = random.randint(0, 100)
        yield deferToDatabase(self.create_event_type, name, description, level)
        interface = yield deferToDatabase(self.make_interface)
        mac_address = interface.mac_address
        event_description = factory.make_name('description')

        yield eventloop.start()
        try:
            response = yield call_responder(
                Region(), SendEventMACAddress, {
                    'mac_address': mac_address.get_raw(),
                    'type_name': name,
                    'description': event_description,
                })
        finally:
            yield eventloop.reset()

        self.assertEqual({}, response)
        event = yield deferToDatabase(self.get_event, mac_address, name)
        self.expectThat(event.node.system_id, Equals(interface.node.system_id))
        self.expectThat(event.description, Equals(event_description))
        self.expectThat(event.type.name, Equals(name))

    @wait_for_reactor
    @inlineCallbacks
    def test_send_event_mac_address_stores_event_with_timestamp_received(self):
        # Use a random time in the recent past and coerce the responder to use
        # it as the time-stamp for the event. We'll check this later on.
        timestamp = datetime.now() - timedelta(seconds=randint(99, 99999))
        self.patch(regionservice, "datetime").now.return_value = timestamp

        event_type = factory.make_name('type_name')
        yield deferToDatabase(self.create_event_type, event_type, "", 0)
        interface = yield deferToDatabase(self.make_interface)
        mac_address = interface.mac_address.get_raw()

        yield eventloop.start()
        try:
            yield call_responder(
                Region(), SendEventMACAddress, {
                    'mac_address': mac_address, 'type_name': event_type,
                    'description': factory.make_name('description'),
                })
        finally:
            yield eventloop.reset()

        event = yield deferToDatabase(self.get_event, mac_address, event_type)
        self.expectThat(event.created, Equals(timestamp))

    @wait_for_reactor
    @inlineCallbacks
    def test_send_event_mac_address_does_not_fail_if_unknown_type(self):
        name = factory.make_name('type_name')
        mac_address = factory.make_mac_address()
        description = factory.make_name('description')

        logger = self.useFixture(TwistedLoggerFixture())

        yield eventloop.start()
        try:
            yield call_responder(
                Region(), SendEventMACAddress, {
                    'mac_address': mac_address,
                    'type_name': name,
                    'description': description,
                })
        finally:
            yield eventloop.reset()

        # The log records the issue. FIXME: Why reject logs if the type is not
        # registered? Seems like the region should record all logs and figure
        # out how to present them.
        self.assertDocTestMatches(
            """\
            Unhandled failure in database task.
            Traceback (most recent call last):
            ...
            provisioningserver.rpc.exceptions.NoSuchEventType:
            ...
            """, logger.output)

    @wait_for_reactor
    @inlineCallbacks
    def test_send_event_mac_address_logs_if_unknown_node(self):
        maaslog = self.patch(events_module, 'maaslog')
        name = factory.make_name('type_name')
        description = factory.make_name('description')
        level = random.randint(0, 100)
        yield deferToDatabase(self.create_event_type, name, description, level)
        mac_address = factory.make_mac_address()
        event_description = factory.make_name('event-description')

        yield eventloop.start()
        try:
            yield call_responder(
                Region(), SendEventMACAddress, {
                    'mac_address': mac_address,
                    'type_name': name,
                    'description': event_description,
                })
        finally:
            yield eventloop.reset()

        self.assertThat(
            maaslog.debug, MockCalledOnceWith(
                "Event '%s: %s' sent for non-existent node with MAC address "
                "'%s'.", name, event_description, mac_address))


class TestRegionProtocol_UpdateServices(MAASTransactionServerTestCase):

    def setUp(self):
        super(TestRegionProtocol_UpdateServices, self).setUp()
        self.useFixture(RegionEventLoopFixture("database-tasks"))

    def test_update_services_is_registered(self):
        protocol = Region()
        responder = protocol.locateResponder(UpdateServices.commandName)
        self.assertIsNotNone(responder)

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_update_services_in_database_thread(self):
        system_id = factory.make_name("system_id")
        services = [{
            "name": factory.make_name("service"),
            "status": factory.make_name("status"),
            "status_info": factory.make_name("status_info"),
        }]

        mock_deferToDatabase = self.patch(regionservice, "deferToDatabase")
        mock_deferToDatabase.return_value = succeed({})

        yield eventloop.start()
        try:
            yield call_responder(
                Region(), UpdateServices, {
                    "system_id": system_id,
                    "services": services,
                    })
        finally:
            yield eventloop.reset()

        self.assertThat(
            mock_deferToDatabase,
            MockCalledWith(update_services, system_id, services))


class TestRegisterAndUnregisterConnection(MAASServerTestCase):
    """Tests for the `registerConnection` and `unregisterConnection`
    function."""

    def test__adds_connection_and_removes_connection(self):
        region = factory.make_RegionController()
        process = factory.make_RegionControllerProcess(region=region)
        endpoint = factory.make_RegionControllerProcessEndpoint(process)

        self.patch(os, "getpid").return_value = process.pid

        host = MagicMock()
        host.host = endpoint.address
        host.port = endpoint.port

        rack_controller = factory.make_RackController()

        registerConnection(region.system_id, rack_controller, host)
        self.assertIsNotNone(
            RegionRackRPCConnection.objects.filter(
                endpoint=endpoint, rack_controller=rack_controller).first())

        # Checks that an exception is not raised if already registered.
        registerConnection(region.system_id, rack_controller, host)

        unregisterConnection(region.system_id, rack_controller.system_id, host)
        self.assertIsNone(
            RegionRackRPCConnection.objects.filter(
                endpoint=endpoint, rack_controller=rack_controller).first())


class TestRegionServer(MAASTransactionServerTestCase):

    def test_interfaces(self):
        protocol = RegionServer()
        # transport.getHandle() is used by AMP._getPeerCertificate, which we
        # call indirectly via the peerCertificate attribute in IConnection.
        self.patch(protocol, "transport")
        verifyObject(IConnection, protocol)

    def test_connectionMade_does_not_update_services_connection_set(self):
        service = RegionService()
        service.running = True  # Pretend it's running.
        service.factory.protocol = HandshakingRegionServer
        protocol = service.factory.buildProtocol(addr=None)  # addr is unused.
        self.assertDictEqual({}, service.connections)
        protocol.connectionMade()
        self.assertDictEqual({}, service.connections)

    def test_connectionMade_drops_connection_if_service_not_running(self):
        service = RegionService()
        service.running = False  # Pretend it's not running.
        service.factory.protocol = HandshakingRegionServer
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
        service.factory.protocol = HandshakingRegionServer
        protocol = service.factory.buildProtocol(addr=None)  # addr is unused.
        protocol.ident = factory.make_name("node")
        connectionLost_up_call = self.patch(amp.AMP, "connectionLost")
        service.connections[protocol.ident] = {protocol}

        protocol.connectionLost(reason=None)
        # The connection is removed from the set, but the key remains.
        self.assertDictEqual({protocol.ident: set()}, service.connections)
        # connectionLost() is called on the superclass.
        self.assertThat(connectionLost_up_call, MockCalledOnceWith(None))

    def test_connectionLost_calls_unregisterConnection_in_thread(self):
        service = RegionService()
        service.running = True  # Pretend it's running.
        service.factory.protocol = HandshakingRegionServer
        protocol = service.factory.buildProtocol(addr=None)  # addr is unused.
        protocol.ident = factory.make_name("node")
        protocol.host = sentinel.host
        protocol.hostIsRemote = True
        protocol.getRegionID = lambda: succeed(sentinel.region_id)
        connectionLost_up_call = self.patch(amp.AMP, "connectionLost")
        service.connections[protocol.ident] = {protocol}

        mock_deferToDatabase = self.patch(regionservice, "deferToDatabase")
        protocol.connectionLost(reason=None)
        self.assertThat(
            mock_deferToDatabase, MockCalledOnceWith(
                unregisterConnection, sentinel.region_id, protocol.ident,
                protocol.host))
        # The connection is removed from the set, but the key remains.
        self.assertDictEqual({protocol.ident: set()}, service.connections)
        # connectionLost() is called on the superclass.
        self.assertThat(connectionLost_up_call, MockCalledOnceWith(None))

    def patch_authenticate_for_failure(self, client):
        authenticate = self.patch_autospec(client, "authenticateCluster")
        authenticate.side_effect = always_succeed_with(False)

    def patch_authenticate_for_error(self, client, exception):
        authenticate = self.patch_autospec(client, "authenticateCluster")
        authenticate.side_effect = always_fail_with(exception)

    def test_connectionMade_drops_connections_if_authentication_fails(self):
        service = RegionService()
        service.running = True  # Pretend it's running.
        service.factory.protocol = HandshakingRegionServer
        protocol = service.factory.buildProtocol(addr=None)  # addr is unused.
        self.patch_authenticate_for_failure(protocol)
        transport = self.patch(protocol, "transport")
        self.assertDictEqual({}, service.connections)
        protocol.connectionMade()
        # The protocol is not added to the connection set.
        self.assertDictEqual({}, service.connections)
        # The transport is instructed to lose the connection.
        self.assertThat(transport.loseConnection, MockCalledOnceWith())

    def test_connectionMade_drops_connections_if_authentication_errors(self):
        logger = self.useFixture(TwistedLoggerFixture())

        service = RegionService()
        service.running = True  # Pretend it's running.
        service.factory.protocol = HandshakingRegionServer
        protocol = service.factory.buildProtocol(addr=None)  # addr is unused.
        protocol.transport = MagicMock()
        exception_type = factory.make_exception_type()
        self.patch_authenticate_for_error(protocol, exception_type())
        self.assertDictEqual({}, service.connections)

        connectionMade = wait_for_reactor(protocol.connectionMade)
        connectionMade()

        # The protocol is not added to the connection set.
        self.assertDictEqual({}, service.connections)
        # The transport is instructed to lose the connection.
        self.assertThat(
            protocol.transport.loseConnection, MockCalledOnceWith())

        # The log was written to.
        self.assertDocTestMatches(
            """\
            Rack controller '...' could not be authenticated; dropping
            connection.
            Traceback (most recent call last):...
            """,
            logger.dump())

    def test_handshakeFailed_does_not_log_when_connection_is_closed(self):
        server = RegionServer()
        with TwistedLoggerFixture() as logger:
            server.handshakeFailed(Failure(ConnectionClosed()))
        # Nothing was logged.
        self.assertEqual("", logger.output)

    def make_handshaking_server(self):
        service = RegionService()
        service.running = True  # Pretend it's running.
        service.factory.protocol = HandshakingRegionServer
        return service.factory.buildProtocol(addr=None)  # addr is unused.

    def make_running_server(self):
        service = RegionService()
        service.running = True  # Pretend it's running.
        # service.factory.protocol = RegionServer
        return service.factory.buildProtocol(addr=None)  # addr is unused.

    def test_authenticateCluster_accepts_matching_digests(self):
        server = self.make_running_server()

        def calculate_digest(_, message):
            # Use the region's own authentication responder.
            return Region().authenticate(message)

        callRemote = self.patch_autospec(server, "callRemote")
        callRemote.side_effect = calculate_digest

        d = server.authenticateCluster()
        self.assertTrue(extract_result(d))

    def test_authenticateCluster_rejects_non_matching_digests(self):
        server = self.make_running_server()

        def calculate_digest(_, message):
            # Return some nonsense.
            response = {
                "digest": factory.make_bytes(),
                "salt": factory.make_bytes(),
            }
            return succeed(response)

        callRemote = self.patch_autospec(server, "callRemote")
        callRemote.side_effect = calculate_digest

        d = server.authenticateCluster()
        self.assertFalse(extract_result(d))

    def test_authenticateCluster_propagates_errors(self):
        server = self.make_running_server()
        exception_type = factory.make_exception_type()

        callRemote = self.patch_autospec(server, "callRemote")
        callRemote.return_value = fail(exception_type())

        d = server.authenticateCluster()
        self.assertRaises(exception_type, extract_result, d)

    def make_Region(self):
        patched_region = RegionServer()
        patched_region.factory = Factory.forProtocol(RegionServer)
        patched_region.factory.service = RegionService()
        return patched_region

    def test_register_is_registered(self):
        protocol = RegionServer()
        responder = protocol.locateResponder(
            RegisterRackController.commandName)
        self.assertIsNotNone(responder)

    def installFakeRegionAdvertisingService(self):
        service = Service()
        service.setName("rpc-advertise")
        service.advertising = DeferredValue()
        service.advertising.set(Mock(
            region_id=factory.make_name("region-id"),
            process_id=randint(1000, 9999)))
        service.setServiceParent(eventloop.services)
        self.addCleanup(service.disownServiceParent)

    @wait_for_reactor
    @inlineCallbacks
    def test_register_returns_system_id(self):
        self.installFakeRegionAdvertisingService()
        rack_controller = yield deferToDatabase(factory.make_RackController)
        protocol = self.make_Region()
        protocol.transport = MagicMock()
        response = yield call_responder(
            protocol, RegisterRackController, {
                "system_id": rack_controller.system_id,
                "hostname": rack_controller.hostname,
                "interfaces": {},
            })
        self.assertEquals(
            {"system_id": rack_controller.system_id}, response)

    @wait_for_reactor
    @inlineCallbacks
    def test_register_updates_interfaces(self):
        self.installFakeRegionAdvertisingService()
        rack_controller = yield deferToDatabase(factory.make_RackController)
        protocol = self.make_Region()
        protocol.transport = MagicMock()
        nic_name = factory.make_name("eth0")
        interfaces = {
            nic_name: {
                "type": "physical",
                "mac_address": factory.make_mac_address(),
                "parents": [],
                "links": [],
                "enabled": True,
            }
        }
        response = yield call_responder(
            protocol, RegisterRackController, {
                "system_id": rack_controller.system_id,
                "hostname": rack_controller.hostname,
                "interfaces": interfaces,
            })

        @transactional
        def has_interface(system_id, nic_name):
            rack_controller = RackController.objects.get(system_id=system_id)
            interfaces = rack_controller.interface_set.filter(name=nic_name)
            self.assertThat(interfaces, HasLength(1))
        yield deferToDatabase(has_interface, response["system_id"], nic_name)

    @wait_for_reactor
    @inlineCallbacks
    def test_register_calls_handle_upgrade(self):
        self.installFakeRegionAdvertisingService()
        rack_controller = yield deferToDatabase(factory.make_RackController)
        protocol = self.make_Region()
        protocol.transport = MagicMock()
        ng_uuid = factory.make_UUID()
        mock_handle_upgrade = self.patch(
            regionservice.rackcontrollers, "handle_upgrade")
        yield call_responder(
            protocol, RegisterRackController, {
                "system_id": rack_controller.system_id,
                "hostname": rack_controller.hostname,
                "interfaces": {},
                "nodegroup_uuid": ng_uuid,
            })
        self.assertThat(
            mock_handle_upgrade, MockCalledOnceWith(rack_controller, ng_uuid))

    @wait_for_reactor
    @inlineCallbacks
    def test_register_sets_ident(self):
        self.installFakeRegionAdvertisingService()
        rack_controller = yield deferToDatabase(factory.make_RackController)
        protocol = self.make_Region()
        protocol.transport = MagicMock()
        yield call_responder(
            protocol, RegisterRackController, {
                "system_id": rack_controller.system_id,
                "hostname": rack_controller.hostname,
                "interfaces": {},
            })
        self.assertEquals(rack_controller.system_id, protocol.ident)

    @wait_for_reactor
    @inlineCallbacks
    def test_register_calls_addConnectionFor(self):
        self.installFakeRegionAdvertisingService()
        rack_controller = yield deferToDatabase(factory.make_RackController)
        protocol = self.make_Region()
        protocol.transport = MagicMock()
        mock_addConnectionFor = self.patch(
            protocol.factory.service, "_addConnectionFor")
        yield call_responder(
            protocol, RegisterRackController, {
                "system_id": rack_controller.system_id,
                "hostname": rack_controller.hostname,
                "interfaces": {},
            })
        self.assertThat(
            mock_addConnectionFor,
            MockCalledOnceWith(rack_controller.system_id, protocol))

    @wait_for_reactor
    @inlineCallbacks
    def test_register_sets_hosts(self):
        self.installFakeRegionAdvertisingService()
        rack_controller = yield deferToDatabase(factory.make_RackController)
        protocol = self.make_Region()
        protocol.transport = MagicMock()
        protocol.transport.getHost.return_value = sentinel.host
        yield call_responder(
            protocol, RegisterRackController, {
                "system_id": rack_controller.system_id,
                "hostname": rack_controller.hostname,
                "interfaces": {},
            })
        self.assertEquals(sentinel.host, protocol.host)

    @wait_for_reactor
    @inlineCallbacks
    def test_register_sets_hostIsRemote_calls_registerConnection(self):
        self.installFakeRegionAdvertisingService()
        rack_controller = yield deferToDatabase(factory.make_RackController)
        protocol = self.make_Region()
        protocol.transport = MagicMock()
        host = IPv4Address(
            type='TCP', host=factory.make_ipv4_address(),
            port=random.randint(1, 400))
        protocol.transport.getHost.return_value = host
        mock_deferToDatabase = self.patch(regionservice, "deferToDatabase")
        yield call_responder(
            protocol, RegisterRackController, {
                "system_id": rack_controller.system_id,
                "hostname": rack_controller.hostname,
                "interfaces": {},
            })
        self.assertTrue(sentinel.host, protocol.hostIsRemote)
        self.assertThat(
            mock_deferToDatabase,
            MockAnyCall(registerConnection, ANY, ANY, host))

    @wait_for_reactor
    @inlineCallbacks
    def test_register_creates_new_rack(self):
        self.installFakeRegionAdvertisingService()
        protocol = self.make_Region()
        protocol.transport = MagicMock()
        hostname = factory.make_hostname()
        yield call_responder(
            protocol, RegisterRackController, {
                "system_id": None,
                "hostname": hostname,
                "interfaces": {},
            })
        yield deferToDatabase(
            RackController.objects.get, hostname=hostname)

    @skip("XXX: GavinPanella 2016-03-09 bug=1555236: Fails spuriously.")
    @wait_for_reactor
    @inlineCallbacks
    def test_register_calls_refresh_when_needed(self):
        protocol = self.make_Region()
        protocol.transport = MagicMock()
        mock_gethost = self.patch(protocol.transport, 'getHost')
        mock_gethost.return_value = IPv4Address(
            type='TCP', host=factory.make_ipv4_address(),
            port=random.randint(1, 65535))
        mock_refresh = self.patch(RackController, 'refresh')
        self.patch(regionservice, 'registerConnection')
        hostname = factory.make_hostname()
        yield call_responder(
            protocol, RegisterRackController, {
                "system_id": None,
                "hostname": hostname,
                "interfaces": {},
            })
        self.assertThat(mock_refresh, MockCalledOnce())

    @wait_for_reactor
    @inlineCallbacks
    def test_register_raises_CannotRegisterRackController_when_it_cant(self):
        self.installFakeRegionAdvertisingService()
        patched_create = self.patch(RackController.objects, 'create')
        patched_create.side_effect = IntegrityError()
        hostname = factory.make_name("hostname")
        error = yield assert_fails_with(
            call_responder(self.make_Region(), RegisterRackController,
                           {"system_id": None,
                            "hostname": hostname,
                            "interfaces": {}}),
            CannotRegisterRackController)
        self.assertEquals((
            "Failed to register rack controller 'None' into the database. "
            "Connection has been dropped.",), error.args)


class TestRegionService(MAASTestCase):

    def test_init_sets_appropriate_instance_attributes(self):
        service = RegionService()
        self.assertThat(service, IsInstance(Service))
        self.assertThat(service.connections, IsInstance(defaultdict))
        self.assertThat(service.connections.default_factory, Is(set))
        self.assertThat(
            service.endpoints, AllMatch(
                AllMatch(Provides(IStreamServerEndpoint))))
        self.assertThat(service.factory, IsInstance(Factory))
        self.assertThat(service.factory.protocol, Equals(RegionServer))
        self.assertThat(service.events.connected, IsInstance(events.Event))
        self.assertThat(service.events.disconnected, IsInstance(events.Event))

    @wait_for_reactor
    def test_starting_and_stopping_the_service(self):
        service = RegionService()
        self.assertThat(service.starting, Is(None))
        service.startService()
        self.assertThat(service.starting, IsInstance(Deferred))

        def check_started(_):
            # Ports are saved as private instance vars.
            self.assertThat(service.ports, HasLength(1))
            [port] = service.ports
            self.assertThat(port, IsInstance(tcp.Port))
            self.assertThat(port.factory, IsInstance(Factory))
            self.assertThat(port.factory.protocol, Equals(RegionServer))
            return service.stopService()

        service.starting.addCallback(check_started)

        def check_stopped(ignore, service=service):
            self.assertThat(service.ports, Equals([]))

        service.starting.addCallback(check_stopped)

        return service.starting

    @wait_for_reactor
    def test_startService_returns_Deferred(self):
        service = RegionService()

        # Don't configure any endpoints.
        self.patch(service, "endpoints", [])

        d = service.startService()
        self.assertThat(d, IsInstance(Deferred))
        # It's actually the `starting` Deferred.
        self.assertIs(service.starting, d)

        def started(_):
            return service.stopService()

        return d.addCallback(started)

    @wait_for_reactor
    def test_start_up_can_be_cancelled(self):
        service = RegionService()

        # Return an inert Deferred from the listen() call.
        endpoints = self.patch(service, "endpoints", [[Mock()]])
        endpoints[0][0].listen.return_value = Deferred()

        service.startService()
        self.assertThat(service.starting, IsInstance(Deferred))

        service.starting.cancel()

        def check(port):
            self.assertThat(port, Is(None))
            self.assertThat(service.ports, HasLength(0))
            return service.stopService()

        return service.starting.addCallback(check)

    @wait_for_reactor
    @inlineCallbacks
    def test_start_up_errors_are_logged(self):
        service = RegionService()

        # Ensure that endpoint.listen fails with a obvious error.
        exception = ValueError("This is not the messiah.")
        endpoints = self.patch(service, "endpoints", [[Mock()]])
        endpoints[0][0].listen.return_value = fail(exception)

        logged_failures = []
        self.patch(log, "msg", (
            lambda failure, **kw: logged_failures.append(failure)))

        logged_failures_expected = [
            AfterPreprocessing(
                (lambda failure: failure.value),
                Is(exception)),
        ]

        yield service.startService()
        self.assertThat(
            logged_failures, MatchesListwise(logged_failures_expected))

    @wait_for_reactor
    @inlineCallbacks
    def test_start_up_binds_first_of_endpoint_options(self):
        service = RegionService()

        endpoint_1 = Mock()
        endpoint_1.listen.return_value = succeed(sentinel.port1)
        endpoint_2 = Mock()
        endpoint_2.listen.return_value = succeed(sentinel.port2)
        service.endpoints = [[endpoint_1, endpoint_2]]

        yield service.startService()

        self.assertThat(service.ports, Equals([sentinel.port1]))

    @wait_for_reactor
    @inlineCallbacks
    def test_start_up_binds_first_of_real_endpoint_options(self):
        service = RegionService()

        # endpoint_1.listen(...) will bind to a random high-numbered port.
        endpoint_1 = TCP4ServerEndpoint(reactor, 0)
        # endpoint_2.listen(...), if attempted, will crash because only root
        # (or a user with explicit capabilities) can do stuff like that. It's
        # a reasonable assumption that the user running these tests is not
        # root, but we'll check the port number later too to be sure.
        endpoint_2 = TCP4ServerEndpoint(reactor, 1)

        service.endpoints = [[endpoint_1, endpoint_2]]

        yield service.startService()
        self.addCleanup(wait_for_reactor(service.stopService))

        # A single port has been bound.
        self.assertThat(service.ports, MatchesAll(
            HasLength(1), AllMatch(IsInstance(tcp.Port))))

        # The port is not listening on port 1; i.e. a belt-n-braces check that
        # endpoint_2 was not used.
        [port] = service.ports
        self.assertThat(port.getHost().port, Not(Equals(1)))

    @wait_for_reactor
    @inlineCallbacks
    def test_start_up_binds_first_successful_of_endpoint_options(self):
        service = RegionService()

        endpoint_broken = Mock()
        endpoint_broken.listen.return_value = fail(factory.make_exception())
        endpoint_okay = Mock()
        endpoint_okay.listen.return_value = succeed(sentinel.port)
        service.endpoints = [[endpoint_broken, endpoint_okay]]

        yield service.startService()

        self.assertThat(service.ports, Equals([sentinel.port]))

    @wait_for_reactor
    @inlineCallbacks
    def test_start_up_logs_failure_if_all_endpoint_options_fail(self):
        service = RegionService()

        error_1 = factory.make_exception_type()
        error_2 = factory.make_exception_type()

        endpoint_1 = Mock()
        endpoint_1.listen.return_value = fail(error_1())
        endpoint_2 = Mock()
        endpoint_2.listen.return_value = fail(error_2())
        service.endpoints = [[endpoint_1, endpoint_2]]

        with TwistedLoggerFixture() as logger:
            yield service.startService()

        self.assertDocTestMatches(
            """\
            RegionServer endpoint failed to listen.
            Traceback (most recent call last):
            ...
            %s:
            """ % fullyQualifiedName(error_2),
            logger.output)

    @wait_for_reactor
    def test_stopping_cancels_startup(self):
        service = RegionService()

        # Return an inert Deferred from the listen() call.
        endpoints = self.patch(service, "endpoints", [[Mock()]])
        endpoints[0][0].listen.return_value = Deferred()

        service.startService()
        service.stopService()

        def check(_):
            # The CancelledError is suppressed.
            self.assertThat(service.ports, HasLength(0))

        return service.starting.addCallback(check)

    @wait_for_reactor
    @inlineCallbacks
    def test_stopping_closes_connections_cleanly(self):
        service = RegionService()
        service.starting = Deferred()
        service.factory.protocol = HandshakingRegionServer
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
        service.factory.protocol = HandshakingRegionServer
        connections = {
            service.factory.buildProtocol(None),
            service.factory.buildProtocol(None),
        }
        for conn in connections:
            transport = self.patch(conn, "transport")
            transport.loseConnection.side_effect = OSError("broken")
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
            builtins.OSError: broken
            ---
            Unhandled Error
            Traceback (most recent call last):
            ...
            builtins.OSError: broken
            """,
            logger.dump())

    @wait_for_reactor
    def test_stopping_when_start_up_failed(self):
        service = RegionService()

        # Ensure that endpoint.listen fails with a obvious error.
        exception = ValueError("This is a very naughty boy.")
        endpoints = self.patch(service, "endpoints", [[Mock()]])
        endpoints[0][0].listen.return_value = fail(exception)
        # Suppress logged messages.
        self.patch(globalLogPublisher, "_observers", [])

        service.startService()
        # The test is that stopService() succeeds.
        return service.stopService()

    @wait_for_reactor
    def test_getClientFor_errors_when_no_connections(self):
        service = RegionService()
        service.connections.clear()
        return assert_fails_with(
            service.getClientFor(factory.make_UUID(), timeout=0),
            exceptions.NoConnectionsAvailable)

    @wait_for_reactor
    def test_getClientFor_errors_when_no_connections_for_cluster(self):
        service = RegionService()
        uuid = factory.make_UUID()
        service.connections[uuid].clear()
        return assert_fails_with(
            service.getClientFor(uuid, timeout=0),
            exceptions.NoConnectionsAvailable)

    @wait_for_reactor
    def test_getClientFor_returns_random_connection(self):
        c1 = DummyConnection()
        c2 = DummyConnection()
        chosen = DummyConnection()

        service = RegionService()
        uuid = factory.make_UUID()
        conns_for_uuid = service.connections[uuid]
        conns_for_uuid.update({c1, c2})

        def check_choice(choices):
            self.assertItemsEqual(choices, conns_for_uuid)
            return chosen
        self.patch(random, "choice", check_choice)

        def check(client):
            self.assertThat(client, Equals(common.Client(chosen)))

        return service.getClientFor(uuid).addCallback(check)

    @wait_for_reactor
    def test_getAllClients_empty(self):
        service = RegionService()
        service.connections.clear()
        self.assertThat(service.getAllClients(), Equals([]))

    @wait_for_reactor
    def test_getAllClients(self):
        service = RegionService()
        uuid1 = factory.make_UUID()
        c1 = DummyConnection()
        c2 = DummyConnection()
        service.connections[uuid1].update({c1, c2})
        uuid2 = factory.make_UUID()
        c3 = DummyConnection()
        c4 = DummyConnection()
        service.connections[uuid2].update({c3, c4})
        clients = service.getAllClients()
        self.assertItemsEqual(clients, {
            common.Client(c1), common.Client(c2),
            common.Client(c3), common.Client(c4),
        })

    def test_addConnectionFor_adds_connection(self):
        service = RegionService()
        uuid = factory.make_UUID()
        c1 = DummyConnection()
        c2 = DummyConnection()

        service._addConnectionFor(uuid, c1)
        service._addConnectionFor(uuid, c2)

        self.assertEqual({uuid: {c1, c2}}, service.connections)

    def test_addConnectionFor_notifies_waiters(self):
        service = RegionService()
        uuid = factory.make_UUID()
        c1 = DummyConnection()
        c2 = DummyConnection()

        waiter1 = Mock()
        waiter2 = Mock()
        service.waiters[uuid].add(waiter1)
        service.waiters[uuid].add(waiter2)

        service._addConnectionFor(uuid, c1)
        service._addConnectionFor(uuid, c2)

        self.assertEqual({uuid: {c1, c2}}, service.connections)
        # Both mock waiters are called twice. A real waiter would only be
        # called once because it immediately unregisters itself once called.
        self.assertThat(
            waiter1.callback,
            MockCallsMatch(call(c1), call(c2)))
        self.assertThat(
            waiter2.callback,
            MockCallsMatch(call(c1), call(c2)))

    def test_addConnectionFor_fires_connected_event(self):
        service = RegionService()
        uuid = factory.make_UUID()
        c1 = DummyConnection()

        mock_fire = self.patch(service.events.connected, "fire")
        service._addConnectionFor(uuid, c1)

        self.assertThat(mock_fire, MockCalledOnceWith(uuid))

    def test_removeConnectionFor_removes_connection(self):
        service = RegionService()
        uuid = factory.make_UUID()
        c1 = DummyConnection()
        c2 = DummyConnection()

        service._addConnectionFor(uuid, c1)
        service._addConnectionFor(uuid, c2)
        service._removeConnectionFor(uuid, c1)

        self.assertEqual({uuid: {c2}}, service.connections)

    def test_removeConnectionFor_is_okay_if_connection_is_not_there(self):
        service = RegionService()
        uuid = factory.make_UUID()

        service._removeConnectionFor(uuid, DummyConnection())

        self.assertEqual({uuid: set()}, service.connections)

    def test_removeConnectionFor_fires_disconnected_event(self):
        service = RegionService()
        uuid = factory.make_UUID()
        c1 = DummyConnection()

        mock_fire = self.patch(service.events.disconnected, "fire")
        service._removeConnectionFor(uuid, c1)

        self.assertThat(mock_fire, MockCalledOnceWith(uuid))

    @wait_for_reactor
    def test_getConnectionFor_returns_existing_connection(self):
        service = RegionService()
        uuid = factory.make_UUID()
        conn = DummyConnection()

        service._addConnectionFor(uuid, conn)

        d = service._getConnectionFor(uuid, 1)
        # No waiter is added because a connection is available.
        self.assertEqual({uuid: set()}, service.waiters)

        def check(conn_returned):
            self.assertEquals(conn, conn_returned)

        return d.addCallback(check)

    @wait_for_reactor
    def test_getConnectionFor_waits_for_connection(self):
        service = RegionService()
        uuid = factory.make_UUID()
        conn = DummyConnection()

        # Add the connection later (we're in the reactor thread right
        # now so this won't happen until after we return).
        reactor.callLater(0, service._addConnectionFor, uuid, conn)

        d = service._getConnectionFor(uuid, 1)
        # A waiter is added for the connection we're interested in.
        self.assertEqual({uuid: {d}}, service.waiters)

        def check(conn_returned):
            self.assertEqual(conn, conn_returned)
            # The waiter has been unregistered.
            self.assertEqual({uuid: set()}, service.waiters)

        return d.addCallback(check)

    @wait_for_reactor
    def test_getConnectionFor_with_concurrent_waiters(self):
        service = RegionService()
        uuid = factory.make_UUID()
        conn = DummyConnection()

        # Add the connection later (we're in the reactor thread right
        # now so this won't happen until after we return).
        reactor.callLater(0, service._addConnectionFor, uuid, conn)

        d1 = service._getConnectionFor(uuid, 1)
        d2 = service._getConnectionFor(uuid, 1)
        # A waiter is added for each call to _getConnectionFor().
        self.assertEqual({uuid: {d1, d2}}, service.waiters)

        d = DeferredList((d1, d2))

        def check(results):
            self.assertEqual(
                [(True, conn), (True, conn)], results)
            # The waiters have both been unregistered.
            self.assertEqual({uuid: set()}, service.waiters)

        return d.addCallback(check)

    @wait_for_reactor
    def test_getConnectionFor_cancels_waiter_when_it_times_out(self):
        service = RegionService()
        uuid = factory.make_UUID()

        d = service._getConnectionFor(uuid, 1)
        # A waiter is added for the connection we're interested in.
        self.assertEqual({uuid: {d}}, service.waiters)
        d = assert_fails_with(d, CancelledError)

        def check(_):
            # The waiter has been unregistered.
            self.assertEqual({uuid: set()}, service.waiters)

        return d.addCallback(check)


class TestRegionAdvertisingService(MAASTransactionServerTestCase):

    run_tests_with = MAASCrochetRunTest

    def setUp(self):
        super(TestRegionAdvertisingService, self).setUp()
        self.maas_id = None

        def set_maas_id(maas_id):
            self.maas_id = maas_id

        self.set_maas_id = self.patch(regionservice, "set_maas_id")
        self.set_maas_id.side_effect = set_maas_id

        def get_maas_id():
            return self.maas_id

        self.get_maas_id = self.patch(regionservice, "get_maas_id")
        self.get_maas_id.side_effect = get_maas_id

    def test_init(self):
        ras = RegionAdvertisingService()
        self.assertThat(
            ras.advertiser, MatchesAll(
                IsInstance(LoopingCall),
                MatchesStructure.byEquality(f=ras._tryUpdate, a=(), kw={}),
                first_only=True,
            ))
        self.assertThat(
            ras.advertising, MatchesAll(
                IsInstance(DeferredValue),
                MatchesStructure.byEquality(isSet=False),
                first_only=True,
            ))

    @wait_for_reactor
    @inlineCallbacks
    def test_try_update_logs_all_errors(self):
        ras = RegionAdvertisingService()
        # Prevent periodic calls to `update`.
        ras._startAdvertising = always_succeed_with(None)
        ras._stopAdvertising = always_succeed_with(None)
        # Start the service and make sure it stops later.
        yield ras.startService()
        try:
            # Ensure that calls to `advertising.update` will crash.
            advertising = yield ras.advertising.get(0.0)
            advertising_update = self.patch(advertising, "update")
            advertising_update.side_effect = factory.make_exception()

            with TwistedLoggerFixture() as logger:
                yield ras._tryUpdate()
            self.assertDocTestMatches(
                """
                Failed to update regiond's process and endpoints;
                  %s record's may be out of date
                Traceback (most recent call last):
                ...
                maastesting.factory.TestException#...
                """ % eventloop.loop.name,
                logger.output)
        finally:
            yield ras.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_starting_and_stopping_the_service(self):
        service = RegionAdvertisingService()

        self.assertThat(service.starting, Is(None))
        starting = service.startService()
        try:
            # The service is already marked as running.
            self.assertTrue(service.running)
            # Wait for start-up to fully complete.
            self.assertThat(service.starting, IsInstance(Deferred))
            self.assertThat(service.starting, Is(starting))
            yield service.starting
            # A RegionController has been created.
            region_ids = yield deferToDatabase(lambda: {
                region.system_id for region in RegionController.objects.all()})
            self.assertThat(region_ids, HasLength(1))
            # The maas_id file has been created too.
            region_id = region_ids.pop()
            self.assertThat(self.set_maas_id, MockCalledOnceWith(region_id))
            # Finally, the advertising value has been set.
            advertising = yield service.advertising.get(0.0)
            self.assertThat(
                advertising, MatchesAll(
                    IsInstance(RegionAdvertising),
                    MatchesStructure.byEquality(region_id=region_id),
                    first_only=True,
                ))
        finally:
            self.assertThat(service.stopping, Is(None))
            stopping = service.stopService()
            # The service is already marked as NOT running.
            self.assertFalse(service.running)
            # Wait for shut-down to fully complete.
            self.assertThat(service.stopping, IsInstance(Deferred))
            self.assertThat(service.stopping, Is(stopping))
            yield service.stopping

    @wait_for_reactor
    @inlineCallbacks
    def test_start_up_errors_are_logged(self):
        service = RegionAdvertisingService()
        # Prevent real pauses.
        self.patch_autospec(regionservice, "pause").return_value = None
        # Make service._getAdvertisingInfo fail the first time it's called.
        exceptions = [ValueError("You don't vote for kings!")]
        original = service._getAdvertisingInfo

        def _getAdvertisingInfo():
            if len(exceptions) == 0:
                return original()
            else:
                raise exceptions.pop(0)

        gao = self.patch(service, "_getAdvertisingInfo")
        gao.side_effect = _getAdvertisingInfo
        # Capture all Twisted logs.
        logger = self.useFixture(TwistedLoggerFixture())

        yield service.startService()
        try:
            self.assertDocTestMatches(
                """\
                Promotion of ... failed; will try again in 5 seconds.
                Traceback (most recent call last):...
                builtins.ValueError: You don't vote for kings!
                """,
                logger.dump())
        finally:
            yield service.stopService()

    def test_stopping_waits_for_startup(self):
        service = RegionAdvertisingService()
        synchronise = threading.Condition()

        # Prevent the advertising loop from starting.
        service._startAdvertising = lambda: None
        service._stopAdvertising = lambda: None

        # Prevent the service's _getAdvertisingInfo method - which is deferred
        # to a thread - from completing while we hold the lock.
        def _getAdvertisingInfo(original=service._getAdvertisingInfo):
            with synchronise:
                synchronise.notify()
                synchronise.wait(2.0)
            return original()
        service._getAdvertisingInfo = _getAdvertisingInfo

        with synchronise:
            # Start the service, but stop it again before promote is able to
            # complete.
            service.startService()
            synchronise.wait(2.0)
            service.stopService()
            synchronise.notify()

        callInReactorWithTimeout(5.0, lambda: service.starting)
        callInReactorWithTimeout(5.0, lambda: service.stopping)
        self.assertFalse(service.running)

    def test_stopping_when_start_up_failed(self):
        service = RegionAdvertisingService()

        # Ensure that service.promote fails with a obvious error.
        exception = ValueError("First, shalt thou take out the holy pin.")
        self.patch(service, "promote").side_effect = exception

        # Start the service, but don't wait.
        service.startService()
        # The test is that stopService() succeeds.
        service.stopService().wait(10)

    def patch_port(self, port):
        getServiceNamed = self.patch(eventloop.services, "getServiceNamed")
        getPort = getServiceNamed.return_value.getPort
        getPort.return_value = port

    def patch_addresses(self, addresses):
        get_all_interface_addresses = self.patch(
            regionservice, "get_all_interface_addresses")
        get_all_interface_addresses.return_value = addresses

    @wait_for_reactor
    @inlineCallbacks
    def test_stopping_demotes_region(self):
        service = RegionAdvertisingService()
        service._getAddresses = always_succeed_with({("192.168.0.1", 9876)})

        yield service.startService()
        yield service.stopService()

        dump = yield deferToDatabase(RegionAdvertising.dump)
        self.assertItemsEqual([], dump)

    def test__getAddresses_excluding_loopback(self):
        service = RegionAdvertisingService()

        example_port = factory.pick_port()
        self.patch_port(example_port)

        example_ipv4_addrs = set()
        for _ in range(5):
            ip = factory.make_ipv4_address()
            if not netaddr.IPAddress(ip).is_loopback():
                example_ipv4_addrs.add(ip)
        example_ipv6_addrs = set()
        for _ in range(5):
            ip = factory.make_ipv6_address()
            if not netaddr.IPAddress(ip).is_loopback():
                example_ipv6_addrs.add(ip)
        example_link_local_addrs = {
            factory.pick_ip_in_network(netaddr.ip.IPV4_LINK_LOCAL),
            factory.pick_ip_in_network(netaddr.ip.IPV6_LINK_LOCAL),
        }
        example_loopback_addrs = {
            factory.pick_ip_in_network(netaddr.ip.IPV4_LOOPBACK),
            str(netaddr.ip.IPV6_LOOPBACK),
        }
        self.patch_addresses(
            example_ipv4_addrs | example_ipv6_addrs |
            example_link_local_addrs | example_loopback_addrs)

        # IPv6 addresses, link-local addresses and loopback are excluded, and
        # thus not advertised.
        self.assertItemsEqual(
            [(addr, example_port) for addr in example_ipv4_addrs],
            service._getAddresses().wait(2.0))

        self.assertThat(
            eventloop.services.getServiceNamed,
            MockCalledOnceWith("rpc"))
        self.assertThat(
            regionservice.get_all_interface_addresses,
            MockCalledOnceWith())

    def test__getAddresses_including_loopback(self):
        service = RegionAdvertisingService()

        example_port = factory.pick_port()
        self.patch_port(example_port)

        example_link_local_addrs = {
            factory.pick_ip_in_network(netaddr.ip.IPV4_LINK_LOCAL),
            factory.pick_ip_in_network(netaddr.ip.IPV6_LINK_LOCAL),
        }
        ipv4_loopback = factory.pick_ip_in_network(netaddr.ip.IPV4_LOOPBACK)
        example_loopback_addrs = {
            ipv4_loopback,
            str(netaddr.ip.IPV6_LOOPBACK),
        }
        self.patch_addresses(
            example_link_local_addrs | example_loopback_addrs)

        # Only IPv4 loopback is exposed.
        self.assertItemsEqual(
            [(ipv4_loopback, example_port)],
            service._getAddresses().wait(2.0))

        self.assertThat(
            eventloop.services.getServiceNamed,
            MockCalledOnceWith("rpc"))
        self.assertThat(
            regionservice.get_all_interface_addresses,
            MockCalledOnceWith())

    def test__getAddresses_when_rpc_down(self):
        service = RegionAdvertisingService()

        # getPort() returns None when the RPC service is not running or
        # not able to bind a port.
        self.patch_port(None)

        get_all_interface_addresses = self.patch(
            regionservice, "get_all_interface_addresses")
        get_all_interface_addresses.return_value = [
            factory.make_ipv4_address(),
            factory.make_ipv4_address(),
        ]

        # If the RPC service is down, _getAddresses() returns nothing.
        self.assertItemsEqual([], service._getAddresses().wait(2.0))


class TestRegionAdvertising(MAASServerTestCase):

    hostname = gethostname()

    def promote(self, region_id=None, hostname=hostname, mac_addresses=None):
        """Convenient wrapper around `RegionAdvertising.promote`."""
        return RegionAdvertising.promote(
            factory.make_name("region-id") if region_id is None else region_id,
            hostname, [] if mac_addresses is None else mac_addresses)

    def make_addresses(self):
        """Return a set of a couple of ``(addr, port)`` tuples."""
        return {
            (factory.make_ipv4_address(), factory.pick_port()),
            (factory.make_ipv4_address(), factory.pick_port()),
        }

    def get_endpoints(self, region_id):
        """Return a set of ``(addr, port)`` tuples for the given region."""
        region = RegionController.objects.get(system_id=region_id)
        return {
            (endpoint.address, endpoint.port)
            for process in region.processes.all()
            for endpoint in process.endpoints.all()
        }

    def test_promote_new_region(self):
        # Before promotion there are no RegionControllers.
        self.assertEquals(
            0, RegionController.objects.count(),
            "No RegionControllers should exist.")

        advertising = self.promote()

        # Now a RegionController exists for the given hostname.
        region = RegionController.objects.get(hostname=gethostname())
        self.assertThat(advertising.region_id, Equals(region.system_id))

    def test_promote_converts_from_node(self):
        node = factory.make_Node(interface=True)
        interfaces = [
            factory.make_Interface(node=node),
            factory.make_Interface(node=node),
        ]
        mac_addresses = [
            str(interface.mac_address)
            for interface in interfaces
        ]

        self.promote(node.system_id, self.hostname, mac_addresses)

        # Node should have been converted to a RegionController.
        node = reload_object(node)
        self.assertEquals(NODE_TYPE.REGION_CONTROLLER, node.node_type)
        # The hostname has also been set.
        self.assertEquals(self.hostname, node.hostname)

    def test_promote_converts_from_rack(self):
        node = factory.make_Node(
            interface=True, node_type=NODE_TYPE.RACK_CONTROLLER)
        interface = node.get_boot_interface()
        mac_address = str(interface.mac_address)

        self.promote(node.system_id, self.hostname, [mac_address])

        # Node should have been converted to a RegionRackController.
        node = reload_object(node)
        self.assertEquals(NODE_TYPE.REGION_AND_RACK_CONTROLLER, node.node_type)
        # The hostname has also been set.
        self.assertEquals(self.hostname, node.hostname)

    def test_promote_sets_region_hostname(self):
        node = factory.make_Node(node_type=NODE_TYPE.REGION_CONTROLLER)

        self.promote(node.system_id, self.hostname)

        # The hostname has been set.
        self.assertEquals(self.hostname, reload_object(node).hostname)

    def test_promote_holds_startup_lock(self):
        # Creating tables in PostgreSQL is a transactional operation like any
        # other. If the isolation level is not sufficient it is susceptible to
        # races. Using a higher isolation level may lead to serialisation
        # failures, for example. However, PostgreSQL provides advisory locking
        # functions, and that's what RegionAdvertising.promote takes advantage
        # of to prevent concurrent creation of the region controllers.

        # A record of the lock's status, populated when a custom
        # patched-in _do_create() is called.
        locked = []

        # Capture the state of `locks.eventloop` while `promote` is running.
        original_fix_node_for_region = regionservice.fix_node_for_region

        def fix_node_for_region(*args, **kwargs):
            locked.append(locks.eventloop.is_locked())
            return original_fix_node_for_region(*args, **kwargs)

        fnfr = self.patch(regionservice, "fix_node_for_region")
        fnfr.side_effect = fix_node_for_region

        # `fix_node_for_region` is only called for preexisting nodes.
        node = factory.make_Node(node_type=NODE_TYPE.REGION_CONTROLLER)

        # The lock is not held before and after `promote` is called.
        self.assertFalse(locks.eventloop.is_locked())
        self.promote(node.system_id)
        self.assertFalse(locks.eventloop.is_locked())

        # The lock was held when `fix_node_for_region` was called.
        self.assertEqual([True], locked)

    def test_update_updates_region_hostname(self):
        advertising = self.promote()

        region = RegionController.objects.get(system_id=advertising.region_id)
        region.hostname = factory.make_name("host")
        region.save()

        advertising.update(self.make_addresses())

        # RegionController should have hostname updated.
        region = reload_object(region)
        self.assertEquals(self.hostname, region.hostname)

    def test_update_creates_process_when_removed(self):
        advertising = self.promote()

        region = RegionController.objects.get(system_id=advertising.region_id)
        [process] = region.processes.all()
        process_id = process.id
        process.delete()

        # Will re-create the process with the same ID.
        advertising.update(self.make_addresses())

        process.id = process_id
        process = reload_object(process)
        self.assertEquals(process.pid, os.getpid())

    def test_update_removes_old_processes(self):
        advertising = self.promote()

        old_time = now() - timedelta(seconds=90)
        region = RegionController.objects.get(system_id=advertising.region_id)
        other_region = factory.make_Node(node_type=NODE_TYPE.REGION_CONTROLLER)
        old_region_process = RegionControllerProcess.objects.create(
            region=region, pid=randint(1, 1000), created=old_time,
            updated=old_time)
        old_other_region_process = RegionControllerProcess.objects.create(
            region=other_region, pid=randint(1000, 2000), created=old_time,
            updated=old_time)

        advertising.update(self.make_addresses())

        self.assertIsNone(reload_object(old_region_process))
        self.assertIsNone(reload_object(old_other_region_process))

    def test_update_updates_updated_time_on_region_and_process(self):
        current_time = now()
        self.patch(timestampedmodel, "now").return_value = current_time

        advertising = self.promote()

        old_time = current_time - timedelta(seconds=90)
        region = RegionController.objects.get(system_id=advertising.region_id)
        region.created = old_time
        region.updated = old_time
        region.save()
        region_process = RegionControllerProcess.objects.get(
            id=advertising.process_id)
        region_process.created = region_process.updated = old_time
        region_process.save()

        advertising.update(self.make_addresses())

        region = reload_object(region)
        region_process = reload_object(region_process)
        self.assertEquals(current_time, region.updated)
        self.assertEquals(current_time, region_process.updated)

    def test_update_creates_endpoints_on_process(self):
        addresses = self.make_addresses()

        advertising = self.promote()
        advertising.update(addresses)

        saved_endpoints = self.get_endpoints(advertising.region_id)
        self.assertEqual(addresses, saved_endpoints)

    def test_update_does_not_insert_endpoints_when_nothings_listening(self):
        advertising = self.promote()
        advertising.update(set())  # No addresses.

        saved_endpoints = self.get_endpoints(advertising.region_id)
        self.assertEqual(set(), saved_endpoints)

    def test_update_deletes_old_endpoints(self):
        addresses_common = self.make_addresses()
        addresses_one = self.make_addresses().union(addresses_common)
        addresses_two = self.make_addresses().union(addresses_common)

        advertising = self.promote()

        advertising.update(addresses_one)
        self.assertEqual(
            addresses_one, self.get_endpoints(advertising.region_id))

        advertising.update(addresses_two)
        self.assertEqual(
            addresses_two, self.get_endpoints(advertising.region_id))

    def test_update_sets_regiond_degraded_with_less_than_4_processes(self):
        advertising = self.promote()
        advertising.update(self.make_addresses())

        region = RegionController.objects.get(system_id=advertising.region_id)
        [process] = region.processes.all()
        regiond_service = ServiceModel.objects.get(node=region, name="regiond")
        self.assertThat(regiond_service, MatchesStructure.byEquality(
            status=SERVICE_STATUS.DEGRADED,
            status_info="1 process running but 4 were expected."))

    def test_update_sets_regiond_running_with_4_processes(self):
        advertising = self.promote()

        region = RegionController.objects.get(system_id=advertising.region_id)
        [process] = region.processes.all()

        # Make 3 more processes.
        for _ in range(3):
            factory.make_RegionControllerProcess(region=region)

        advertising.update(self.make_addresses())

        regiond_service = ServiceModel.objects.get(node=region, name="regiond")
        self.assertThat(regiond_service, MatchesStructure.byEquality(
            status=SERVICE_STATUS.RUNNING, status_info=""))

    def test_update_calls_mark_dead_on_regions_without_processes(self):
        advertising = self.promote()

        other_region = factory.make_RegionController()
        mock_mark_dead = self.patch(ServiceModel.objects, "mark_dead")

        advertising.update(self.make_addresses())

        self.assertThat(
            mock_mark_dead,
            MockCalledOnceWith(other_region, dead_region=True))

    def test_demote(self):
        region_id = factory.make_name("region-id")
        hostname = gethostname()
        addresses = {
            (factory.make_ipv4_address(), factory.pick_port()),
            (factory.make_ipv4_address(), factory.pick_port()),
        }
        advertising = RegionAdvertising.promote(region_id, hostname, [])
        advertising.update(addresses)
        advertising.demote()
        self.assertItemsEqual([], advertising.dump())

    def test_dump(self):
        region_id = factory.make_name("region-id")
        hostname = gethostname()
        addresses = {
            (factory.make_ipv4_address(), factory.pick_port()),
            (factory.make_ipv4_address(), factory.pick_port()),
        }
        advertising = RegionAdvertising.promote(region_id, hostname, [])
        advertising.update(addresses)

        expected = [
            ("%s:pid=%d" % (hostname, os.getpid()), addr, port)
            for (addr, port) in addresses
        ]
        self.assertItemsEqual(expected, advertising.dump())


class TestRegionProtocol_ReportForeignDHCPServer(
        MAASTransactionServerTestCase):

    def test_is_registered(self):
        protocol = Region()
        responder = protocol.locateResponder(
            ReportForeignDHCPServer.commandName)
        self.assertIsNotNone(responder)

    @transactional
    def create_rack_interface(self):
        rack_controller = factory.make_RackController(interface=False)
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=rack_controller)
        return rack_controller, interface

    @transactional
    def get_vlan_for_interface(self, interface):
        return reload_object(interface.vlan)

    @wait_for_reactor
    @inlineCallbacks
    def test_sets_external_dhcp_value(self):
        dhcp_ip = factory.make_ipv4_address()
        rack, interface = yield deferToDatabase(
            self.create_rack_interface)

        response = yield call_responder(
            Region(), ReportForeignDHCPServer,
            {
                'system_id': rack.system_id,
                'interface_name': interface.name,
                'dhcp_ip': dhcp_ip,
            })

        self.assertEqual({}, response)
        vlan = yield deferToDatabase(
            self.get_vlan_for_interface, interface)
        self.assertEqual(
            dhcp_ip, vlan.external_dhcp)


class TestRegionProtocol_CreateNode(MAASTransactionServerTestCase):

    def test_create_node_is_registered(self):
        protocol = Region()
        responder = protocol.locateResponder(
            CreateNode.commandName)
        self.assertIsNotNone(responder)

    @transactional
    def create_node(self):
        return factory.make_Node()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_create_node_function(self):
        create_node_function = self.patch(regionservice, 'create_node')
        create_node_function.return_value = yield deferToDatabase(
            self.create_node)

        params = {
            'architecture': make_usable_architecture(self),
            'power_type': factory.make_name('power_type'),
            'power_parameters': dumps({}),
            'mac_addresses': [factory.make_mac_address()],
            'domain': factory.make_name('domain'),
            'hostname': None,
        }

        response = yield call_responder(
            Region(), CreateNode, params)
        self.assertIsNotNone(response)

        self.assertThat(
            create_node_function,
            MockCalledOnceWith(
                params['architecture'], params['power_type'],
                params['power_parameters'], params['mac_addresses'],
                domain=params['domain'],
                hostname=params['hostname']))
        self.assertEqual(
            create_node_function.return_value.system_id,
            response['system_id'])


class TestRegionProtocol_CommissionNode(MAASTransactionServerTestCase):

    def test_commission_node_is_registered(self):
        protocol = Region()
        responder = protocol.locateResponder(
            CommissionNode.commandName)
        self.assertIsNotNone(responder)

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_commission_node_function(self):
        commission_node_function = self.patch(regionservice, 'commission_node')

        params = {
            'system_id': factory.make_name('system_id'),
            'user': factory.make_name('user'),
        }

        response = yield call_responder(
            Region(), CommissionNode, params)
        self.assertIsNotNone(response)

        self.assertThat(
            commission_node_function,
            MockCalledOnceWith(
                params['system_id'], params['user']))


class TestRegionProtocol_UpdateInterfaces(MAASTransactionServerTestCase):

    def test_update_interfaces_is_registered(self):
        protocol = Region()
        responder = protocol.locateResponder(
            UpdateInterfaces.commandName)
        self.assertIsNotNone(responder)

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_update_interfaces_function(self):
        update_interfaces = self.patch(
            regionservice.rackcontrollers, 'update_interfaces')

        params = {
            'system_id': factory.make_name('system_id'),
            'interfaces': {
                'eth0': {
                    'type': 'physical',
                },
            }
        }

        response = yield call_responder(
            Region(), UpdateInterfaces, params)
        self.assertIsNotNone(response)

        self.assertThat(
            update_interfaces,
            MockCalledOnceWith(
                params['system_id'], params['interfaces']))


class TestRegionProtocol_RequestNodeInforByMACAddress(
        MAASTransactionServerTestCase):

    def test_request_node_info_by_mac_address_is_registered(self):
        protocol = Region()
        responder = protocol.locateResponder(
            RequestNodeInfoByMACAddress.commandName)
        self.assertIsNotNone(responder)

    @transactional
    def make_interface(self, node):
        return factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)

    @transactional
    def create_node(self):
        return factory.make_Node()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_request_node_info_by_mac_address_function(self):
        purpose = factory.make_name('purpose')
        node = yield deferToDatabase(self.create_node)
        node_info_function = self.patch(
            regionservice, 'request_node_info_by_mac_address')
        node_info_function.return_value = (node, purpose)
        interface = yield deferToDatabase(self.make_interface, node)

        params = {
            'mac_address': interface.mac_address.get_raw(),
        }

        response = yield call_responder(
            Region(), RequestNodeInfoByMACAddress, params)
        self.assertIsNotNone(response)
        self.assertThat(
            node_info_function,
            MockCalledOnceWith(params['mac_address']))
        response_purpose = response.pop('purpose')
        self.assertEqual(purpose, response_purpose)
        # Remove the boot_type from the response as node no longer has that
        # attribute.
        copy_response = dict(response)
        del copy_response["boot_type"]
        self.assertAttributes(node, copy_response)
        self.assertEquals("fastpath", response["boot_type"])

    @wait_for_reactor
    def test_request_node_info_by_mac_address_raises_if_unknown_mac(self):
        params = {'mac_address': factory.make_mac_address()}
        d = call_responder(Region(), RequestNodeInfoByMACAddress, params)
        return assert_fails_with(d, NoSuchNode)
