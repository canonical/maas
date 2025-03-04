# Copyright 2016-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


from datetime import timedelta
from hashlib import sha256
from hmac import HMAC
from json import dumps
import random
from random import randint

from django.utils import timezone
from twisted.internet.defer import inlineCallbacks, succeed
from twisted.python.failure import Failure

from maasserver import eventloop
from maasserver.dns.config import get_trusted_networks
from maasserver.enum import INTERFACE_TYPE, NODE_STATUS
from maasserver.models import Config, Event, EventType, Node
from maasserver.models import node as node_module
from maasserver.models.interface import PhysicalInterface
from maasserver.models.signals.testing import SignalsDisabled
from maasserver.rpc import events as events_module
from maasserver.rpc import regionservice
from maasserver.rpc.nodes import get_controller_type, get_time_configuration
from maasserver.rpc.regionservice import Region
from maasserver.rpc.services import update_services
from maasserver.security import get_shared_secret
from maasserver.testing.architecture import make_usable_architecture
from maasserver.testing.eventloop import RegionEventLoopFixture
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASTransactionServerTestCase
from maasserver.utils.orm import reload_object, transactional
from maasserver.utils.threads import deferToDatabase
from maastesting.crochet import wait_for
from maastesting.testcase import MAASTestCase
from maastesting.twisted import TwistedLoggerFixture
from provisioningserver.enum import POWER_STATE
from provisioningserver.rpc.exceptions import NoSuchCluster, NoSuchNode
from provisioningserver.rpc.region import (
    Authenticate,
    CommissionNode,
    CreateNode,
    GetBootConfig,
    GetControllerType,
    GetDNSConfiguration,
    GetProxyConfiguration,
    GetSyslogConfiguration,
    GetTimeConfiguration,
    Identify,
    ListNodePowerParameters,
    MarkNodeFailed,
    RegisterEventType,
    ReportForeignDHCPServer,
    ReportNeighbours,
    RequestNodeInfoByMACAddress,
    RequestRackRefresh,
    SendEvent,
    SendEventMACAddress,
    UpdateNodePowerState,
    UpdateServices,
)
from provisioningserver.rpc.testing import call_responder

wait_for_reactor = wait_for()


@transactional
def transactional_reload_object(obj):
    return reload_object(obj)


class TestRegionProtocol(MAASTestCase):
    def test_unauthenticated_allowed_commands(self):
        protocol = Region()
        self.assertEqual(
            [Authenticate.commandName], protocol.unauthenticated_commands
        )

    def test_default_auth_status(self):
        protocol = Region()
        self.assertEqual(False, protocol.auth_status.is_authenticated)


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


class TestRegionProtocol_Authenticate(MAASTransactionServerTestCase):
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
        self.assertEqual(len(salt), 16)


class TestRegionProtocol_GetBootConfig(MAASTransactionServerTestCase):
    def test_get_boot_config_is_registered(self):
        protocol = Region()
        responder = protocol.locateResponder(GetBootConfig.commandName)
        self.assertIsNotNone(responder)

    @wait_for_reactor
    @inlineCallbacks
    def test_get_boot_config_returns_expected_result(self):
        rack_controller = yield deferToDatabase(
            transactional(factory.make_RackController)
        )
        yield deferToDatabase(factory.make_RegionController)
        yield deferToDatabase(make_usable_architecture, self)
        local_ip = factory.make_ip_address()
        remote_ip = factory.make_ip_address()

        response = yield call_responder(
            Region(),
            GetBootConfig,
            {
                "system_id": rack_controller.system_id,
                "local_ip": local_ip,
                "remote_ip": remote_ip,
            },
        )

        self.assertGreater(
            response.keys(),
            {
                "arch",
                "subarch",
                "osystem",
                "release",
                "kernel_osystem",
                "kernel_release",
                "kernel",
                "initrd",
                "boot_dtb",
                "purpose",
                "hostname",
                "domain",
                "preseed_url",
                "fs_host",
                "log_host",
                "extra_opts",
                "ephemeral_opts",
            },
        )


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
        self.useFixture(SignalsDisabled("power"))
        self.patch(node_module, "stop_workflow")
        system_id = yield deferToDatabase(self.create_deploying_node)

        error_description = factory.make_name("error-description")
        response = yield call_responder(
            Region(),
            MarkNodeFailed,
            {"system_id": system_id, "error_description": error_description},
        )

        self.assertEqual({}, response)
        new_status = yield deferToDatabase(self.get_node_status, system_id)
        new_error_description = yield deferToDatabase(
            self.get_node_error_description, system_id
        )
        self.assertEqual(
            (NODE_STATUS.FAILED_DEPLOYMENT, error_description),
            (new_status, new_error_description),
        )

    @wait_for_reactor
    def test_mark_node_failed_errors_if_node_cannot_be_found(self):
        system_id = factory.make_name("unknown-system-id")
        error_description = factory.make_name("error-description")

        d = call_responder(
            Region(),
            MarkNodeFailed,
            {"system_id": system_id, "error_description": error_description},
        )

        def check(error):
            self.assertIsInstance(error, Failure)
            self.assertIsInstance(error.value, NoSuchNode)
            # The error message contains a reference to system_id.
            self.assertIn(system_id, str(error.value))

        return d.addErrback(check)


class TestRegionProtocol_ListNodePowerParameters(
    MAASTransactionServerTestCase
):
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

    def test_is_registered(self):
        protocol = Region()
        responder = protocol.locateResponder(
            ListNodePowerParameters.commandName
        )
        self.assertIsNotNone(responder)

    @wait_for_reactor
    @inlineCallbacks
    def test_returns_correct_arguments(self):
        rack = yield deferToDatabase(self.create_rack_controller)

        nodes = []
        for _ in range(3):
            node = yield deferToDatabase(
                self.create_node,
                power_type="virsh",
                power_state_updated=None,
                bmc_connected_to=rack,
            )
            power_params = yield deferToDatabase(
                self.get_node_power_parameters, node
            )
            nodes.append(
                {
                    "system_id": node.system_id,
                    "hostname": node.hostname,
                    "power_state": node.power_state,
                    "power_type": node.get_effective_power_type(),
                    "context": power_params,
                }
            )

        # Create a node with an invalid power type.
        # This will not be reported by the call to ListNodePowerParameters.
        yield deferToDatabase(
            self.create_node, power_type="invalid", power_state_updated=None
        )

        response = yield call_responder(
            Region(), ListNodePowerParameters, {"uuid": rack.system_id}
        )

        self.maxDiff = None
        self.assertCountEqual(nodes, response["nodes"])

    @wait_for_reactor
    @inlineCallbacks
    def test_raises_exception_if_nodegroup_doesnt_exist(self):
        uuid = factory.make_UUID()

        d = call_responder(Region(), ListNodePowerParameters, {"uuid": uuid})

        with self.assertRaisesRegex(
            NoSuchCluster,
            rf"The rack controller with UUID {uuid} could not be found\.",
        ):
            yield d


class TestRegionProtocol_UpdateNodePowerState(MAASTransactionServerTestCase):
    @transactional
    def create_node(self, power_state):
        node = factory.make_Node(power_state=power_state)
        return node

    @transactional
    def get_node_power_state(self, system_id):
        node = Node.objects.get(system_id=system_id)
        return node.power_state

    def test_is_registered(self):
        protocol = Region()
        responder = protocol.locateResponder(UpdateNodePowerState.commandName)
        self.assertIsNotNone(responder)

    @wait_for_reactor
    @inlineCallbacks
    def test_changes_power_state(self):
        power_state = factory.pick_enum(POWER_STATE)
        node = yield deferToDatabase(self.create_node, power_state)

        new_state = factory.pick_enum(POWER_STATE, but_not=[power_state])
        yield call_responder(
            Region(),
            UpdateNodePowerState,
            {"system_id": node.system_id, "power_state": new_state},
        )

        db_state = yield deferToDatabase(
            self.get_node_power_state, node.system_id
        )
        self.assertEqual(new_state, db_state)

    @wait_for_reactor
    def test_errors_if_node_cannot_be_found(self):
        system_id = factory.make_name("unknown-system-id")
        power_state = factory.pick_enum(POWER_STATE)

        d = call_responder(
            Region(),
            UpdateNodePowerState,
            {"system_id": system_id, "power_state": power_state},
        )

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
        name = factory.make_name("name")
        description = factory.make_name("description")
        level = random.randint(0, 100)
        response = yield call_responder(
            Region(),
            RegisterEventType,
            {"name": name, "description": description, "level": level},
        )

        self.assertEqual({}, response)
        event_type = yield deferToDatabase(self.get_event_type, name)
        self.assertEqual(event_type.name, name)
        self.assertEqual(event_type.description, description)
        self.assertEqual(event_type.level, level)

    @wait_for_reactor
    @inlineCallbacks
    def test_register_event_type_does_not_error_for_existing_event_types(self):
        # This is a regression test for bug 1373357.
        name = factory.make_name("name")
        old_description = factory.make_name("old-description")
        level = random.randint(0, 100)
        response = yield call_responder(
            Region(),
            RegisterEventType,
            {"name": name, "description": old_description, "level": level},
        )
        self.assertEqual({}, response)

        new_description = factory.make_name("new-description")
        response = yield call_responder(
            Region(),
            RegisterEventType,
            {"name": name, "description": new_description, "level": level},
        )
        # If we get this far, no error has been raised, even though we
        # sent a duplicate request for registration.
        self.assertEqual({}, response)


class TestRegionProtocol_SendEvent(MAASTransactionServerTestCase):
    def setUp(self):
        super().setUp()
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
        all_events_qs = Event.objects.all().select_related("node", "type")
        event = all_events_qs.get(
            node__system_id=system_id, type__name=type_name
        )
        return event

    @transactional
    def create_event_type(self, name, description, level):
        EventType.objects.create(
            name=name, description=description, level=level
        )

    @transactional
    def create_node(self):
        return factory.make_Node().system_id

    @wait_for_reactor
    @inlineCallbacks
    def test_send_event_stores_event(self):
        name = factory.make_name("type_name")
        description = factory.make_name("description")
        level = random.randint(0, 100)
        yield deferToDatabase(self.create_event_type, name, description, level)
        system_id = yield deferToDatabase(self.create_node)

        event_description = factory.make_name("description")

        yield eventloop.start()
        try:
            response = yield call_responder(
                Region(),
                SendEvent,
                {
                    "system_id": system_id,
                    "type_name": name,
                    "description": event_description,
                },
            )
        finally:
            yield eventloop.reset()

        self.assertEqual({}, response)
        event = yield deferToDatabase(self.get_event, system_id, name)
        self.assertEqual(event.node.system_id, system_id)
        self.assertEqual(event.description, event_description)
        self.assertEqual(event.type.name, name)

    @wait_for_reactor
    @inlineCallbacks
    def test_send_event_stores_event_with_timestamp_received(self):
        # Use a random time in the recent past and coerce the responder to use
        # it as the time-stamp for the event. We'll check this later on.
        timestamp = timezone.now() - timedelta(seconds=randint(99, 99999))
        self.patch(regionservice, "timezone").now.return_value = timestamp

        event_type = factory.make_name("type_name")
        yield deferToDatabase(self.create_event_type, event_type, "", 0)
        system_id = yield deferToDatabase(self.create_node)

        yield eventloop.start()
        try:
            yield call_responder(
                Region(),
                SendEvent,
                {
                    "system_id": system_id,
                    "type_name": event_type,
                    "description": factory.make_name("description"),
                },
            )
        finally:
            yield eventloop.reset()

        event = yield deferToDatabase(self.get_event, system_id, event_type)
        self.assertEqual(event.created, timestamp)

    @wait_for_reactor
    @inlineCallbacks
    def test_send_event_does_not_fail_if_unknown_type(self):
        name = factory.make_name("type_name")
        system_id = factory.make_name("system_id")
        description = factory.make_name("description")

        logger = self.useFixture(TwistedLoggerFixture())

        yield eventloop.start()
        try:
            yield call_responder(
                Region(),
                SendEvent,
                {
                    "system_id": system_id,
                    "type_name": name,
                    "description": description,
                },
            )
        finally:
            yield eventloop.reset()

        # The log records the issue. FIXME: Why reject logs if the type is not
        # registered? Seems like the region should record all logs and figure
        # out how to present them.
        self.assertRegex(
            logger.output,
            (
                r"(?ms)Unhandled failure in database task\..*"
                r"Traceback \(most recent call last\):.*"
                "provisioningserver.rpc.exceptions.NoSuchEventType:"
            ),
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_send_event_logs_if_unknown_node(self):
        log = self.patch(events_module, "log")
        name = factory.make_name("type_name")
        description = factory.make_name("description")
        level = random.randint(0, 100)
        yield deferToDatabase(self.create_event_type, name, description, level)

        system_id = factory.make_name("system_id")
        event_description = factory.make_name("event-description")

        yield eventloop.start()
        try:
            yield call_responder(
                Region(),
                SendEvent,
                {
                    "system_id": system_id,
                    "type_name": name,
                    "description": event_description,
                },
            )
        finally:
            yield eventloop.reset()

        log.debug.assert_called_once_with(
            "Event '{type}: {description}' sent for "
            "non-existent node '{node_id}'.",
            type=name,
            description=event_description,
            node_id=system_id,
        )


class TestRegionProtocol_SendEventMACAddress(MAASTransactionServerTestCase):
    def setUp(self):
        super().setUp()
        self.useFixture(RegionEventLoopFixture("database-tasks"))

    def test_send_event_mac_address_is_registered(self):
        protocol = Region()
        responder = protocol.locateResponder(SendEventMACAddress.commandName)
        self.assertIsNotNone(responder)

    @transactional
    def get_event(self, mac_address, type_name):
        # Pre-fetch the related 'node' and 'type' because the caller
        # runs in the event-loop and this can't dereference related
        # objects (unless they have been prefetched).
        all_events_qs = Event.objects.all().select_related("node", "type")
        node = PhysicalInterface.objects.get(
            mac_address=mac_address
        ).node_config.node
        event = all_events_qs.get(node=node, type__name=type_name)
        return event

    @transactional
    def create_event_type(self, name, description, level):
        EventType.objects.create(
            name=name, description=description, level=level
        )

    @transactional
    def make_interface(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        # Precache the node. So a database query is not made in the event-loop.
        interface.node_config.node  # noqa: B018
        return interface

    @wait_for_reactor
    @inlineCallbacks
    def test_send_event_mac_address_stores_event(self):
        name = factory.make_name("type_name")
        description = factory.make_name("description")
        level = random.randint(0, 100)
        yield deferToDatabase(self.create_event_type, name, description, level)
        interface = yield deferToDatabase(self.make_interface)
        mac_address = interface.mac_address
        event_description = factory.make_name("description")

        yield eventloop.start()
        try:
            response = yield call_responder(
                Region(),
                SendEventMACAddress,
                {
                    "mac_address": mac_address,
                    "type_name": name,
                    "description": event_description,
                },
            )
        finally:
            yield eventloop.reset()

        self.assertEqual({}, response)
        event = yield deferToDatabase(self.get_event, mac_address, name)
        self.assertEqual(
            event.node.system_id, interface.node_config.node.system_id
        )
        self.assertEqual(event.description, event_description)
        self.assertEqual(event.type.name, name)

    @wait_for_reactor
    @inlineCallbacks
    def test_send_event_mac_address_stores_event_with_timestamp_received(self):
        # Use a random time in the recent past and coerce the responder to use
        # it as the time-stamp for the event. We'll check this later on.
        timestamp = timezone.now() - timedelta(seconds=randint(99, 99999))
        self.patch(regionservice, "timezone").now.return_value = timestamp

        event_type = factory.make_name("type_name")
        yield deferToDatabase(self.create_event_type, event_type, "", 0)
        interface = yield deferToDatabase(self.make_interface)
        mac_address = interface.mac_address

        yield eventloop.start()
        try:
            yield call_responder(
                Region(),
                SendEventMACAddress,
                {
                    "mac_address": mac_address,
                    "type_name": event_type,
                    "description": factory.make_name("description"),
                },
            )
        finally:
            yield eventloop.reset()

        event = yield deferToDatabase(self.get_event, mac_address, event_type)
        self.assertEqual(event.created, timestamp)

    @wait_for_reactor
    @inlineCallbacks
    def test_send_event_mac_address_does_not_fail_if_unknown_type(self):
        name = factory.make_name("type_name")
        mac_address = factory.make_mac_address()
        description = factory.make_name("description")

        logger = self.useFixture(TwistedLoggerFixture())

        yield eventloop.start()
        try:
            yield call_responder(
                Region(),
                SendEventMACAddress,
                {
                    "mac_address": mac_address,
                    "type_name": name,
                    "description": description,
                },
            )
        finally:
            yield eventloop.reset()

        # The log records the issue. FIXME: Why reject logs if the type is not
        # registered? Seems like the region should record all logs and figure
        # out how to present them.
        self.assertRegex(
            logger.output,
            (
                r"(?ms)Unhandled failure in database task\..*"
                r"Traceback \(most recent call last\):.*"
                "provisioningserver.rpc.exceptions.NoSuchEventType:"
            ),
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_send_event_mac_address_logs_if_unknown_node(self):
        log = self.patch(events_module, "log")
        name = factory.make_name("type_name")
        description = factory.make_name("description")
        level = random.randint(0, 100)
        yield deferToDatabase(self.create_event_type, name, description, level)
        mac_address = factory.make_mac_address()
        event_description = factory.make_name("event-description")

        yield eventloop.start()
        try:
            yield call_responder(
                Region(),
                SendEventMACAddress,
                {
                    "mac_address": mac_address,
                    "type_name": name,
                    "description": event_description,
                },
            )
        finally:
            yield eventloop.reset()

        log.debug.assert_called_once_with(
            "Event '{type}: {description}' sent for non-existent node "
            "with MAC address '{mac}'.",
            type=name,
            description=event_description,
            mac=mac_address,
        )


class TestRegionProtocol_UpdateServices(MAASTransactionServerTestCase):
    def setUp(self):
        super().setUp()
        self.useFixture(RegionEventLoopFixture("database-tasks"))

    def test_update_services_is_registered(self):
        protocol = Region()
        responder = protocol.locateResponder(UpdateServices.commandName)
        self.assertIsNotNone(responder)

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_update_services_in_database_thread(self):
        system_id = factory.make_name("system_id")
        services = [
            {
                "name": factory.make_name("service"),
                "status": factory.make_name("status"),
                "status_info": factory.make_name("status_info"),
            }
        ]

        mock_deferToDatabase = self.patch(regionservice, "deferToDatabase")
        mock_deferToDatabase.return_value = succeed({})

        yield eventloop.start()
        try:
            yield call_responder(
                Region(),
                UpdateServices,
                {"system_id": system_id, "services": services},
            )
        finally:
            yield eventloop.reset()

        mock_deferToDatabase.assert_called_with(
            update_services, system_id, services
        )


class TestRegionProtocol_ReportForeignDHCPServer(
    MAASTransactionServerTestCase
):
    def test_is_registered(self):
        protocol = Region()
        responder = protocol.locateResponder(
            ReportForeignDHCPServer.commandName
        )
        self.assertIsNotNone(responder)

    @transactional
    def create_rack_interface(self):
        rack_controller = factory.make_RackController(interface=False)
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=rack_controller
        )
        return rack_controller, interface

    @transactional
    def get_vlan_for_interface(self, interface):
        return reload_object(interface.vlan)

    @wait_for_reactor
    @inlineCallbacks
    def test_sets_external_dhcp_value(self):
        dhcp_ip = factory.make_ipv4_address()
        rack, interface = yield deferToDatabase(self.create_rack_interface)

        response = yield call_responder(
            Region(),
            ReportForeignDHCPServer,
            {
                "system_id": rack.system_id,
                "interface_name": interface.name,
                "dhcp_ip": dhcp_ip,
            },
        )

        self.assertEqual({}, response)
        vlan = yield deferToDatabase(self.get_vlan_for_interface, interface)
        self.assertEqual(dhcp_ip, vlan.external_dhcp)


class TestRegionProtocol_CreateNode(MAASTransactionServerTestCase):
    def test_create_node_is_registered(self):
        protocol = Region()
        responder = protocol.locateResponder(CreateNode.commandName)
        self.assertIsNotNone(responder)

    @transactional
    def create_node(self):
        return factory.make_Node()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_create_node_function(self):
        create_node_function = self.patch(regionservice, "create_node")
        create_node_function.return_value = yield deferToDatabase(
            self.create_node
        )

        params = {
            "architecture": factory.make_name("arch"),
            "power_type": factory.make_name("power_type"),
            "power_parameters": dumps({}),
            "mac_addresses": [factory.make_mac_address()],
            "domain": factory.make_name("domain"),
            "hostname": None,
        }

        response = yield call_responder(Region(), CreateNode, params)
        self.assertIsNotNone(response)

        create_node_function.assert_called_once_with(
            params["architecture"],
            params["power_type"],
            params["power_parameters"],
            params["mac_addresses"],
            domain=params["domain"],
            hostname=params["hostname"],
        )
        self.assertEqual(
            create_node_function.return_value.system_id, response["system_id"]
        )


class TestRegionProtocol_CommissionNode(MAASTransactionServerTestCase):
    def test_commission_node_is_registered(self):
        protocol = Region()
        responder = protocol.locateResponder(CommissionNode.commandName)
        self.assertIsNotNone(responder)

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_commission_node_function(self):
        commission_node_function = self.patch(regionservice, "commission_node")

        params = {
            "system_id": factory.make_name("system_id"),
            "user": factory.make_name("user"),
        }

        response = yield call_responder(Region(), CommissionNode, params)
        self.assertIsNotNone(response)

        commission_node_function.assert_called_once_with(
            params["system_id"], params["user"]
        )


class TestRegionProtocol_ReportNeighbours(MAASTestCase):
    def test_report_neighbours_is_registered(self):
        protocol = Region()
        responder = protocol.locateResponder(ReportNeighbours.commandName)
        self.assertIsNotNone(responder)

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_report_neighbours_function(self):
        report_neighbours = self.patch(
            regionservice.rackcontrollers, "report_neighbours"
        )

        params = {
            "system_id": factory.make_name("system_id"),
            "neighbours": [{"ip": "127.0.0.1"}, {"ip": "127.0.0.2"}],
        }

        response = yield call_responder(Region(), ReportNeighbours, params)
        self.assertIsNotNone(response)

        report_neighbours.assert_called_once_with(
            params["system_id"], params["neighbours"]
        )


class TestRegionProtocol_RequestNodeInforByMACAddress(
    MAASTransactionServerTestCase
):
    def test_request_node_info_by_mac_address_is_registered(self):
        protocol = Region()
        responder = protocol.locateResponder(
            RequestNodeInfoByMACAddress.commandName
        )
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
        purpose = factory.make_name("purpose")
        node = yield deferToDatabase(self.create_node)
        node_info_function = self.patch(
            regionservice, "request_node_info_by_mac_address"
        )
        node_info_function.return_value = (node, purpose)
        interface = yield deferToDatabase(self.make_interface, node)

        params = {"mac_address": interface.mac_address}

        response = yield call_responder(
            Region(), RequestNodeInfoByMACAddress, params
        )
        self.assertIsNotNone(response)
        node_info_function.assert_called_once_with(params["mac_address"])
        response_purpose = response.pop("purpose")
        self.assertEqual(purpose, response_purpose)
        # Remove the boot_type from the response as node no longer has that
        # attribute.
        copy_response = dict(response)
        del copy_response["boot_type"]
        for key, value in copy_response.items():
            self.assertEqual(getattr(node, key), value)
        self.assertEqual("fastpath", response["boot_type"])

    @wait_for_reactor
    @inlineCallbacks
    def test_request_node_info_by_mac_address_raises_if_unknown_mac(self):
        params = {"mac_address": factory.make_mac_address()}
        d = call_responder(Region(), RequestNodeInfoByMACAddress, params)

        with self.assertRaisesRegex(
            NoSuchNode,
            rf"^Node with mac_address={params['mac_address']} could not be found\.",
        ):
            yield d


class TestRegionProtocol_RequestRefresh(MAASTransactionServerTestCase):
    def test_request_refresh_is_registered(self):
        protocol = Region()
        responder = protocol.locateResponder(RequestRackRefresh.commandName)
        self.assertIsNotNone(responder)

    @wait_for_reactor
    @inlineCallbacks
    def test_prepares_for_refresh(self):
        def get_events(rack):
            return [
                event.type.name
                for event in Event.objects.filter(
                    node_system_id=rack.system_id
                )
            ]

        rack = yield deferToDatabase(factory.make_RackController)
        response = yield call_responder(
            Region(),
            RequestRackRefresh,
            {"system_id": rack.system_id},
        )
        self.assertCountEqual(
            ["consumer_key", "token_key", "token_secret"], response.keys()
        )

        event_names = yield deferToDatabase(get_events, rack)
        self.assertIn("REQUEST_CONTROLLER_REFRESH", event_names)


class TestRegionProtocol_GetControllerType(MAASTransactionServerTestCase):
    def test_get_controller_type_is_registered(self):
        protocol = Region()
        responder = protocol.locateResponder(GetControllerType.commandName)
        self.assertIsNotNone(responder)

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_get_controller_type(self):
        example_response = {
            "is_region": factory.pick_bool(),
            "is_rack": factory.pick_bool(),
        }
        deferToDatabase = self.patch(regionservice, "deferToDatabase")
        deferToDatabase.return_value = succeed(example_response)
        system_id = factory.make_name("id")
        response = yield call_responder(
            Region(), GetControllerType, {"system_id": system_id}
        )
        self.assertEqual(example_response, response)
        deferToDatabase.assert_called_once_with(get_controller_type, system_id)

    @wait_for_reactor
    @inlineCallbacks
    def test_raises_NoSuchNode_when_node_does_not_exist(self):
        arguments = {"system_id": factory.make_name("id")}
        d = call_responder(Region(), GetControllerType, arguments)
        with self.assertRaisesRegex(
            NoSuchNode,
            rf"^Node with system_id={arguments['system_id']} could not be found\.",
        ):
            yield d


class TestRegionProtocol_GetTimeConfiguration(MAASTransactionServerTestCase):
    def test_get_time_configuration_is_registered(self):
        protocol = Region()
        responder = protocol.locateResponder(GetTimeConfiguration.commandName)
        self.assertIsNotNone(responder)

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_get_time_configuration(self):
        example_response = {
            "servers": [
                factory.make_ipv4_address(),
                factory.make_ipv6_address(),
                factory.make_hostname(),
            ],
            "peers": [
                factory.make_ipv4_address(),
                factory.make_ipv6_address(),
            ],
        }
        deferToDatabase = self.patch(regionservice, "deferToDatabase")
        deferToDatabase.return_value = succeed(example_response)
        system_id = factory.make_name("id")
        response = yield call_responder(
            Region(), GetTimeConfiguration, {"system_id": system_id}
        )
        self.assertEqual(example_response, response)
        deferToDatabase.assert_called_once_with(
            get_time_configuration, system_id
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_raises_NoSuchNode_when_node_does_not_exist(self):
        arguments = {"system_id": factory.make_name("id")}
        d = call_responder(Region(), GetTimeConfiguration, arguments)
        with self.assertRaisesRegex(
            NoSuchNode,
            rf"^Node with system_id={arguments['system_id']} could not be found\.",
        ):
            yield d


class TestRegionProtocol_GetDNSConfiguration(MAASTransactionServerTestCase):
    def test_get_dns_configuration_is_registered(self):
        protocol = Region()
        responder = protocol.locateResponder(GetDNSConfiguration.commandName)
        self.assertIsNotNone(responder)

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_get_trusted_networks(self):
        example_networks = [
            factory.make_ipv4_address(),
            factory.make_ipv6_address(),
        ]
        deferToDatabase = self.patch(regionservice, "deferToDatabase")
        deferToDatabase.return_value = succeed(example_networks)
        system_id = factory.make_name("id")
        response = yield call_responder(
            Region(), GetDNSConfiguration, {"system_id": system_id}
        )
        self.assertEqual({"trusted_networks": example_networks}, response)
        deferToDatabase.assert_called_once_with(get_trusted_networks)


class TestRegionProtocol_GetProxyConfiguration(MAASTransactionServerTestCase):
    def test_get_proxy_configuration_is_registered(self):
        protocol = Region()
        responder = protocol.locateResponder(GetProxyConfiguration.commandName)
        self.assertIsNotNone(responder)

    @wait_for_reactor
    @inlineCallbacks
    def test_returns_proxy_configuration(self):
        def _db_work():
            cidrs = [
                factory.make_Subnet(allow_proxy=True).cidr for _ in range(3)
            ]
            for _ in range(3):
                factory.make_Subnet(allow_proxy=False)
            enabled = factory.pick_bool()
            Config.objects.set_config("enable_http_proxy", enabled)
            port = random.randint(1000, 8000)
            Config.objects.set_config("maas_proxy_port", port)
            prefer_v4_proxy = factory.pick_bool()
            Config.objects.set_config("prefer_v4_proxy", prefer_v4_proxy)
            return cidrs, enabled, port, prefer_v4_proxy

        cidrs, enabled, port, prefer_v4_proxy = yield deferToDatabase(_db_work)

        system_id = factory.make_name("id")
        response = yield call_responder(
            Region(), GetProxyConfiguration, {"system_id": system_id}
        )
        self.assertEqual(
            response,
            {
                "enabled": enabled,
                "port": port,
                "allowed_cidrs": cidrs,
                "prefer_v4_proxy": prefer_v4_proxy,
            },
        )


class TestRegionProtocol_GetSyslogConfiguration(MAASTransactionServerTestCase):
    def test_get_proxy_configuration_is_registered(self):
        protocol = Region()
        responder = protocol.locateResponder(
            GetSyslogConfiguration.commandName
        )
        self.assertIsNotNone(responder)

    @wait_for_reactor
    @inlineCallbacks
    def test_returns_syslog_configuration(self):
        def _db_work():
            port = random.randint(1000, 8000)
            Config.objects.set_config("maas_syslog_port", port)
            return port

        port = yield deferToDatabase(_db_work)

        system_id = factory.make_name("id")
        response = yield call_responder(
            Region(), GetSyslogConfiguration, {"system_id": system_id}
        )
        self.assertEqual({"port": port, "promtail_port": None}, response)

    @wait_for_reactor
    @inlineCallbacks
    def test_returns_syslog_promtail_configuration(self):
        def _db_work():
            port = random.randint(1000, 8000)
            Config.objects.set_config("maas_syslog_port", port)
            Config.objects.set_config("promtail_enabled", True)
            Config.objects.set_config("promtail_port", port + 1)
            return port

        port = yield deferToDatabase(_db_work)

        system_id = factory.make_name("id")
        response = yield call_responder(
            Region(), GetSyslogConfiguration, {"system_id": system_id}
        )
        self.assertEqual({"port": port, "promtail_port": port + 1}, response)
