# Copyright 2012-2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import base64
from datetime import datetime, timedelta
import email
import json
import logging
import random
import re
from textwrap import dedent
from typing import Set
from unittest.mock import ANY, call, MagicMock, Mock, sentinel

import crochet
from crochet import TimeoutError
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models.deletion import Collector
from django.db.models.query import QuerySet
from fixtures import LoggerFixture
from netaddr import IPAddress, IPNetwork
from testscenarios import multiply_scenarios
from testtools import ExpectedException
from testtools.matchers import (
    AfterPreprocessing,
    Contains,
    Equals,
    HasLength,
    Is,
    IsInstance,
    MatchesAll,
    MatchesStructure,
    Not,
)
from twisted.internet import defer
from twisted.internet.error import ConnectionClosed, ConnectionDone
import yaml

from maasserver import bootresources
from maasserver import preseed as preseed_module
from maasserver import server_address
from maasserver import workflow as workflow_module
from maasserver.clusterrpc import boot_images
from maasserver.clusterrpc.driver_parameters import get_driver_choices
from maasserver.clusterrpc.testing.boot_images import make_rpc_boot_image
from maasserver.enum import (
    BOOT_RESOURCE_FILE_TYPE,
    BOOT_RESOURCE_TYPE,
    BRIDGE_TYPE_CHOICES,
    CACHE_MODE_TYPE,
    FILESYSTEM_GROUP_TYPE,
    FILESYSTEM_TYPE,
    INTERFACE_LINK_TYPE,
    INTERFACE_TYPE,
    IPADDRESS_TYPE,
    IPRANGE_TYPE,
    NODE_STATUS,
    NODE_STATUS_CHOICES,
    NODE_STATUS_CHOICES_DICT,
    NODE_TYPE,
    NODE_TYPE_CHOICES,
    PARTITION_TABLE_TYPE,
    POWER_STATE,
    SERVICE_STATUS,
)
from maasserver.exceptions import (
    IPAddressCheckFailed,
    NetworkingResetProblem,
    NodeStateViolation,
    PowerProblem,
    StaticIPAddressExhaustion,
)
from maasserver.models import (
    BMCRoutableRackControllerRelationship,
    BootResource,
    BridgeInterface,
    Config,
    Controller,
    Device,
    Domain,
    Event,
    EventType,
    Interface,
    LicenseKey,
    Machine,
    Neighbour,
    Node,
)
from maasserver.models import (
    NodeDevice,
    NodeUserData,
    OwnerData,
    PhysicalInterface,
    RackController,
    RAID,
    RegionController,
    RegionRackRPCConnection,
    ResourcePool,
    ScriptResult,
    ScriptSet,
    Service,
    StaticIPAddress,
    Subnet,
    UnknownInterface,
    VLAN,
    VolumeGroup,
)
from maasserver.models import Bcache, BMC
from maasserver.models import bmc as bmc_module
from maasserver.models import node as node_module
from maasserver.models.config import NetworkDiscoveryConfig
import maasserver.models.interface as interface_module
from maasserver.models.node import (
    DEFAULT_BIOS_BOOT_METHOD,
    DefaultGateways,
    GatewayDefinition,
    generate_node_system_id,
    PowerInfo,
)
from maasserver.models.nodeconfig import NODE_CONFIG_TYPE
from maasserver.models.partitiontable import PARTITION_TABLE_EXTRA_SPACE
from maasserver.models.signals import power as node_query
from maasserver.models.timestampedmodel import now
from maasserver.node_status import (
    COMMISSIONING_LIKE_STATUSES,
    get_node_timeout,
    MONITORED_STATUSES,
    NODE_FAILURE_MONITORED_STATUS_TRANSITIONS,
    NODE_FAILURE_STATUS_TRANSITIONS,
    NODE_TESTING_RESET_READY_TRANSITIONS,
    NODE_TRANSITIONS,
)
from maasserver.permissions import NodePermission
from maasserver.preseed import CURTIN_INSTALL_LOG
from maasserver.preseed_network import compose_curtin_network_config
from maasserver.preseed_storage import compose_curtin_storage_config
from maasserver.rbac import FakeRBACClient, rbac
from maasserver.rpc.testing.fixtures import MockLiveRegionToClusterRPCFixture
from maasserver.secrets import SecretManager
from maasserver.storage_layouts import (
    MIN_BOOT_PARTITION_SIZE,
    StorageLayoutError,
    StorageLayoutMissingBootDiskError,
    VMFS6StorageLayout,
    VMFS7StorageLayout,
)
from maasserver.testing.eventloop import (
    RegionEventLoopFixture,
    RunningEventLoopFixture,
)
from maasserver.testing.factory import factory, RANDOM
from maasserver.testing.testcase import (
    MAASServerTestCase,
    MAASTransactionServerTestCase,
)
from maasserver.tests.test_preseed_network import AssertNetworkConfigMixin
from maasserver.tests.test_preseed_storage import AssertStorageConfigMixin
from maasserver.utils.orm import (
    post_commit,
    post_commit_hooks,
    reload_object,
    transactional,
)
from maasserver.utils.threads import callOutToDatabase, deferToDatabase
from maasserver.worker_user import get_worker_user
from maastesting.crochet import wait_for
from maastesting.matchers import (
    DocTestMatches,
    MockCalledOnce,
    MockCalledOnceWith,
    MockCallsMatch,
    MockNotCalled,
)
from metadataserver.builtin_scripts import load_builtin_scripts
from metadataserver.builtin_scripts.tests import test_hooks
from metadataserver.enum import (
    RESULT_TYPE,
    SCRIPT_STATUS,
    SCRIPT_STATUS_RUNNING_OR_PENDING,
    SCRIPT_TYPE,
)
from provisioningserver.drivers.pod import Capabilities, DiscoveredPodHints
from provisioningserver.drivers.power.ipmi import IPMI_BOOT_TYPE
from provisioningserver.drivers.power.registry import PowerDriverRegistry
from provisioningserver.events import EVENT_DETAILS, EVENT_TYPES
from provisioningserver.refresh.node_info_scripts import (
    COMMISSIONING_OUTPUT_NAME,
    NODE_INFO_SCRIPTS,
)
from provisioningserver.rpc.cluster import (
    AddChassis,
    DecomposeMachine,
    DisableAndShutoffRackd,
    IsImportBootImagesRunning,
)
from provisioningserver.rpc.exceptions import (
    CannotDisableAndShutoffRackd,
    NoConnectionsAvailable,
    PodActionFail,
    PowerActionFail,
    UnknownPowerType,
)
from provisioningserver.rpc.testing.doubles import DummyConnection
from provisioningserver.utils import znums
from provisioningserver.utils.enum import map_enum, map_enum_reverse
from provisioningserver.utils.env import MAAS_ID
from provisioningserver.utils.network import inet_ntop
from provisioningserver.utils.testing import MAASIDFixture

wait_for_reactor = wait_for()


class TestGenerateNodeSystemID(MAASServerTestCase):
    """Tests for `generate_node_system_id`."""

    def test_identifier_is_six_digits(self):
        self.assertThat(generate_node_system_id(), HasLength(6))

    def test_avoids_identifiers_already_in_use(self):
        used_system_id = factory.make_Node().system_id
        used_system_num = znums.to_int(used_system_id)
        randrange = self.patch_autospec(random, "randrange")
        randrange.side_effect = [used_system_num, used_system_num + 1]
        self.assertEqual(
            znums.from_int(used_system_num + 1),
            generate_node_system_id(),
        )

    def test_crashes_after_1000_iterations(self):
        used_system_id = factory.make_Node().system_id
        used_system_num = znums.to_int(used_system_id)
        randrange = self.patch_autospec(random, "randrange")
        randrange.return_value = used_system_num
        error = self.assertRaises(AssertionError, generate_node_system_id)
        self.assertThat(
            str(error),
            DocTestMatches(
                "... after 1000 iterations ... no unused node identifiers."
            ),
        )


def HasType(type_):
    return AfterPreprocessing(type, Is(type_), annotate=False)


def SharesStorageWith(other):
    return AfterPreprocessing(
        (lambda thing: thing.__dict__), Is(other.__dict__), annotate=False
    )


class TestTypeCastToNodeType(MAASServerTestCase):
    def test_cast_to_self(self):
        node = factory.make_Node().as_node()
        node_types = set(map_enum(NODE_TYPE).values())
        casts = {
            NODE_TYPE.DEVICE: Device,
            NODE_TYPE.MACHINE: Machine,
            NODE_TYPE.RACK_CONTROLLER: RackController,
            NODE_TYPE.REGION_AND_RACK_CONTROLLER: RackController,
            NODE_TYPE.REGION_CONTROLLER: RegionController,
        }
        self.assertEqual(node_types, casts.keys())
        for node_type, cast_type in casts.items():
            node.node_type = node_type
            node_as_self = node.as_self()
            self.assertThat(node, HasType(Node))
            self.assertThat(node_as_self, HasType(cast_type))
            self.assertThat(node_as_self, SharesStorageWith(node))

    def test_cast_to_machine(self):
        node = factory.make_Node().as_node()
        machine = node.as_machine()
        self.assertThat(node, HasType(Node))
        self.assertThat(machine, HasType(Machine))
        self.assertThat(machine, SharesStorageWith(node))

    def test_cast_to_rack_controller(self):
        node = factory.make_Node().as_node()
        rack = node.as_rack_controller()
        self.assertThat(node, HasType(Node))
        self.assertThat(rack, HasType(RackController))
        self.assertThat(rack, SharesStorageWith(node))

    def test_cast_to_region_controller(self):
        node = factory.make_Node().as_node()
        region = node.as_region_controller()
        self.assertThat(node, HasType(Node))
        self.assertThat(region, HasType(RegionController))
        self.assertThat(region, SharesStorageWith(node))

    def test_cast_to_device(self):
        node = factory.make_Node().as_node()
        device = node.as_device()
        self.assertThat(node, HasType(Node))
        self.assertThat(device, HasType(Device))
        self.assertThat(device, SharesStorageWith(node))

    def test_cast_to_node(self):
        machine = factory.make_Machine()
        node = machine.as_node()
        self.assertThat(machine, HasType(Machine))
        self.assertThat(node, HasType(Node))
        self.assertThat(node, SharesStorageWith(machine))


class TestNodeGetLatestScriptResults(MAASServerTestCase):
    def test_get_latest_script_results(self):
        node = factory.make_Node()
        latest_script_results = []
        for _ in range(5):
            script = factory.make_Script()
            for run in range(10):
                script_set = factory.make_ScriptSet(
                    result_type=script.script_type, node=node
                )
                factory.make_ScriptResult(script=script, script_set=script_set)

            script_set = factory.make_ScriptSet(
                result_type=script.script_type, node=node
            )
            latest_script_results.append(
                factory.make_ScriptResult(script=script, script_set=script_set)
            )

        self.assertCountEqual(
            latest_script_results, node.get_latest_script_results
        )

    def test_get_latest_script_results_storage(self):
        # Verify multiple instances of the same script are shown as the latest.
        node = factory.make_Node()
        script = factory.make_Script(
            parameters={"storage": {"type": "storage"}}
        )
        script_set = factory.make_ScriptSet(
            result_type=script.script_type, node=node
        )
        script_results = []
        for _ in range(5):
            bd = factory.make_PhysicalBlockDevice(node=node)
            script_result = factory.make_ScriptResult(
                script=script, script_set=script_set, physical_blockdevice=bd
            )
            script_results.append(script_result)

        self.assertCountEqual(
            [script_result.id for script_result in script_results],
            [
                script_result.id
                for script_result in node.get_latest_script_results
            ],
        )

    def test_get_latest_script_results_interface(self):
        # Verify multiple instances of the same script are shown as the latest.
        node = factory.make_Node()
        script = factory.make_Script(
            parameters={"interface": {"type": "interface"}}
        )
        script_set = factory.make_ScriptSet(
            result_type=script.script_type, node=node
        )
        script_results = []
        for _ in range(5):
            nic = factory.make_Interface(node=node)
            script_result = factory.make_ScriptResult(
                script=script, script_set=script_set, interface=nic
            )
            script_results.append(script_result)

        self.assertCountEqual(
            [script_result.id for script_result in script_results],
            [
                script_result.id
                for script_result in node.get_latest_script_results
            ],
        )

    def test_get_latest_commissioning_script_results(self):
        node = factory.make_Node()
        latest_script_results = []
        for _ in range(5):
            script = factory.make_Script()
            for run in range(10):
                script_set = factory.make_ScriptSet(
                    result_type=script.script_type, node=node
                )
                factory.make_ScriptResult(script=script, script_set=script_set)

            script_set = factory.make_ScriptSet(
                result_type=script.script_type, node=node
            )
            script_result = factory.make_ScriptResult(
                script=script, script_set=script_set
            )
            if script.script_type == SCRIPT_TYPE.COMMISSIONING:
                latest_script_results.append(script_result)

        self.assertCountEqual(
            latest_script_results, node.get_latest_commissioning_script_results
        )

    def test_get_latest_testing_script_results(self):
        node = factory.make_Node()
        latest_script_results = []
        for _ in range(5):
            script = factory.make_Script()
            for run in range(10):
                script_set = factory.make_ScriptSet(
                    result_type=script.script_type, node=node
                )
                factory.make_ScriptResult(script=script, script_set=script_set)

            script_set = factory.make_ScriptSet(
                result_type=script.script_type, node=node
            )
            script_result = factory.make_ScriptResult(
                script=script, script_set=script_set
            )
            if script.script_type == SCRIPT_TYPE.TESTING:
                latest_script_results.append(script_result)

        self.assertCountEqual(
            latest_script_results, node.get_latest_testing_script_results
        )

    def test_get_latest_installation_script_results(self):
        node = factory.make_Node()
        for _ in range(10):
            script_set = factory.make_ScriptSet(
                result_type=RESULT_TYPE.INSTALLATION, node=node
            )
            factory.make_ScriptResult(
                script_name=CURTIN_INSTALL_LOG, script_set=script_set
            )

        script_set = factory.make_ScriptSet(
            result_type=RESULT_TYPE.INSTALLATION, node=node
        )
        latest_script_results = [
            factory.make_ScriptResult(
                script_name=CURTIN_INSTALL_LOG, script_set=script_set
            )
        ]

        self.assertCountEqual(
            latest_script_results, node.get_latest_installation_script_results
        )


class TestMachineManager(MAASServerTestCase):
    def make_machine(self, *args, **kwargs):
        return factory.make_Node(
            status=NODE_STATUS.READY, with_boot_disk=False, **kwargs
        )

    def test_machine_lists_node_type_machine(self):
        machine = self.make_machine()
        factory.make_Device()
        factory.make_Node(
            node_type=NODE_TYPE.RACK_CONTROLLER, with_boot_disk=False
        )
        self.assertCountEqual([machine], Machine.objects.all())

    def test_get_available_machines_finds_available_machines(self):
        user = factory.make_User()
        machine1 = self.make_machine()
        machine2 = self.make_machine()
        self.assertCountEqual(
            [machine1, machine2],
            Machine.objects.get_available_machines_for_acquisition(user),
        )

    def test_get_available_machines_returns_empty_list_if_empty(self):
        user = factory.make_User()
        self.assertEqual(
            [],
            list(Machine.objects.get_available_machines_for_acquisition(user)),
        )

    def test_get_available_machines_ignores_taken_machines(self):
        user = factory.make_User()
        available_status = NODE_STATUS.READY
        unavailable_statuses = set(NODE_STATUS_CHOICES_DICT) - {
            available_status
        }
        machine = factory.make_Machine(with_boot_disk=False)
        for status in unavailable_statuses:
            machine.status = status
            self.assertEqual(
                [],
                list(
                    Machine.objects.get_available_machines_for_acquisition(
                        user
                    )
                ),
            )

    def test_get_available_machines_ignores_invisible_machines(self):
        user = factory.make_User()
        machine = self.make_machine()
        machine.owner = factory.make_User()
        machine.save()
        self.assertEqual(
            [],
            list(Machine.objects.get_available_machines_for_acquisition(user)),
        )


class TestControllerManager(MAASServerTestCase):
    def test_controller_lists_node_type_rack_and_region(self):
        racks_and_regions = set()
        factory.make_Node(node_type=NODE_TYPE.MACHINE)
        factory.make_Device()
        for node_type in (
            NODE_TYPE.RACK_CONTROLLER,
            NODE_TYPE.REGION_CONTROLLER,
            NODE_TYPE.REGION_AND_RACK_CONTROLLER,
        ):
            racks_and_regions.add(factory.make_Node(node_type=node_type))
        self.assertCountEqual(racks_and_regions, Controller.objects.all())


class TestRackControllerManager(MAASServerTestCase):
    def make_rack_controller_with_ip(self, subnet=None):
        rack = factory.make_RackController(subnet=subnet)
        # factory.make_Node_with_Interface_on_Subnet gives the rack an
        # interface on the specified subnet a static IP but doesn't actually
        # set one. Setting one in the factory breaks a number of other tests.
        static_ip = rack.boot_interface.ip_addresses.first()
        if subnet is None:
            subnet = static_ip.subnet
        static_ip.ip = factory.pick_ip_in_Subnet(subnet)
        static_ip.save()
        return rack

    def test_rack_controller_lists_node_type_rack_controller(self):
        factory.make_Machine()
        factory.make_Device()
        rack_controller = factory.make_RackController()
        self.assertCountEqual([rack_controller], RackController.objects.all())

    def test_get_running_controller(self):
        rack = factory.make_RackController()
        self.useFixture(MAASIDFixture(rack.system_id))
        rack_running = RackController.objects.get_running_controller()
        self.assertEqual(rack, rack_running)
        self.assertIsInstance(rack_running, RackController)

    def test_filter_by_url_accessible_finds_correct_racks(self):
        accessible_subnet = factory.make_Subnet()
        accessible_racks = set()
        for _ in range(3):
            accessible_racks.add(
                self.make_rack_controller_with_ip(accessible_subnet)
            )
            self.make_rack_controller_with_ip()
        url = factory.pick_ip_in_Subnet(accessible_subnet)
        mock_getaddr_info = self.patch(node_module.socket, "getaddrinfo")
        mock_getaddr_info.return_value = (("", "", "", "", (url,)),)
        self.assertCountEqual(
            accessible_racks,
            RackController.objects.filter_by_url_accessible(url, False),
        )

    def test_filter_by_url_accessible_parses_full_url(self):
        hostname = factory.make_hostname()
        url = "%s://%s:%s@%s:%d/%s" % (
            factory.make_name("protocol"),
            factory.make_name("username"),
            factory.make_name("password"),
            hostname,
            random.randint(0, 65535),
            factory.make_name("path"),
        )
        accessible_subnet = factory.make_Subnet()
        accessible_rack = self.make_rack_controller_with_ip(accessible_subnet)
        factory.make_RackController()
        ip = factory.pick_ip_in_Subnet(accessible_subnet)
        mock_getaddr_info = self.patch(node_module.socket, "getaddrinfo")
        mock_getaddr_info.return_value = (("", "", "", "", (ip,)),)
        self.assertEqual(
            [accessible_rack],
            RackController.objects.filter_by_url_accessible(url, False),
        )
        mock_getaddr_info.assert_called_once_with(hostname, None)

    def test_filter_by_url_accessible_parses_host_port(self):
        hostname = factory.make_hostname()
        url = "%s:%d" % (hostname, random.randint(0, 65535))
        accessible_subnet = factory.make_Subnet()
        accessible_rack = self.make_rack_controller_with_ip(accessible_subnet)
        factory.make_RackController()
        ip = factory.pick_ip_in_Subnet(accessible_subnet)
        mock_getaddr_info = self.patch(node_module.socket, "getaddrinfo")
        mock_getaddr_info.return_value = (("", "", "", "", (ip,)),)
        self.assertEqual(
            [accessible_rack],
            RackController.objects.filter_by_url_accessible(url, False),
        )
        mock_getaddr_info.assert_called_once_with(hostname, None)

    def test_filter_by_url_accessible_parses_host_user_pass(self):
        hostname = factory.make_hostname()
        url = "{}:{}@{}".format(
            factory.make_name("username"),
            factory.make_name("password"),
            hostname,
        )
        accessible_subnet = factory.make_Subnet()
        accessible_rack = self.make_rack_controller_with_ip(accessible_subnet)
        factory.make_RackController()
        ip = factory.pick_ip_in_Subnet(accessible_subnet)
        mock_getaddr_info = self.patch(node_module.socket, "getaddrinfo")
        mock_getaddr_info.return_value = (("", "", "", "", (ip,)),)
        self.assertEqual(
            [accessible_rack],
            RackController.objects.filter_by_url_accessible(url, False),
        )
        mock_getaddr_info.assert_called_once_with(hostname, None)

    def test_filter_by_url_finds_self_with_loopback(self):
        rack = self.make_rack_controller_with_ip()
        mock_getaddr_info = self.patch(node_module.socket, "getaddrinfo")
        ip = random.choice(["127.0.0.1", "::1"])
        mock_getaddr_info.return_value = (("", "", "", "", (ip,)),)
        self.useFixture(MAASIDFixture(rack.system_id))
        self.assertEqual(
            [rack], RackController.objects.filter_by_url_accessible(ip, False)
        )

    def test_filter_by_url_only_returns_connected_controllers(self):
        subnet = factory.make_Subnet()
        accessible_racks = set()
        connections = list()
        for _ in range(3):
            accessible_rack = self.make_rack_controller_with_ip(subnet=subnet)
            accessible_racks.add(accessible_rack)
            conn = DummyConnection()
            conn.ident = accessible_rack.system_id
            connections.append(conn)
            self.make_rack_controller_with_ip()
        ip = factory.pick_ip_in_Subnet(subnet)
        mock_getaddr_info = self.patch(node_module.socket, "getaddrinfo")
        mock_getaddr_info.return_value = (("", "", "", "", (ip,)),)
        mock_getallclients = self.patch(node_module, "getAllClients")
        mock_getallclients.return_value = connections
        self.assertCountEqual(
            accessible_racks,
            RackController.objects.filter_by_url_accessible(ip, True),
        )

    def test_get_accessible_by_url(self):
        accessible_subnet = factory.make_Subnet()
        accessible_rack = self.make_rack_controller_with_ip(accessible_subnet)
        url = factory.pick_ip_in_Subnet(accessible_subnet)
        self.patch(node_module.socket, "getaddrinfo").return_value = (
            ("", "", "", "", (url,)),
        )
        self.assertEqual(
            RackController.objects.get_accessible_by_url(url, False),
            accessible_rack,
        )

    def test_get_accessible_by_url_returns_none_when_not_found(self):
        factory.make_RackController()
        accessible_subnet = factory.make_Subnet()
        url = factory.pick_ip_in_Subnet(accessible_subnet)
        self.patch(node_module.socket, "getaddrinfo").return_value = (
            ("", "", "", "", (url,)),
        )
        self.assertEqual(
            None, RackController.objects.get_accessible_by_url(url, False)
        )


class TestRegionControllerManager(MAASServerTestCase):
    def test_region_controller_lists_node_type_region_controller(self):
        # Create a device, a machine, and a rack controller.
        factory.make_Device()
        factory.make_Machine()
        factory.make_RackController()
        # Create region controllers.
        region = factory.make_RegionController()
        # Only the region controllers are found.
        self.assertCountEqual([region], RegionController.objects.all())

    def test_get_running_controller_finds_controller_via_maas_id(self):
        region = factory.make_RegionController()
        self.useFixture(MAASIDFixture(region.system_id))
        region_running = RegionController.objects.get_running_controller()
        self.assertIsInstance(region_running, RegionController)
        self.assertEqual(region, region_running)

    def test_get_running_controller_crashes_when_maas_id_is_not_set(self):
        self.useFixture(MAASIDFixture(None))
        self.assertRaises(
            RegionController.DoesNotExist,
            RegionController.objects.get_running_controller,
        )

    def test_get_running_controller_crashes_when_maas_id_is_not_found(self):
        self.useFixture(MAASIDFixture("bogus"))
        self.assertRaises(
            RegionController.DoesNotExist,
            RegionController.objects.get_running_controller,
        )


class TestRegionControllerManagerGetOrCreateRunningController(
    MAASServerTestCase
):
    scenarios_hosts = (
        ("rack", dict(make_host_node=factory.make_RackController)),
        ("region", dict(make_host_node=factory.make_RegionController)),
        ("machine", dict(make_host_node=factory.make_Machine)),
        ("device", dict(make_host_node=factory.make_Device)),
        ("unknown", dict(make_host_node=None)),
    )

    scenarios_hostnames = (
        ("hostname-matches", dict(hostname_matches=True)),
        ("hostname-does-not-match", dict(hostname_matches=False)),
    )

    scenarios_mac_addresses = (
        ("macs-match", dict(mac_addresses_match=True)),
        ("macs-do-not-match", dict(mac_addresses_match=False)),
    )

    scenarios_owners = (
        ("owned-by-worker", dict(make_owner=get_worker_user)),
        ("owned-by-other", dict(make_owner=factory.make_User)),
        ("owned-by-nobody", dict(make_owner=lambda: None)),
    )

    scenarios_maas_ids = (
        ("maas-id-is-set", dict(with_maas_id="yes")),
        ("maas-id-not-set", dict(with_maas_id="no")),
        ("maas-id-stale", dict(with_maas_id="stale")),
    )

    scenarios = multiply_scenarios(
        scenarios_hosts,
        scenarios_hostnames,
        scenarios_mac_addresses,
        scenarios_owners,
        scenarios_maas_ids,
    )

    def setUp(self):
        super().setUp()
        # Patch out gethostname and get_mac_addresses.
        self.patch_autospec(node_module, "gethostname")
        hostname = factory.make_name("host")
        # Bug#1614584: make sure that we handle the case where gethostname()
        # returns an FQDN, instead of a domainless hostname.
        if factory.pick_bool():
            hostname += ".%s" % factory.make_name("domain")
        node_module.gethostname.return_value = hostname
        self.patch_autospec(node_module, "get_mac_addresses")
        node_module.get_mac_addresses.return_value = []

    def set_hostname_to_match(self, node):
        node_module.gethostname.return_value = node.hostname

    def set_mac_address_to_match(self, node):
        raw_macs = [
            nic.mac_address for nic in node.current_config.interface_set.all()
        ]
        node_module.get_mac_addresses.return_value = [random.choice(raw_macs)]

    def prepare_existing_host(self):
        # Create a record for the current host if requested.
        if self.make_host_node is None:
            host = owner = None
        else:
            # Create the host record using this scenario's factory.
            host = self.make_host_node()
            # Give the host an owner using this scenario's factory.
            owner = host.owner = self.make_owner()
            host.save()
            # Optionally make the host discoverable by hostname.
            if self.hostname_matches:
                self.set_hostname_to_match(host)
            # Optionally make the host discoverable by MAC address.
            if self.mac_addresses_match:
                factory.make_Interface(node=host)
                factory.make_Interface(node=host)
                self.set_mac_address_to_match(host)
        return host, owner

    def prepare_maas_id(self, host):
        # Configure a preexisting MAAS ID file.
        if self.with_maas_id == "stale":
            # Populate the MAAS ID file with something bogus.
            self.useFixture(MAASIDFixture(factory.make_name("stale")))
        elif self.with_maas_id == "yes":
            # Populate the MAAS ID file for the current host, if there is one.
            self.useFixture(
                MAASIDFixture(None if host is None else host.system_id)
            )
        else:
            # Remove the MAAD ID file.
            self.useFixture(MAASIDFixture(None))

    def get_or_create_running_controller(self):
        # A more concise way to call get_or_create_running_controller().
        with post_commit_hooks:
            return RegionController.objects.get_or_create_running_controller()

    def can_be_discovered(self):
        # An existing host record can only be discovered by hostname, MAC
        # address, or from the value stored in the MAAS ID file.
        return (
            self.hostname_matches
            or self.mac_addresses_match
            or self.with_maas_id == "yes"
        )

    def test(self):
        host, owner = self.prepare_existing_host()
        self.prepare_maas_id(host)

        # This is the big moment.
        region = self.get_or_create_running_controller()

        # The type returned is always RegionController.
        self.assertIsInstance(region, RegionController)
        # The MAAS ID always matches the controller's.
        self.assertEqual(MAAS_ID.get(), region.system_id)

        if host is None:
            # There was no existing host record so, no matter what else, a new
            # controller is created.
            self.assertControllerCreated(region)
        elif self.can_be_discovered():
            # The current host is represented in the database and we do have
            # enough information to discover it.
            self.assertControllerDiscovered(region, host, owner)
        else:
            # The current host is represented in the database but we do NOT
            # have enough information to discover it. Though unlikely this is
            # possible if the MAAS ID file is removed, the hostname is
            # changed, and all MAC addresses differ.
            self.assertControllerNotDiscovered(region, host)

        # The region node should always have a ScriptSet to allow refresh
        # on start to upload commissioning results.
        self.assertIsNotNone(region.current_commissioning_script_set)

    def assertControllerCreated(self, region):
        # A controller is created and it is always a region controller.
        self.assertEqual(NODE_TYPE.REGION_CONTROLLER, region.node_type)
        # It's a fresh controller so the worker user is always owner.
        self.assertEqual(get_worker_user(), region.owner)
        self.assertEqual(NODE_STATUS.DEPLOYED, region.status)
        self.assertTrue(region.dynamic)

    def assertControllerDiscovered(self, region, host, owner):
        # The controller discovered is the original host.
        self.assertEqual(host.id, region.id)
        # When the discovered host record is not owned the worker user is
        # used, otherwise existing ownership remains intact.
        self.assertEqual(
            get_worker_user() if owner is None else region.owner,
            region.owner,
        )
        # The host has been upgraded to the expected type.
        self.assertThat(
            region.node_type,
            Equals(
                NODE_TYPE.REGION_AND_RACK_CONTROLLER
                if host.is_rack_controller
                else NODE_TYPE.REGION_CONTROLLER
            ),
        )

    def assertControllerNotDiscovered(self, region, host):
        # A controller is created and it is always a region controller.
        self.assertEqual(NODE_TYPE.REGION_CONTROLLER, region.node_type)
        # It's new; the primary key differs from the host we planted.
        self.assertNotEqual(host.id, region.id)
        # It's a fresh controller so the worker user is always owner.
        self.assertEqual(get_worker_user(), region.owner)


class TestDeviceManager(MAASServerTestCase):
    def test_device_lists_node_type_devices(self):
        factory.make_Machine()
        factory.make_RackController()
        device = factory.make_Device()
        self.assertCountEqual([device], Device.objects.all())

    def test_empty_architecture_accepted_for_type_device(self):
        device = factory.make_Device(architecture="")
        self.assertIsInstance(device, Device)
        self.assertEqual("", device.architecture)


class TestNode(MAASServerTestCase):
    def setUp(self):
        super().setUp()
        self.patch_autospec(node_module, "power_driver_check")

    def disable_node_query(self):
        self.addCleanup(node_query.signals.enable)
        node_query.signals.disable()

    def test_is_rack_controller_machine(self):
        machine = factory.make_Node()
        self.assertFalse(machine.is_rack_controller)

    def test_is_rack_controller_device(self):
        device = factory.make_Device()
        self.assertFalse(device.is_rack_controller)

    def test_is_rack_controller_region_controller(self):
        region = factory.make_RegionController()
        self.assertFalse(region.is_rack_controller)

    def test_is_rack_controller_region_rack_controller(self):
        region_rack = factory.make_RegionRackController()
        self.assertTrue(region_rack.is_rack_controller)

    def test_is_rack_controller_rack_controller(self):
        rack = factory.make_RackController()
        self.assertTrue(rack.is_rack_controller)

    def test_is_region_controller_machine(self):
        machine = factory.make_Node()
        self.assertFalse(machine.is_region_controller)

    def test_is_region_controller_device(self):
        device = factory.make_Device()
        self.assertFalse(device.is_region_controller)

    def test_is_region_controller_region_controller(self):
        region = factory.make_RegionController()
        self.assertTrue(region.is_region_controller)

    def test_is_region_controller_region_rack_controller(self):
        region_rack = factory.make_RegionRackController()
        self.assertTrue(region_rack.is_region_controller)

    def test_is_region_controller_rack_controller(self):
        rack = factory.make_RackController()
        self.assertFalse(rack.is_region_controller)

    def test_is_controller_machine(self):
        machine = factory.make_Node()
        self.assertFalse(machine.is_controller)

    def test_is_controller_device(self):
        device = factory.make_Device()
        self.assertFalse(device.is_controller)

    def test_is_controller_region_controller(self):
        region = factory.make_RegionController()
        self.assertTrue(region.is_controller)

    def test_is_controller_region_rack_controller(self):
        region_rack = factory.make_RegionRackController()
        self.assertTrue(region_rack.is_controller)

    def test_is_controller_rack_controller(self):
        rack = factory.make_RackController()
        self.assertTrue(rack.is_controller)

    def test_is_machine_machine(self):
        machine = factory.make_Node()
        self.assertTrue(machine.is_machine)

    def test_is_machine_device(self):
        device = factory.make_Device()
        self.assertFalse(device.is_machine)

    def test_is_machine_region_controller(self):
        region = factory.make_RegionController()
        self.assertFalse(region.is_machine)

    def test_is_machine_region_rack_controller(self):
        region_rack = factory.make_RegionRackController()
        self.assertFalse(region_rack.is_machine)

    def test_is_machine_rack_controller(self):
        rack = factory.make_RackController()
        self.assertFalse(rack.is_machine)

    def test_is_device_machine(self):
        machine = factory.make_Node()
        self.assertFalse(machine.is_device)

    def test_is_device_device(self):
        device = factory.make_Device()
        self.assertTrue(device.is_device)

    def test_is_device_region_controller(self):
        region = factory.make_RegionController()
        self.assertFalse(region.is_device)

    def test_is_device_region_rack_controller(self):
        region_rack = factory.make_RegionRackController()
        self.assertFalse(region_rack.is_device)

    def test_is_device_rack_controller(self):
        rack = factory.make_RackController()
        self.assertFalse(rack.is_device)

    def test_is_diskless(self):
        node = factory.make_Node(with_boot_disk=False)
        self.assertTrue(node.is_diskless)

    def test_is_not_diskless(self):
        node = factory.make_Node(with_boot_disk=True)
        self.assertFalse(node.is_diskless)

    def test_no_ephemeral_deploy(self):
        node = factory.make_Node(
            ephemeral_deploy=False, status=NODE_STATUS.DEPLOYING
        )
        self.assertFalse(node.ephemeral_deploy)

    def test_ephemeral_deploy(self):
        node = factory.make_Node(
            ephemeral_deploy=True, status=NODE_STATUS.DEPLOYING
        )
        self.assertTrue(node.ephemeral_deploy)

    def test_ephemeral_deployment_checks_diskless(self):
        node = factory.make_Node(
            with_boot_disk=True, status=NODE_STATUS.DEPLOYING
        )
        self.assertFalse(node.ephemeral_deploy)

    def test_ephemeral_deployment_checks_ephemeral_deploy(self):
        node = factory.make_Node(
            ephemeral_deploy=True, status=NODE_STATUS.DEPLOYING
        )
        self.assertTrue(node.ephemeral_deploy)

    def test_ephemeral_deployment_checks_no_ephemeral_deploy(self):
        node = factory.make_Node(
            ephemeral_deploy=False, status=NODE_STATUS.DEPLOYING
        )
        self.assertFalse(node.ephemeral_deploy)

    def test_ephemeral_deploy_scriptstatus_no(self):
        node = factory.make_Node_with_Interface_on_Subnet(
            ephemeral_deploy=True, status=NODE_STATUS.ALLOCATED
        )
        node._start_deployment()
        self.assertIsNone(node.current_installation_script_set)

    def test_ephemeral_deploy_no_scriptstatus_yes(self):
        node = factory.make_Node_with_Interface_on_Subnet(
            ephemeral_deploy=False, status=NODE_STATUS.ALLOCATED
        )
        node._start_deployment()
        self.assertIsNotNone(node.current_installation_script_set)

    def test_system_id_is_a_valid_znum(self):
        node = factory.make_Node()
        self.assertThat(
            node.system_id, AfterPreprocessing(znums.to_int, IsInstance(int))
        )

    def test_system_id_is_exactly_6_characters(self):
        node = factory.make_Node()
        self.assertThat(node.system_id, HasLength(6))

    def test_set_zone(self):
        zone = factory.make_Zone()
        node = factory.make_Node()
        node.set_zone(zone)
        self.assertEqual(node.zone, zone)

    def test_hostname_is_validated(self):
        bad_hostname = "-_?!@*-"
        self.assertRaises(
            ValidationError, factory.make_Node, hostname=bad_hostname
        )

    def test_instance_name_no_vm(self):
        node = factory.make_Node()
        self.assertIsNone(node.instance_name)

    def test_instance_name_virsh_vm(self):
        node = factory.make_Node()
        node.set_instance_power_parameters({"power_id": "vm"})
        self.assertEqual(node.instance_name, "vm")

    def test_instance_name_lxd_vm(self):
        node = factory.make_Node()
        node.set_instance_power_parameters({"instance_name": "vm"})
        self.assertEqual(node.instance_name, "vm")

    def test_default_pool_for_machine(self):
        node = factory.make_Node()
        self.assertEqual(
            node.pool, ResourcePool.objects.get_default_resource_pool()
        )

    def test_other_pool_for_machine(self):
        pool = factory.make_ResourcePool()
        node = factory.make_Node(pool=pool)
        self.assertEqual(node.pool, pool)

    def test_no_pool_for_device(self):
        node = factory.make_Node(node_type=NODE_TYPE.DEVICE)
        self.assertIsNone(node.pool)

    def test_no_pool_assign_for_device(self):
        pool = factory.make_ResourcePool()
        self.assertRaises(
            ValidationError,
            factory.make_Node,
            node_type=NODE_TYPE.DEVICE,
            pool=pool,
        )

    def test_update_pool(self):
        pool = factory.make_ResourcePool()
        node = factory.make_Node()
        node.pool = pool
        node.save()
        self.assertEqual(node.pool, pool)

    def test_lock_deployed(self):
        user = factory.make_User()
        node = factory.make_Node(status=NODE_STATUS.DEPLOYED)
        node.lock(user)
        self.assertTrue(node.locked)

    def test_lock_deploying(self):
        user = factory.make_User()
        node = factory.make_Node(status=NODE_STATUS.DEPLOYING)
        node.lock(user)
        self.assertTrue(node.locked)

    def test_lock_locked(self):
        user = factory.make_User()
        node = factory.make_Node(status=NODE_STATUS.DEPLOYED, locked=True)
        node.lock(user)
        self.assertTrue(node.locked)

    def test_lock_logs_request(self):
        user = factory.make_User()
        node = factory.make_Node(status=NODE_STATUS.DEPLOYED)
        register_event = self.patch(node, "_register_request_event")
        node.lock(user, comment="lock my node")
        self.assertThat(
            register_event,
            MockCalledOnceWith(
                user,
                EVENT_TYPES.REQUEST_NODE_LOCK,
                action="lock",
                comment="lock my node",
            ),
        )

    def test_lock_invalid_status_fails(self):
        user = factory.make_User()
        node = factory.make_Node(status=NODE_STATUS.READY)
        self.assertRaises(NodeStateViolation, node.lock, user)
        self.assertFalse(node.locked)

    def test_unlock(self):
        user = factory.make_User()
        node = factory.make_Node(status=NODE_STATUS.DEPLOYED, locked=True)
        node.unlock(user)
        self.assertFalse(node.locked)

    def test_unlock_not_locked(self):
        user = factory.make_User()
        node = factory.make_Node()
        node.unlock(user)
        self.assertFalse(node.locked)

    def test_unlock_logs_request(self):
        user = factory.make_User()
        node = factory.make_Node(status=NODE_STATUS.DEPLOYED, locked=True)
        register_event = self.patch(node, "_register_request_event")
        node.unlock(user, comment="unlock my node")
        self.assertThat(
            register_event,
            MockCalledOnceWith(
                user,
                EVENT_TYPES.REQUEST_NODE_UNLOCK,
                action="unlock",
                comment="unlock my node",
            ),
        )

    def test_display_status_shows_default_status(self):
        node = factory.make_Node()
        self.assertEqual(
            NODE_STATUS_CHOICES_DICT[node.status], node.display_status()
        )

    def test_display_memory_returns_decimal_less_than_1024(self):
        node = factory.make_Node(memory=512)
        self.assertEqual(0.5, node.display_memory())

    def test_display_memory_returns_value_divided_by_1024(self):
        node = factory.make_Node(memory=2560)
        self.assertEqual(2.5, node.display_memory())

    def test_physicalblockdevice_set_returns_physicalblockdevices(self):
        node = factory.make_Node(with_boot_disk=False)
        device = factory.make_PhysicalBlockDevice(node=node)
        factory.make_BlockDevice(node=node)
        factory.make_PhysicalBlockDevice()
        self.assertCountEqual([device], node.physicalblockdevice_set.all())

    def test_storage_returns_size_of_physical_blockdevices_in_mb(self):
        node = factory.make_Node(with_boot_disk=False)
        for _ in range(3):
            factory.make_PhysicalBlockDevice(node=node, size=50 * (1000**2))
        self.assertEqual(50 * 3, node.storage)

    def test_get_boot_disk_returns_set_boot_disk(self):
        node = factory.make_Node(with_boot_disk=False)
        # First disk.
        factory.make_PhysicalBlockDevice(node=node, bootable=True)
        boot_disk = factory.make_PhysicalBlockDevice(node=node, bootable=True)
        node.boot_disk = boot_disk
        node.save()
        self.assertEqual(boot_disk, node.get_boot_disk())

    def test_get_boot_disk_returns_first(self):
        node = factory.make_Node(with_boot_disk=False)
        boot_disk = factory.make_PhysicalBlockDevice(node=node, bootable=True)
        # Second disk.
        factory.make_PhysicalBlockDevice(node=node)
        factory.make_PhysicalBlockDevice(node=node)
        self.assertEqual(boot_disk, node.get_boot_disk())

    def test_get_boot_disk_returns_big_enough(self):
        node = factory.make_Node(with_boot_disk=False)
        factory.make_PhysicalBlockDevice(
            node=node, size=MIN_BOOT_PARTITION_SIZE / 2
        )
        boot_disk = factory.make_PhysicalBlockDevice(node=node, bootable=True)
        factory.make_PhysicalBlockDevice(node=node)
        self.assertEqual(boot_disk, node.get_boot_disk())

    def test_get_boot_disk_returns_None(self):
        node = factory.make_Node(with_boot_disk=False)
        self.assertIsNone(node.get_boot_disk())

    def test_get_bios_boot_method_returns_pxe(self):
        node = factory.make_Node(bios_boot_method="pxe")
        self.assertEqual("pxe", node.get_bios_boot_method())

    def test_get_bios_boot_method_returns_uefi(self):
        node = factory.make_Node(bios_boot_method="uefi")
        self.assertEqual("uefi", node.get_bios_boot_method())

    def test_get_bios_boot_method_returns_powernv(self):
        node = factory.make_Node(bios_boot_method="powernv")
        self.assertEqual("powernv", node.get_bios_boot_method())

    def test_get_bios_boot_method_returns_powerkvm(self):
        node = factory.make_Node(bios_boot_method="powerkvm")
        self.assertEqual("powerkvm", node.get_bios_boot_method())

    def test_get_bios_boot_method_returns_s390x_partition(self):
        node = factory.make_Node(bios_boot_method="s390x_partition")
        self.assertEqual("s390x_partition", node.get_bios_boot_method())

    def test_get_bios_boot_method_ipmi_efi_fallback(self):
        ipmi_efi = factory.make_BMC(
            power_type="ipmi",
            power_parameters={"power_boot_type": IPMI_BOOT_TYPE.EFI},
        )
        node = factory.make_Machine(bios_boot_method=None, bmc=ipmi_efi)
        self.assertEqual("uefi", node.get_bios_boot_method())

    def test_get_bios_boot_method_ipmi_auto_fallback(self):
        ipmi_efi = factory.make_BMC(
            power_type="ipmi",
            power_parameters={"power_boot_type": IPMI_BOOT_TYPE.DEFAULT},
        )
        node = factory.make_Machine(bios_boot_method=None, bmc=ipmi_efi)
        self.assertEqual(DEFAULT_BIOS_BOOT_METHOD, node.get_bios_boot_method())

    def test_get_bios_boot_method_no_bmc_fallback(self):
        node = factory.make_Node(bios_boot_method=None)
        node.bmc = None
        self.assertEqual(DEFAULT_BIOS_BOOT_METHOD, node.get_bios_boot_method())

    def test_get_bios_boot_method_ipmi_legacy_fallback(self):
        ipmi_efi = factory.make_BMC(
            power_type="ipmi",
            power_parameters={"power_boot_type": IPMI_BOOT_TYPE.LEGACY},
        )
        node = factory.make_Machine(bios_boot_method=None, bmc=ipmi_efi)
        self.assertEqual("pxe", node.get_bios_boot_method())

    def test_get_bios_boot_method_fallback_to_pxe(self):
        node = factory.make_Node(bios_boot_method=factory.make_name("boot"))
        self.assertEqual("pxe", node.get_bios_boot_method())

    def test_add_physical_interface(self):
        mac = factory.make_mac_address()
        node = factory.make_Node()
        node.add_physical_interface(mac)
        interfaces = PhysicalInterface.objects.filter(
            node_config=node.current_config, mac_address=mac
        ).count()
        self.assertEqual(1, interfaces)

    def test_add_physical_interface_link_numanode_machine(self):
        mac = factory.make_mac_address()
        node = factory.make_Node()
        node.add_physical_interface(mac)
        interface = PhysicalInterface.objects.get(
            node_config=node.current_config, mac_address=mac
        )
        self.assertIsNotNone(interface.numa_node)
        self.assertEqual(interface.numa_node, node.default_numanode)

    def test_add_physical_interface_link_numanode_device(self):
        mac = factory.make_mac_address()
        node = factory.make_Device()
        node.add_physical_interface(mac)
        interface = PhysicalInterface.objects.get(
            node_config=node.current_config, mac_address=mac
        )
        self.assertIsNone(interface.numa_node)

    def test_add_already_attached_mac_address_doesnt_raise_error(self):
        """Re-adding a MAC address should not fail"""
        node = factory.make_Node()
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        mac = str(interface.mac_address)
        added_interface = node.add_physical_interface(mac)
        self.assertEqual(added_interface, interface)

    def test_add_physical_interface_attached_another_node_raises_error(self):
        """Adding a MAC address that's already in use in another node should
        fail"""
        node1 = factory.make_Node()
        node2 = factory.make_Node()
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node2)
        mac = str(interface.mac_address)
        self.assertRaises(ValidationError, node1.add_physical_interface, mac)

    def test_add_physical_interface_adds_interface(self):
        mac = factory.make_mac_address()
        node = factory.make_Node()
        node.add_physical_interface(mac)
        ifaces = PhysicalInterface.objects.filter(mac_address=mac)
        self.assertEqual(1, ifaces.count())
        self.assertEqual("eth0", ifaces.first().name)

    def test_add_physical_interface_adds_interfaces(self):
        node = factory.make_Node()
        node.add_physical_interface(factory.make_mac_address())
        node.add_physical_interface(factory.make_mac_address())
        ifaces = PhysicalInterface.objects.all()
        self.assertEqual(2, ifaces.count())
        self.assertEqual(
            ["eth0", "eth1"],
            list(ifaces.order_by("id").values_list("name", flat=True)),
        )

    def test_add_physical_interface_adds_with_sequential_names(self):
        node = factory.make_Node()
        factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node, name="eth4000"
        )
        node.add_physical_interface(factory.make_mac_address())
        ifaces = PhysicalInterface.objects.all()
        self.assertEqual(2, ifaces.count())
        self.assertEqual(
            ["eth4000", "eth4001"],
            list(ifaces.order_by("id").values_list("name", flat=True)),
        )

    def test_add_physical_interface_removes_matching_unknown_interface(self):
        mac = factory.make_mac_address()
        factory.make_Interface(INTERFACE_TYPE.UNKNOWN, mac_address=mac)
        node = factory.make_Node()
        node.add_physical_interface(mac)
        interfaces = PhysicalInterface.objects.filter(mac_address=mac).count()
        self.assertEqual(1, interfaces)
        interfaces = UnknownInterface.objects.filter(mac_address=mac).count()
        self.assertEqual(0, interfaces)

    def test_get_metadata_empty(self):
        node = factory.make_Node()
        self.assertEqual({}, node.get_metadata())

    def test_get_metadata(self):
        node = factory.make_Node()
        factory.make_NodeMetadata(node=node, key="foo", value="bar")
        self.assertEqual({"foo": "bar"}, node.get_metadata())

    def test_get_osystem_returns_default_osystem(self):
        node = factory.make_Node(osystem="")
        osystem = Config.objects.get_config("default_osystem")
        self.assertEqual(osystem, node.get_osystem())

    def test_get_osystem_returns_passed_default(self):
        node = factory.make_Node(osystem="")
        default = factory.make_name("default")
        self.assertEqual(default, node.get_osystem(default=default))

    def test_get_distro_series_returns_default_series(self):
        node = factory.make_Node(distro_series="")
        series = Config.objects.get_config("default_distro_series")
        self.assertEqual(series, node.get_distro_series())

    def test_get_distro_series_returns_passed_default(self):
        node = factory.make_Node(osystem="")
        default = factory.make_name("default")
        self.assertEqual(default, node.get_distro_series(default=default))

    def test_get_effective_license_key_returns_node_value(self):
        license_key = factory.make_name("license_key")
        node = factory.make_Node(license_key=license_key)
        self.assertEqual(license_key, node.get_effective_license_key())

    def test_get_effective_license_key_returns_blank(self):
        node = factory.make_Node()
        self.assertEqual("", node.get_effective_license_key())

    def test_get_effective_license_key_returns_global(self):
        license_key = factory.make_name("license_key")
        osystem = factory.make_name("os")
        series = factory.make_name("series")
        LicenseKey.objects.create(
            osystem=osystem, distro_series=series, license_key=license_key
        )
        node = factory.make_Node(osystem=osystem, distro_series=series)
        self.assertEqual(license_key, node.get_effective_license_key())

    def test_get_effective_special_filesystems_acquired(self):
        node = factory.make_Node(status=NODE_STATUS.DEPLOYED)
        filesystem = factory.make_Filesystem(
            node_config=node.current_config, fstype="tmpfs", acquired=True
        )
        factory.make_Filesystem(
            node_config=node.current_config, fstype="tmpfs", acquired=False
        )
        self.assertCountEqual(
            node.get_effective_special_filesystems(), [filesystem]
        )

    def test_get_effective_special_filesystems_acquired_prev(self):
        node = factory.make_Node(
            status=NODE_STATUS.RESCUE_MODE,
            previous_status=NODE_STATUS.DEPLOYED,
        )
        filesystem = factory.make_Filesystem(
            node_config=node.current_config, fstype="tmpfs", acquired=True
        )
        factory.make_Filesystem(
            node_config=node.current_config, fstype="tmpfs", acquired=False
        )
        self.assertCountEqual(
            node.get_effective_special_filesystems(), [filesystem]
        )

    def test_get_effective_special_filesystems_not_acquired(self):
        node = factory.make_Node(status=NODE_STATUS.READY)
        factory.make_Filesystem(
            node_config=node.current_config, fstype="tmpfs", acquired=True
        )
        filesystem = factory.make_Filesystem(
            node_config=node.current_config, fstype="tmpfs", acquired=False
        )
        self.assertCountEqual(
            node.get_effective_special_filesystems(), [filesystem]
        )

    def test_get_effective_special_filesystems_not_acquired_prev(self):
        node = factory.make_Node(
            status=NODE_STATUS.RESCUE_MODE,
            previous_status=NODE_STATUS.ALLOCATED,
        )
        factory.make_Filesystem(
            node_config=node.current_config, fstype="tmpfs", acquired=True
        )
        filesystem = factory.make_Filesystem(
            node_config=node.current_config, fstype="tmpfs", acquired=False
        )
        self.assertCountEqual(
            node.get_effective_special_filesystems(), [filesystem]
        )

    # Deleting Node deletes BMC. Regression for lp:1586555.
    def test_delete_node_deletes_owned_bmc(self):
        node = factory.make_Node()
        bmc = factory.make_BMC(
            power_type="virsh",
            power_parameters={
                "power_address": "protocol://%s:8080/path/to/thing#tag"
                % (factory.make_ipv4_address())
            },
        )
        node.bmc = bmc
        node.save()
        node.delete()
        self.assertIsNone(reload_object(bmc))

    # Deleting Node deletes BMC. Regression for lp:1586555.
    def test_delete_node_doesnt_delete_shared_bmc(self):
        bmc = factory.make_BMC(
            power_type="virsh",
            power_parameters={
                "power_address": "protocol://%s:8080/path/to/thing#tag"
                % (factory.make_ipv4_address())
            },
        )
        nodes = [factory.make_Node(bmc=bmc), factory.make_Node(bmc=bmc)]
        # Shouldn't delete BMC, as 2nd node is still using it.
        nodes[0].delete()
        self.assertIsNotNone(reload_object(bmc))
        # Should now delete BMC, as nobody else is using it.
        nodes[1].delete()
        self.assertIsNone(reload_object(bmc))

    def test_delete_node_doesnt_delete_pod(self):
        node = factory.make_Node()
        pod = factory.make_Pod()
        node.bmc = pod
        node.save()
        node.delete()
        self.assertIsNotNone(reload_object(pod))

    def test_delete_node_deletes_related_interface(self):
        node = factory.make_Node()
        interface = node.add_physical_interface("AA:BB:CC:DD:EE:FF")
        ip = factory.make_StaticIPAddress(interface=interface)
        node.delete()
        self.assertIsNone(reload_object(interface))
        self.assertIsNone(reload_object(ip))

    def test_can_delete_allocated_node(self):
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED)
        system_id = node.system_id
        node.delete()
        self.assertCountEqual([], Node.objects.filter(system_id=system_id))

    def test_delete_nodeconfig_doesnt_delete_referenced_ips(self):
        node = factory.make_Node()
        node_config = factory.make_NodeConfig(
            node=node,
            name=NODE_CONFIG_TYPE.DEPLOYMENT,
        )
        iface1 = factory.make_Interface(node_config=node.current_config)
        iface2 = factory.make_Interface(node_config=node_config)
        iface3 = factory.make_Interface(node_config=node_config)
        ip1 = factory.make_StaticIPAddress(interface=iface1)
        ip1.interface_set.add(iface2)
        ip2 = factory.make_StaticIPAddress(interface=iface3)
        node_config.delete()
        self.assertIsNotNone(reload_object(ip1))
        self.assertIsNone(reload_object(ip2))

    def test_delete_deletes_node_secrets(self):
        node = factory.make_Node()
        secret_manager = SecretManager()
        secret_manager.set_simple_secret(
            "deploy-metadata", {"foo": "bar"}, obj=node
        )
        node.delete()
        self.assertIsNone(
            secret_manager.get_simple_secret(
                "deploy-metadata", obj=node, default=None
            )
        )

    def test_set_random_hostname_set_hostname(self):
        node = factory.make_Node()
        original_hostname = node.hostname
        node.set_random_hostname()
        self.assertNotEqual(original_hostname, node.hostname)
        self.assertNotEqual("", node.hostname)

    def test_get_effective_power_type_raises_if_not_set(self):
        node = factory.make_Node(power_type=None)
        self.assertRaises(UnknownPowerType, node.get_effective_power_type)

    def test_get_effective_power_type_reads_node_field(self):
        power_type = factory.pick_choice(get_driver_choices())
        node = factory.make_Node(power_type=power_type)
        self.assertEqual(power_type, node.get_effective_power_type())

    def test_get_effective_power_parameters_returns_power_parameters(self):
        params = {"test_parameter": factory.make_string()}
        node = factory.make_Node(power_parameters=params)
        self.assertEqual(
            params["test_parameter"],
            node.get_effective_power_parameters()["test_parameter"],
        )

    def test_get_effective_power_parameters_adds_system_id(self):
        node = factory.make_Node()
        self.assertEqual(
            node.system_id, node.get_effective_power_parameters()["system_id"]
        )

    def test_get_effective_power_parameters_adds_no_mac_if_params_set(self):
        node = factory.make_Node(power_parameters={"foo": "bar"})
        mac = factory.make_mac_address()
        node.add_physical_interface(mac)
        self.assertNotIn("mac", node.get_effective_power_parameters())

    def test_get_effective_power_type_no_default_power_address_if_not_virsh(
        self,
    ):
        node = factory.make_Node(power_type="manual")
        params = node.get_effective_power_parameters()
        self.assertEqual(None, params.get("power_address"))

    def test_get_effective_power_type_defaults_power_address_if_virsh(self):
        node = factory.make_Node(power_type="virsh")
        params = node.get_effective_power_parameters()
        self.assertEqual("qemu://localhost/system", params["power_address"])

    def test_get_effective_power_parameters_sets_local_boot_mode(self):
        node = factory.make_Node(status=NODE_STATUS.DEPLOYED, power_type="amt")
        params = node.get_effective_power_parameters()
        self.assertEqual("local", params["boot_mode"])

    def test_get_effective_power_parameters_sets_pxe_boot_mode(self):
        status = factory.pick_enum(NODE_STATUS, but_not=[NODE_STATUS.DEPLOYED])
        node = factory.make_Node(status=status, power_type="amt")
        params = node.get_effective_power_parameters()
        self.assertEqual("pxe", params["boot_mode"])

    def test_get_effective_power_info_is_False_for_unset_power_type(self):
        node = factory.make_Node(power_type=None)
        self.assertEqual(
            (False, False, False, False, None, None),
            node.get_effective_power_info(),
        )

    def test_get_effective_power_info_is_True_for_set_power_type(self):
        node = factory.make_Node(power_type=factory.make_name("pwr"))
        gepp = self.patch(node, "get_effective_power_parameters")
        gepp.return_value = sentinel.power_parameters
        self.assertEqual(
            PowerInfo(
                True,
                True,
                False,
                False,
                node.power_type,
                sentinel.power_parameters,
            ),
            node.get_effective_power_info(),
        )

    def test_get_effective_power_info_can_be_False_for_manual(self):
        node = factory.make_Node(power_type="manual")
        gepp = self.patch(node, "get_effective_power_parameters")
        # For manual the power can never be turned off or on.
        gepp.return_value = {}
        self.assertEqual(
            (False, False, False, False, "manual", {}),
            node.get_effective_power_info(),
        )

    def test_get_effective_power_info_can_be_False_for_rack_controller(self):
        for node_type in (
            NODE_TYPE.REGION_AND_RACK_CONTROLLER,
            NODE_TYPE.REGION_CONTROLLER,
        ):
            node = factory.make_Node(node_type=node_type)
            gepp = self.patch(node, "get_effective_power_parameters")
            # For manual the power can never be turned off or on.
            gepp.return_value = sentinel.power_parameters
            self.assertEqual(
                (
                    False,
                    False,
                    True,
                    False,
                    node.power_type,
                    sentinel.power_parameters,
                ),
                node.get_effective_power_info(),
            )

    def test_get_effective_power_info_cant_be_queried(self):
        uncontrolled_power_types = [
            driver.name
            for _, driver in PowerDriverRegistry
            if not driver.queryable
        ]
        for power_type in uncontrolled_power_types:
            node = factory.make_Node(power_type=power_type)
            gepp = self.patch(node, "get_effective_power_parameters")
            self.assertEqual(
                PowerInfo(
                    power_type != "manual",
                    power_type != "manual",
                    False,
                    False,
                    power_type,
                    gepp(),
                ),
                node.get_effective_power_info(),
            )

    def test_get_effective_power_info_can_be_queried(self):
        power_driver = random.choice(
            [driver for _, driver in PowerDriverRegistry if driver.queryable]
        )
        node = factory.make_Node(power_type=power_driver.name)
        gepp = self.patch(node, "get_effective_power_parameters")
        self.assertEqual(
            PowerInfo(
                True,
                power_driver.name != "manual",
                True,
                power_driver.can_set_boot_order,
                power_driver.name,
                gepp(),
            ),
            node.get_effective_power_info(),
        )

    def test_get_effective_power_info_returns_named_tuple(self):
        node = factory.make_Node(power_type="manual")
        gepp = self.patch(node, "get_effective_power_parameters")
        gepp.return_value = {}
        self.assertThat(
            node.get_effective_power_info(),
            MatchesStructure.byEquality(
                can_be_started=False,
                can_be_stopped=False,
                can_be_queried=False,
                can_set_boot_order=False,
                power_type="manual",
                power_parameters={},
            ),
        )

    def test_get_boot_order_network(self):
        node = factory.make_Node(with_boot_disk=False, power_type="hmcz")
        interfaces = [factory.make_Interface(node=node) for _ in range(5)]
        block_devices = [
            factory.make_PhysicalBlockDevice(node=node) for _ in range(5)
        ]
        node.boot_interface = random.choice(interfaces)
        node.boot_disk = random.choice(block_devices)
        node.save()

        expected_boot_order = [node.boot_interface.serialize()]
        expected_boot_order += [
            iface.serialize()
            for iface in interfaces
            if iface.id != node.boot_interface.id
        ]
        expected_boot_order += [node.boot_disk.serialize()]
        expected_boot_order += [
            bd.serialize()
            for bd in block_devices
            if bd.id != node.boot_disk.id
        ]

        self.assertEqual(expected_boot_order, node._get_boot_order(True))

    def test_get_boot_order_local(self):
        node = factory.make_Node(with_boot_disk=False, power_type="hmcz")
        interfaces = [factory.make_Interface(node=node) for _ in range(5)]
        block_devices = [
            factory.make_PhysicalBlockDevice(node=node) for _ in range(5)
        ]
        node.boot_interface = random.choice(interfaces)
        node.boot_disk = random.choice(block_devices)
        node.save()

        expected_boot_order = [node.boot_disk.serialize()]
        expected_boot_order += [
            bd.serialize()
            for bd in block_devices
            if bd.id != node.boot_disk.id
        ]
        expected_boot_order += [node.boot_interface.serialize()]
        expected_boot_order += [
            iface.serialize()
            for iface in interfaces
            if iface.id != node.boot_interface.id
        ]

        self.assertEqual(expected_boot_order, node._get_boot_order(False))

    def test_get_boot_order_network_no_boot_devices_set(self):
        node = factory.make_Node(with_boot_disk=False, power_type="hmcz")
        interfaces = [factory.make_Interface(node=node) for _ in range(5)]
        block_devices = [
            factory.make_PhysicalBlockDevice(node=node) for _ in range(5)
        ]

        self.assertEqual(
            [obj.serialize() for obj in interfaces + block_devices],
            node._get_boot_order(True),
        )

    def test_get_boot_order_local_no_boot_devices_set(self):
        node = factory.make_Node(with_boot_disk=False, power_type="hmcz")
        interfaces = [factory.make_Interface(node=node) for _ in range(5)]
        block_devices = [
            factory.make_PhysicalBlockDevice(node=node) for _ in range(5)
        ]

        self.assertEqual(
            [obj.serialize() for obj in block_devices + interfaces],
            node._get_boot_order(False),
        )

    def test_get_boot_order_auto_ephemeral(self):
        node = factory.make_Node(
            with_boot_disk=False, ephemeral_deploy=True, power_type="hmcz"
        )
        interfaces = [factory.make_Interface(node=node) for _ in range(5)]
        block_devices = [
            factory.make_PhysicalBlockDevice(node=node) for _ in range(5)
        ]

        self.assertEqual(
            [obj.serialize() for obj in interfaces + block_devices],
            node._get_boot_order(),
        )

    def test_get_boot_order_auto_exiting_rescue_mode(self):
        node = factory.make_Node(
            with_boot_disk=False,
            power_type="hmcz",
            status=NODE_STATUS.EXITING_RESCUE_MODE,
            previous_status=NODE_STATUS.FAILED_COMMISSIONING,
        )
        interfaces = [factory.make_Interface(node=node) for _ in range(5)]
        block_devices = [
            factory.make_PhysicalBlockDevice(node=node) for _ in range(5)
        ]

        self.assertEqual(
            [obj.serialize() for obj in interfaces + block_devices],
            node._get_boot_order(),
        )

    def test_get_boot_order_auto_exiting_rescue_mode_deployed(self):
        node = factory.make_Node(
            with_boot_disk=False,
            power_type="hmcz",
            status=NODE_STATUS.EXITING_RESCUE_MODE,
            previous_status=NODE_STATUS.DEPLOYED,
        )
        interfaces = [factory.make_Interface(node=node) for _ in range(5)]
        block_devices = [
            factory.make_PhysicalBlockDevice(node=node) for _ in range(5)
        ]

        self.assertEqual(
            [obj.serialize() for obj in block_devices + interfaces],
            node._get_boot_order(),
        )

    def test_get_boot_order_auto_deployed(self):
        node = factory.make_Node(
            with_boot_disk=False,
            power_type="hmcz",
            status=NODE_STATUS.DEPLOYED,
        )
        interfaces = [factory.make_Interface(node=node) for _ in range(5)]
        block_devices = [
            factory.make_PhysicalBlockDevice(node=node) for _ in range(5)
        ]

        self.assertEqual(
            [obj.serialize() for obj in block_devices + interfaces],
            node._get_boot_order(),
        )

    def test_get_boot_order_auto_not_deployed(self):
        node = factory.make_Node(
            with_boot_disk=False,
            power_type="hmcz",
            status=factory.pick_choice(
                NODE_STATUS_CHOICES, but_not=[NODE_STATUS.DEPLOYED]
            ),
        )
        interfaces = [factory.make_Interface(node=node) for _ in range(5)]
        block_devices = [
            factory.make_PhysicalBlockDevice(node=node) for _ in range(5)
        ]

        self.assertEqual(
            [obj.serialize() for obj in interfaces + block_devices],
            node._get_boot_order(),
        )

    def test_set_boot_order(self):
        node = factory.make_Node(interface=True, power_type="hmcz")
        mock_power_control_node = self.patch(node, "_power_control_node")
        mock_power_control_node.return_value = defer.succeed(None)
        network_boot = factory.pick_bool()

        node.set_boot_order(network_boot)

        mock_power_control_node.assert_called_with(
            ANY,
            None,
            node.get_effective_power_info(),
            node._get_boot_order(network_boot),
        )
        self.assertTrue(mock_power_control_node.return_value.called)

    def test_set_boot_order_does_nothing_if_unsupported(self):
        node = factory.make_Node(interface=True, power_type="manual")
        mock_power_control_node = self.patch(node, "_power_control_node")

        node.set_boot_order(factory.pick_bool())

        mock_power_control_node.assert_not_called()

    def test_get_effective_kernel_options_with_nothing_set(self):
        node = factory.make_Node()
        self.assertEqual(node.get_effective_kernel_options(), "")

    def test_get_effective_kernel_options_not_confused_by_None_opts(self):
        node = factory.make_Node()
        tag = factory.make_Tag()
        node.tags.add(tag)
        kernel_opts = factory.make_string()
        self.assertEqual(
            node.get_effective_kernel_options(default_kernel_opts=kernel_opts),
            kernel_opts,
        )

    def test_get_effective_kernel_options_not_confused_by_empty_str_opts(self):
        node = factory.make_Node()
        tag = factory.make_Tag(kernel_opts="")
        node.tags.add(tag)
        kernel_opts = factory.make_string()
        self.assertEqual(
            node.get_effective_kernel_options(default_kernel_opts=kernel_opts),
            kernel_opts,
        )

    def test_get_effective_kernel_options_multiple_tags_with_opts(self):
        node = factory.make_Node()
        node.tags.add(factory.make_Tag("tag_a"))
        node.tags.add(factory.make_Tag("tag_b", kernel_opts=""))
        tag_c = factory.make_Tag("tag_c", kernel_opts="bacon-n-eggs")
        tag_d = factory.make_Tag("tag_d", kernel_opts="foo-bar")
        node.tags.add(tag_c)
        node.tags.add(tag_d)
        self.assertEqual(
            node.get_effective_kernel_options(), "bacon-n-eggs foo-bar"
        )

    def test_get_effective_kernel_options_ignores_unassociated_tag_value(self):
        node = factory.make_Node()
        factory.make_Tag(kernel_opts=factory.make_string())
        self.assertEqual(node.get_effective_kernel_options(), "")

    def test_get_effective_kernel_options_uses_tag_value(self):
        node = factory.make_Node()
        tag = factory.make_Tag(kernel_opts=factory.make_string())
        node.tags.add(tag)
        self.assertEqual(node.get_effective_kernel_options(), tag.kernel_opts)

    def test_get_effective_kernel_options_tag_includes_default(self):
        node = factory.make_Node()
        default_opts = factory.make_string()
        tag = factory.make_Tag(kernel_opts=factory.make_string())
        node.tags.add(tag)
        self.assertEqual(
            node.get_effective_kernel_options(
                default_kernel_opts=default_opts
            ),
            f"{default_opts} {tag.kernel_opts}",
        )

    def test_acquire(self):
        node = factory.make_Node(status=NODE_STATUS.READY, with_boot_disk=True)
        user = factory.make_User()
        agent_name = factory.make_name("agent-name")
        node.acquire(user, agent_name)
        self.assertEqual(
            (user, NODE_STATUS.ALLOCATED, agent_name),
            (node.owner, node.status, node.agent_name),
        )

    def test_acquire_calls__create_acquired_filesystems(self):
        node = factory.make_Node(status=NODE_STATUS.READY, with_boot_disk=True)
        user = factory.make_User()
        agent_name = factory.make_name("agent-name")
        mock_create_acquired_filesystems = self.patch_autospec(
            node, "_create_acquired_filesystems"
        )
        node.acquire(user, agent_name)
        self.assertThat(mock_create_acquired_filesystems, MockCalledOnceWith())

    def test_acquire_logs_user_request(self):
        node = factory.make_Node(status=NODE_STATUS.READY, with_boot_disk=True)
        user = factory.make_User()
        agent_name = factory.make_name("agent-name")
        register_event = self.patch(node, "_register_request_event")
        node.acquire(user, agent_name)
        self.assertThat(
            register_event,
            MockCalledOnceWith(
                user,
                EVENT_TYPES.REQUEST_NODE_ACQUIRE,
                action="acquire",
                comment=None,
            ),
        )

    def test_acquire_calls__create_acquired_bridges(self):
        node = factory.make_Node(status=NODE_STATUS.READY, with_boot_disk=True)
        user = factory.make_User()
        agent_name = factory.make_name("agent-name")
        mock_create_acquired_bridges = self.patch_autospec(
            node, "_create_acquired_bridges"
        )
        bridge_type = factory.pick_choice(BRIDGE_TYPE_CHOICES)
        bridge_stp = factory.pick_bool()
        bridge_fd = random.randint(0, 500)
        node.acquire(
            user,
            agent_name,
            bridge_all=True,
            bridge_type=bridge_type,
            bridge_stp=bridge_stp,
            bridge_fd=bridge_fd,
        )
        self.assertThat(
            mock_create_acquired_bridges,
            MockCalledOnceWith(
                bridge_type=bridge_type,
                bridge_stp=bridge_stp,
                bridge_fd=bridge_fd,
            ),
        )

    def test_set_default_storage_layout_does_nothing_if_skip_storage(self):
        node = factory.make_Node(skip_storage=True)
        mock_set_storage_layout = self.patch(node, "set_storage_layout")
        node.set_default_storage_layout()
        mock_set_storage_layout.assert_not_called()
        self.assertEqual(node.last_applied_storage_layout, "")

    def test_set_default_storage_layout_uses_default(self):
        node = factory.make_Node()
        default_layout = Config.objects.get_config("default_storage_layout")
        mock_set_storage_layout = self.patch(node, "set_storage_layout")
        node.set_default_storage_layout()
        mock_set_storage_layout.assert_called_once_with(default_layout)

    def test_set_default_storage_layout_logs_error_missing_boot_disk(self):
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED)
        mock_get_layout = self.patch(
            node_module, "get_storage_layout_for_node"
        )
        maaslog = self.patch(node_module, "maaslog")
        layout_object = MagicMock()
        layout_object.configure.side_effect = (
            StorageLayoutMissingBootDiskError()
        )
        mock_get_layout.return_value = layout_object
        node.set_default_storage_layout()
        self.assertThat(
            maaslog.error,
            MockCalledOnceWith(
                "%s: Unable to set any default storage layout because "
                "it has no writable disks.",
                node.hostname,
            ),
        )

    def test_set_default_storage_layout_logs_error_when_layout_fails(self):
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED)
        mock_get_layout = self.patch(
            node_module, "get_storage_layout_for_node"
        )
        maaslog = self.patch(node_module, "maaslog")
        layout_object = MagicMock()
        exception = StorageLayoutError(factory.make_name("error"))
        layout_object.configure.side_effect = exception
        mock_get_layout.return_value = layout_object
        node.set_default_storage_layout()
        self.assertThat(
            maaslog.error,
            MockCalledOnceWith(
                "%s: Failed to configure storage layout: %s",
                node.hostname,
                exception,
            ),
        )

    def test_set_storage_layout_calls_configure_on_layout(self):
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED)
        mock_get_layout = self.patch(
            node_module, "get_storage_layout_for_node"
        )
        layout_object = MagicMock()
        mock_get_layout.return_value = layout_object
        layout_object.configure.return_value = "used-layout"
        allow_fallback = factory.pick_bool()
        node.set_storage_layout(
            "foo-layout", sentinel.params, allow_fallback=allow_fallback
        )
        mock_get_layout.assert_called_once_with(
            "foo-layout",
            node,
            params=sentinel.params,
        )
        layout_object.configure.assert_called_once_with(
            allow_fallback=allow_fallback,
        )
        self.assertEqual(node.last_applied_storage_layout, "used-layout")

    def test_set_storage_layout_logs_success(self):
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED)
        mock_get_layout = self.patch(
            node_module, "get_storage_layout_for_node"
        )
        maaslog = self.patch(node_module, "maaslog")
        used_layout = factory.make_name("layout")
        layout_object = MagicMock()
        layout_object.configure.return_value = used_layout
        mock_get_layout.return_value = layout_object
        node.set_storage_layout("foo-layout", sentinel.params)
        maaslog.info.assert_called_once_with(
            f"{node.hostname}: Storage layout was set to {used_layout}."
        )
        self.assertEqual(node.last_applied_storage_layout, used_layout)

    def test_set_storage_layout_raises_error_when_unknown_layout(self):
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED)
        mock_get_layout = self.patch(
            node_module, "get_storage_layout_for_node"
        )
        mock_get_layout.return_value = None
        unknown_layout = factory.make_name("layout")
        with ExpectedException(StorageLayoutError):
            node.set_storage_layout(unknown_layout, sentinel.params)

    def test_start_ephemeral_checks_image_is_avail(self):
        owner = factory.make_User()
        node = factory.make_Node(
            status=random.choice(COMMISSIONING_LIKE_STATUSES), owner=owner
        )
        self.assertRaises(ValidationError, node._start, owner)

    def test_start_disk_erasing_uses_global_values(self):
        agent_name = factory.make_name("agent-name")
        owner = factory.make_User()
        node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=owner, agent_name=agent_name
        )
        node_start = self.patch(node, "_start")
        # Return a post-commit hook from Node.start().
        node_start.side_effect = lambda *args, **kwargs: post_commit()
        Config.objects.set_config("disk_erase_with_secure_erase", True)
        Config.objects.set_config("disk_erase_with_quick_erase", True)
        with post_commit_hooks:
            node.start_disk_erasing(owner)
        # Extract the user_data from the start call.
        user_data = node_start.call_args[0][1]
        parsed_data = email.message_from_string(user_data.decode("utf-8"))
        user_data_script = parsed_data.get_payload()[0]
        self.assertIn(
            b"maas-wipe --secure-erase --quick-erase",
            base64.b64decode(user_data_script.get_payload()),
        )

    def test_start_disk_erasing_uses_passed_values(self):
        agent_name = factory.make_name("agent-name")
        owner = factory.make_User()
        node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=owner, agent_name=agent_name
        )
        node_start = self.patch(node, "_start")
        # Return a post-commit hook from Node.start().
        node_start.side_effect = lambda *args, **kwargs: post_commit()
        Config.objects.set_config("disk_erase_with_secure_erase", False)
        Config.objects.set_config("disk_erase_with_quick_erase", False)
        with post_commit_hooks:
            node.start_disk_erasing(owner, secure_erase=True, quick_erase=True)
        # Extract the user_data from the start call.
        user_data = node_start.call_args[0][1]
        parsed_data = email.message_from_string(user_data.decode("utf-8"))
        user_data_script = parsed_data.get_payload()[0]
        self.assertIn(
            b"maas-wipe --secure-erase --quick-erase",
            base64.b64decode(user_data_script.get_payload()),
        )

    def test_start_disk_erasing_changes_state_and_starts_node(self):
        agent_name = factory.make_name("agent-name")
        owner = factory.make_User()
        node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=owner, agent_name=agent_name
        )
        node_start = self.patch(node, "_start")
        # Return a post-commit hook from Node.start().
        node_start.side_effect = lambda *args, **kwargs: post_commit()
        config = Config.objects.get_configs(
            [
                "commissioning_osystem",
                "commissioning_distro_series",
                "default_osystem",
                "default_distro_series",
                "disk_erase_with_secure_erase",
                "disk_erase_with_quick_erase",
            ]
        )
        with post_commit_hooks:
            node.start_disk_erasing(owner)
        self.expectThat(node.owner, Equals(owner))
        self.expectThat(node.status, Equals(NODE_STATUS.DISK_ERASING))
        self.expectThat(node.agent_name, Equals(agent_name))
        self.assertThat(
            node_start,
            MockCalledOnceWith(
                owner,
                ANY,
                NODE_STATUS.ALLOCATED,
                allow_power_cycle=True,
                config=config,
            ),
        )

    def test_start_disk_erasing_logs_user_request(self):
        owner = factory.make_User()
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED, owner=owner)
        node_start = self.patch(node, "_start")
        # Return a post-commit hook from Node.start().
        node_start.side_effect = lambda *args, **kwargs: post_commit()
        config = Config.objects.get_configs(
            [
                "commissioning_osystem",
                "commissioning_distro_series",
                "default_osystem",
                "default_distro_series",
                "disk_erase_with_secure_erase",
                "disk_erase_with_quick_erase",
            ]
        )
        register_event = self.patch(node, "_register_request_event")
        with post_commit_hooks:
            node.start_disk_erasing(owner)
        self.assertThat(
            node_start,
            MockCalledOnceWith(
                owner,
                ANY,
                NODE_STATUS.ALLOCATED,
                allow_power_cycle=True,
                config=config,
            ),
        )
        self.assertThat(
            register_event,
            MockCalledOnceWith(
                owner,
                EVENT_TYPES.REQUEST_NODE_ERASE_DISK,
                action="start disk erasing",
                comment=None,
            ),
        )

    def test_abort_disk_erasing_changes_state_and_stops_node(self):
        agent_name = factory.make_name("agent-name")
        owner = factory.make_User()
        node = factory.make_Node(
            status=NODE_STATUS.DISK_ERASING, owner=owner, agent_name=agent_name
        )
        node_stop = self.patch(node, "_stop")
        # Return a post-commit hook from Node.stop().
        node_stop.side_effect = lambda user: post_commit()
        self.patch(Node, "_set_status")

        with post_commit_hooks:
            node.abort_disk_erasing(owner)

        self.assertThat(node_stop, MockCalledOnceWith(owner))
        self.assertThat(
            node._set_status,
            MockCalledOnceWith(
                node.system_id, status=NODE_STATUS.FAILED_DISK_ERASING
            ),
        )

        # Neither the owner nor the agent has been changed.
        node = reload_object(node)
        self.expectThat(node.owner, Equals(owner))
        self.expectThat(node.agent_name, Equals(agent_name))

    def test_abort_disk_erasing_logs_user_request_and_creates_sts_msg(self):
        owner = factory.make_User()
        node = factory.make_Node(status=NODE_STATUS.DISK_ERASING, owner=owner)
        node_stop = self.patch(node, "_stop")
        # Return a post-commit hook from Node.stop().
        node_stop.side_effect = lambda user: post_commit()
        self.patch(Node, "_set_status")
        with post_commit_hooks:
            node.abort_disk_erasing(owner)
        events = Event.objects.filter(node=node).order_by("id")
        self.assertEqual(
            events[0].type.name, EVENT_TYPES.REQUEST_NODE_ABORT_ERASE_DISK
        )
        self.assertEqual(events[1].type.name, EVENT_TYPES.ABORTED_DISK_ERASING)

    def test_start_disk_erasing_reverts_to_sane_state_on_error(self):
        # If start_disk_erasing encounters an error when calling start(), it
        # will transition the node to a sane state. Failures encountered in
        # one call to start_disk_erasing() won't affect subsequent calls.
        self.disable_node_query()
        admin = factory.make_admin()
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED)
        generate_user_data_for_status = self.patch(
            node_module, "generate_user_data_for_status"
        )
        node_start = self.patch(node, "_start")
        node_start.side_effect = factory.make_exception()
        config = Config.objects.get_configs(
            [
                "commissioning_osystem",
                "commissioning_distro_series",
                "default_osystem",
                "default_distro_series",
                "disk_erase_with_secure_erase",
                "disk_erase_with_quick_erase",
            ]
        )

        try:
            with transaction.atomic():
                node.start_disk_erasing(admin)
        except node_start.side_effect.__class__:
            # We don't care about the error here, so suppress it. It
            # exists only to cause the transaction to abort.
            pass

        self.assertThat(
            node_start,
            MockCalledOnceWith(
                admin,
                generate_user_data_for_status.return_value,
                NODE_STATUS.ALLOCATED,
                allow_power_cycle=True,
                config=config,
            ),
        )
        self.assertEqual(NODE_STATUS.FAILED_DISK_ERASING, node.status)

    def test_start_disk_erasing_sets_status_on_post_commit_error(self):
        # When start_disk_erasing encounters an error in its post-commit hook,
        # it will set the node's status to FAILED_DISK_ERASING.
        admin = factory.make_admin()
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED)
        # Patch out some things that we don't want to do right now.
        self.patch(node, "_start").return_value = None
        # Fake an error during the post-commit hook.
        error_message = factory.make_name("error")
        error_type = factory.make_exception_type()
        _start_async = self.patch_autospec(node, "_start_disk_erasing_async")
        _start_async.side_effect = error_type(error_message)
        # Capture calls to _set_status.
        self.patch_autospec(Node, "_set_status")

        with LoggerFixture("maas") as logger:
            with ExpectedException(error_type):
                with post_commit_hooks:
                    node.start_disk_erasing(admin)

        # The status is set to be reverted to its initial status.
        self.assertThat(
            node._set_status,
            MockCalledOnceWith(
                node.system_id, status=NODE_STATUS.FAILED_DISK_ERASING
            ),
        )
        # It's logged too.
        self.assertThat(
            logger.output,
            Contains(
                "%s: Could not start node for disk erasure: %s\n"
                % (node.hostname, error_message)
            ),
        )

    def test_start_disk_erasing_logs_and_raises_errors_in_starting(self):
        self.disable_node_query()
        admin = factory.make_admin()
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED)
        maaslog = self.patch(node_module, "maaslog")
        exception_type = factory.make_exception_type()
        exception = exception_type(factory.make_name())
        self.patch(node, "_start").side_effect = exception
        self.assertRaises(exception_type, node.start_disk_erasing, admin)
        self.assertEqual(NODE_STATUS.FAILED_DISK_ERASING, node.status)
        self.assertThat(
            maaslog.error,
            MockCalledOnceWith(
                "%s: Could not start node for disk erasure: %s",
                node.hostname,
                exception,
            ),
        )

    def test_abort_operation_aborts_commissioning(self):
        agent_name = factory.make_name("agent-name")
        user = factory.make_admin()
        node = factory.make_Node(
            status=NODE_STATUS.COMMISSIONING, agent_name=agent_name
        )
        abort_commissioning = self.patch_autospec(node, "abort_commissioning")
        node.abort_operation(user)
        self.assertThat(abort_commissioning, MockCalledOnceWith(user, None))

    def test_abort_operation_aborts_disk_erasing(self):
        agent_name = factory.make_name("agent-name")
        owner = factory.make_User()
        node = factory.make_Node(
            status=NODE_STATUS.DISK_ERASING, owner=owner, agent_name=agent_name
        )
        abort_disk_erasing = self.patch_autospec(node, "abort_disk_erasing")
        node.abort_operation(owner)
        self.assertThat(abort_disk_erasing, MockCalledOnceWith(owner, None))

    def test_abort_operation_aborts_deployment(self):
        agent_name = factory.make_name("agent-name")
        user = factory.make_admin()
        node = factory.make_Node(
            status=NODE_STATUS.DEPLOYING, agent_name=agent_name
        )
        abort_deploying = self.patch_autospec(node, "abort_deploying")
        node.abort_operation(user)
        self.assertThat(abort_deploying, MockCalledOnceWith(user, None))

    def test_abort_operation_aborts_testing(self):
        agent_name = factory.make_name("agent-name")
        user = factory.make_admin()
        node = factory.make_Node(
            status=NODE_STATUS.TESTING, agent_name=agent_name
        )
        abort_testing = self.patch_autospec(node, "abort_testing")
        node.abort_operation(user)
        self.assertThat(abort_testing, MockCalledOnceWith(user, None))

    def test_abort_deployment_logs_user_request_and_creates_sts_msg(self):
        agent_name = factory.make_name("agent-name")
        admin = factory.make_admin()
        node = factory.make_Node(
            status=NODE_STATUS.DEPLOYING, agent_name=agent_name
        )
        self.patch(Node, "_clear_status_expires")
        self.patch(Node, "_set_status")
        self.patch(Node, "_stop").return_value = None
        with post_commit_hooks:
            node.abort_deploying(admin)
        events = Event.objects.filter(node=node).order_by("id")
        self.assertEqual(
            events[0].type.name, EVENT_TYPES.REQUEST_NODE_ABORT_DEPLOYMENT
        )
        self.assertEqual(events[1].type.name, EVENT_TYPES.ABORTED_DEPLOYMENT)

    def test_abort_deployment_sets_script_result_to_aborted(self):
        node = factory.make_Node(
            status=NODE_STATUS.DEPLOYING, with_empty_script_sets=True
        )
        admin = factory.make_admin()
        self.patch(Node, "_stop").return_value = None
        self.patch_autospec(Node, "_clear_status_expires")
        self.patch(Node, "_set_status")
        abort_all_tests = self.patch_autospec(Node, "_abort_all_tests")
        with post_commit_hooks:
            node.abort_deploying(admin)
        self.assertThat(
            abort_all_tests,
            MockCalledOnceWith(node.current_installation_script_set_id),
        )

    def test_abort_deployment_clears_deployment_resources(self):
        node = factory.make_Node(status=NODE_STATUS.DEPLOYING)
        node_id = node.id
        admin = factory.make_admin()
        self.patch(Node, "_stop").return_value = None
        self.patch_autospec(Node, "_clear_status_expires")
        self.patch(Node, "_set_status")
        mock_clear_resources = self.patch(Node, "_clear_deployment_resources")
        with post_commit_hooks:
            node.abort_deploying(admin)
        self.assertThat(mock_clear_resources, MockCalledOnceWith(node_id))

    def test_abort_operation_raises_exception_for_unsupported_state(self):
        agent_name = factory.make_name("agent-name")
        owner = factory.make_User()
        node = factory.make_Node(
            status=NODE_STATUS.READY, owner=owner, agent_name=agent_name
        )
        self.assertRaises(NodeStateViolation, node.abort_operation, owner)

    def test_abort_testing_reverts_to_previous_state(self):
        admin = factory.make_admin()
        status = random.choice(list(NODE_TESTING_RESET_READY_TRANSITIONS))
        node = factory.make_Node(
            previous_status=status,
            status=NODE_STATUS.TESTING,
            power_type="virsh",
        )
        mock_stop = self.patch(node, "_stop")
        # Return a post-commit hook from Node.stop().
        mock_stop.side_effect = lambda user: post_commit()
        mock_set_status = self.patch(Node, "_set_status")

        with post_commit_hooks:
            node.abort_testing(admin)

        # Allow abortion of auto testing into ready state.
        if status == NODE_STATUS.COMMISSIONING:
            status = NODE_STATUS.READY

        self.assertThat(mock_stop, MockCalledOnceWith(admin))
        self.assertThat(
            mock_set_status, MockCalledOnceWith(node.system_id, status=status)
        )

    def test_abort_testing_logs_user_request_and_creates_sts_msg(self):
        node = factory.make_Node(status=NODE_STATUS.TESTING)
        admin = factory.make_admin()
        self.patch(Node, "_set_status")
        self.patch(Node, "_stop").return_value = None
        with post_commit_hooks:
            node.abort_testing(admin)
        events = Event.objects.filter(node=node).order_by("id")
        self.assertEqual(
            events[0].type.name, EVENT_TYPES.REQUEST_NODE_ABORT_TESTING
        )
        self.assertEqual(events[1].type.name, EVENT_TYPES.ABORTED_TESTING)

    def test_abort_testing_logs_and_raises_errors_in_stopping(self):
        admin = factory.make_admin()
        node = factory.make_Node(status=NODE_STATUS.TESTING)
        maaslog = self.patch(node_module, "maaslog")
        exception_class = factory.make_exception_type()
        exception = exception_class(factory.make_name())
        self.patch(node, "_stop").side_effect = exception
        self.assertRaises(exception_class, node.abort_testing, admin)
        self.assertEqual(NODE_STATUS.TESTING, node.status)
        self.assertThat(
            maaslog.error,
            MockCalledOnceWith(
                "%s: Error when aborting testing: %s", node.hostname, exception
            ),
        )

    def test_abort_testing_errors_if_node_is_not_testing(self):
        admin = factory.make_admin()
        unaccepted_statuses = set(map_enum(NODE_STATUS).values())
        unaccepted_statuses.remove(NODE_STATUS.TESTING)
        for status in unaccepted_statuses:
            node = factory.make_Node(status=status, power_type="virsh")
            self.assertRaises(NodeStateViolation, node.abort_testing, admin)

    def test_abort_testing_sets_script_result_to_aborted(self):
        node = factory.make_Node(
            status=NODE_STATUS.TESTING, with_empty_script_sets=True
        )
        admin = factory.make_admin()
        self.patch(Node, "_stop").return_value = None
        self.patch_autospec(Node, "_clear_status_expires")
        self.patch(Node, "_set_status")
        abort_all_tests = self.patch_autospec(Node, "_abort_all_tests")
        with post_commit_hooks:
            node.abort_testing(admin)
        self.assertThat(
            abort_all_tests,
            MockCalledOnceWith(node.current_testing_script_set_id),
        )

    def test_abort_disk_erasing_reverts_to_sane_state_on_error(self):
        # If abort_disk_erasing encounters an error when calling stop(), it
        # will transition the node to a sane state. Failures encountered in
        # one call to start_disk_erasing() won't affect subsequent calls.
        admin = factory.make_admin()
        node = factory.make_Node(
            status=NODE_STATUS.DISK_ERASING, power_type="virsh"
        )
        node_stop = self.patch(node, "_stop")
        node_stop.side_effect = factory.make_exception()

        try:
            with transaction.atomic():
                node.abort_disk_erasing(admin)
        except node_stop.side_effect.__class__:
            # We don't care about the error here, so suppress it. It
            # exists only to cause the transaction to abort.
            pass

        self.assertThat(node_stop, MockCalledOnceWith(admin))
        self.assertEqual(NODE_STATUS.DISK_ERASING, node.status)

    def test_abort_disk_erasing_logs_and_raises_errors_in_stopping(self):
        admin = factory.make_admin()
        node = factory.make_Node(status=NODE_STATUS.DISK_ERASING)
        maaslog = self.patch(node_module, "maaslog")
        exception_class = factory.make_exception_type()
        exception = exception_class(factory.make_name())
        self.patch(node, "_stop").side_effect = exception
        self.assertRaises(exception_class, node.abort_disk_erasing, admin)
        self.assertEqual(NODE_STATUS.DISK_ERASING, node.status)
        self.assertThat(
            maaslog.error,
            MockCalledOnceWith(
                "%s: Error when aborting disk erasure: %s",
                node.hostname,
                exception,
            ),
        )

    def test_release_node_that_has_power_on_and_controlled_power_type(self):
        d = defer.succeed(None)
        self.patch(node_module, "post_commit").return_value = d
        agent_name = factory.make_name("agent-name")
        owner = factory.make_User()
        owner_data = {factory.make_name("key"): factory.make_name("value")}
        rack = factory.make_RackController()
        node = factory.make_Node_with_Interface_on_Subnet(
            status=NODE_STATUS.DEPLOYING,
            owner=owner,
            owner_data=owner_data,
            agent_name=agent_name,
            power_type="virsh",
            primary_rack=rack,
        )
        self.patch(Node, "_set_status_expires")
        self.patch(node_module, "post_commit_do")
        self.patch(node, "_power_control_node")
        node.power_state = POWER_STATE.ON
        with post_commit_hooks:
            node.release()
        self.expectThat(
            Node._set_status_expires,
            MockCalledOnceWith(node.system_id, NODE_STATUS.RELEASING),
        )
        self.expectThat(node.status, Equals(NODE_STATUS.RELEASING))
        self.expectThat(node.owner, Equals(owner))
        self.expectThat(node.agent_name, Equals(""))
        self.expectThat(node.netboot, Is(True))
        self.expectThat(node.ephemeral_deploy, Is(False))
        self.expectThat(node.osystem, Equals(""))
        self.expectThat(node.distro_series, Equals(""))
        self.expectThat(node.license_key, Equals(""))
        self.expectThat(node.install_rackd, Is(False))

        expected_power_info = node.get_effective_power_info()
        node._power_control_node.assert_called_once_with(
            d, "power_off", expected_power_info, []
        )

    def test_release_node_that_has_power_on_and_uncontrolled_power_type(self):
        agent_name = factory.make_name("agent-name")
        owner = factory.make_User()
        owner_data = {factory.make_name("key"): factory.make_name("value")}
        # Use an "uncontrolled" power type (i.e. a power type for which we
        # cannot query the status of the node).
        power_type = random.choice(
            [
                driver.name
                for _, driver in PowerDriverRegistry
                if not driver.queryable
            ]
        )
        rack = factory.make_RackController()
        node = factory.make_Node_with_Interface_on_Subnet(
            status=NODE_STATUS.ALLOCATED,
            owner=owner,
            owner_data=owner_data,
            agent_name=agent_name,
            power_type=power_type,
            primary_rack=rack,
        )
        self.patch(Node, "_set_status_expires")
        mock_stop = self.patch(node, "_stop")
        mock_finalize_release = self.patch(node, "_finalize_release")
        node.power_state = POWER_STATE.ON
        node.release(owner)
        self.expectThat(Node._set_status_expires, MockNotCalled())
        self.expectThat(node.status, Equals(NODE_STATUS.RELEASING))
        self.expectThat(node.owner, Equals(owner))
        self.expectThat(node.agent_name, Equals(""))
        self.expectThat(node.netboot, Is(True))
        self.expectThat(node.ephemeral_deploy, Is(False))
        self.expectThat(node.osystem, Equals(""))
        self.expectThat(node.distro_series, Equals(""))
        self.expectThat(node.license_key, Equals(""))
        self.expectThat(node.install_rackd, Is(False))
        self.expectThat(mock_stop, MockCalledOnceWith(node.owner))
        self.expectThat(mock_finalize_release, MockCalledOnceWith())

    def test_release_node_that_has_power_off_and_creates_status_messages(self):
        agent_name = factory.make_name("agent-name")
        owner = factory.make_User()
        owner_data = {factory.make_name("key"): factory.make_name("value")}
        node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED,
            owner=owner,
            owner_data=owner_data,
            agent_name=agent_name,
        )
        self.patch(node, "_stop")
        self.patch(Node, "_set_status_expires")
        node.power_state = POWER_STATE.OFF
        with post_commit_hooks:
            node.release()
        events = Event.objects.filter(node=node).order_by("id")
        self.expectThat(events[1].type.name, Equals(EVENT_TYPES.RELEASING))
        self.expectThat(events[2].type.name, Equals(EVENT_TYPES.RELEASED))
        self.expectThat(node._stop, MockNotCalled())
        self.expectThat(Node._set_status_expires, MockNotCalled())
        self.expectThat(node.status, Equals(NODE_STATUS.NEW))
        self.expectThat(node.owner, Equals(None))
        self.expectThat(node.agent_name, Equals(""))
        self.expectThat(node.netboot, Is(True))
        self.expectThat(node.ephemeral_deploy, Is(False))
        self.expectThat(node.osystem, Equals(""))
        self.expectThat(node.distro_series, Equals(""))
        self.expectThat(node.license_key, Equals(""))
        self.expectThat(node.install_rackd, Is(False))
        self.expectThat(OwnerData.objects.filter(node=node), HasLength(0))

    def test_release_to_new_if_no_commissioning_data(self):
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED)
        self.patch(node, "_stop")
        self.patch(node, "_set_status_expires")
        node.power_state = POWER_STATE.OFF
        with post_commit_hooks:
            node.release()
        self.assertIsNone(node.current_commissioning_script_set)
        self.assertEqual(node.status, NODE_STATUS.NEW)

    def test_release_to_new_if_no_commissioning_results(self):
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED)
        self.patch(node, "_stop")
        self.patch(node, "_set_status_expires")
        node.power_state = POWER_STATE.OFF
        script_set = factory.make_ScriptSet(
            node=node,
            result_type=RESULT_TYPE.COMMISSIONING,
        )
        script = factory.make_Script(script_type=SCRIPT_TYPE.COMMISSIONING)
        script_set.add_pending_script(script)
        with post_commit_hooks:
            node.release()
        self.assertIsNone(node.current_commissioning_script_set)
        self.assertEqual(node.status, NODE_STATUS.NEW)

    def test_release_to_ready_if_commissioning_results(self):
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED)
        self.patch(node, "_stop")
        self.patch(node, "_set_status_expires")
        script_set = factory.make_ScriptSet(
            node=node,
            result_type=RESULT_TYPE.COMMISSIONING,
        )
        node.power_state = POWER_STATE.OFF
        node.current_commissioning_script_set = script_set
        node.save()
        script = factory.make_Script(script_type=SCRIPT_TYPE.COMMISSIONING)
        script_set.add_pending_script(script)
        script_result = script.scriptresult_set.first()
        script_result.status = SCRIPT_STATUS.PASSED
        script_result.save()
        with post_commit_hooks:
            node.release()
        self.assertEqual(node.status, NODE_STATUS.READY)

    def test_release_sets_enable_hw_sync_to_False(self):
        node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, enable_hw_sync=True
        )
        self.patch(node, "_stop")
        self.patch(node, "_set_status_expires")
        with post_commit_hooks:
            node.release()
        self.assertFalse(node.enable_hw_sync)

    def test_release_sets_sync_interval_to_None(self):
        node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, enable_hw_sync=True
        )
        self.patch(node, "_stop")
        self.patch(node, "_set_status_expires")
        self.assertEqual(
            node.sync_interval, timedelta(minutes=15).total_seconds()
        )
        with post_commit_hooks:
            node.release()
        self.assertIsNone(node.sync_interval)

    def test_sync_interval_is_set_when_enable_hw_sync_is_True(self):
        node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, enable_hw_sync=True
        )
        self.assertEqual(
            node.sync_interval, timedelta(minutes=15).total_seconds()
        )

    def test_next_sync_returns_time_after_last_sync(self):
        node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, enable_hw_sync=True
        )
        node.last_sync = datetime.now()
        expected_interval = timedelta(minutes=15)
        self.assertEqual(node.next_sync, node.last_sync + expected_interval)

    def test_dynamic_ip_addresses_from_ip_address_table(self):
        node = factory.make_Node()
        interfaces = [
            factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
            for _ in range(3)
        ]
        ip_addresses = [
            factory.make_StaticIPAddress(
                alloc_type=IPADDRESS_TYPE.DISCOVERED, interface=interface
            )
            for interface in interfaces[:2]
        ]
        # Empty ip should not appear
        factory.make_StaticIPAddress(
            ip="",
            alloc_type=IPADDRESS_TYPE.DISCOVERED,
            interface=interfaces[2],
        )
        self.assertCountEqual(
            [ip.ip for ip in ip_addresses], node.dynamic_ip_addresses()
        )

    def test_static_ip_addresses_returns_static_ip_addresses(self):
        node = factory.make_Node()
        [interface1, interface2] = [
            factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
            for _ in range(2)
        ]
        ip1 = factory.make_StaticIPAddress(interface=interface1)
        ip2 = factory.make_StaticIPAddress(interface=interface2)
        # Create another node with a static IP address.
        other_node = factory.make_Node(interface=True)
        factory.make_StaticIPAddress(interface=other_node.get_boot_interface())
        self.assertCountEqual([ip1.ip, ip2.ip], node.static_ip_addresses())

    def test_static_ip_addresses_returns_filtered_ip_addresses(self):
        node = factory.make_Node()
        [interface1, interface2] = [
            factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
            for _ in range(2)
        ]
        factory.make_StaticIPAddress(interface=interface1)
        ip2 = factory.make_StaticIPAddress(interface=interface2)
        # Create another node with a static IP address.
        other_node = factory.make_Node(interface=True)
        factory.make_StaticIPAddress(interface=other_node.get_boot_interface())
        self.assertCountEqual([ip2.ip], node.static_ip_addresses([interface2]))

    def test_ip_addresses_returns_static_ip_addresses_if_allocated(self):
        # If both static and dynamic IP addresses are present, the static
        # addresses take precedence: they are allocated and deallocated in
        # a synchronous fashion whereas the dynamic addresses are updated
        # periodically.
        node = factory.make_Node(interface=True)
        interface = node.get_boot_interface()
        ip = factory.make_StaticIPAddress(interface=interface)
        self.assertCountEqual([ip.ip], node.ip_addresses())

    def test_ip_addresses_returns_dynamic_ip_if_no_static_ip(self):
        node = factory.make_Node()
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.DISCOVERED, interface=interface
        )
        self.assertCountEqual([ip.ip], node.ip_addresses())

    def test_ip_addresses_includes_static_ipv4_addresses_by_default(self):
        node = factory.make_Node()
        ipv4_address = factory.make_ipv4_address()
        ipv6_address = factory.make_ipv6_address()
        self.patch(node, "static_ip_addresses").return_value = [
            ipv4_address,
            ipv6_address,
        ]
        self.assertCountEqual(
            [ipv4_address, ipv6_address], node.ip_addresses()
        )

    def test_ip_addresses_includes_dynamic_ipv4_addresses_by_default(self):
        node = factory.make_Node()
        ipv4_address = factory.make_ipv4_address()
        ipv6_address = factory.make_ipv6_address()
        self.patch(node, "dynamic_ip_addresses").return_value = [
            ipv4_address,
            ipv6_address,
        ]
        self.assertCountEqual(
            [ipv4_address, ipv6_address], node.ip_addresses()
        )

    def test_get_interfaces_returns_all_connected_interfaces(self):
        node = factory.make_Node()
        phy1 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        phy2 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        phy3 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        vlan = factory.make_Interface(INTERFACE_TYPE.VLAN, parents=[phy1])
        bond = factory.make_Interface(
            INTERFACE_TYPE.BOND, parents=[phy2, phy3]
        )
        vlan_bond = factory.make_Interface(INTERFACE_TYPE.VLAN, parents=[bond])

        self.assertCountEqual(
            [phy1, phy2, phy3, vlan, bond, vlan_bond],
            node.current_config.interface_set.all(),
        )

    def test_get_interfaces_ignores_interface_on_other_nodes(self):
        other_node = factory.make_Node()
        factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=other_node)
        node = factory.make_Node()
        phy = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        vlan = factory.make_Interface(INTERFACE_TYPE.VLAN, parents=[phy])

        self.assertCountEqual(
            [phy, vlan], node.current_config.interface_set.all()
        )

    def test_get_interface_names_returns_interface_name(self):
        node = factory.make_Node()
        factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node, name="eth0")
        self.assertEqual(["eth0"], node.get_interface_names())

    def test_get_next_ifname_names_returns_sane_default(self):
        node = factory.make_Node()
        self.assertEqual("eth0", node.get_next_ifname(ifnames=[]))

    def test_get_next_ifname_names_returns_next_available(self):
        node = factory.make_Node()
        self.assertEqual(
            "eth2", node.get_next_ifname(ifnames=["eth0", "eth1"])
        )

    def test_get_next_ifname_names_returns_next_in_sequence(self):
        node = factory.make_Node()
        self.assertEqual(
            "eth12", node.get_next_ifname(ifnames=["eth10", "eth11"])
        )

    def test_get_next_ifname_ignores_vlans_in_names(self):
        node = factory.make_Node()
        self.assertEqual(
            "eth12", node.get_next_ifname(ifnames=["eth10.1", "eth11.2"])
        )

    def test_get_next_ifname_ignores_aliases_in_names(self):
        node = factory.make_Node()
        self.assertEqual(
            "eth12", node.get_next_ifname(ifnames=["eth10:5", "eth11:bob"])
        )

    def test_get_next_block_device_name_names_returns_sane_default(self):
        node = factory.make_Node()
        self.assertEqual(
            "sda", node.get_next_block_device_name(block_device_names=[])
        )

    def test_get_next_block_device_name_names_returns_next_available(self):
        node = factory.make_Node()
        self.assertEqual(
            "sdb",
            node.get_next_block_device_name(block_device_names=["sda", "sdf"]),
        )

    def test_get_next_block_device_name_ignores_different_prefix(self):
        node = factory.make_Node()
        self.assertEqual(
            "sda",
            node.get_next_block_device_name(block_device_names=["vda", "vdb"]),
        )

    def test_release_turns_on_netboot(self):
        node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=factory.make_User()
        )
        self.patch(node, "_stop")
        self.patch(node, "_set_status")
        node.set_netboot(on=False)
        with post_commit_hooks:
            node.release()
        self.assertTrue(node.netboot)

    def test_release_sets_install_rackd_false(self):
        node = factory.make_Node(
            status=NODE_STATUS.DEPLOYED, owner=factory.make_User()
        )
        self.patch(node, "_stop")
        self.patch(node, "_set_status")
        node.install_rackd = True
        with post_commit_hooks:
            node.release()
        self.assertFalse(node.install_rackd)

    def test_release_logs_user_request_and_creates_sts_msg(self):
        owner = factory.make_User()
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED, owner=owner)
        self.patch(node, "_stop")
        self.patch(node, "_set_status")
        with post_commit_hooks:
            node.release(owner)
        events = Event.objects.filter(node=node).order_by("id")
        self.assertEqual(events[0].type.name, EVENT_TYPES.REQUEST_NODE_RELEASE)
        self.assertEqual(events[1].type.name, EVENT_TYPES.RELEASING)

    def test_release_clears_osystem_and_distro_series(self):
        node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=factory.make_User()
        )
        node.osystem = factory.make_name("os")
        node.distro_series = factory.make_name("series")
        self.patch(node, "_stop")
        self.patch(node, "_set_status")
        with post_commit_hooks:
            node.release()
        self.assertEqual("", node.osystem)
        self.assertEqual("", node.distro_series)

    def test_release_powers_off_node_when_on(self):
        user = factory.make_User()
        node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED,
            owner=user,
            power_type="virsh",
            power_state=POWER_STATE.ON,
        )
        self.patch(Node, "_set_status_expires")
        node_stop = self.patch(node, "_stop")
        with post_commit_hooks:
            node.release(user)
        self.assertThat(node_stop, MockCalledOnceWith(user))

    def test_release_calls_stop_with_user_call_not_owner(self):
        user = factory.make_User()
        owner = factory.make_User()
        node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED,
            owner=owner,
            power_type="virsh",
            power_state=POWER_STATE.ON,
        )
        self.patch(Node, "_set_status_expires")
        node_stop = self.patch(node, "_stop")
        with post_commit_hooks:
            node.release(user)
        self.assertThat(node_stop, MockCalledOnceWith(user))

    def test_release_doesnt_power_off_node_when_off(self):
        user = factory.make_User()
        node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED,
            owner=user,
            power_type="virsh",
            power_state=POWER_STATE.OFF,
        )
        self.patch(Node, "_set_status_expires")
        node_stop = self.patch(node, "_stop")
        with post_commit_hooks:
            node.release()
        self.assertThat(node_stop, MockNotCalled())

    def test_release_calls_release_interface_config_when_node_is_off(self):
        """Releasing a powered down node calls `release_interface_config`."""
        user = factory.make_User()
        node = factory.make_Node_with_Interface_on_Subnet(
            owner=user,
            status=NODE_STATUS.ALLOCATED,
            power_state=POWER_STATE.OFF,
        )
        release_interface_config = self.patch_autospec(
            node, "release_interface_config"
        )
        self.patch(Node, "_set_status_expires")
        with post_commit_hooks:
            node.release()
        self.assertThat(release_interface_config, MockCalledOnceWith())

    def test_release_calls_release_interface_config_when_cant_be_queried(self):
        """Releasing a node that can't be queried calls
        `release_interface_config`."""
        user = factory.make_User()
        node = factory.make_Node_with_Interface_on_Subnet(
            owner=user,
            status=NODE_STATUS.ALLOCATED,
            power_state=POWER_STATE.ON,
            power_type="manual",
        )
        release_interface_config = self.patch_autospec(
            node, "release_interface_config"
        )
        self.patch(Node, "_set_status_expires")
        self.patch(node, "_stop")
        self.patch(node, "_set_status")
        with post_commit_hooks:
            node.release()
        self.assertThat(release_interface_config, MockCalledOnceWith())

    def test_release_doesnt_release_interface_config_when_node_releasing(self):
        user = factory.make_User()
        node = factory.make_Node_with_Interface_on_Subnet(
            owner=user,
            status=NODE_STATUS.ALLOCATED,
            power_state=POWER_STATE.ON,
            power_type="virsh",
        )
        release = self.patch_autospec(node, "release_interface_config")
        self.patch_autospec(node, "_stop")
        self.patch(Node, "_set_status_expires")
        with post_commit_hooks:
            node.release()
        self.assertThat(release, MockNotCalled())

    def test_release_logs_and_raises_errors_in_stopping(self):
        node = factory.make_Node(
            status=NODE_STATUS.DEPLOYED, power_state=POWER_STATE.ON
        )
        maaslog = self.patch(node_module, "maaslog")
        exception_class = factory.make_exception_type()
        exception = exception_class(factory.make_name())
        self.patch(node, "_stop").side_effect = exception
        self.assertRaises(exception_class, node.release)
        self.assertEqual(NODE_STATUS.DEPLOYED, node.status)
        self.assertThat(
            maaslog.error,
            MockCalledOnceWith(
                "%s: Unable to shut node down: %s",
                node.hostname,
                str(exception),
            ),
        )

    def test_release_reverts_to_sane_state_on_error(self):
        # If release() encounters an error when stopping the node, it
        # will leave the node in its previous state (i.e. DEPLOYED).
        owner = factory.make_User()
        node = factory.make_Node(
            status=NODE_STATUS.DEPLOYED,
            power_type="virsh",
            power_state=POWER_STATE.ON,
            owner=owner,
        )
        node_stop = self.patch(node, "_stop")
        node_stop.side_effect = factory.make_exception()

        try:
            with post_commit_hooks:
                node.release(owner)
        except node_stop.side_effect.__class__:
            # We don't care about the error here, so suppress it. It
            # exists only to cause the transaction to abort.
            pass

        self.assertThat(node_stop, MockCalledOnceWith(node.owner))
        self.assertEqual(NODE_STATUS.DEPLOYED, node.status)

    def test_release_calls__clear_acquired_filesystems(self):
        node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=factory.make_User()
        )
        mock_clear = self.patch(node, "_clear_acquired_filesystems")
        self.patch(node, "_stop")
        self.patch(node, "_set_status")
        with post_commit_hooks:
            node.release()
        self.assertThat(mock_clear, MockCalledOnceWith())

    def test_release_clears_hugepages(self):
        node = factory.make_Node(
            status=NODE_STATUS.DEPLOYED, owner=factory.make_User()
        )
        hugepages = factory.make_NUMANodeHugepages(
            numa_node=node.default_numanode
        )
        self.patch(node, "_stop")
        self.patch(node, "_set_status")
        with post_commit_hooks:
            node.release()
        self.assertIsNone(reload_object(hugepages))

    def test_releases_clears_current_installation_script_set(self):
        node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=factory.make_User()
        )
        self.patch(node, "_stop")
        with post_commit_hooks:
            node.release()
        self.assertIsNone(node.current_installation_script_set)

    def test_accept_enlistment_gets_node_out_of_declared_state(self):
        # If called on a node in New state, accept_enlistment()
        # changes the node's status, and returns the node.
        self.disable_node_query()
        target_state = NODE_STATUS.COMMISSIONING

        user = factory.make_User()
        node = factory.make_Node(status=NODE_STATUS.NEW, owner=user)
        self.patch(Node, "_set_status_expires")
        self.patch(Node, "_start").return_value = None
        with post_commit_hooks:
            return_value = node.accept_enlistment(user)
        self.assertEqual((node, target_state), (return_value, node.status))

    def test_accept_enlistment_does_nothing_if_already_accepted(self):
        # If a node has already been accepted, but not assigned a role
        # yet, calling accept_enlistment on it is meaningless but not an
        # error.  The method returns None in this case.
        self.disable_node_query()
        accepted_states = [NODE_STATUS.COMMISSIONING, NODE_STATUS.READY]

        user = factory.make_User()
        node = factory.make_Node()
        for status in accepted_states:
            node.update_status(status)
            self.assertIsNone(node.accept_enlistment(user))

    def test_accept_enlistment_rejects_bad_state_change(self):
        # If a node is neither New nor in one of the "accepted"
        # states where acceptance is a safe no-op, accept_enlistment
        # raises a node state violation and leaves the node's state
        # unchanged.
        self.disable_node_query()
        all_states = set(map_enum(NODE_STATUS).values())
        acceptable_states = {
            NODE_STATUS.NEW,
            NODE_STATUS.COMMISSIONING,
            NODE_STATUS.READY,
        }
        unacceptable_states = set(all_states) - acceptable_states
        user = factory.make_User()
        node = factory.make_Node()
        for status in unacceptable_states:
            node.status = status
            self.assertRaises(NodeStateViolation, node.accept_enlistment, user)

    def test_start_commissioning_errors_for_unconfigured_power_type(self):
        node = factory.make_Node(
            interface=True,
            status=NODE_STATUS.NEW,
            power_type=None,
        )
        admin = factory.make_admin()
        self.assertRaises(UnknownPowerType, node.start_commissioning, admin)

    def test_start_commissioning_changes_status_and_starts_node(self):
        node = factory.make_Node(
            interface=True, status=NODE_STATUS.NEW, power_type="manual"
        )
        node_start = self.patch(node, "_start")
        # Return a post-commit hook from Node.start().
        node_start.side_effect = lambda *args, **kwargs: post_commit()
        config = Config.objects.get_configs(
            [
                "commissioning_osystem",
                "commissioning_distro_series",
                "default_osystem",
                "default_distro_series",
                "default_min_hwe_kernel",
            ]
        )
        admin = factory.make_admin()
        node.start_commissioning(admin)
        post_commit_hooks.reset()  # Ignore these for now.
        node = reload_object(node)
        self.assertEqual(node.status, NODE_STATUS.COMMISSIONING)
        self.assertThat(
            node_start,
            MockCalledOnceWith(
                admin,
                ANY,
                NODE_STATUS.NEW,
                allow_power_cycle=True,
                config=config,
            ),
        )

    def test_start_commissioning_sets_options(self):
        rack = factory.make_RackController()
        node = factory.make_Node(
            interface=True,
            status=NODE_STATUS.NEW,
            power_type="virsh",
            bmc_connected_to=rack,
        )
        node_start = self.patch(node, "_start")
        # Return a post-commit hook from Node.start().
        node_start.side_effect = lambda *args, **kwargs: post_commit()
        admin = factory.make_admin()
        enable_ssh = factory.pick_bool()
        skip_networking = factory.pick_bool()
        skip_storage = factory.pick_bool()
        node.start_commissioning(
            admin,
            enable_ssh=enable_ssh,
            skip_networking=skip_networking,
            skip_storage=skip_storage,
        )
        post_commit_hooks.reset()  # Ignore these for now.
        node = reload_object(node)
        self.assertEqual(node.enable_ssh, enable_ssh)
        self.assertEqual(node.skip_networking, skip_networking)
        self.assertEqual(node.skip_storage, skip_storage)

    def test_start_commissioning_sets_user_data(self):
        node = factory.make_Node(status=NODE_STATUS.NEW)
        node_start = self.patch(node, "_start")
        node_start.side_effect = lambda *args, **kwargs: post_commit()
        config = Config.objects.get_configs(
            [
                "commissioning_osystem",
                "commissioning_distro_series",
                "default_osystem",
                "default_distro_series",
                "default_min_hwe_kernel",
            ]
        )
        user_data = factory.make_string().encode("ascii")
        generate_user_data_for_status = self.patch(
            node_module, "generate_user_data_for_status"
        )
        generate_user_data_for_status.return_value = user_data
        admin = factory.make_admin()
        node.start_commissioning(admin)
        post_commit_hooks.reset()  # Ignore these for now.
        self.assertThat(
            node_start,
            MockCalledOnceWith(
                admin,
                user_data,
                NODE_STATUS.NEW,
                allow_power_cycle=True,
                config=config,
            ),
        )

    def test_start_commissioning_sets_min_hwe_kernel_when_not_set(self):
        node = factory.make_Node(status=NODE_STATUS.NEW)
        node_start = self.patch(node, "_start")
        node_start.side_effect = lambda *args, **kwargs: post_commit()
        user_data = factory.make_string().encode("ascii")
        generate_user_data_for_status = self.patch(
            node_module, "generate_user_data_for_status"
        )
        generate_user_data_for_status.return_value = user_data
        admin = factory.make_admin()
        Config.objects.set_config("default_min_hwe_kernel", "hwe-16.04")
        node.start_commissioning(admin)
        post_commit_hooks.reset()  # Ignore these for now.
        self.assertEqual("hwe-16.04", node.min_hwe_kernel)

    def test_start_commissioning_sets_min_hwe_kernel_when_previously_set(self):
        node = factory.make_Node(
            status=NODE_STATUS.READY, min_hwe_kernel="ga-16.04"
        )
        node_start = self.patch(node, "_start")
        node_start.side_effect = lambda *args, **kwargs: post_commit()
        user_data = factory.make_string().encode("ascii")
        generate_user_data_for_status = self.patch(
            node_module, "generate_user_data_for_status"
        )
        generate_user_data_for_status.return_value = user_data
        admin = factory.make_admin()
        Config.objects.set_config("default_min_hwe_kernel", "hwe-16.04")
        node.start_commissioning(admin)
        post_commit_hooks.reset()  # Ignore these for now.
        self.assertEqual("ga-16.04", node.min_hwe_kernel)

    def test_start_commissioning_sets_min_hwe_kernel_when_default_set(self):
        node = factory.make_Node(status=NODE_STATUS.NEW)
        node_start = self.patch(node, "_start")
        node_start.side_effect = lambda *args, **kwargs: post_commit()
        user_data = factory.make_string().encode("ascii")
        generate_user_data_for_status = self.patch(
            node_module, "generate_user_data_for_status"
        )
        generate_user_data_for_status.return_value = user_data
        admin = factory.make_admin()
        Config.objects.set_config("default_min_hwe_kernel", "hwe-16.04")
        node.start_commissioning(admin)
        post_commit_hooks.reset()  # Ignore these for now.
        self.assertEqual("hwe-16.04", node.min_hwe_kernel)

    def test_start_commissioning_starts_node_if_already_on(self):
        node = factory.make_Node(
            interface=True,
            status=NODE_STATUS.NEW,
            power_type="manual",
            power_state=POWER_STATE.ON,
        )
        node_start = self.patch(node, "_start")
        # Return a post-commit hook from Node.start().
        node_start.side_effect = lambda *args, **kwargs: post_commit()
        config = Config.objects.get_configs(
            [
                "commissioning_osystem",
                "commissioning_distro_series",
                "default_osystem",
                "default_distro_series",
                "default_min_hwe_kernel",
            ]
        )
        admin = factory.make_admin()
        node.start_commissioning(admin)
        post_commit_hooks.reset()  # Ignore these for now.
        node = reload_object(node)
        self.assertEqual(node.status, NODE_STATUS.COMMISSIONING)
        self.assertEqual(node.owner, admin)
        self.assertThat(
            node_start,
            MockCalledOnceWith(
                admin,
                ANY,
                NODE_STATUS.NEW,
                allow_power_cycle=True,
                config=config,
            ),
        )

    def test_start_commissioning_adds_commissioning_script_set(self):
        load_builtin_scripts()
        # Test for when there are no testing scripts
        node = factory.make_Node(status=NODE_STATUS.NEW)
        node_start = self.patch(node, "_start")
        node_start.side_effect = lambda *args, **kwargs: post_commit()

        with post_commit_hooks:
            node.start_commissioning(factory.make_admin())

        node = reload_object(node)

        self.assertIsNotNone(node.current_commissioning_script_set)
        self.assertIsNotNone(node.current_testing_script_set)

    def test_start_commissioning_adds_default_script_sets(self):
        load_builtin_scripts()
        # Test for when there are testing scripts
        factory.make_Script(
            script_type=SCRIPT_TYPE.TESTING, tags=["commissioning"]
        )
        node = factory.make_Node(status=NODE_STATUS.NEW)
        node_start = self.patch(node, "_start")
        node_start.side_effect = lambda *args, **kwargs: post_commit()

        with post_commit_hooks:
            node.start_commissioning(factory.make_admin())

        node = reload_object(node)

        self.assertIsNotNone(node.current_commissioning_script_set)
        self.assertIsNotNone(node.current_testing_script_set)

    def test_start_commissioning_adds_selected_scripts(self):
        load_builtin_scripts()
        node = factory.make_Node(status=NODE_STATUS.NEW)
        node_start = self.patch(node, "_start")
        node_start.side_effect = lambda *args, **kwargs: post_commit()
        commissioning_scripts = [
            factory.make_Script(script_type=SCRIPT_TYPE.COMMISSIONING)
            for _ in range(10)
        ]
        commissioning_script_selected_by_tag = random.choice(
            commissioning_scripts
        )
        commissioning_script_selected_by_name = random.choice(
            commissioning_scripts
        )
        expected_commissioning_scripts = list(NODE_INFO_SCRIPTS)
        expected_commissioning_scripts.append(
            commissioning_script_selected_by_tag.name
        )
        expected_commissioning_scripts.append(
            commissioning_script_selected_by_name.name
        )

        testing_scripts = [
            factory.make_Script(script_type=SCRIPT_TYPE.TESTING)
            for _ in range(10)
        ]
        testing_script_selected_by_tag = random.choice(testing_scripts)
        testing_script_selected_by_name = random.choice(testing_scripts)
        expected_testing_scripts = [
            testing_script_selected_by_tag.name,
            testing_script_selected_by_name.name,
        ]

        with post_commit_hooks:
            node.start_commissioning(
                factory.make_admin(),
                commissioning_scripts=expected_commissioning_scripts,
                testing_scripts=expected_testing_scripts,
            )

        node = reload_object(node)
        commissioning_script_set = node.current_commissioning_script_set
        testing_script_set = node.current_testing_script_set

        self.assertCountEqual(
            set(expected_commissioning_scripts),
            [script_result.name for script_result in commissioning_script_set],
        )
        self.assertCountEqual(
            set(expected_testing_scripts),
            [script_result.name for script_result in testing_script_set],
        )

    def test_start_commissioning_clears_storage_configuration(self):
        node = factory.make_Node(status=NODE_STATUS.NEW)
        node_start = self.patch(node, "_start")
        node_start.side_effect = lambda *args, **kwargs: post_commit()
        clear_storage = self.patch_autospec(
            node, "_clear_full_storage_configuration"
        )
        admin = factory.make_admin()
        node.start_commissioning(admin, skip_storage=False)
        post_commit_hooks.reset()  # Ignore these for now.
        self.assertThat(clear_storage, MockCalledOnceWith())

    def test_start_commissioning_doesnt_clear_storage_configuration(self):
        node = factory.make_Node(status=NODE_STATUS.NEW)
        node_start = self.patch(node, "_start")
        node_start.side_effect = lambda *args, **kwargs: post_commit()
        clear_storage = self.patch_autospec(
            node, "_clear_full_storage_configuration"
        )
        admin = factory.make_admin()
        node.start_commissioning(admin, skip_storage=True)
        post_commit_hooks.reset()  # Ignore these for now.
        self.assertThat(clear_storage, MockNotCalled())

    def test_start_commissioning_calls__clear_networking_configuration(self):
        node = factory.make_Node(status=NODE_STATUS.NEW)
        node_start = self.patch(node, "_start")
        node_start.side_effect = lambda *args, **kwargs: post_commit()
        clear_networking = self.patch_autospec(
            node, "_clear_networking_configuration"
        )
        admin = factory.make_admin()
        node.start_commissioning(admin, skip_networking=False)
        post_commit_hooks.reset()  # Ignore these for now.
        self.assertThat(clear_networking, MockCalledOnceWith())

    def test_start_commissioning_doesnt_call__clear_networking(self):
        node = factory.make_Node(status=NODE_STATUS.NEW)
        node_start = self.patch(node, "_start")
        node_start.side_effect = lambda *args, **kwargs: post_commit()
        clear_networking = self.patch_autospec(
            node, "_clear_networking_configuration"
        )
        admin = factory.make_admin()
        node.start_commissioning(admin, skip_networking=True)
        post_commit_hooks.reset()  # Ignore these for now.
        self.assertThat(clear_networking, MockNotCalled())

    def test_start_commissioning_ignores_other_commissioning_results(self):
        node = factory.make_Node(with_empty_script_sets=True)
        script = factory.make_Script(script_type=SCRIPT_TYPE.COMMISSIONING)
        stdout = factory.make_bytes()
        factory.make_ScriptResult(
            script=script,
            stdout=stdout,
            script_set=node.current_commissioning_script_set,
        )
        other_node = factory.make_Node(
            status=NODE_STATUS.NEW, with_empty_script_sets=True
        )
        self.patch(Node, "_start").return_value = None
        with post_commit_hooks:
            other_node.start_commissioning(factory.make_admin())
        self.assertEqual(
            stdout,
            ScriptResult.objects.get(
                script_set=node.current_commissioning_script_set, script=script
            ).stdout,
        )

    def test_start_commissioning_skip_bmc_config(self):
        script = factory.make_Script(
            script_type=SCRIPT_TYPE.COMMISSIONING, tags=["bmc-config"]
        )
        node = factory.make_Node()
        admin = factory.make_admin()
        self.patch(Node, "_start").return_value = None

        node.start_commissioning(admin, skip_bmc_config=True)
        post_commit_hooks.reset()  # Ignore these for now.

        script_result = (
            node.current_commissioning_script_set.scriptresult_set.get(
                script=script
            )
        )
        self.assertEqual(0, script_result.exit_status)
        self.assertEqual(SCRIPT_STATUS.SKIPPED, script_result.status)

    def test_start_commissioning_skip_bmc_config_s390x(self):
        script = factory.make_Script(
            script_type=SCRIPT_TYPE.COMMISSIONING, tags=["bmc-config"]
        )
        node = factory.make_Node(architecture="s390x/generic")
        admin = factory.make_admin()
        self.patch(Node, "_start").return_value = None

        node.start_commissioning(admin)
        post_commit_hooks.reset()  # Ignore these for now.

        script_result = (
            node.current_commissioning_script_set.scriptresult_set.get(
                script=script
            )
        )
        self.assertEqual(0, script_result.exit_status)
        self.assertEqual(SCRIPT_STATUS.SKIPPED, script_result.status)

    def test_start_commissioning_reverts_to_sane_state_on_error(self):
        # When start_commissioning encounters an error when trying to
        # start the node, it will revert the node to its previous
        # status.
        admin = factory.make_admin()
        node = factory.make_Node(status=NODE_STATUS.NEW)
        generate_user_data_for_status = self.patch(
            node_module, "generate_user_data_for_status"
        )
        node_start = self.patch(node, "_start")
        node_start.side_effect = factory.make_exception()
        config = Config.objects.get_configs(
            [
                "commissioning_osystem",
                "commissioning_distro_series",
                "default_osystem",
                "default_distro_series",
                "default_min_hwe_kernel",
            ]
        )

        try:
            with transaction.atomic():
                node.start_commissioning(
                    admin,
                    enable_ssh=True,
                    skip_networking=True,
                    skip_storage=True,
                )
        except node_start.side_effect.__class__:
            # We don't care about the error here, so suppress it. It
            # exists only to cause the transaction to abort.
            pass

        self.assertThat(
            node_start,
            MockCalledOnceWith(
                admin,
                generate_user_data_for_status.return_value,
                NODE_STATUS.NEW,
                allow_power_cycle=True,
                config=config,
            ),
        )
        self.assertEqual(NODE_STATUS.NEW, node.status)
        self.assertFalse(node.enable_ssh)
        self.assertFalse(node.skip_networking)
        self.assertFalse(node.skip_storage)

    def test_start_commissioning_logs_and_raises_errors_in_starting(self):
        admin = factory.make_admin()
        node = factory.make_Node(status=NODE_STATUS.NEW)
        maaslog = self.patch(node_module, "maaslog")
        exception = NoConnectionsAvailable(factory.make_name())
        self.patch(node, "_start").side_effect = exception
        self.assertRaises(
            NoConnectionsAvailable, node.start_commissioning, admin
        )
        self.assertEqual(NODE_STATUS.NEW, node.status)
        self.assertThat(
            maaslog.error,
            MockCalledOnceWith(
                "%s: Could not start node for commissioning: %s",
                node.hostname,
                exception,
            ),
        )

    def test_start_commissioning_logs_user_request_creates_sts_msg(self):
        node = factory.make_Node(
            interface=True, status=NODE_STATUS.NEW, power_type="manual"
        )
        node_start = self.patch(node, "_start")
        # Return a post-commit hook from Node.start().
        node_start.side_effect = lambda *args, **kwargs: post_commit()
        admin = factory.make_admin()
        node.start_commissioning(admin)
        post_commit_hooks.reset()  # Ignore these for now.
        node = reload_object(node)
        events = Event.objects.filter(node=node).order_by("id")
        self.assertEqual(
            events[0].type.name, EVENT_TYPES.REQUEST_NODE_START_COMMISSIONING
        )
        self.assertEqual(events[1].type.name, EVENT_TYPES.COMMISSIONING)

    def test_start_commissioning_fails_on_xenial_with_network_testing_c(self):
        Config.objects.set_config("commissioning_distro_series", "xenial")
        node = factory.make_Node(status=NODE_STATUS.NEW)
        admin = factory.make_admin()
        script = factory.make_Script(
            script_type=SCRIPT_TYPE.COMMISSIONING,
            apply_configured_networking=True,
        )
        self.assertRaises(
            ValidationError,
            node.start_commissioning,
            user=admin,
            commissioning_scripts=[script.name],
        )
        self.assertEqual(0, ScriptSet.objects.count())
        self.assertEqual(0, ScriptResult.objects.count())

    def test_start_commissioning_fails_on_xenial_with_network_testing_t(self):
        Config.objects.set_config("commissioning_distro_series", "xenial")
        node = factory.make_Node(status=NODE_STATUS.NEW)
        admin = factory.make_admin()
        script = factory.make_Script(
            script_type=SCRIPT_TYPE.TESTING, apply_configured_networking=True
        )
        self.assertRaises(
            ValidationError,
            node.start_commissioning,
            user=admin,
            testing_scripts=[script.name],
        )
        self.assertEqual(0, ScriptSet.objects.count())
        self.assertEqual(0, ScriptResult.objects.count())

    def test_abort_commissioning_reverts_to_sane_state_on_error(self):
        # If abort commissioning hits an error when trying to stop the
        # node, it will revert the node to the state it was in before
        # abort_commissioning() was called.
        admin = factory.make_admin()
        node = factory.make_Node(
            status=NODE_STATUS.COMMISSIONING, power_type="virsh"
        )
        node_stop = self.patch(node, "_stop")
        node_stop.side_effect = factory.make_exception()

        try:
            with transaction.atomic():
                node.abort_commissioning(admin)
        except node_stop.side_effect.__class__:
            # We don't care about the error here, so suppress it. It
            # exists only to cause the transaction to abort.
            pass

        self.assertThat(node_stop, MockCalledOnceWith(admin))
        self.assertEqual(NODE_STATUS.COMMISSIONING, node.status)

    def test_start_commissioning_sets_status_expired(self):
        node = factory.make_Node(status=NODE_STATUS.NEW)
        admin = factory.make_admin()

        set_status_expires = self.patch_autospec(Node, "_set_status_expires")

        self.patch(Node, "_start").return_value = None

        with post_commit_hooks:
            node.start_commissioning(admin)

        self.assertThat(set_status_expires, MockCalledOnceWith(node.system_id))

    def test_abort_commissioning_clears_status_expires(self):
        node = factory.make_Node(status=NODE_STATUS.COMMISSIONING)
        admin = factory.make_admin()
        self.patch(Node, "_stop").return_value = None
        clear_status_expires = self.patch_autospec(
            Node, "_clear_status_expires"
        )
        self.patch(Node, "_set_status")
        with post_commit_hooks:
            node.abort_commissioning(admin)
        self.assertThat(
            clear_status_expires, MockCalledOnceWith(node.system_id)
        )

    def test_abort_commissioning_sets_script_results_to_aborted(self):
        node = factory.make_Node(
            status=NODE_STATUS.COMMISSIONING, with_empty_script_sets=True
        )
        admin = factory.make_admin()
        self.patch(Node, "_stop").return_value = None
        self.patch_autospec(Node, "_clear_status_expires")
        self.patch(Node, "_set_status")
        abort_all_tests = self.patch_autospec(Node, "_abort_all_tests")
        with post_commit_hooks:
            node.abort_commissioning(admin)
        self.assertThat(
            abort_all_tests,
            MockCallsMatch(
                call(node.current_commissioning_script_set_id),
                call(node.current_testing_script_set_id),
            ),
        )

    def test_abort_commissioning_logs_user_request_and_creates_sts_msg(self):
        node = factory.make_Node(status=NODE_STATUS.COMMISSIONING)
        admin = factory.make_admin()
        self.patch(Node, "_clear_status_expires")
        self.patch(Node, "_set_status")
        self.patch(Node, "_stop").return_value = None
        with post_commit_hooks:
            node.abort_commissioning(admin)
        events = Event.objects.filter(node=node).order_by("id")
        self.assertEqual(
            events[0].type.name, EVENT_TYPES.REQUEST_NODE_ABORT_COMMISSIONING
        )
        self.assertEqual(
            events[1].type.name, EVENT_TYPES.ABORTED_COMMISSIONING
        )

    def test_abort_commissioning_logs_and_raises_errors_in_stopping(self):
        admin = factory.make_admin()
        node = factory.make_Node(status=NODE_STATUS.COMMISSIONING)
        maaslog = self.patch(node_module, "maaslog")
        exception_class = factory.make_exception_type()
        exception = exception_class(factory.make_name())
        self.patch(node, "_stop").side_effect = exception
        self.assertRaises(exception_class, node.abort_commissioning, admin)
        self.assertEqual(NODE_STATUS.COMMISSIONING, node.status)
        self.assertThat(
            maaslog.error,
            MockCalledOnceWith(
                "%s: Error when aborting commissioning: %s",
                node.hostname,
                exception,
            ),
        )

    def test_abort_commissioning_changes_status_and_stops_node(self):
        node = factory.make_Node(
            status=NODE_STATUS.COMMISSIONING, power_type="virsh"
        )
        admin = factory.make_admin()

        node_stop = self.patch(node, "_stop")
        # Return a post-commit hook from Node.stop().
        node_stop.side_effect = lambda user: post_commit()
        self.patch(Node, "_set_status")

        with post_commit_hooks:
            node.abort_commissioning(admin)

        self.assertThat(node_stop, MockCalledOnceWith(admin))
        self.assertThat(
            node._set_status,
            MockCalledOnceWith(node.system_id, status=NODE_STATUS.NEW),
        )

    def test_abort_commissioning_errors_if_node_is_not_commissioning(self):
        self.disable_node_query()
        unaccepted_statuses = set(map_enum(NODE_STATUS).values())
        unaccepted_statuses.remove(NODE_STATUS.COMMISSIONING)
        node = factory.make_Node(power_type="virsh")
        for status in unaccepted_statuses:
            node.status = status
            self.assertRaises(
                NodeStateViolation,
                node.abort_commissioning,
                factory.make_admin(),
            )

    def test_start_commissioning_sets_owner(self):
        node = factory.make_Node(
            status=NODE_STATUS.NEW, power_type="manual", enable_ssh=True
        )
        br = factory.make_default_ubuntu_release_bootable(
            arch=node.architecture
        )
        os_name, release = br.name.split("/")
        self.patch(
            boot_images, "get_common_available_boot_images"
        ).return_value = [
            {"osystem": os_name, "release": release, "purpose": "xinstall"}
        ]
        node_start = self.patch(node, "start")
        # Return a post-commit hook from Node.start().
        node_start.side_effect = (
            lambda user, user_data, old_status: post_commit()
        )
        admin = factory.make_admin()
        node.start_commissioning(admin)
        post_commit_hooks.reset()  # Ignore these for now.
        node = reload_object(node)
        self.assertEqual(node.status, NODE_STATUS.COMMISSIONING)
        self.assertEqual(node.owner, admin)

    def test_start_commissioning_requires_commissioning_os(self):
        node = factory.make_Node(
            status=NODE_STATUS.NEW, power_type="manual", enable_ssh=True
        )
        node_start = self.patch(node, "start")
        # Return a post-commit hook from Node.start().
        node_start.side_effect = (
            lambda user, user_data, old_status: post_commit()
        )
        admin = factory.make_admin()
        self.assertRaises(ValidationError, node.start_commissioning, admin)
        post_commit_hooks.reset()  # Ignore these for now.

    def test_abort_commissioning_unsets_owner(self):
        node = factory.make_Node(
            status=NODE_STATUS.COMMISSIONING,
            power_type="virsh",
            enable_ssh=True,
        )
        admin = factory.make_admin()

        node_stop = self.patch(node, "_stop")
        # Return a post-commit hook from Node.stop().
        node_stop.side_effect = lambda user: post_commit()
        self.patch(Node, "_set_status")

        with post_commit_hooks:
            node.abort_commissioning(admin)

        self.assertThat(node_stop, MockCalledOnceWith(admin))
        self.assertThat(
            node._set_status,
            MockCalledOnceWith(node.system_id, status=NODE_STATUS.NEW),
        )
        self.assertIsNone(node.owner)

    def test_start_testing_mode_raises_PermissionDenied_if_no_edit(self):
        user = factory.make_User()
        node = factory.make_Node(owner=user, status=NODE_STATUS.DEPLOYED)
        self.assertRaises(
            PermissionDenied, node.start_testing, factory.make_User()
        )

    def test_start_testing_errors_for_unconfigured_power_type(self):
        node = factory.make_Node(
            interface=True,
            status=NODE_STATUS.DEPLOYED,
            power_type=None,
        )
        admin = factory.make_admin()
        self.assertRaises(UnknownPowerType, node.start_testing, admin)

    def test_start_testing_errors_for_new_node_no_commissioning(self):
        node = factory.make_Node(interface=True, status=NODE_STATUS.NEW)
        admin = factory.make_admin()
        self.assertRaises(ValidationError, node.start_testing, admin)

    def test_start_testing_logs_user_request_creates_sts_msg(self):
        script = factory.make_Script(script_type=SCRIPT_TYPE.TESTING)
        node = factory.make_Node(
            interface=True, status=NODE_STATUS.DEPLOYED, power_type="manual"
        )
        self.patch(node, "_start").return_value = None
        admin = factory.make_admin()
        node.start_testing(admin, testing_scripts=[script.name])
        events = Event.objects.filter(node=node).order_by("id")
        post_commit_hooks.reset()  # Ignore these for now.
        node = reload_object(node)
        self.assertEqual(
            events[0].type.name, EVENT_TYPES.REQUEST_NODE_START_TESTING
        )
        self.assertEqual(events[1].type.name, EVENT_TYPES.TESTING)

    def test_start_testing_changes_status_and_starts_node(self):
        script = factory.make_Script(script_type=SCRIPT_TYPE.TESTING)
        node = factory.make_Node(
            interface=True, status=NODE_STATUS.DEPLOYED, power_type="manual"
        )
        mock_node_start = self.patch(node, "_start")
        mock_node_start.return_value = None
        admin = factory.make_admin()
        node.start_testing(admin, testing_scripts=[script.name])
        post_commit_hooks.reset()  # Ignore these for now.
        node = reload_object(node)
        self.assertEqual(NODE_STATUS.TESTING, node.status)
        self.assertThat(mock_node_start, MockCalledOnce())

    def test_start_testing_changes_status_and_starts_new_node(self):
        script = factory.make_Script(script_type=SCRIPT_TYPE.TESTING)
        node = factory.make_Node(
            interface=True, status=NODE_STATUS.NEW, power_type="manual"
        )
        node.current_commissioning_script_set = factory.make_ScriptSet(
            node=node, result_type=RESULT_TYPE.COMMISSIONING
        )
        factory.make_ScriptResult(
            script_set=node.current_commissioning_script_set
        )
        mock_node_start = self.patch(node, "_start")
        mock_node_start.return_value = None
        admin = factory.make_admin()
        node.start_testing(admin, testing_scripts=[script.name])
        post_commit_hooks.reset()  # Ignore these for now.
        node = reload_object(node)
        self.assertEqual(NODE_STATUS.TESTING, node.status)
        self.assertThat(mock_node_start, MockCalledOnce())

    def test_start_testing_sets_options(self):
        script = factory.make_Script(script_type=SCRIPT_TYPE.TESTING)
        rack = factory.make_RackController()
        node = factory.make_Node(
            interface=True,
            status=NODE_STATUS.DEPLOYED,
            power_type="virsh",
            bmc_connected_to=rack,
        )
        self.patch(node, "_start").return_value = None
        admin = factory.make_admin()
        enable_ssh = factory.pick_bool()
        node.start_testing(
            admin, enable_ssh=enable_ssh, testing_scripts=[script.name]
        )
        post_commit_hooks.reset()  # Ignore these for now.
        node = reload_object(node)
        self.assertEqual(enable_ssh, node.enable_ssh)

    def test_start_testing_sets_user_data(self):
        script = factory.make_Script(script_type=SCRIPT_TYPE.TESTING)
        node = factory.make_Node(status=NODE_STATUS.DEPLOYED)
        node_start = self.patch(node, "_start")
        node_start.side_effect = lambda *args, **kwargs: post_commit()
        user_data = factory.make_string().encode("ascii")
        generate_user_data_for_status = self.patch(
            node_module, "generate_user_data_for_status"
        )
        generate_user_data_for_status.return_value = user_data
        admin = factory.make_admin()
        node.start_testing(admin, testing_scripts=[script.name])
        post_commit_hooks.reset()  # Ignore these for now.
        self.assertThat(
            node_start,
            MockCalledOnceWith(
                admin, user_data, NODE_STATUS.DEPLOYED, allow_power_cycle=True
            ),
        )

    def test_start_testing_adds_default_testing_script_set(self):
        factory.make_Script(
            script_type=SCRIPT_TYPE.TESTING, tags=["commissioning"]
        )
        node = factory.make_Node(status=NODE_STATUS.DEPLOYED)
        self.patch(node, "_start").return_value = None

        with post_commit_hooks:
            node.start_testing(factory.make_admin())

        node = reload_object(node)

        self.assertIsNotNone(node.current_testing_script_set)

    def test_start_testing_adds_selected_scripts(self):
        node = factory.make_Node(status=NODE_STATUS.DEPLOYED)
        self.patch(node, "_start").return_value = None
        testing_scripts = [
            factory.make_Script(script_type=SCRIPT_TYPE.TESTING)
            for _ in range(10)
        ]
        testing_script_selected_by_tag = random.choice(testing_scripts)
        testing_script_selected_by_name = random.choice(testing_scripts)
        expected_testing_scripts = [
            testing_script_selected_by_tag.name,
            testing_script_selected_by_name.name,
        ]

        with post_commit_hooks:
            node.start_testing(
                factory.make_admin(), testing_scripts=expected_testing_scripts
            )

        node = reload_object(node)
        testing_script_set = node.current_testing_script_set

        self.assertCountEqual(
            set(expected_testing_scripts),
            [script_result.name for script_result in testing_script_set],
        )

    def test_start_testing_reverts_status_on_error(self):
        script = factory.make_Script(script_type=SCRIPT_TYPE.TESTING)
        # When start_testing encounters an error when trying to power cycle the
        # node, it will revert the node to its previous status.
        admin = factory.make_admin()
        node = factory.make_Node(status=NODE_STATUS.DEPLOYED)
        mock_node_start = self.patch(node, "_start")
        mock_node_start.side_effect = factory.make_exception()

        try:
            with transaction.atomic():
                node.start_testing(
                    admin, enable_ssh=True, testing_scripts=[script.name]
                )
        except mock_node_start.side_effect.__class__:
            # We don't care about the error here, so suppress it. It
            # exists only to cause the transaction to abort.
            pass

        self.expectThat(mock_node_start, MockCalledOnce())
        self.expectThat(NODE_STATUS.DEPLOYED, Equals(node.status))
        self.assertFalse(node.enable_ssh)

    def test_start_testing_logs_and_raises_errors(self):
        script = factory.make_Script(script_type=SCRIPT_TYPE.TESTING)
        admin = factory.make_admin()
        node = factory.make_Node(status=NODE_STATUS.DEPLOYED)
        mock_maaslog = self.patch(node_module, "maaslog")
        exception = NoConnectionsAvailable(factory.make_name())
        self.patch(node, "_start").side_effect = exception
        self.assertRaises(
            NoConnectionsAvailable,
            node.start_testing,
            admin,
            testing_scripts=[script.name],
        )
        self.expectThat(NODE_STATUS.DEPLOYED, Equals(node.status))
        self.expectThat(
            mock_maaslog.error,
            MockCalledOnceWith(
                "%s: Could not start testing for node: %s",
                node.hostname,
                exception,
            ),
        )

    def test_start_testing_sets_status_expired(self):
        node = factory.make_Node(status=NODE_STATUS.DEPLOYED)
        script = factory.make_Script(script_type=SCRIPT_TYPE.TESTING)
        admin = factory.make_admin()

        set_status_expires = self.patch_autospec(Node, "_set_status_expires")

        self.patch(node, "_start").return_value = None

        with post_commit_hooks:
            node.start_testing(admin, testing_scripts=[script.name])

        self.assertThat(set_status_expires, MockCalledOnceWith(node.system_id))

    def test_abort_testing_clears_status_expires(self):
        node = factory.make_Node(status=NODE_STATUS.TESTING)
        admin = factory.make_admin()
        self.patch(Node, "_stop").return_value = None
        clear_status_expires = self.patch_autospec(
            Node, "_clear_status_expires"
        )
        self.patch(Node, "_set_status")
        with post_commit_hooks:
            node.abort_testing(admin)
        self.assertThat(
            clear_status_expires, MockCalledOnceWith(node.system_id)
        )

    def test_start_testing_prevents_unconfigured_interfaces(self):
        script = factory.make_Script(
            script_type=SCRIPT_TYPE.TESTING,
            parameters={"interface": {"type": "interface"}},
        )
        admin = factory.make_admin()
        node = factory.make_Node(status=NODE_STATUS.DEPLOYED)
        self.assertRaises(
            ValidationError,
            node.start_testing,
            admin,
            testing_scripts=[script.name],
        )
        self.assertFalse(ScriptSet.objects.filter(node=node).exists())

    def test_start_testing_prevents_destructive_tests_on_deployed(self):
        script = factory.make_Script(
            script_type=SCRIPT_TYPE.TESTING, destructive=True
        )
        admin = factory.make_admin()
        node = factory.make_Node(status=NODE_STATUS.DEPLOYED)
        self.assertRaises(
            ValidationError,
            node.start_testing,
            admin,
            testing_scripts=[script.name],
        )
        self.assertFalse(ScriptSet.objects.filter(node=node).exists())

    def test_start_testing_prevents_destructive_tests_on_prev_deployed(self):
        script = factory.make_Script(
            script_type=SCRIPT_TYPE.TESTING, destructive=True
        )
        admin = factory.make_admin()
        node = factory.make_Node(
            previous_status=NODE_STATUS.DEPLOYED,
            status=NODE_STATUS.FAILED_TESTING,
        )
        self.assertRaises(
            ValidationError,
            node.start_testing,
            admin,
            testing_scripts=[script.name],
        )
        self.assertFalse(ScriptSet.objects.filter(node=node).exists())

    def test_start_testing_prevents_network_testing_with_xenial(self):
        script = factory.make_Script(
            script_type=SCRIPT_TYPE.TESTING, apply_configured_networking=True
        )
        admin = factory.make_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        self.assertRaises(
            ValidationError,
            node.start_testing,
            admin,
            testing_scripts=[script.name],
        )
        self.assertEqual(0, ScriptSet.objects.count())
        self.assertEqual(0, ScriptResult.objects.count())

    def test_udpate_status_logs_node_status_transition(self):
        self.disable_node_query()
        node = factory.make_Node(
            status=NODE_STATUS.DEPLOYING, owner=factory.make_User()
        )

        with LoggerFixture("maas") as logger:
            node.update_status(NODE_STATUS.DEPLOYED)

        stat = map_enum_reverse(NODE_STATUS)
        self.assertEqual(
            logger.output.strip(),
            f"{node.hostname}: Status transition "
            f"from {stat[NODE_STATUS.DEPLOYING]} to {stat[NODE_STATUS.DEPLOYED]}",
        )

    def test_update_status_checks_status_transition_and_raises_if_invalid(
        self,
    ):
        self.disable_node_query()
        # RETIRED -> ALLOCATED is an invalid transition.
        node = factory.make_Node(
            status=NODE_STATUS.RETIRED, owner=factory.make_User()
        )
        self.assertRaisesRegex(
            NodeStateViolation,
            "Invalid transition: Retired -> Allocated.",
            node.update_status,
            NODE_STATUS.ALLOCATED,
        )

    def test_save_passes_if_status_unchanged(self):
        self.disable_node_query()
        status = factory.pick_choice(NODE_STATUS_CHOICES)
        node = factory.make_Node(status=status)
        node.update_status(status)
        node.save()
        # The test is that this does not raise an error.

    def test_save_passes_if_status_valid_transition(self):
        self.disable_node_query()
        # NODE_STATUS.READY -> NODE_STATUS.ALLOCATED is a valid
        # transition.
        status = NODE_STATUS.READY
        node = factory.make_Node(status=status)
        node.update_status(NODE_STATUS.ALLOCATED)
        node.save()
        # The test is that this does not raise an error.

    def test_update_status_raises_node_state_violation_on_bad_transition(self):
        # RETIRED -> ALLOCATED is an invalid transition.
        node = factory.make_Node(
            status=NODE_STATUS.RETIRED, owner=factory.make_User()
        )
        self.assertRaisesRegex(
            NodeStateViolation,
            "Invalid transition: Retired -> Allocated.",
            node.update_status,
            NODE_STATUS.ALLOCATED,
        )

    def test_save_resets_status_expires_on_non_monitored_status(self):
        # Regression test for LP:1603563
        node = factory.make_Node(status=NODE_STATUS.RELEASING)
        Node._set_status_expires(node.system_id, 60)
        node = reload_object(node)
        node.update_status(NODE_STATUS.READY)
        node.save()
        node = reload_object(node)
        self.assertIsNone(node.status_expires)

    def test_netboot_defaults_to_True(self):
        node = Node()
        self.assertTrue(node.netboot)

    def test_ephemeral_deploy_defaults_to_False(self):
        node = Node()
        self.assertFalse(node.ephemeral_deploy)

    def test_fqdn_validation_failure_if_nonexistant(self):
        hostname_with_domain = "{}.{}".format(
            factory.make_string(),
            factory.make_string(),
        )
        self.assertRaises(
            ValidationError, factory.make_Node, hostname=hostname_with_domain
        )

    def test_fqdn_default_domain_if_not_given(self):
        domain = Domain.objects.get_default_domain()
        domain.name = factory.make_name("domain")
        domain.save()
        hostname_without_domain = factory.make_string()
        hostname = f"{hostname_without_domain}.{domain.name}"
        node = factory.make_Node(hostname=hostname_without_domain)
        self.assertEqual(hostname, node.fqdn)

    def test_fqdn_if_specified(self):
        # instantiate the default domain name
        Domain.objects.get_default_domain()
        # one for us.
        domain = factory.make_Domain()
        hostname_without_domain = factory.make_string()
        hostname = f"{hostname_without_domain}.{domain.name}"
        node = factory.make_Node(hostname=hostname)
        self.assertEqual(hostname, node.fqdn)

    def test_split_arch_doesnt_raise_on_missing_arch(self):
        # Method can be called from partition.py, etc, when arch is None.
        node = factory.make_Node(architecture=None)
        self.assertEqual(("", ""), node.split_arch())

    def test_split_arch_returns_arch_as_tuple(self):
        main_arch = factory.make_name("arch")
        sub_arch = factory.make_name("subarch")
        full_arch = f"{main_arch}/{sub_arch}"
        node = factory.make_Node(architecture=full_arch)
        self.assertEqual((main_arch, sub_arch), node.split_arch())

    def test_split_arch_always_2_tuple(self):
        node = factory.make_Node(architecture="foo/bar/baz")
        self.assertEqual(node.split_arch(), ("foo", "bar/baz"))

    def test_mark_failed_updates_status(self):
        self.disable_node_query()
        nodes_mapping = {
            status: factory.make_Node(status=status)
            for status in NODE_FAILURE_STATUS_TRANSITIONS
        }
        for node in nodes_mapping.values():
            node.mark_failed(None, factory.make_name("error-description"))
        self.assertEqual(
            NODE_FAILURE_STATUS_TRANSITIONS,
            {status: node.status for status, node in nodes_mapping.items()},
        )

    def test_mark_failed_logs_user_request(self):
        owner = factory.make_User()
        self.disable_node_query()
        node = factory.make_Node(status=NODE_STATUS.COMMISSIONING, owner=owner)
        description = factory.make_name("error-description")
        register_event = self.patch(node, "_register_request_event")
        node.mark_failed(owner, description)
        self.assertThat(
            register_event,
            MockCalledOnceWith(
                owner,
                EVENT_TYPES.REQUEST_NODE_MARK_FAILED,
                action="mark_failed",
                comment=description,
            ),
        )

    def test_mark_failed_updates_all_pending_and_running_script_statuses(self):
        self.disable_node_query()
        node = factory.make_Node(
            status=random.choice(
                list(NODE_FAILURE_MONITORED_STATUS_TRANSITIONS)
            )
        )
        node.current_commissioning_script_set = factory.make_ScriptSet(
            node=node
        )
        node.current_testing_script_set = factory.make_ScriptSet(node=node)
        node.current_installation_script_set = factory.make_ScriptSet(
            node=node
        )
        updated_script_results = []
        untouched_script_results = []
        for script_set in (
            node.current_commissioning_script_set,
            node.current_testing_script_set,
            node.current_installation_script_set,
        ):
            script_result = factory.make_ScriptResult(script_set)
            if script_result.status in SCRIPT_STATUS_RUNNING_OR_PENDING:
                updated_script_results.append(script_result)
            else:
                untouched_script_results.append(script_result)
        script_result_status = random.choice(
            [SCRIPT_STATUS.TIMEDOUT, SCRIPT_STATUS.FAILED]
        )

        node.mark_failed(script_result_status=script_result_status)

        for script_result in updated_script_results:
            self.assertEqual(
                script_result_status, reload_object(script_result).status
            )
        for script_result in untouched_script_results:
            self.assertEqual(
                script_result.status, reload_object(script_result).status
            )

    def test_mark_failed_updates_error_description(self):
        self.disable_node_query()
        node = factory.make_Node(status=NODE_STATUS.COMMISSIONING)
        description = factory.make_name("error-description")
        node.mark_failed(None, description)
        self.assertEqual(description, reload_object(node).error_description)

    def test_mark_failed_raises_for_unauthorized_node_status(self):
        but_not = list(NODE_FAILURE_STATUS_TRANSITIONS.keys())
        but_not.extend(NODE_FAILURE_STATUS_TRANSITIONS.values())
        but_not.append(NODE_STATUS.NEW)
        status = factory.pick_choice(NODE_STATUS_CHOICES, but_not=but_not)
        node = factory.make_Node(status=status)
        description = factory.make_name("error-description")
        self.assertRaises(
            NodeStateViolation, node.mark_failed, None, description
        )

    def test_mark_failed_ignores_if_already_failed(self):
        status = random.choice(
            [NODE_STATUS.FAILED_DEPLOYMENT, NODE_STATUS.FAILED_COMMISSIONING]
        )
        node = factory.make_Node(status=status)
        description = factory.make_name("error-description")
        node.mark_failed(None, description)
        self.assertEqual(status, node.status)

    def test_mark_failed_ignores_if_status_is_NEW(self):
        node = factory.make_Node(status=NODE_STATUS.NEW)
        description = factory.make_name("error-description")
        node.mark_failed(None, description)
        self.assertEqual(NODE_STATUS.NEW, node.status)

    def test_mark_broken_changes_status_to_broken(self):
        user = factory.make_User()
        node = factory.make_Node(status=NODE_STATUS.NEW, owner=user)
        node.mark_broken(user, factory.make_name("error-description"))
        self.assertEqual(NODE_STATUS.BROKEN, reload_object(node).status)

    def test_mark_broken_logs_user_request(self):
        owner = factory.make_User()
        node = factory.make_Node(status=NODE_STATUS.NEW, owner=owner)
        description = factory.make_name("error-description")
        register_event = self.patch(node, "_register_request_event")
        node.mark_broken(owner, description)
        self.assertThat(
            register_event,
            MockCalledOnceWith(
                owner,
                EVENT_TYPES.REQUEST_NODE_MARK_BROKEN,
                action="mark broken",
                comment=description,
            ),
        )

    def test_mark_broken_releases_allocated_node(self):
        user = factory.make_User()
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED, owner=user)
        err_desc = factory.make_name("error-description")
        release = self.patch(node, "_release")
        node.mark_broken(user, err_desc)
        self.expectThat(node.owner, Is(None))
        self.assertThat(release, MockCalledOnceWith(user))

    def test_mark_fixed_sets_default_osystem_and_distro_series(self):
        node = factory.make_Node(status=NODE_STATUS.BROKEN)
        node.osystem = factory.make_name("osystem")
        node.distro_series = factory.make_name("distro_series")
        node.mark_fixed(factory.make_User())
        expected_osystem = expected_distro_series = ""
        self.expectThat(expected_osystem, Equals(node.osystem))
        self.expectThat(expected_distro_series, Equals(node.distro_series))

    def test_mark_fixed_changes_status(self):
        node = factory.make_Node(status=NODE_STATUS.BROKEN)
        node.mark_fixed(factory.make_User())
        self.assertEqual(NODE_STATUS.READY, reload_object(node).status)

    def test_mark_fixed_changes_status_to_deployed_if_previous_status(self):
        node = factory.make_Node(
            status=NODE_STATUS.BROKEN, previous_status=NODE_STATUS.DEPLOYED
        )
        node.mark_fixed(factory.make_User())
        self.assertEqual(NODE_STATUS.DEPLOYED, reload_object(node).status)

    def test_mark_fixed_logs_user_request(self):
        owner = factory.make_User()
        node = factory.make_Node(status=NODE_STATUS.BROKEN, owner=owner)
        register_event = self.patch(node, "_register_request_event")
        node.mark_fixed(owner)
        self.assertThat(
            register_event,
            MockCalledOnceWith(
                owner,
                EVENT_TYPES.REQUEST_NODE_MARK_FIXED,
                action="mark fixed",
                comment=None,
            ),
        )

    def test_mark_fixed_updates_error_description(self):
        description = factory.make_name("error-description")
        node = factory.make_Node(
            status=NODE_STATUS.BROKEN, error_description=description
        )
        node.mark_fixed(factory.make_User())
        self.assertEqual("", reload_object(node).error_description)

    def test_mark_fixed_fails_if_node_isnt_broken(self):
        status = factory.pick_choice(
            NODE_STATUS_CHOICES, but_not=[NODE_STATUS.BROKEN]
        )
        node = factory.make_Node(status=status)
        self.assertRaises(
            NodeStateViolation, node.mark_fixed, factory.make_User()
        )

    def test_mark_fixed_clears_current_installation_results(self):
        node = factory.make_Node(
            status=NODE_STATUS.BROKEN, with_empty_script_sets=True
        )
        node.mark_fixed(factory.make_User())
        self.assertIsNone(reload_object(node).current_installation_script_set)

    def test_override_failed_testing_logs_user_request(self):
        owner = factory.make_User()
        node = factory.make_Node(
            status=NODE_STATUS.FAILED_TESTING, owner=owner
        )
        register_event = self.patch(node, "_register_request_event")
        node.override_failed_testing(owner)
        self.assertThat(
            register_event,
            MockCalledOnceWith(
                owner,
                EVENT_TYPES.REQUEST_NODE_OVERRIDE_FAILED_TESTING,
                action="ignore failed tests",
                comment=None,
            ),
        )

    def test_override_failed_testing_updates_error_description(self):
        owner = factory.make_User()
        description = factory.make_name("error-description")
        node = factory.make_Node(
            status=NODE_STATUS.FAILED_TESTING,
            owner=owner,
            error_description=description,
        )
        node.override_failed_testing(owner)
        self.assertEqual("", reload_object(node).error_description)

    def test_override_failed_testing_fails_if_node_isnt_broken(self):
        owner = factory.make_User()
        status = factory.pick_choice(
            NODE_STATUS_CHOICES, but_not=[NODE_STATUS.FAILED_TESTING]
        )
        node = factory.make_Node(status=status, owner=owner)
        self.assertRaises(
            NodeStateViolation, node.override_failed_testing, owner
        )

    def test_override_failed_testing_sets_status_to_ready(self):
        owner = factory.make_User()
        node = factory.make_Node(
            status=NODE_STATUS.FAILED_TESTING, owner=owner, osystem=""
        )
        node.override_failed_testing(owner)
        node = reload_object(node)
        self.assertEqual(NODE_STATUS.READY, node.status)
        self.assertEqual("", node.osystem)

    def test_override_failed_testing_sets_status_to_deployed(self):
        owner = factory.make_User()
        osystem = factory.make_name("osystem")
        node = factory.make_Node(
            status=NODE_STATUS.FAILED_TESTING, owner=owner, osystem=osystem
        )
        node.override_failed_testing(owner)
        node = reload_object(node)
        self.assertEqual(NODE_STATUS.DEPLOYED, node.status)
        self.assertEqual(osystem, node.osystem)

    def test_update_power_state(self):
        node = factory.make_Node()
        state = factory.pick_enum(POWER_STATE)
        node.update_power_state(state)
        self.assertEqual(state, reload_object(node).power_state)

    def test_update_power_state_sets_last_updated_field(self):
        node = factory.make_Node(power_state_updated=None)
        self.assertIsNone(node.power_state_updated)
        previous_updated = node.power_state_updated = now()
        node.save()
        state = factory.pick_enum(POWER_STATE)
        node.update_power_state(state)
        self.assertNotEqual(
            previous_updated, reload_object(node).power_state_updated
        )

    def test_update_power_state_readies_node_if_releasing(self):
        node = factory.make_Node(
            power_state=POWER_STATE.ON,
            status=NODE_STATUS.RELEASING,
            owner=None,
        )
        self.patch(Node, "_clear_status_expires")
        with post_commit_hooks:
            node.update_power_state(POWER_STATE.OFF)
        self.expectThat(node.status, Equals(NODE_STATUS.NEW))
        self.expectThat(node.owner, Is(None))

    def test_update_power_state_does_not_change_status_if_not_releasing(self):
        node = factory.make_Node(
            power_state=POWER_STATE.ON, status=NODE_STATUS.ALLOCATED
        )
        node.update_power_state(POWER_STATE.OFF)
        self.assertEqual(NODE_STATUS.ALLOCATED, node.status)

    def test_update_power_state_clear_status_expires_if_releasing(self):
        node = factory.make_Node(
            power_state=POWER_STATE.ON,
            status=NODE_STATUS.RELEASING,
            owner=None,
            status_expires=datetime.now(),
        )
        node.update_power_state(POWER_STATE.OFF)
        self.assertIsNone(node.status_expires)

    def test_update_power_state_does_not_clear_expires_if_not_releasing(self):
        node = factory.make_Node(
            power_state=POWER_STATE.ON, status=NODE_STATUS.ALLOCATED
        )
        self.patch(Node, "_clear_status_expires")
        node.update_power_state(POWER_STATE.OFF)
        self.assertThat(Node._clear_status_expires, MockNotCalled())

    def test_update_power_state_does_not_change_status_if_not_off(self):
        node = factory.make_Node(
            power_state=POWER_STATE.OFF, status=NODE_STATUS.ALLOCATED
        )
        node.update_power_state(POWER_STATE.ON)
        self.assertEqual(NODE_STATUS.ALLOCATED, node.status)

    def test_update_power_state_release_interface_config_if_releasing(self):
        node = factory.make_Node(
            power_state=POWER_STATE.ON,
            status=NODE_STATUS.RELEASING,
            owner=None,
        )
        release = self.patch_autospec(node, "release_interface_config")
        self.patch(Node, "_clear_status_expires")
        node.update_power_state(POWER_STATE.OFF)
        # release_interface_config() is called once by update_power_state and
        # a second time by the release_auto_ips() signal. Whichever runs
        # second is a noop but is needed for commissioning/testing.
        self.assertThat(release, MockCallsMatch(call(), call()))

    def test_update_power_state_doesnt_release_interface_config_if_on(self):
        node = factory.make_Node(
            power_state=POWER_STATE.OFF, status=NODE_STATUS.ALLOCATED
        )
        release = self.patch_autospec(node, "release_interface_config")
        node.update_power_state(POWER_STATE.ON)
        self.assertThat(release, MockNotCalled())

    def test_update_power_state_reverts_status(self):
        previous_status = random.choice(
            [
                transition
                for transition, statuses in NODE_TRANSITIONS.items()
                if NODE_STATUS.ENTERING_RESCUE_MODE in statuses
                and transition != NODE_STATUS.DEPLOYED
            ]
        )
        node = factory.make_Node(
            status=NODE_STATUS.EXITING_RESCUE_MODE,
            previous_status=previous_status,
        )
        node.update_power_state(POWER_STATE.OFF)
        self.assertEqual(previous_status, node.status)

    def test_update_power_state_sets_status_to_deployed(self):
        node = factory.make_Node(
            status=NODE_STATUS.EXITING_RESCUE_MODE,
            previous_status=NODE_STATUS.DEPLOYED,
        )
        node.update_power_state(POWER_STATE.ON)
        self.assertEqual(NODE_STATUS.DEPLOYED, node.status)

    def test_update_power_state_fails_exiting_rescue_mode_for_ready(self):
        node = factory.make_Node(
            status=NODE_STATUS.EXITING_RESCUE_MODE,
            previous_status=NODE_STATUS.READY,
        )
        node.update_power_state(POWER_STATE.ON)
        self.assertEqual(NODE_STATUS.FAILED_EXITING_RESCUE_MODE, node.status)

    def test_update_power_state_fails_exiting_rescue_mode_for_broken(self):
        node = factory.make_Node(
            status=NODE_STATUS.EXITING_RESCUE_MODE,
            previous_status=NODE_STATUS.BROKEN,
        )
        node.update_power_state(POWER_STATE.ON)
        self.assertEqual(NODE_STATUS.FAILED_EXITING_RESCUE_MODE, node.status)

    def test_update_power_state_fails_exiting_rescue_mode_for_deployed(self):
        node = factory.make_Node(
            status=NODE_STATUS.EXITING_RESCUE_MODE,
            previous_status=NODE_STATUS.DEPLOYED,
        )
        node.update_power_state(POWER_STATE.OFF)
        self.assertEqual(NODE_STATUS.FAILED_EXITING_RESCUE_MODE, node.status)

    def test_update_power_state_fails_exiting_rescue_mode_status_msg(self):
        node = factory.make_Node(
            status=NODE_STATUS.EXITING_RESCUE_MODE,
            previous_status=NODE_STATUS.DEPLOYED,
        )
        node.update_power_state(POWER_STATE.OFF)
        event = Event.objects.last()
        self.assertEqual(
            event.type.name, EVENT_TYPES.FAILED_EXITING_RESCUE_MODE
        )

    def test_update_power_state_creates_status_message_for_deployed(self):
        node = factory.make_Node(
            status=NODE_STATUS.EXITING_RESCUE_MODE,
            previous_status=NODE_STATUS.DEPLOYED,
        )
        node.update_power_state(POWER_STATE.ON)
        event = Event.objects.get(node=node)
        self.assertEqual(NODE_STATUS.DEPLOYED, node.status)
        self.assertEqual(event.type.name, EVENT_TYPES.EXITED_RESCUE_MODE)

    def test_update_power_state_creates_status_message_for_non_deployed(self):
        node = factory.make_Node(
            status=NODE_STATUS.EXITING_RESCUE_MODE,
            previous_status=NODE_STATUS.READY,
        )
        node.update_power_state(POWER_STATE.OFF)
        event = Event.objects.get(node=node)
        self.assertEqual(NODE_STATUS.READY, node.status)
        self.assertEqual(event.type.name, EVENT_TYPES.EXITED_RESCUE_MODE)

    def test_end_deployment_changes_state_and_creates_sts_msg(self):
        self.disable_node_query()
        node = factory.make_Node(status=NODE_STATUS.DEPLOYING)
        node.end_deployment()
        events = Event.objects.filter(node=node)
        self.assertEqual(NODE_STATUS.DEPLOYED, reload_object(node).status)
        self.assertEqual(
            {event.type.name for event in events},
            {EVENT_TYPES.IMAGE_DEPLOYED, EVENT_TYPES.DEPLOYED},
        )

    def test_end_deployment_sets_first_last_sync_value(self):
        self.disable_node_query()
        node = factory.make_Node(
            status=NODE_STATUS.DEPLOYING, enable_hw_sync=True
        )
        self.assertIsNone(node.last_sync)
        node.end_deployment()
        self.assertIsNotNone(node.last_sync)

    def test_start_deployment_changes_state_and_creates_sts_msg(self):
        node = factory.make_Node_with_Interface_on_Subnet(
            status=NODE_STATUS.ALLOCATED
        )
        node._start_deployment()
        event = Event.objects.get(node=node)
        self.assertEqual(NODE_STATUS.DEPLOYING, reload_object(node).status)
        self.assertEqual(event.type.name, EVENT_TYPES.DEPLOYING)

    def test_start_deployment_creates_installation_script_set(self):
        node = factory.make_Node_with_Interface_on_Subnet(
            status=NODE_STATUS.ALLOCATED
        )
        node._start_deployment()
        self.assertIsNotNone(node.current_installation_script_set)
        node.current_installation_script_set.scriptresult_set.get(
            script_name=CURTIN_INSTALL_LOG
        )

    def test_start_deployment_requires_deployment_os(self):
        node = factory.make_Node_with_Interface_on_Subnet(
            status=NODE_STATUS.ALLOCATED
        )
        node.osystem = factory.make_name("osystem")
        node.distro_series = factory.make_name("distro")
        admin = factory.make_admin()
        self.assertRaises(ValidationError, node._start, admin)

    def test_start_deployment_requires_commissioning_os_for_non_ubuntu(self):
        node = factory.make_Node_with_Interface_on_Subnet(
            status=NODE_STATUS.ALLOCATED
        )
        node.osystem = factory.make_name("osystem")
        node.distro_series = factory.make_name("distro")
        admin = factory.make_admin()
        self.patch(
            boot_images, "get_common_available_boot_images"
        ).return_value = [
            {
                "osystem": node.osystem,
                "release": node.distro_series,
                "purpose": "xinstall",
            }
        ]
        self.assertRaises(ValidationError, node._start, admin)

    def test_get_boot_purpose_known_node(self):
        # The following table shows the expected boot "purpose" for each set
        # of node parameters.
        options = [
            ("commissioning", {"status": NODE_STATUS.NEW}),
            ("commissioning", {"status": NODE_STATUS.COMMISSIONING}),
            ("commissioning", {"status": NODE_STATUS.TESTING}),
            ("commissioning", {"status": NODE_STATUS.DISK_ERASING}),
            ("poweroff", {"status": NODE_STATUS.FAILED_COMMISSIONING}),
            ("poweroff", {"status": NODE_STATUS.MISSING}),
            ("poweroff", {"status": NODE_STATUS.READY}),
            ("poweroff", {"status": NODE_STATUS.RESERVED}),
            ("xinstall", {"status": NODE_STATUS.DEPLOYING, "netboot": True}),
            ("local", {"status": NODE_STATUS.DEPLOYING, "netboot": False}),
            ("local", {"status": NODE_STATUS.DEPLOYED}),
            ("poweroff", {"status": NODE_STATUS.RETIRED}),
            (
                "local",
                {"status": NODE_STATUS.DEFAULT, "node_type": NODE_TYPE.DEVICE},
            ),
        ]
        node = factory.make_Node()
        mock_get_boot_images_for = self.patch(
            preseed_module, "get_boot_images_for"
        )
        for purpose, parameters in options:
            boot_image = make_rpc_boot_image(purpose=purpose)
            mock_get_boot_images_for.return_value = [boot_image]
            for name, value in parameters.items():
                setattr(node, name, value)
            self.assertEqual(purpose, node.get_boot_purpose())

    def test_boot_interface_default_is_none(self):
        node = factory.make_Node()
        self.assertIsNone(node.boot_interface)

    def test_get_boot_interface_returns_boot_interface_if_set(self):
        node = factory.make_Node(interface=True)
        node.boot_interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node
        )
        node.save()
        self.assertEqual(node.boot_interface, node.get_boot_interface())

    def test_get_boot_interface_returns_first_interface_if_unset(self):
        node = factory.make_Node(interface=True)
        for _ in range(3):
            factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        self.assertEqual(
            node.current_config.interface_set.order_by("id").first(),
            node.get_boot_interface(),
        )

    def test_boot_interface_deletion_does_not_delete_node(self):
        node = factory.make_Node(interface=True)
        node.boot_interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node
        )
        node.save()
        node.boot_interface.delete()
        self.assertIsNotNone(reload_object(node))

    def test_get_extra_macs_returns_all_but_boot_interface_mac(self):
        node = factory.make_Node()
        interfaces = [
            factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
            for _ in range(3)
        ]
        # Do not set the boot interface to the first interface to make sure the
        # boot interface (and not the first created) is excluded from the list
        # returned by `get_extra_macs`.
        boot_interface_index = 1
        node.boot_interface = interfaces[boot_interface_index]
        node.save()
        del interfaces[boot_interface_index]
        self.assertCountEqual(
            [interface.mac_address for interface in interfaces],
            node.get_extra_macs(),
        )

    def test_get_extra_macs_returns_all_but_first_interface_if_not_boot(self):
        node = factory.make_Node()
        interfaces = [
            factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
            for _ in range(3)
        ]
        self.assertCountEqual(
            [interface.mac_address for interface in interfaces[1:]],
            node.get_extra_macs(),
        )

    def test_clear_full_storage_configuration_removes_related_objects(self):
        node = factory.make_Node()
        physical_block_devices = [
            factory.make_PhysicalBlockDevice(node=node, size=10 * 1000**3)
            for _ in range(3)
        ]
        filesystem = factory.make_Filesystem(
            block_device=physical_block_devices[0]
        )
        partition_table = factory.make_PartitionTable(
            block_device=physical_block_devices[1]
        )
        partition = factory.make_Partition(partition_table=partition_table)
        fslvm = factory.make_Filesystem(
            block_device=physical_block_devices[2],
            fstype=FILESYSTEM_TYPE.LVM_PV,
        )
        vgroup = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.LVM_VG, filesystems=[fslvm]
        )
        vbd1 = factory.make_VirtualBlockDevice(
            filesystem_group=vgroup, size=2 * 1000**3
        )
        vbd2 = factory.make_VirtualBlockDevice(
            filesystem_group=vgroup, size=3 * 1000**3
        )
        filesystem_on_vbd1 = factory.make_Filesystem(
            block_device=vbd1, fstype=FILESYSTEM_TYPE.LVM_PV
        )
        vgroup_on_vgroup = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.LVM_VG,
            filesystems=[filesystem_on_vbd1],
        )
        vbd3_on_vbd1 = factory.make_VirtualBlockDevice(
            filesystem_group=vgroup_on_vgroup, size=1 * 1000**3
        )
        node._clear_full_storage_configuration()
        for pbd in physical_block_devices:
            self.expectThat(
                reload_object(pbd),
                Not(Is(None)),
                "Physical block device should not have been deleted.",
            )
        self.expectThat(
            reload_object(filesystem),
            Is(None),
            "Filesystem should have been removed.",
        )
        self.expectThat(
            reload_object(partition_table),
            Is(None),
            "PartitionTable should have been removed.",
        )
        self.expectThat(
            reload_object(partition),
            Is(None),
            "Partition should have been removed.",
        )
        self.expectThat(
            reload_object(fslvm),
            Is(None),
            "LVM PV Filesystem should have been removed.",
        )
        self.expectThat(
            reload_object(vgroup),
            Is(None),
            "Volume group should have been removed.",
        )
        self.expectThat(
            reload_object(vbd1),
            Is(None),
            "Virtual block device should have been removed.",
        )
        self.expectThat(
            reload_object(vbd2),
            Is(None),
            "Virtual block device should have been removed.",
        )
        self.expectThat(
            reload_object(filesystem_on_vbd1),
            Is(None),
            "Filesystem on virtual block device should have been removed.",
        )
        self.expectThat(
            reload_object(vgroup_on_vgroup),
            Is(None),
            "Volume group on virtual block device should have been removed.",
        )
        self.expectThat(
            reload_object(vbd3_on_vbd1),
            Is(None),
            "Virtual block device on another virtual block device should have "
            "been removed.",
        )

    def test_clear_full_storage_configuration_removes_special_fs(self):
        node = factory.make_Node()
        special_filesystems = [
            factory.make_Filesystem(
                node_config=node.current_config, fstype=FILESYSTEM_TYPE.TMPFS
            ),
            factory.make_Filesystem(
                node_config=node.current_config, fstype=FILESYSTEM_TYPE.TMPFS
            ),
        ]
        self.assertCountEqual(
            node.current_config.special_filesystems.all(), special_filesystems
        )
        node._clear_full_storage_configuration()
        self.assertCountEqual(
            node.current_config.special_filesystems.all(), []
        )

    def test_clear_full_storage_configuration_lp1815091(self):
        node = factory.make_Node()
        physical_block_devices = [
            factory.make_PhysicalBlockDevice(node=node, size=10 * 1000**3)
            for _ in range(4)
        ]
        raid5_filesystems = [
            factory.make_Filesystem(
                block_device=bd, fstype=FILESYSTEM_TYPE.RAID
            )
            for bd in physical_block_devices[:3]
        ]
        raid5 = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.RAID_5,
            filesystems=raid5_filesystems,
        ).virtual_device
        backing_filesystem = factory.make_Filesystem(
            block_device=raid5, fstype=FILESYSTEM_TYPE.BCACHE_BACKING
        )
        cacheset = factory.make_CacheSet(
            block_device=physical_block_devices[3]
        )
        root = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.BCACHE,
            filesystems=[backing_filesystem],
            cache_set=cacheset,
        )
        node._clear_full_storage_configuration()
        for pbd in physical_block_devices:
            self.expectThat(
                reload_object(pbd),
                Not(Is(None)),
                "Physical block device should not have been deleted.",
            )
        self.expectThat(
            reload_object(root), Is(None), "Bcache should have been removed."
        )
        self.expectThat(
            reload_object(raid5), Is(None), "Raid should have been removed."
        )

    def test_create_acquired_filesystems(self):
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED)
        block_device = factory.make_PhysicalBlockDevice(node=node)
        filesystem = factory.make_Filesystem(
            block_device=block_device, fstype=FILESYSTEM_TYPE.EXT4
        )
        node._create_acquired_filesystems()
        self.assertIsNotNone(
            reload_object(filesystem),
            "Original filesystem on should not have been deleted.",
        )
        self.assertIsNot(
            filesystem,
            block_device.get_effective_filesystem(),
            "Filesystem on block device should now be a different object.",
        )
        self.assertTrue(
            block_device.get_effective_filesystem().acquired,
            "Filesystem on block device should have acquired set.",
        )

    def test_create_acquired_filesystems_calls_clear(self):
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED)
        mock_clear_acquired_filesystems = self.patch_autospec(
            node, "_clear_acquired_filesystems"
        )
        node._create_acquired_filesystems()
        self.assertThat(mock_clear_acquired_filesystems, MockCalledOnceWith())

    def test_clear_acquired_filesystems_only_removes_acquired(self):
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED)
        block_device = factory.make_PhysicalBlockDevice(node=node)
        filesystem = factory.make_Filesystem(
            block_device=block_device, fstype=FILESYSTEM_TYPE.EXT4
        )
        acquired_filesystem = factory.make_Filesystem(
            block_device=block_device,
            fstype=FILESYSTEM_TYPE.EXT4,
            acquired=True,
        )
        node._clear_acquired_filesystems()
        self.expectThat(
            reload_object(acquired_filesystem),
            Is(None),
            "Acquired filesystem should have been deleted.",
        )
        self.expectThat(
            reload_object(filesystem),
            Not(Is(None)),
            "Non-acquired filesystem should not have been deleted.",
        )

    def test_boot_disk_removes_formatable_filesystem(self):
        node = factory.make_Node()
        new_boot_disk = factory.make_PhysicalBlockDevice(node=node)
        filesystem = factory.make_Filesystem(
            fstype=FILESYSTEM_TYPE.EXT4, block_device=new_boot_disk
        )
        node.boot_disk = new_boot_disk
        node.save()
        self.assertIsNone(reload_object(filesystem))

    def test_boot_disk_displays_error_if_in_filesystem_group(self):
        node = factory.make_Node()
        new_boot_disk = factory.make_PhysicalBlockDevice(node=node)
        pv_filesystem = factory.make_Filesystem(
            fstype=FILESYSTEM_TYPE.LVM_PV, block_device=new_boot_disk
        )
        filesystem_group = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.LVM_VG,
            filesystems=[pv_filesystem],
        )
        node.boot_disk = new_boot_disk
        error = self.assertRaises(ValidationError, node.save)
        self.assertEqual(
            {
                "boot_disk": [
                    "Cannot be set as the boot disk; already in-use in %s "
                    "'%s'."
                    % (filesystem_group.get_nice_name(), filesystem_group.name)
                ]
            },
            error.message_dict,
        )

    def test_boot_disk_displays_error_if_in_cache_set(self):
        node = factory.make_Node()
        new_boot_disk = factory.make_PhysicalBlockDevice(node=node)
        cache_set = factory.make_CacheSet(block_device=new_boot_disk)
        node.boot_disk = new_boot_disk
        error = self.assertRaises(ValidationError, node.save)
        self.assertEqual(
            {
                "boot_disk": [
                    "Cannot be set as the boot disk; already in-use in cache set "
                    "'%s'." % (cache_set.name,)
                ]
            },
            error.message_dict,
        )

    def test_boot_interface_displays_error_if_not_hosts_interface(self):
        node0 = factory.make_Node(interface=True)
        node1 = factory.make_Node()
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node1)
        node0.boot_interface = interface
        exception = self.assertRaises(ValidationError, node0.save)
        msg = {"boot_interface": ["Must be one of the node's interfaces."]}
        self.assertEqual(msg, exception.message_dict)

    def test_boot_interface_accepts_valid_interface(self):
        node = factory.make_Node()
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        node.boot_interface = interface
        node.save()

    def test_get_boot_rack_controller_returns_rack_from_boot_ip(self):
        node = factory.make_Node()
        fabric = factory.make_Fabric()
        vlan = fabric.get_default_vlan()
        subnet = factory.make_Subnet(vlan=vlan)
        boot_interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node, vlan=vlan
        )
        primary_rack = factory.make_RackController()
        primary_rack_interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=primary_rack, vlan=vlan
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_Subnet(subnet),
            subnet=subnet,
            interface=primary_rack_interface,
        )
        secondary_rack = factory.make_RackController()
        secondary_rack_interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=secondary_rack, vlan=vlan
        )
        secondary_rack_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_Subnet(subnet),
            subnet=subnet,
            interface=secondary_rack_interface,
        )
        vlan.dhcp_on = True
        vlan.primary_rack = primary_rack
        vlan.secondary_rack = secondary_rack
        vlan.save()
        node.boot_interface = boot_interface
        node.boot_cluster_ip = secondary_rack_ip.ip
        node.save()
        self.assertEqual(secondary_rack, node.get_boot_rack_controller())

    def test_get_boot_rack_controller_returns_primary_rack(self):
        node = factory.make_Node()
        fabric = factory.make_Fabric()
        vlan = fabric.get_default_vlan()
        subnet = factory.make_Subnet(vlan=vlan)
        boot_interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node, vlan=vlan
        )
        primary_rack = factory.make_RackController()
        primary_rack_interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=primary_rack, vlan=vlan
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_Subnet(subnet),
            subnet=subnet,
            interface=primary_rack_interface,
        )
        secondary_rack = factory.make_RackController()
        secondary_rack_interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=secondary_rack, vlan=vlan
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_Subnet(subnet),
            subnet=subnet,
            interface=secondary_rack_interface,
        )
        vlan.dhcp_on = True
        vlan.primary_rack = primary_rack
        vlan.secondary_rack = secondary_rack
        vlan.save()
        node.boot_interface = boot_interface
        node.save()
        self.assertEqual(primary_rack, node.get_boot_rack_controller())

    def test_register_request_event_saves_event(self):
        node = factory.make_Node()
        user = factory.make_User()
        log_mock = self.patch_autospec(
            Event.objects, "register_event_and_event_type"
        )
        event_name = EVENT_TYPES.REQUEST_NODE_START
        event_action = factory.make_name("action")
        event_details = EVENT_DETAILS[event_name]
        comment = factory.make_name("comment")
        event_description = f"({user.username}) - {comment}"
        node._register_request_event(user, event_name, event_action, comment)
        self.assertThat(
            log_mock,
            MockCalledOnceWith(
                EVENT_TYPES.REQUEST_NODE_START,
                type_level=event_details.level,
                type_description=event_details.description,
                user=user,
                event_action=event_action,
                event_description=event_description,
                system_id=node.system_id,
            ),
        )

    def test_register_request_event_none_user_saves_comment_not_user(self):
        node = factory.make_Node()
        log_mock = self.patch_autospec(
            Event.objects, "register_event_and_event_type"
        )
        event_name = EVENT_TYPES.REQUEST_NODE_START
        event_action = factory.make_name("action")
        event_details = EVENT_DETAILS[event_name]
        comment = factory.make_name("comment")
        event_description = "%s" % comment
        node._register_request_event(None, event_name, event_action, comment)
        self.assertThat(
            log_mock,
            MockCalledOnceWith(
                EVENT_TYPES.REQUEST_NODE_START,
                type_level=event_details.level,
                type_description=event_details.description,
                user=None,
                event_action=event_action,
                event_description=event_description,
                system_id=node.system_id,
            ),
        )

    def test_status_event_returns_cached_event(self):
        # The first event won't be returned.
        event = factory.make_Event(
            type=factory.make_EventType(level=logging.INFO),
            description="Uninteresting event",
        )
        node = event.node
        # The second (and last) event will be returned.
        message = "Interesting event"
        event = factory.make_Event(
            type=factory.make_EventType(level=logging.INFO),
            description=message,
            node=node,
        )
        # New event that would be returned if not cached.
        factory.make_Event(
            type=factory.make_EventType(level=logging.INFO),
            description=message,
            node=node,
        )
        node._status_event = event
        self.assertEqual(event, node.status_event())

    def test_status_event_returns_most_recent_event(self):
        # The first event won't be returned.
        event = factory.make_Event(
            type=factory.make_EventType(level=logging.INFO),
            description="Uninteresting event",
        )
        node = event.node
        # The second (and last) event will be returned.
        message = "Interesting event"
        event = factory.make_Event(
            type=factory.make_EventType(level=logging.INFO),
            description=message,
            node=node,
        )
        # DEBUG event will not be returned.
        factory.make_Event(
            type=factory.make_EventType(level=logging.DEBUG), node=node
        )
        self.assertEqual(event, node.status_event())

    def test_status_event_returns_none_for_new_node(self):
        node = factory.make_Node()
        self.assertIsNone(node.status_event())

    def test_status_message_returns_most_recent_event(self):
        # The first event won't be returned.
        event = factory.make_Event(
            type=factory.make_EventType(level=logging.INFO),
            description="Uninteresting event",
        )
        node = event.node
        # The second (and last) event will be returned.
        type_message = "Event"
        message = "Interesting event"
        factory.make_Event(
            type=factory.make_EventType(
                level=logging.INFO, description=type_message
            ),
            description=message,
            node=node,
        )
        # DEBUG event will not be returned.
        factory.make_Event(
            type=factory.make_EventType(level=logging.DEBUG), node=node
        )
        self.assertEqual(f"{type_message} - {message}", node.status_message())

    def test_status_message_returns_none_for_new_node(self):
        node = factory.make_Node()
        self.assertIsNone(node.status_message())

    def test_status_action_returns_most_recent_event(self):
        # The first event won't be returned.
        event = factory.make_Event(
            type=factory.make_EventType(level=logging.INFO),
            action="Uninteresting event",
        )
        node = event.node
        # The second (and last) event will be returned.
        action = "Interesting event"
        factory.make_Event(
            type=factory.make_EventType(level=logging.INFO),
            action=action,
            node=node,
        )
        # DEBUG event will not be returned.
        factory.make_Event(
            type=factory.make_EventType(level=logging.DEBUG), node=node
        )
        self.assertEqual(action, node.status_action())

    def test_on_network_returns_true_when_connected(self):
        node = factory.make_Node_with_Interface_on_Subnet(
            status=NODE_STATUS.ALLOCATED
        )
        self.assertTrue(node.on_network())

    def test_on_network_returns_false_when_not_connected(self):
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED)
        self.assertFalse(node.on_network())

    def test_reset_status_expires(self):
        status = random.choice(MONITORED_STATUSES)
        node = factory.make_Node(status=status)
        node.status_expires = factory.make_date()
        node.reset_status_expires()
        # Testing for the exact time will fail during testing due to now()
        # being different in reset_status_expires vs here. Pad by 1 minute
        # to make sure its reset but won't fail testing.
        expected_time = now() + timedelta(minutes=get_node_timeout(status))
        self.assertGreaterEqual(
            node.status_expires, expected_time - timedelta(minutes=1)
        )
        self.assertLessEqual(
            node.status_expires, expected_time + timedelta(minutes=1)
        )

    def test_reset_status_expires_does_nothing_when_not_set(self):
        status = random.choice(MONITORED_STATUSES)
        node = factory.make_Node(status=status)
        node.reset_status_expires()
        self.assertIsNone(node.status_expires)

    def test_storage_layout_issues_is_valid_when_flat(self):
        node = factory.make_Node()
        self.assertEqual([], node.storage_layout_issues())

    def test_storage_layout_issues_returns_valid_with_boot_and_bcache(self):
        node = factory.make_Node(with_boot_disk=False)
        boot_partition = factory.make_Partition(node=node, bootable=True)
        factory.make_Filesystem(partition=boot_partition, mount_point="/boot")
        fs_group = factory.make_FilesystemGroup(
            node=node, group_type=FILESYSTEM_GROUP_TYPE.BCACHE
        )
        bcache = fs_group.virtual_device
        factory.make_Filesystem(block_device=bcache, mount_point="/")
        self.assertEqual([], node.storage_layout_issues())

    def test_storage_layout_issues_is_valid_when_ephemeral_deployment(self):
        # A diskless node is one that it is ephemerally deployed.
        node = factory.make_Node(
            ephemeral_deploy=True,
            with_boot_disk=False,
            osystem="ubuntu",
            status=NODE_STATUS.DEPLOYING,
        )
        self.assertEqual([], node.storage_layout_issues())

    def test_storage_layout_issues_is_invalid_when_no_disks_non_ubuntu(self):
        node = factory.make_Node(with_boot_disk=False)
        node.osystem = "rhel"
        self.assertEqual(
            [
                "There are currently no storage devices.  Please add a storage "
                "device to be able to deploy this node."
            ],
            node.storage_layout_issues(),
        )

    def test_storage_layout_issues_is_invalid_when_no_disk_specified(self):
        node = factory.make_Node(with_boot_disk=False)
        factory.make_BlockDevice(node=node)
        node.osystem = "rhel"
        self.assertEqual(
            [
                "Specify a storage device to be able to deploy this node.",
                "Mount the root '/' filesystem to be able to deploy this node.",
            ],
            node.storage_layout_issues(),
        )

    def test_storage_layout_issues_is_invalid_when_root_on_bcache(self):
        node = factory.make_Node(with_boot_disk=False, osystem="ubuntu")
        factory.make_Partition(
            node=node, block_device_size=MIN_BOOT_PARTITION_SIZE
        )
        fs_group = factory.make_FilesystemGroup(
            node=node, group_type=FILESYSTEM_GROUP_TYPE.BCACHE
        )
        bcache = fs_group.virtual_device
        factory.make_Filesystem(block_device=bcache, mount_point="/")
        self.assertEqual(
            [
                "This node cannot be deployed because it cannot boot from a "
                "bcache volume. Mount /boot on a non-bcache device to be able to "
                "deploy this node."
            ],
            node.storage_layout_issues(),
        )

    def test_storage_layout_issues_is_invalid_when_bcache_on_centos(self):
        osystem = random.choice(["centos", "rhel"])
        node = factory.make_Node(osystem=osystem)
        factory.make_FilesystemGroup(
            node=node, group_type=FILESYSTEM_GROUP_TYPE.BCACHE
        )
        self.assertEqual(
            [
                "This node cannot be deployed because the selected deployment "
                "OS, %s, does not support Bcache." % osystem
            ],
            node.storage_layout_issues(),
        )

    def test_storage_layout_issues_is_invalid_when_zfs_on_centos(self):
        osystem = random.choice(["centos", "rhel"])
        node = factory.make_Node(osystem=osystem)
        bd = factory.make_BlockDevice(node=node)
        factory.make_Filesystem(
            block_device=bd, fstype=FILESYSTEM_TYPE.ZFSROOT
        )
        self.assertEqual(
            [
                "This node cannot be deployed because the selected deployment "
                "OS, %s, does not support ZFS." % osystem
            ],
            node.storage_layout_issues(),
        )

    def test_storage_layout_issues_is_invalid_when_btrfs_on_centos8(self):
        osystem = random.choice(["centos", "rhel"])
        node = factory.make_Node(
            osystem=osystem, distro_series=factory.make_name("8")
        )
        bd = factory.make_BlockDevice(node=node)
        factory.make_Filesystem(block_device=bd, fstype=FILESYSTEM_TYPE.BTRFS)
        self.assertEqual(
            [
                "This node cannot be deployed because the selected deployment "
                "OS release, %s %s, does not support BTRFS."
                % (node.osystem, node.distro_series)
            ],
            node.storage_layout_issues(),
        )

    def test_start_rescue_mode_raises_PermissionDenied_if_no_edit(self):
        user = factory.make_User()
        node = factory.make_Node(
            owner=user,
            status=random.choice(
                [NODE_STATUS.READY, NODE_STATUS.BROKEN, NODE_STATUS.DEPLOYED]
            ),
        )
        self.assertRaises(
            PermissionDenied, node.start_rescue_mode, factory.make_User()
        )

    def test_start_rescue_mode_errors_for_unconfigured_power_type(self):
        node = factory.make_Node(
            status=random.choice(
                [NODE_STATUS.READY, NODE_STATUS.BROKEN, NODE_STATUS.DEPLOYED]
            ),
            power_type=None,
        )
        self.assertRaises(
            UnknownPowerType, node.start_rescue_mode, factory.make_admin()
        )

    def test_start_rescue_mode_logs_user_request_and_creates_sts_msg(self):
        node = factory.make_Node(
            status=random.choice(
                [NODE_STATUS.READY, NODE_STATUS.BROKEN, NODE_STATUS.DEPLOYED]
            )
        )
        mock_node_power_cycle = self.patch(node, "_power_cycle")
        # Return a post-commit hook from Node.power_cycle().
        mock_node_power_cycle.side_effect = lambda: post_commit()
        admin = factory.make_admin()
        node.start_rescue_mode(admin)
        post_commit_hooks.reset()  # Ignore these for now.
        node = reload_object(node)
        events = Event.objects.filter(node=node).order_by("id")
        self.assertEqual(
            events[0].type.name, EVENT_TYPES.REQUEST_NODE_START_RESCUE_MODE
        )
        self.assertEqual(events[1].type.name, EVENT_TYPES.ENTERING_RESCUE_MODE)

    def test_start_rescue_mode_sets_status_owner_and_power_cycles_node(self):
        node = factory.make_Node(
            status=random.choice(
                [NODE_STATUS.READY, NODE_STATUS.BROKEN, NODE_STATUS.DEPLOYED]
            )
        )
        mock_node_power_cycle = self.patch(node, "_power_cycle")
        # Return a post-commit hook from Node.power_cycle().
        mock_node_power_cycle.side_effect = lambda: post_commit()
        admin = factory.make_admin()
        node.start_rescue_mode(admin)
        post_commit_hooks.reset()  # Ignore these for now.
        node = reload_object(node)
        self.assertEqual(node.status, NODE_STATUS.ENTERING_RESCUE_MODE)
        self.assertEqual(node.owner, admin)
        self.expectThat(mock_node_power_cycle, MockCalledOnceWith())

    def test_start_rescue_mode_reverts_status_on_error(self):
        # When start_rescue_mode encounters an error when trying to
        # power cycle the node, it will revert the node to its previous
        # status.
        admin = factory.make_admin()
        status = random.choice(
            [NODE_STATUS.READY, NODE_STATUS.BROKEN, NODE_STATUS.DEPLOYED]
        )
        node = factory.make_Node(status=status)
        mock_node_power_cycle = self.patch(node, "_power_cycle")
        mock_node_power_cycle.side_effect = factory.make_exception()

        try:
            with transaction.atomic():
                node.start_rescue_mode(admin)
        except mock_node_power_cycle.side_effect.__class__:
            # We don't care about the error here, so suppress it. It
            # exists only to cause the transaction to abort.
            pass

        self.expectThat(mock_node_power_cycle, MockCalledOnceWith())
        self.expectThat(status, Equals(node.status))

    def test_start_rescue_mode_reverts_status_on_post_commit_error(self):
        self.disable_node_query()
        # When start_rescue_mode encounters an error in its post-commit
        # hook, it will revert the node to its previous status.
        admin = factory.make_admin()
        status = random.choice(
            [NODE_STATUS.READY, NODE_STATUS.BROKEN, NODE_STATUS.DEPLOYED]
        )
        node = factory.make_Node(status=status)
        # Patch out some things that we don't want to do right now.
        self.patch(node, "_power_cycle").return_value = None
        # Fake an error during the post-commit hook.
        error_message = factory.make_name("error")
        error_type = factory.make_exception_type()
        _start_async = self.patch_autospec(node, "_start_rescue_mode_async")
        _start_async.side_effect = error_type(error_message)
        # Capture calls to _set_status.
        self.patch_autospec(Node, "_set_status")

        with LoggerFixture("maas") as logger:
            with ExpectedException(error_type):
                with post_commit_hooks:
                    node.start_rescue_mode(admin)

        # The status is set to be reverted to its initial status.
        self.expectThat(
            node._set_status, MockCalledOnceWith(node.system_id, status=status)
        )
        # It's logged too.
        self.expectThat(
            logger.output,
            Contains(
                "%s: Could not start rescue mode for node: %s\n"
                % (node.hostname, error_message)
            ),
        )

    def test_start_rescue_mode_logs_and_raises_errors(self):
        admin = factory.make_admin()
        status = random.choice(
            [NODE_STATUS.READY, NODE_STATUS.BROKEN, NODE_STATUS.DEPLOYED]
        )
        node = factory.make_Node(status=status)
        mock_maaslog = self.patch(node_module, "maaslog")
        exception = NoConnectionsAvailable(factory.make_name())
        self.patch(node, "_power_cycle").side_effect = exception
        self.assertRaises(
            NoConnectionsAvailable, node.start_rescue_mode, admin
        )
        self.expectThat(status, Equals(node.status))
        self.expectThat(
            mock_maaslog.error,
            MockCalledOnceWith(
                "%s: Could not start rescue mode for node: %s",
                node.hostname,
                exception,
            ),
        )

    def test_stop_rescue_mode_raises_PermissionDenied_if_no_edit(self):
        user = factory.make_User()
        node = factory.make_Node(owner=user, status=NODE_STATUS.RESCUE_MODE)
        self.assertRaises(
            PermissionDenied, node.stop_rescue_mode, factory.make_User()
        )

    def test_stop_rescue_mode_logs_user_request(self):
        node = factory.make_Node(status=NODE_STATUS.RESCUE_MODE)
        admin = factory.make_admin()
        self.patch(Node, "_set_status")
        self.patch(Node, "_stop").return_value = None
        self.patch(Node, "_power_cycle").return_value = None
        mock_register_event = self.patch(node, "_register_request_event")
        node.stop_rescue_mode(admin)
        self.assertThat(
            mock_register_event,
            MockCalledOnceWith(
                admin,
                EVENT_TYPES.REQUEST_NODE_STOP_RESCUE_MODE,
                action="stop rescue mode",
            ),
        )

    def test_stop_rescue_mode_stops_node_and_sets_status(self):
        node = factory.make_Node(
            status=NODE_STATUS.RESCUE_MODE,
            previous_status=random.choice(
                [NODE_STATUS.READY, NODE_STATUS.BROKEN]
            ),
        )
        admin = factory.make_admin()
        mock_node_stop = self.patch(node, "_stop")
        node.stop_rescue_mode(admin)

        self.expectThat(mock_node_stop, MockCalledOnceWith(admin))
        self.expectThat(
            reload_object(node).status, Equals(NODE_STATUS.EXITING_RESCUE_MODE)
        )

    def test_stop_rescue_mode_power_cycles_node_and_sets_status(self):
        node = factory.make_Node(
            status=NODE_STATUS.RESCUE_MODE,
            previous_status=NODE_STATUS.DEPLOYED,
        )
        admin = factory.make_admin()
        mock_node_power_cycle = self.patch(node, "_power_cycle")
        node.stop_rescue_mode(admin)

        self.expectThat(mock_node_power_cycle, MockCalledOnceWith())
        self.expectThat(
            reload_object(node).status, Equals(NODE_STATUS.EXITING_RESCUE_MODE)
        )

    def test_stop_rescue_mode_manual_power_cycles_node_and_sets_status(self):
        node = factory.make_Node(
            status=NODE_STATUS.RESCUE_MODE,
            power_type="manual",
            previous_status=NODE_STATUS.DEPLOYED,
        )
        admin = factory.make_admin()
        mock_node_power_cycle = self.patch(node, "_power_cycle")
        node.stop_rescue_mode(admin)

        self.expectThat(mock_node_power_cycle, MockCalledOnceWith())
        self.expectThat(
            reload_object(node).status, Equals(NODE_STATUS.DEPLOYED)
        )

    def test_stop_rescue_mode_logs_and_raises_errors(self):
        admin = factory.make_admin()
        node = factory.make_Node(
            status=NODE_STATUS.RESCUE_MODE,
            previous_status=random.choice(
                [NODE_STATUS.READY, NODE_STATUS.BROKEN]
            ),
        )
        mock_maaslog = self.patch(node_module, "maaslog")
        exception_class = factory.make_exception_type()
        exception = exception_class(factory.make_name())
        self.patch(node, "_stop").side_effect = exception
        self.assertRaises(exception_class, node.stop_rescue_mode, admin)
        self.expectThat(NODE_STATUS.RESCUE_MODE, Equals(node.status))
        self.expectThat(
            mock_maaslog.error,
            MockCalledOnceWith(
                "%s: Could not stop rescue mode for node: %s",
                node.hostname,
                exception,
            ),
        )

    def test_default_numanode(self):
        node = factory.make_Node()
        factory.make_NUMANode(node)
        factory.make_NUMANode(node)
        self.assertIs(node.default_numanode.node, node)
        self.assertEqual(node.default_numanode.index, 0)

    def test_current_config(self):
        node = factory.make_Node()
        factory.make_NodeConfig(node=node, name=NODE_CONFIG_TYPE.DEPLOYMENT)
        self.assertEqual(node.current_config.name, NODE_CONFIG_TYPE.DISCOVERED)

    def test_default_node_config_for_device(self):
        device = factory.make_Device()
        self.assertEqual(
            device.current_config.name, NODE_CONFIG_TYPE.DISCOVERED
        )

    def test_get_commissioning_resources_no_script(self):
        node = factory.make_Node()
        script_set = ScriptSet.objects.create_commissioning_script_set(
            node=node,
        )
        node.current_commissioning_script_set = script_set
        node.save()
        self.assertIsNone(node.get_commissioning_resources())

    def test_get_commissioning_resources(self):
        node = factory.make_Node()
        factory.make_PhysicalBlockDevice(name="sda", node=node)
        lxd_script = factory.make_Script(
            name=COMMISSIONING_OUTPUT_NAME,
            script_type=SCRIPT_TYPE.COMMISSIONING,
        )
        script_set = ScriptSet.objects.create_commissioning_script_set(
            node,
            scripts=[lxd_script.name],
        )
        node.current_commissioning_script_set = script_set
        node.save()

        data = test_hooks.make_lxd_output()
        layout_data = {
            "layout": {
                "sda": {
                    "type": "disk",
                    "ptable": "gpt",
                    "partitions": [
                        {"name": "sda1", "size": "200M", "fs": "vfat"},
                        {"name": "sda2", "size": "10G", "fs": "ext4"},
                    ],
                }
            },
            "mounts": {
                "/boot/efi": {
                    "device": "sda1",
                },
                "/": {
                    "device": "sda2",
                },
            },
        }
        data["storage-extra"] = layout_data
        output = json.dumps(data).encode()
        factory.make_ScriptResult(
            script_set=script_set,
            script=lxd_script,
            exit_status=0,
            output=output,
            stdout=output,
        )
        self.assertEqual(node.get_commissioning_resources(), data)

    def test_hardware_sync_physical_block_device_addition_is_preserved_on_release(
        self,
    ):
        d = defer.succeed(None)
        self.patch(node_module, "post_commit").return_value = d
        node = factory.make_Node(
            enable_hw_sync=True, status=NODE_STATUS.DEPLOYED
        )
        self.patch(Node, "_set_status_expires")
        self.patch(node_module, "post_commit_do")
        self.patch(node, "_power_control_node")
        self.patch(node, "stop")
        block_device = factory.make_PhysicalBlockDevice(
            node_config=node.current_config
        )
        with post_commit_hooks:
            node.release()
        self.assertIn(
            block_device.name,
            [bd.name for bd in node.current_config.blockdevice_set.all()],
        )

    def test_hardware_sync_physical_block_device_removal_is_preserved_on_release(
        self,
    ):
        d = defer.succeed(None)
        self.patch(node_module, "post_commit").return_value = d
        node = factory.make_Node(
            enable_hw_sync=True, status=NODE_STATUS.DEPLOYED
        )
        self.patch(Node, "_set_status_expires")
        self.patch(node_module, "post_commit_do")
        self.patch(node, "_power_control_node")
        self.patch(node, "stop")
        block_device = factory.make_PhysicalBlockDevice(
            node_config=node.current_config
        )
        self.assertIn(
            block_device.name,
            [bd.name for bd in node.current_config.blockdevice_set.all()],
        )
        block_device.delete()
        with post_commit_hooks:
            node.release()
        self.assertNotIn(
            block_device.name,
            [bd.name for bd in node.current_config.blockdevice_set.all()],
        )

    def test_hardware_sync_physical_interface_addition_is_preserved_on_release(
        self,
    ):
        d = defer.succeed(None)
        self.patch(node_module, "post_commit").return_value = d
        node = factory.make_Node(
            enable_hw_sync=True, status=NODE_STATUS.DEPLOYED
        )
        self.patch(Node, "_set_status_expires")
        self.patch(node_module, "post_commit_do")
        self.patch(node, "_power_control_node")
        self.patch(node, "stop")
        interface = factory.make_Interface(node_config=node.current_config)
        with post_commit_hooks:
            node.release()
        self.assertIn(interface, list(node.current_config.interface_set.all()))

    def test_hardware_sync_physical_interface_removal_is_preserved_on_release(
        self,
    ):
        d = defer.succeed(None)
        self.patch(node_module, "post_commit").return_value = d
        node = factory.make_Node(
            enable_hw_sync=True, status=NODE_STATUS.DEPLOYED
        )
        self.patch(Node, "_set_status_expires")
        self.patch(node_module, "post_commit_do")
        self.patch(node, "_power_control_node")
        self.patch(node, "stop")
        interface = factory.make_Interface(node_config=node.current_config)
        self.assertIn(interface, list(node.current_config.interface_set.all()))
        interface.delete()
        with post_commit_hooks:
            node.release()
            # interfaces for managed power types are released when powering off
            node.update_power_state(POWER_STATE.OFF)
        self.assertNotIn(
            interface, list(node.current_config.interface_set.all())
        )

    def test_hardware_sync_node_device_is_preserved_on_release(self):
        d = defer.succeed(None)
        self.patch(node_module, "post_commit").return_value = d
        node = factory.make_Node(
            enable_hw_sync=True, status=NODE_STATUS.DEPLOYED
        )
        self.patch(Node, "_set_status_expires")
        self.patch(node_module, "post_commit_do")
        self.patch(node, "_power_control_node")
        self.patch(node, "stop")
        node_device = factory.make_NodeDevice(node_config=node.current_config)
        with post_commit_hooks:
            node.release()
        self.assertIn(
            node_device,
            list(NodeDevice.objects.filter(node_config=node.current_config)),
        )

    def test_hardware_sync_virtual_interface_is_removed_on_release(self):
        d = defer.succeed(None)
        self.patch(node_module, "post_commit").return_value = d
        node = factory.make_Node(
            enable_hw_sync=True,
            status=NODE_STATUS.DEPLOYED,
        )
        self.patch(Node, "_set_status_expires")
        self.patch(node_module, "post_commit_do")
        self.patch(node, "_power_control_node")
        self.patch(node, "stop")
        parent = factory.make_Interface(node_config=node.current_config)
        interface = factory.make_Interface(
            node_config=node.current_config,
            iftype=INTERFACE_TYPE.VLAN,
            parents=[parent],
        )
        interface.acquired = True
        interface.save()
        with post_commit_hooks:
            node.release()
            # interfaces for managed power types are released when powering off
            node.update_power_state(POWER_STATE.OFF)
        self.assertNotIn(
            interface, list(node.current_config.interface_set.all())
        )

    def test_get_bmc_client_connection_info_layer2(self):
        admin = factory.make_admin()
        subnet = factory.make_Subnet()

        rack_controllers = [
            factory.make_RackController(owner=admin) for _ in range(2)
        ]
        for rack_controller in rack_controllers:
            ip = subnet.get_next_ip_for_allocation()[0]
            factory.make_Interface(node=rack_controller, ip=ip)

        clients = [Mock() for _ in rack_controllers]
        for i, rack_controller in enumerate(rack_controllers):
            clients[i].ident = rack_controller.system_id

        mock_getAllClients = self.patch(node_module, "getAllClients")
        mock_getAllClients.return_value = clients

        ip = subnet.get_next_ip_for_allocation()[0]
        ip_address = factory.make_StaticIPAddress(ip=ip)
        bmc = factory.make_BMC(ip_address=ip_address)
        node = factory.make_Node(bmc=bmc)
        clients, _ = node._get_bmc_client_connection_info()
        self.assertCountEqual(
            [
                rack_controller.system_id
                for rack_controller in rack_controllers
            ],
            clients,
        )

    def test_get_bmc_client_connection_info_routable(self):
        admin = factory.make_admin()
        subnet1 = factory.make_Subnet()
        subnet2 = factory.make_Subnet()

        rack_controllers = [
            factory.make_RackController(owner=admin) for _ in range(2)
        ]
        for rack_controller in rack_controllers:
            ip = subnet1.get_next_ip_for_allocation()[0]
            factory.make_Interface(node=rack_controller, ip=ip)

        clients = [Mock() for _ in rack_controllers]
        for i, rack_controller in enumerate(rack_controllers):
            clients[i].ident = rack_controller.system_id

        mock_getAllClients_node = self.patch(node_module, "getAllClients")
        mock_getAllClients_node.return_value = clients
        mock_getAllClients_bmc = self.patch(bmc_module, "getAllClients")
        mock_getAllClients_bmc.return_value = clients

        ip = subnet2.get_next_ip_for_allocation()[0]
        ip_address = factory.make_StaticIPAddress(ip=ip, subnet=subnet2)
        bmc = factory.make_BMC(ip_address=ip_address)
        node = factory.make_Node(bmc=bmc)
        [
            BMCRoutableRackControllerRelationship(
                bmc=bmc, rack_controller=rack_controller, routable=True
            ).save()
            for rack_controller in rack_controllers
        ]
        clients, _ = node._get_bmc_client_connection_info()
        self.assertCountEqual(
            [
                rack_controller.system_id
                for rack_controller in rack_controllers
            ],
            clients,
        )

    def test_copy_between_interface_mappings_exclude_addresses(self):
        source_node = factory.make_Node_with_Interface_on_Subnet(ifname="eth0")
        iface = source_node.current_config.interface_set.first()
        subnet = iface.vlan.subnet_set.first()
        factory.make_StaticIPAddress(interface=iface, subnet=subnet)
        node = factory.make_Node_with_Interface_on_Subnet(ifname="eth0")
        mapping = node._get_interface_mapping_between_nodes(source_node)
        [exclude_address] = node._copy_between_interface_mappings(mapping)
        self.assertIn(IPAddress(exclude_address), IPNetwork(subnet.cidr))

    def test_delete_deletes_node_power_secrets(self):
        node = factory.make_Node()
        secret_manager = SecretManager()
        secret_manager.set_composite_secret(
            "power-parameters", {"foo": "bar"}, obj=node
        )

        node.delete()
        self.assertIsNone(
            secret_manager.get_simple_secret(
                "power-parameters", obj=node, default=None
            )
        )


class TestNodePowerParameters(MAASServerTestCase):
    def setUp(self):
        super().setUp()
        self.patch_autospec(node_module, "power_driver_check")

    def test_power_parameters_are_stored(self):
        parameters = dict(user="tarquin", address="10.1.2.3")
        node = factory.make_Node(
            power_type="ipmi", power_parameters=parameters
        )
        node.save()
        node = reload_object(node)
        self.assertEqual(parameters, node.get_power_parameters())

    def test_power_parameters_default(self):
        node = factory.make_Node(power_type=None)
        self.assertEqual({}, node.get_power_parameters())
        self.assertIsNone(node.bmc)

    def test_power_parameters_from_commissioning_not_new(self):
        node = factory.make_Node(power_type="virsh")
        node.set_power_config("ipmi", {}, from_commissioning=True)
        self.assertTrue(node.bmc.created_by_commissioning)

    def test_power_parameters_not_from_commissioning_not_new(self):
        node = factory.make_Node(power_type="virsh")
        node.set_power_config("ipmi", {}, from_commissioning=False)
        self.assertIsNotNone(node.bmc.created_by_commissioning)
        self.assertFalse(node.bmc.created_by_commissioning)

    def test_power_parameters_from_commissioning_not_new_chassis(self):
        node = factory.make_Node(power_type="virsh")
        node.set_power_config("redfish", {}, from_commissioning=True)
        self.assertTrue(node.bmc.created_by_commissioning)

    def test_power_parameters_not_from_commissioning_not_new_chassis(self):
        node = factory.make_Node(power_type="virsh")
        node.set_power_config("redfish", {}, from_commissioning=False)
        self.assertIsNotNone(node.bmc.created_by_commissioning)
        self.assertFalse(node.bmc.created_by_commissioning)

    def test_power_parameters_from_commissioning_new(self):
        node = factory.make_Node(power_type=None)
        node.set_power_config("ipmi", {}, from_commissioning=True)
        self.assertTrue(node.bmc.created_by_commissioning)

    def test_power_parameters_not_from_commissioning_new(self):
        node = factory.make_Node(power_type=None)
        node.set_power_config("ipmi", {}, from_commissioning=False)
        self.assertIsNotNone(node.bmc.created_by_commissioning)
        self.assertFalse(node.bmc.created_by_commissioning)

    def test_power_parameters_from_commissioning_new_chassis(self):
        node = factory.make_Node(power_type=None)
        node.set_power_config("redfish", {}, from_commissioning=True)
        self.assertTrue(node.bmc.created_by_commissioning)

    def test_power_parameters_not_from_commissioning_new_chassis(self):
        node = factory.make_Node(power_type=None)
        node.set_power_config("redfish", {}, from_commissioning=False)
        self.assertIsNotNone(node.bmc.created_by_commissioning)
        self.assertFalse(node.bmc.created_by_commissioning)

    def test_power_parameters_from_commissioning_same(self):
        node = factory.make_Node(
            power_type="ipmi",
            power_parameters={"power_address": factory.make_ipv4_address()},
        )
        old_value = random.choice([None, True, False])
        node.bmc.created_by_commissioning = old_value
        node.bmc.save()
        node.set_power_config(
            "ipmi",
            {"power_address": factory.make_ipv6_address()},
            from_commissioning=True,
        )
        self.assertEqual(node.bmc.created_by_commissioning, old_value)

    def test_power_type_and_bmc_power_parameters_stored_in_bmc(self):
        node = factory.make_Node(power_type="hmc")
        ip_address = factory.make_ipv4_address()
        bmc_parameters = dict(power_address=ip_address)
        node_parameters = dict(server_name=factory.make_string())
        parameters = {**bmc_parameters, **node_parameters}
        node.set_power_config("hmc", parameters)
        node.save()
        node = reload_object(node)
        self.assertEqual(parameters, node.get_power_parameters())
        self.assertEqual(node_parameters, node.get_instance_power_parameters())
        self.assertEqual(bmc_parameters, node.bmc.get_power_parameters())
        self.assertEqual("hmc", node.bmc.power_type)
        self.assertEqual(node.power_type, node.bmc.power_type)
        self.assertEqual(ip_address, node.bmc.ip_address.ip)

    def test_power_type_creates_new_bmc_for_manual_power_type(self):
        ip_address = factory.make_ipv4_address()
        bmc_parameters = dict(power_address=ip_address)
        node_parameters = dict(server_name=factory.make_string())
        parameters = {**bmc_parameters, **node_parameters}
        node = factory.make_Node(
            power_type="virsh", power_parameters=parameters
        )
        self.assertFalse(BMC.objects.filter(power_type="manual"))
        node.set_power_config("manual", {})
        node.save()
        node = reload_object(node)
        self.assertEqual("manual", node.bmc.power_type)
        self.assertEqual({}, node.bmc.get_power_parameters())
        self.assertTrue(BMC.objects.filter(power_type="manual"))

    def test_power_type_does_not_create_new_bmc_for_already_manual(self):
        ip_address = factory.make_ipv4_address()
        bmc_parameters = dict(power_address=ip_address)
        node_parameters = dict(server_name=factory.make_string())
        parameters = {**bmc_parameters, **node_parameters}
        node = factory.make_Node(
            power_type="manual", power_parameters=parameters
        )
        bmc_id = node.bmc.id
        node.set_power_config("manual", {})
        node.save()
        node = reload_object(node)
        self.assertEqual(bmc_id, node.bmc.id)

    def test_set_power_config_creates_multiple_bmcs_for_manual(self):
        node1 = factory.make_Node()
        node1.set_power_config("manual", {})
        node2 = factory.make_Node()
        node2.set_power_config("manual", {})
        self.assertNotEqual(node1.bmc, node2.bmc)

    def test_power_parameters_are_stored_in_proper_scopes(self):
        node = factory.make_Node()
        bmc_parameters = dict(
            power_address="qemu+ssh://trapnine@10.0.2.1/system",
            power_pass=factory.make_string(),
        )
        node_parameters = dict(power_id="maas-x")
        parameters = {**bmc_parameters, **node_parameters}
        node.set_power_config("virsh", parameters)
        node.save()
        node = reload_object(node)
        self.assertEqual(parameters, node.get_power_parameters())
        self.assertEqual(node_parameters, node.get_instance_power_parameters())
        self.assertEqual(bmc_parameters, node.bmc.get_power_parameters())
        self.assertEqual("10.0.2.1", node.bmc.ip_address.ip)

    def test_unknown_power_parameter_stored_on_node(self):
        node = factory.make_Node()
        bmc_parameters = dict(power_address=factory.make_ipv4_address())
        node_parameters = dict(server_name=factory.make_string())
        # This random parameters will be stored on the node instance.
        node_parameters[factory.make_string()] = factory.make_string()
        parameters = {**bmc_parameters, **node_parameters}
        node.set_power_config("hmc", parameters)
        node.save()
        node = reload_object(node)
        self.assertEqual(parameters, node.get_power_parameters())
        self.assertEqual(node_parameters, node.get_instance_power_parameters())
        self.assertEqual(bmc_parameters, node.bmc.get_power_parameters())

    def test_none_chassis_bmc_doesnt_consolidate(self):
        for _ in range(3):
            node = factory.make_Node()
            node.set_power_config("manual", {})
            node.save()

        # Should be 3 BMC's even though they all have the same information.
        self.assertEqual(3, BMC.objects.count())

    def test_bmc_consolidation(self):
        nodes = []
        for _ in range(3):
            bmc_parameters = dict(power_address=factory.make_ipv4_address())
            node_parameters = dict(power_id=factory.make_string())
            parameters = {**bmc_parameters, **node_parameters}
            node = factory.make_Node()
            node.set_power_config("apc", parameters)
            node.save()
            node = reload_object(node)
            self.assertEqual(parameters, node.get_power_parameters())
            self.assertEqual(
                node_parameters, node.get_instance_power_parameters()
            )
            self.assertEqual(bmc_parameters, node.bmc.get_power_parameters())
            self.assertEqual("apc", node.bmc.power_type)
            nodes.append(node)

        # Make sure there are now 3 different BMC's.
        self.assertEqual(3, BMC.objects.count())
        self.assertNotEqual(nodes[0].bmc_id, nodes[1].bmc_id)
        self.assertNotEqual(nodes[0].bmc_id, nodes[2].bmc_id)

        # Set equivalent bmc power_parameters, and confirm BMC count decrease,
        # even when the Node's instance_power_parameter varies.
        parameters["power_id"] = factory.make_string()
        nodes[0].set_power_config(nodes[0].power_type, parameters)
        nodes[0].save()
        nodes[0] = reload_object(nodes[0])
        # 0 now shares a BMC with 2.
        self.assertEqual(2, BMC.objects.count())
        self.assertNotEqual(nodes[0].bmc_id, nodes[1].bmc_id)
        self.assertEqual(nodes[0].bmc_id, nodes[2].bmc_id)

        parameters["power_id"] = factory.make_string()
        nodes[1].set_power_config(nodes[1].power_type, parameters)
        nodes[1].save()
        nodes[1] = reload_object(nodes[1])
        # All 3 share the same BMC, and only one exists.
        self.assertEqual(1, BMC.objects.count())
        self.assertEqual(nodes[0].bmc_id, nodes[1].bmc_id)
        self.assertEqual(nodes[0].bmc_id, nodes[2].bmc_id)

        # Now change parameters and confirm the count doesn't change,
        # as changing the one linked BMC should affect all linked nodes.
        parameters["power_address"] = factory.make_ipv4_address()
        nodes[1].set_power_config(nodes[1].power_type, parameters)
        nodes[1].save()
        nodes[1] = reload_object(nodes[1])
        self.assertEqual(1, BMC.objects.count())
        self.assertEqual(nodes[0].bmc_id, nodes[1].bmc_id)
        self.assertEqual(nodes[0].bmc_id, nodes[2].bmc_id)

        # Now change type and confirm the count goes up,
        # as changing the type makes a new linked BMC.
        parameters["power_address"] = factory.make_ipv4_address()
        nodes[1].set_power_config("virsh", parameters)
        nodes[1].save()
        nodes[1] = reload_object(nodes[1])
        self.assertEqual(2, BMC.objects.count())
        self.assertNotEqual(nodes[0].bmc_id, nodes[1].bmc_id)
        self.assertEqual(nodes[0].bmc_id, nodes[2].bmc_id)

        # Set new BMC's values back to match original BMC, and make
        # sure the BMC count decreases as they consolidate.
        parameters = nodes[0].get_power_parameters()
        parameters["power_id"] = factory.make_string()
        nodes[1].set_power_config(nodes[0].power_type, parameters)
        nodes[1].save()
        nodes[1] = reload_object(nodes[1])
        # 1 now shares a BMC with 0 and 2.
        self.assertEqual(nodes[0].bmc_id, nodes[1].bmc_id)
        self.assertEqual(nodes[0].bmc_id, nodes[2].bmc_id)
        self.assertEqual(1, BMC.objects.count())

    def test_power_parameters_ip_address_extracted(self):
        node = factory.make_Node()
        ip_address = factory.make_ipv4_address()
        parameters = dict(power_address=ip_address)
        node.set_power_config("hmc", parameters)
        node.save()
        self.assertEqual(parameters, node.get_power_parameters())
        self.assertEqual(ip_address, node.bmc.ip_address.ip)

    def test_power_parameters_unexpected_values_tolerated(self):
        node = factory.make_Node()
        parameters = {factory.make_string(): factory.make_string()}
        node.set_power_config("virsh", parameters)
        node.save()
        self.assertEqual(parameters, node.get_power_parameters())
        self.assertIsNone(node.bmc.ip_address)

    def test_power_parameters_blank_ip_address_tolerated(self):
        node = factory.make_Node()
        parameters = dict(power_address="")
        node.set_power_config("hmc", parameters)
        node.save()
        self.assertEqual(parameters, node.get_power_parameters())
        self.assertIsNone(node.bmc.ip_address)

    def test_power_parameters_ip_address_reset(self):
        node = factory.make_Node()
        ip_address = factory.make_ipv4_address()
        parameters = dict(power_address=ip_address)
        node.set_power_config("hmc", parameters)
        node.save()
        self.assertEqual(parameters, node.get_power_parameters())
        self.assertEqual(ip_address, node.bmc.ip_address.ip)

        # StaticIPAddress can be changed after being set.
        ip_address = factory.make_ipv4_address()
        parameters = dict(power_address=ip_address)
        node.set_power_config("hmc", parameters)
        node.save()
        self.assertEqual(parameters, node.get_power_parameters())
        self.assertEqual(ip_address, node.bmc.ip_address.ip)

        # StaticIPAddress can be made None after being set.
        ip_address = factory.make_ipv4_address()
        parameters = dict(power_address="")
        node.set_power_config("hmc", parameters)
        node.save()
        self.assertEqual(parameters, node.get_power_parameters())
        self.assertIsNone(node.bmc.ip_address)

        # StaticIPAddress can be changed after being made None.
        ip_address = factory.make_ipv4_address()
        parameters = dict(power_address=ip_address)
        node.set_power_config("hmc", parameters)
        node.save()
        self.assertEqual(parameters, node.get_power_parameters())
        self.assertEqual(ip_address, node.bmc.ip_address.ip)

    def test_orphaned_bmcs_are_removed(self):
        bmc = factory.make_BMC()
        machine = factory.make_Node(bmc=factory.make_BMC())
        machine.bmc = None
        machine.save()
        self.assertIsNone(reload_object(bmc))

    def test_orphaned_pods_are_removed(self):
        pod = factory.make_Pod()
        machine = factory.make_Node(bmc=factory.make_BMC())
        machine.bmc = None
        machine.save()
        self.assertIsNotNone(reload_object(pod))

    def test_is_sync_healthy_returns_false_when_enable_hw_sync_is_false(self):
        node = factory.make_Node()
        self.assertFalse(node.is_sync_healthy)

    def test_is_sync_healthy_returns_true_when_last_sync_within_window(self):
        node = factory.make_Node(enable_hw_sync=True)
        now = datetime.now()
        node.last_sync = now - timedelta(seconds=node.sync_interval)
        node.save()
        self.assertTrue(node.is_sync_healthy)

    def test_is_sync_healthy_returns_false_when_last_sync_is_beyond_window(
        self,
    ):
        node = factory.make_Node(enable_hw_sync=True)
        now = datetime.now()
        node.last_sync = now - (2 * timedelta(seconds=node.sync_interval))
        node.save()
        self.assertFalse(node.is_sync_healthy)


class TestPowerControlNode(MAASTransactionServerTestCase):
    @wait_for_reactor
    @defer.inlineCallbacks
    def test_power_control_node_updates_routable_rack_controllers(self):
        bmc = yield deferToDatabase(factory.make_BMC)
        node = yield deferToDatabase(
            factory.make_Node_with_Interface_on_Subnet, bmc=bmc
        )
        rack_ip = yield deferToDatabase(factory.make_ip_address)
        rack_controller = yield deferToDatabase(node.get_boot_rack_controller)
        yield deferToDatabase(
            factory.make_Interface, node=rack_controller, ip=rack_ip
        )

        def _create_initial_relationship():
            b = BMCRoutableRackControllerRelationship(
                bmc=bmc, rack_controller=rack_controller, routable=True
            )
            b.save()

        yield deferToDatabase(_create_initial_relationship)

        other_rack_controller = yield deferToDatabase(
            factory.make_RackController
        )

        def _assert_no_routable():
            self.assertRaises(
                BMCRoutableRackControllerRelationship.DoesNotExist,
                BMCRoutableRackControllerRelationship.objects.get,
                bmc=node.bmc,
                rack_controller=other_rack_controller,
            )

        yield deferToDatabase(_assert_no_routable)

        self.patch(workflow_module, "temporal_wrapper")
        self.patch(node_module, "execute_workflow").return_value = {
            "state": "on"
        }

        client = Mock()
        client.ident = other_rack_controller.system_id
        self.patch(bmc_module, "getAllClients").return_value = [client]
        self.patch(node_module, "getAllClients").return_value = [client]
        client2 = Mock()
        client2.return_value = defer.succeed({"missing_packages": []})
        d1 = defer.succeed(client2)
        self.patch(bmc_module, "getClientFromIdentifiers").return_value = d1
        self.patch(node_module, "getClientFromIdentifiers").return_value = d1
        self.patch(
            node_module, "power_query_all"
        ).return_value = defer.succeed(
            (POWER_STATE.ON, set([other_rack_controller.system_id]), set())
        )

        power_info = yield deferToDatabase(node.get_effective_power_info)
        yield node._power_control_node(
            defer.succeed(None), "power_query", power_info
        )

        def _assert_routable():
            self.assertTrue(
                BMCRoutableRackControllerRelationship.objects.get(
                    bmc=node.bmc, rack_controller=other_rack_controller
                )
            )

        yield deferToDatabase(_assert_routable)

    @wait_for_reactor
    @defer.inlineCallbacks
    def test_power_control_node_updates_power_state(self):
        bmc = yield deferToDatabase(factory.make_BMC)
        node = yield deferToDatabase(
            factory.make_Node_with_Interface_on_Subnet,
            bmc=bmc,
            status=NODE_STATUS.EXITING_RESCUE_MODE,
            previous_status=NODE_STATUS.DEPLOYED,
        )
        rack_ip = yield deferToDatabase(factory.make_ip_address)
        rack_controller = yield deferToDatabase(node.get_boot_rack_controller)
        yield deferToDatabase(
            factory.make_Interface, node=rack_controller, ip=rack_ip
        )

        def _create_initial_relationship():
            b = BMCRoutableRackControllerRelationship(
                bmc=bmc, rack_controller=rack_controller, routable=True
            )
            b.save()

        yield deferToDatabase(_create_initial_relationship)

        self.patch(workflow_module, "temporal_wrapper")
        self.patch(node_module, "execute_workflow").return_value = {
            "state": "on"
        }

        client = Mock()
        client.ident = rack_controller.system_id
        self.patch(bmc_module, "getAllClients").return_value = [client]
        self.patch(node_module, "getAllClients").return_value = [client]
        client2 = Mock()
        client2.return_value = defer.succeed({"missing_packages": []})
        d1 = defer.succeed(client2)
        self.patch(bmc_module, "getClientFromIdentifiers").return_value = d1
        self.patch(node_module, "getClientFromIdentifiers").return_value = d1

        power_info = yield deferToDatabase(node.get_effective_power_info)
        yield node._power_control_node(
            defer.succeed(None), "power_cycle", power_info
        )

        def _assert_node_status_updated():
            self.assertEqual(
                NODE_STATUS.DEPLOYED, Node.objects.get(id=node.id).status
            )

        yield deferToDatabase(_assert_node_status_updated)


class TestDecomposeMachineMixin:
    """Mixin to help `TestDecomposeMachine` and
    `TestDecomposeMachineTransactional`."""

    def make_composable_pod(self):
        return factory.make_Pod(capabilities=[Capabilities.COMPOSABLE])

    def fake_rpc_client(self):
        client = Mock()
        client.return_value = defer.succeed({})
        self.patch(
            node_module, "getClientFromIdentifiers"
        ).return_value = defer.succeed(client)
        return client


class TestDecomposeMachine(MAASServerTestCase, TestDecomposeMachineMixin):
    """Test that a machine in a composable pod is decomposed."""

    def test_does_nothing_unless_machine(self):
        pod = self.make_composable_pod()
        client = self.fake_rpc_client()
        for node_type, _ in NODE_TYPE_CHOICES:
            if node_type != NODE_TYPE.MACHINE:
                node = factory.make_Node(node_type=node_type)
                node.bmc = pod
                node.save()
                node.delete()
        self.assertThat(client, MockNotCalled())

    def test_does_nothing_if_machine_without_bmc(self):
        client = self.fake_rpc_client()
        machine = factory.make_Node()
        machine.bmc = None
        machine.save()
        machine.delete()
        self.assertThat(client, MockNotCalled())

    def test_does_nothing_if_standard_bmc(self):
        client = self.fake_rpc_client()
        machine = factory.make_Node()
        machine.bmc = factory.make_BMC()
        machine.save()
        machine.delete()
        self.assertThat(client, MockNotCalled())

    def test_does_nothing_if_none_composable_pod(self):
        client = self.fake_rpc_client()
        machine = factory.make_Node()
        machine.bmc = factory.make_Pod()
        machine.save()
        machine.delete()
        self.assertThat(client, MockNotCalled())


class TestDecomposeMachineTransactional(
    MAASTransactionServerTestCase, TestDecomposeMachineMixin
):
    """Test that a machine in a composable pod is decomposed."""

    @transactional
    def create_pod_machine_and_hints(self, **kwargs):
        hints = DiscoveredPodHints(
            cores=random.randint(1, 8),
            cpu_speed=random.randint(1000, 2000),
            memory=random.randint(1024, 8192),
            local_storage=0,
        )
        pod = self.make_composable_pod()
        client = self.fake_rpc_client()
        client.return_value = defer.succeed({"hints": hints})
        machine = factory.make_Node(**kwargs)
        machine.bmc = pod
        machine.set_instance_power_parameters(
            {"power_id": factory.make_name("power_id")}
        )
        return pod, machine, hints, client

    def test_delete_deletes_virtual_machine(self):
        pod, machine, hints, client = self.create_pod_machine_and_hints()
        vm = factory.make_VirtualMachine(bmc=pod, machine=machine)
        with post_commit_hooks:
            machine.delete()
        self.assertIsNone(reload_object(vm))
        client.assert_called_once()

    def test_performs_decompose_machine(self):
        pod, machine, hints, client = self.create_pod_machine_and_hints(
            interface=True
        )
        interface = transactional(machine.current_config.interface_set.first)()
        with post_commit_hooks:
            machine.delete()
        self.assertThat(
            client,
            MockCalledOnceWith(
                DecomposeMachine,
                type=pod.power_type,
                context=machine.get_power_parameters(),
                pod_id=pod.id,
                name=pod.name,
            ),
        )
        pod = transactional(reload_object)(pod)
        self.assertThat(
            pod.hints,
            MatchesStructure.byEquality(
                cores=hints.cores,
                memory=hints.memory,
                local_storage=hints.local_storage,
            ),
        )
        machine = transactional(reload_object)(machine)
        self.assertIsNone(machine)
        interface = transactional(reload_object)(interface)
        self.assertIsNone(interface)

    def test_delete_doesnt_fail_removal(self):
        mock_log_warning = self.patch(node_module.maaslog, "warning")
        pod, machine, hints, client = self.create_pod_machine_and_hints()
        client.return_value = defer.fail(PodActionFail("bang!"))
        with post_commit_hooks:
            machine.delete()
        mock_log_warning.assert_called_with(
            f"{machine.hostname}: Failure decomposing machine: "
            "Unable to decompose machine because: bang!"
        )
        # the machine is still deleted
        self.assertIsNone(transactional(reload_object)(machine))

    def test_release_deletes_dynamic_machine(self):
        owner = transactional(factory.make_User)()
        pod, machine, hints, client = self.create_pod_machine_and_hints(
            status=NODE_STATUS.ALLOCATED,
            owner=owner,
            dynamic=True,
            power_state=POWER_STATE.OFF,
            interface=True,
        )
        interface = transactional(machine.current_config.interface_set.first)()
        with post_commit_hooks:
            machine.release()
        self.assertThat(
            client,
            MockCalledOnceWith(
                DecomposeMachine,
                type=pod.power_type,
                context=machine.get_power_parameters(),
                pod_id=pod.id,
                name=pod.name,
            ),
        )
        pod = transactional(reload_object)(pod)
        self.assertThat(
            pod.hints,
            MatchesStructure.byEquality(
                cores=hints.cores,
                memory=hints.memory,
                local_storage=hints.local_storage,
            ),
        )
        machine = transactional(reload_object)(machine)
        self.assertIsNone(machine)
        interface = transactional(reload_object)(interface)
        self.assertIsNone(interface)

    def test_delete_virtual_machine_for_machine(self):
        pod, machine, hints, client = self.create_pod_machine_and_hints()
        vm = transactional(factory.make_VirtualMachine)(
            bmc=pod, machine=machine
        )
        with post_commit_hooks:
            machine.delete()
        self.assertIsNone(transactional(reload_object)(vm))


class TestNodeTransitions(MAASServerTestCase):
    def test_NODE_TRANSITIONS_initial_states(self):
        allowed_states = set(list(NODE_STATUS_CHOICES_DICT.keys()) + [None])

        self.assertLessEqual(set(NODE_TRANSITIONS.keys()), allowed_states)

    def test_NODE_TRANSITIONS_destination_state(self):
        all_destination_states = []
        for destination_states in NODE_TRANSITIONS.values():
            all_destination_states.extend(destination_states)
        allowed_states = set(NODE_STATUS_CHOICES_DICT.keys())

        self.assertLessEqual(set(all_destination_states), allowed_states)


class TestNodeManager(MAASServerTestCase):
    def make_node(self, user=None, **kwargs):
        """Create a node, allocated to `user` if given."""
        if user is None:
            status = NODE_STATUS.READY
        else:
            status = NODE_STATUS.ALLOCATED
        return factory.make_Node(status=status, owner=user, **kwargs)

    def make_user_data(self):
        """Create a blob of arbitrary user-data."""
        return factory.make_string().encode("ascii")

    def test_node_lists_all_node_types(self):
        # Create machines.
        machines = [
            factory.make_Node(node_type=NODE_TYPE.MACHINE) for _ in range(3)
        ]
        # Create devices.
        devices = [factory.make_Device() for _ in range(3)]
        # Create rack_controllers.
        rack_controllers = [
            factory.make_Node(node_type=NODE_TYPE.RACK_CONTROLLER)
            for _ in range(3)
        ]
        self.assertCountEqual(
            machines + devices + rack_controllers, Node.objects.all()
        )

    def test_filter_by_ids_filters_nodes_by_ids(self):
        nodes = [factory.make_Node() for counter in range(2)]
        ids = [node.system_id for node in nodes]
        selection = slice(1, 2)
        self.assertCountEqual(
            nodes[selection],
            Node.objects.filter_by_ids(Node.objects.all(), ids[selection]),
        )

    def test_filter_by_ids_with_empty_list_returns_empty(self):
        factory.make_Node()
        self.assertCountEqual(
            [], Node.objects.filter_by_ids(Node.objects.all(), [])
        )

    def test_filter_by_ids_without_ids_returns_full(self):
        node = factory.make_Node()
        self.assertCountEqual(
            [node], Node.objects.filter_by_ids(Node.objects.all(), None)
        )

    def test_get_nodes_for_user_lists_visible_nodes(self):
        """get_nodes with perm=NodePermission.view lists the nodes a user
        has access to.

        When run for a regular user it returns unowned nodes and nodes owned by
        that user.

        """
        user = factory.make_User()
        visible_nodes = [self.make_node(owner) for owner in [None, user]]
        self.make_node(factory.make_User())
        self.assertCountEqual(
            visible_nodes, Node.objects.get_nodes(user, NodePermission.view)
        )

    def test_get_nodes_admin_lists_all_nodes(self):
        admin = factory.make_admin()
        owners = [None, factory.make_User(), factory.make_admin(), admin]
        nodes = [self.make_node(owner) for owner in owners]
        self.assertCountEqual(
            nodes, Node.objects.get_nodes(admin, NodePermission.view)
        )

    def test_get_nodes_filters_by_id(self):
        user = factory.make_User()
        nodes = [self.make_node(user) for counter in range(5)]
        ids = [node.system_id for node in nodes]
        wanted_slice = slice(0, 3)
        self.assertCountEqual(
            nodes[wanted_slice],
            Node.objects.get_nodes(
                user, NodePermission.view, ids=ids[wanted_slice]
            ),
        )

    def test_get_nodes_filters_from_nodes(self):
        admin = factory.make_admin()
        # Node that we want to see in the result:
        wanted_node = factory.make_Node()
        # Node that we'll exclude from from_nodes:
        factory.make_Node()

        self.assertCountEqual(
            [wanted_node],
            Node.objects.get_nodes(
                admin,
                NodePermission.view,
                from_nodes=Node.objects.filter(id=wanted_node.id),
            ),
        )

    def test_get_nodes_combines_from_nodes_with_other_filter(self):
        user = factory.make_User()
        # Node that we want to see in the result:
        matching_node = factory.make_Node(owner=user)
        # Node that we'll exclude from from_nodes:
        factory.make_Node(owner=user)
        # Node that will be ignored on account of belonging to someone else:
        invisible_node = factory.make_Node(owner=factory.make_User())

        self.assertCountEqual(
            [matching_node],
            Node.objects.get_nodes(
                user,
                NodePermission.view,
                from_nodes=Node.objects.filter(
                    id__in=(matching_node.id, invisible_node.id)
                ),
            ),
        )

    def test_get_nodes_with_edit_perm_for_user_lists_owned_nodes(self):
        user = factory.make_User()
        visible_node = self.make_node(user)
        unowned = self.make_node(None)
        self.make_node(factory.make_User())
        self.assertCountEqual(
            [visible_node, unowned],
            Node.objects.get_nodes(user, NodePermission.edit),
        )

    def test_get_nodes_with_edit_perm_admin_lists_all_nodes(self):
        admin = factory.make_admin()
        owners = [None, factory.make_User(), factory.make_admin(), admin]
        nodes = [self.make_node(owner) for owner in owners]
        self.assertCountEqual(
            nodes, Node.objects.get_nodes(admin, NodePermission.edit)
        )

    def test_get_nodes_with_admin_perm_returns_empty_list_for_user(self):
        user = factory.make_User()
        [self.make_node(user) for counter in range(5)]
        self.assertCountEqual(
            [], Node.objects.get_nodes(user, NodePermission.admin)
        )

    def test_get_nodes_with_admin_perm_returns_all_nodes_for_admin(self):
        user = factory.make_User()
        nodes = [self.make_node(user) for counter in range(5)]
        nodes.append(factory.make_RackController())
        nodes.append(factory.make_RegionController())
        nodes.append(factory.make_RegionRackController())
        self.assertCountEqual(
            nodes,
            Node.objects.get_nodes(factory.make_admin(), NodePermission.admin),
        )

    def test_get_nodes_with_edit_perm_filters_locked(self):
        user = factory.make_User()
        factory.make_Node(owner=user)
        node = factory.make_Node(
            owner=user, status=NODE_STATUS.DEPLOYED, locked=True
        )
        self.assertNotIn(
            node, Node.objects.get_nodes(user, NodePermission.edit)
        )

    def test_get_nodes_with_null_user(self):
        # Recreate conditions of bug 1376023. It is not valid to have a
        # node in this state with no user, however the code should not
        # crash.
        node = factory.make_Node(
            status=NODE_STATUS.FAILED_RELEASING, owner=None
        )
        observed = Node.objects.get_nodes(
            user=None, perm=NodePermission.edit, ids=[node.system_id]
        )
        self.assertCountEqual([], observed)

    def test_get_nodes_only_returns_managed_nodes(self):
        user = factory.make_User()
        machine = self.make_node(user)
        for _ in range(3):
            self.make_node(user, node_type=NODE_TYPE.DEVICE)
        self.assertCountEqual(
            [machine],
            Machine.objects.get_nodes(
                user=user,
                perm=NodePermission.view,
                from_nodes=Node.objects.all(),
            ),
        )

    def test_get_nodes_non_admin_hides_controllers(self):
        user = factory.make_User()
        user_visible_nodes = [self.make_node(user), self.make_node(None)]
        admin_visible_nodes = user_visible_nodes + [
            self.make_node(factory.make_User()),
            factory.make_RackController(owner=user),
            factory.make_RackController(owner=None),
            factory.make_RegionController(),
            factory.make_RegionRackController(),
        ]
        self.assertCountEqual(
            admin_visible_nodes,
            Node.objects.get_nodes(factory.make_admin(), NodePermission.admin),
        )
        self.assertCountEqual(
            user_visible_nodes,
            Node.objects.get_nodes(user, NodePermission.view),
        )

    def test_filter_nodes_by_spaces(self):
        # Create a throwaway node and a throwaway space.
        # (to ensure they are filtered out.)
        factory.make_Space()
        vlan1 = factory.make_VLAN(space=factory.make_Space())
        vlan2 = factory.make_VLAN(space=factory.make_Space())
        factory.make_Node_with_Interface_on_Subnet(vlan=vlan1)
        node = factory.make_Node_with_Interface_on_Subnet(
            with_dhcp_rack_primary=False, vlan=vlan2
        )
        iface = node.get_boot_interface()
        ip = iface.ip_addresses.first()
        space = ip.subnet.space
        self.assertCountEqual([node], Node.objects.filter_by_spaces([space]))

    def test_filter_nodes_by_not_spaces(self):
        factory.make_Space()
        vlan1 = factory.make_VLAN(space=factory.make_Space())
        vlan2 = factory.make_VLAN(space=factory.make_Space())
        extra_node = factory.make_Node_with_Interface_on_Subnet(
            with_dhcp_rack_primary=False, vlan=vlan1
        )
        node = factory.make_Node_with_Interface_on_Subnet(
            with_dhcp_rack_primary=False, vlan=vlan2
        )
        iface = node.get_boot_interface()
        ip = iface.ip_addresses.first()
        space = ip.subnet.space
        self.assertCountEqual(
            [extra_node], Node.objects.exclude_spaces([space])
        )

    def test_filter_nodes_by_fabrics(self):
        fabric = factory.make_Fabric()
        factory.make_Space()
        factory.make_Node_with_Interface_on_Subnet(
            with_dhcp_rack_primary=False
        )
        node = factory.make_Node_with_Interface_on_Subnet(
            with_dhcp_rack_primary=False, fabric=fabric
        )
        iface = node.get_boot_interface()
        fabric = iface.vlan.fabric
        self.assertCountEqual([node], Node.objects.filter_by_fabrics([fabric]))

    def test_filter_nodes_by_not_fabrics(self):
        fabric = factory.make_Fabric()
        extra_node = factory.make_Node_with_Interface_on_Subnet(
            with_dhcp_rack_primary=False
        )
        node = factory.make_Node_with_Interface_on_Subnet(
            with_dhcp_rack_primary=False, fabric=fabric
        )
        iface = node.get_boot_interface()
        fabric = iface.vlan.fabric
        self.assertCountEqual(
            [extra_node], Node.objects.exclude_fabrics([fabric])
        )

    def test_filter_nodes_by_fabric_classes(self):
        fabric1 = factory.make_Fabric(class_type="10g")
        fabric2 = factory.make_Fabric(class_type="1g")
        node1 = factory.make_Node_with_Interface_on_Subnet(
            with_dhcp_rack_primary=False, fabric=fabric1
        )
        factory.make_Node_with_Interface_on_Subnet(
            with_dhcp_rack_primary=False, fabric=fabric2
        )
        self.assertCountEqual(
            [node1], Node.objects.filter_by_fabric_classes(["10g"])
        )

    def test_filter_nodes_by_not_fabric_classes(self):
        fabric1 = factory.make_Fabric(class_type="10g")
        fabric2 = factory.make_Fabric(class_type="1g")
        factory.make_Node_with_Interface_on_Subnet(
            with_dhcp_rack_primary=False, fabric=fabric1
        )
        node2 = factory.make_Node_with_Interface_on_Subnet(
            with_dhcp_rack_primary=False, fabric=fabric2
        )
        self.assertCountEqual(
            [node2], Node.objects.exclude_fabric_classes(["10g"])
        )

    def test_filter_nodes_by_vids(self):
        vlan1 = factory.make_VLAN(vid=1)
        vlan2 = factory.make_VLAN(vid=2)
        node1 = factory.make_Node_with_Interface_on_Subnet(
            with_dhcp_rack_primary=False, vlan=vlan1
        )
        factory.make_Node_with_Interface_on_Subnet(
            with_dhcp_rack_primary=False, vlan=vlan2
        )
        self.assertCountEqual([node1], Node.objects.filter_by_vids([1]))

    def test_filter_nodes_by_not_vids(self):
        vlan1 = factory.make_VLAN(vid=1)
        vlan2 = factory.make_VLAN(vid=2)
        factory.make_Node_with_Interface_on_Subnet(
            with_dhcp_rack_primary=False, vlan=vlan1
        )
        node2 = factory.make_Node_with_Interface_on_Subnet(
            with_dhcp_rack_primary=False, vlan=vlan2
        )
        self.assertCountEqual([node2], Node.objects.exclude_vids([1]))

    def test_filter_nodes_by_subnet(self):
        subnet1 = factory.make_Subnet()
        subnet2 = factory.make_Subnet()
        node1 = factory.make_Node_with_Interface_on_Subnet(
            with_dhcp_rack_primary=False, subnet=subnet1
        )
        factory.make_Node_with_Interface_on_Subnet(
            with_dhcp_rack_primary=False, subnet=subnet2
        )
        self.assertCountEqual(
            [node1], Node.objects.filter_by_subnets([subnet1])
        )

    def test_filter_nodes_by_not_subnet(self):
        subnet1 = factory.make_Subnet()
        subnet2 = factory.make_Subnet()
        factory.make_Node_with_Interface_on_Subnet(
            with_dhcp_rack_primary=False, subnet=subnet1
        )
        node2 = factory.make_Node_with_Interface_on_Subnet(
            with_dhcp_rack_primary=False, subnet=subnet2
        )
        self.assertCountEqual([node2], Node.objects.exclude_subnets([subnet1]))

    def test_filter_nodes_by_subnet_cidr(self):
        subnet1 = factory.make_Subnet(cidr="192.168.1.0/24")
        subnet2 = factory.make_Subnet(cidr="192.168.2.0/24")
        node1 = factory.make_Node_with_Interface_on_Subnet(
            with_dhcp_rack_primary=False, subnet=subnet1
        )
        factory.make_Node_with_Interface_on_Subnet(
            with_dhcp_rack_primary=False, subnet=subnet2
        )
        self.assertCountEqual(
            [node1], Node.objects.filter_by_subnet_cidrs(["192.168.1.0/24"])
        )

    def test_filter_nodes_by_not_subnet_cidr(self):
        subnet1 = factory.make_Subnet(cidr="192.168.1.0/24")
        subnet2 = factory.make_Subnet(cidr="192.168.2.0/24")
        factory.make_Node_with_Interface_on_Subnet(
            with_dhcp_rack_primary=False, subnet=subnet1
        )
        node2 = factory.make_Node_with_Interface_on_Subnet(
            with_dhcp_rack_primary=False, subnet=subnet2
        )
        self.assertCountEqual(
            [node2], Node.objects.exclude_subnet_cidrs(["192.168.1.0/24"])
        )

    def test_filter_fabric_subnet_filter_chain(self):
        fabric1 = factory.make_Fabric()
        subnet1 = factory.make_Subnet(cidr="192.168.1.0/24", fabric=fabric1)
        subnet2 = factory.make_Subnet(cidr="192.168.2.0/24", fabric=fabric1)
        factory.make_Node_with_Interface_on_Subnet(
            with_dhcp_rack_primary=False, subnet=subnet1, fabric=fabric1
        )
        node2 = factory.make_Node_with_Interface_on_Subnet(
            with_dhcp_rack_primary=False, subnet=subnet2, fabric=fabric1
        )
        self.assertCountEqual(
            [node2],
            Node.objects.filter_by_fabrics([fabric1]).exclude_subnet_cidrs(
                ["192.168.1.0/24"]
            ),
        )

    def test_get_node_or_404_ok(self):
        """get_node_or_404 fetches nodes by system_id."""
        user = factory.make_User()
        node = self.make_node(user)
        self.assertEqual(
            node,
            Node.objects.get_node_or_404(
                node.system_id, user, NodePermission.view
            ),
        )

    def test_get_node_or_404_edit_locked(self):
        user = factory.make_User()
        node = factory.make_Node(status=NODE_STATUS.DEPLOYED, locked=True)
        self.assertRaises(
            PermissionDenied,
            Node.objects.get_node_or_404,
            node.system_id,
            user,
            NodePermission.edit,
        )

    def test_get_node_or_404_returns_proper_node_object(self):
        user = factory.make_User()
        node = self.make_node(user, node_type=NODE_TYPE.RACK_CONTROLLER)
        rack = Node.objects.get_node_or_404(
            node.system_id, user, NodePermission.view
        )
        self.assertEqual(node, rack)
        self.assertIsInstance(rack, RackController)

    def test_netboot_on(self):
        node = factory.make_Node(netboot=False)
        node.set_netboot(True)
        self.assertTrue(node.netboot)

    def test_netboot_off(self):
        node = factory.make_Node(netboot=True)
        node.set_netboot(False)
        self.assertFalse(node.netboot)


class TestNodeManagerGetNodesRBAC(MAASServerTestCase):
    def setUp(self):
        super().setUp()
        SecretManager().set_composite_secret(
            "external-auth", {"rbac-url": "http://rbac.example.com"}
        )
        self.client = FakeRBACClient()
        rbac._store.client = self.client
        rbac._store.cleared = False  # Prevent re-creation of the client.
        self.store = self.client.store

    def make_ResourcePool(self, *args, **kwargs):
        """Create a resource pool and register it with RBAC."""
        pool = factory.make_ResourcePool(*args, **kwargs)
        self.store.add_pool(pool)
        return pool

    def test_get_nodes_no_permissions(self):
        pool1 = self.make_ResourcePool()
        factory.make_Node(pool=pool1)
        user = factory.make_User()
        self.assertCountEqual(
            [], Node.objects.get_nodes(user, NodePermission.view)
        )

    def test_get_nodes_view_view_permissions_unowned(self):
        user = factory.make_User()
        pool1 = self.make_ResourcePool()
        pool2 = self.make_ResourcePool()
        visible_node = factory.make_Node(pool=pool1)
        factory.make_Node(pool=pool2)
        self.store.allow(user.username, pool1, "view")
        self.assertCountEqual(
            [visible_node], Node.objects.get_nodes(user, NodePermission.view)
        )

    def test_get_nodes_view_view_permissions_owned_self(self):
        user = factory.make_User()
        pool1 = self.make_ResourcePool()
        pool2 = self.make_ResourcePool()
        visible_node = factory.make_Node(pool=pool1, owner=user)
        factory.make_Node(pool=pool2)
        self.store.allow(user.username, pool1, "view")
        self.assertCountEqual(
            [visible_node], Node.objects.get_nodes(user, NodePermission.view)
        )

    def test_get_nodes_view_view_permissions_owned_other(self):
        user = factory.make_User()
        other = factory.make_User()
        pool1 = self.make_ResourcePool()
        owned_node = factory.make_Node(pool=pool1, owner=user)
        factory.make_Node(pool=pool1, owner=other)
        self.store.allow(user.username, pool1, "view")
        self.assertCountEqual(
            [owned_node], Node.objects.get_nodes(user, NodePermission.view)
        )

    def test_get_nodes_view_view_all_permissions_owned_other(self):
        user = factory.make_User()
        other = factory.make_User()
        pool1 = self.make_ResourcePool()
        owned_node = factory.make_Node(pool=pool1, owner=user)
        other_node = factory.make_Node(pool=pool1, owner=other)
        self.store.allow(user.username, pool1, "view-all")
        self.assertCountEqual(
            [owned_node, other_node],
            Node.objects.get_nodes(user, NodePermission.view),
        )

    def test_get_nodes_view_admin_returns_none_when_no_pools(self):
        admin = factory.make_admin()
        pool1 = self.make_ResourcePool()
        pool2 = self.make_ResourcePool()
        factory.make_Node(pool=pool1)
        factory.make_Node(pool=pool2)
        self.assertCountEqual(
            [], Node.objects.get_nodes(admin, NodePermission.view)
        )

    def test_get_nodes_view_user_doesnt_return_controllers(self):
        user = factory.make_User()
        pool1 = self.make_ResourcePool()
        pool2 = self.make_ResourcePool()
        factory.make_Node(pool=pool1)
        factory.make_Node(pool=pool2)
        factory.make_RegionController()
        self.assertCountEqual(
            [], Node.objects.get_nodes(user, NodePermission.view)
        )

    def test_get_nodes_view_admin_returns_controllers(self):
        admin = factory.make_admin()
        pool1 = self.make_ResourcePool()
        pool2 = self.make_ResourcePool()
        factory.make_Node(pool=pool1)
        factory.make_Node(pool=pool2)
        controller = factory.make_RegionController()
        self.assertCountEqual(
            [controller], Node.objects.get_nodes(admin, NodePermission.view)
        )

    def test_get_nodes_view_admin_returns_all_devices(self):
        admin = factory.make_admin()
        pool1 = self.make_ResourcePool()
        pool2 = self.make_ResourcePool()
        factory.make_Node(pool=pool1)
        factory.make_Node(pool=pool2)
        owned_device = factory.make_Device(owner=admin)
        device = factory.make_Device()
        self.assertCountEqual(
            [owned_device, device],
            Node.objects.get_nodes(admin, NodePermission.view),
        )

    def test_get_nodes_view_user_returns_owned_devices(self):
        user = factory.make_User()
        pool1 = self.make_ResourcePool()
        pool2 = self.make_ResourcePool()
        factory.make_Node(pool=pool1)
        factory.make_Node(pool=pool2)
        owned_device = factory.make_Device(owner=user)
        factory.make_Device()
        self.assertCountEqual(
            [owned_device], Node.objects.get_nodes(user, NodePermission.view)
        )

    def test_get_nodes_view_admin_permissions_unowned(self):
        user = factory.make_User()
        pool1 = self.make_ResourcePool()
        pool2 = self.make_ResourcePool()
        visible_node = factory.make_Node(pool=pool1)
        factory.make_Node(pool=pool2)
        self.store.allow(user.username, pool1, "view")
        self.store.allow(user.username, pool1, "admin-machines")
        self.assertCountEqual(
            [visible_node], Node.objects.get_nodes(user, NodePermission.view)
        )

    def test_get_nodes_view_admin_permissions_owned_self(self):
        user = factory.make_User()
        pool1 = self.make_ResourcePool()
        pool2 = self.make_ResourcePool()
        visible_node = factory.make_Node(pool=pool1, owner=user)
        factory.make_Node(pool=pool2)
        self.store.allow(user.username, pool1, "view")
        self.store.allow(user.username, pool1, "admin-machines")
        self.assertCountEqual(
            [visible_node], Node.objects.get_nodes(user, NodePermission.view)
        )

    def test_get_nodes_view_admin_permissions_owned_other(self):
        user = factory.make_User()
        other = factory.make_User()
        pool1 = self.make_ResourcePool()
        owned_node = factory.make_Node(pool=pool1, owner=user)
        other_node = factory.make_Node(pool=pool1, owner=other)
        self.store.allow(user.username, pool1, "view")
        self.store.allow(user.username, pool1, "admin-machines")
        self.assertCountEqual(
            [owned_node, other_node],
            Node.objects.get_nodes(user, NodePermission.view),
        )

    def test_get_nodes_edit_view_permissions_unowned(self):
        user = factory.make_User()
        pool1 = self.make_ResourcePool()
        pool2 = self.make_ResourcePool()
        node1 = factory.make_Node(pool=pool1)
        factory.make_Node(pool=pool2)
        self.store.allow(user.username, pool1, "view")
        self.store.allow(user.username, pool1, "deploy-machines")
        self.assertCountEqual(
            [node1], Node.objects.get_nodes(user, NodePermission.edit)
        )

    def test_get_nodes_edit_view_permissions_owned_self(self):
        user = factory.make_User()
        pool1 = self.make_ResourcePool()
        pool2 = self.make_ResourcePool()
        visible_node = factory.make_Node(pool=pool1, owner=user)
        factory.make_Node(pool=pool2)
        self.store.allow(user.username, pool1, "view")
        self.store.allow(user.username, pool1, "deploy-machines")
        self.assertCountEqual(
            [visible_node], Node.objects.get_nodes(user, NodePermission.edit)
        )

    def test_get_nodes_edit_view_permissions_owned_other(self):
        user = factory.make_User()
        other = factory.make_User()
        pool1 = self.make_ResourcePool()
        owned_node = factory.make_Node(pool=pool1, owner=user)
        factory.make_Node(pool=pool1, owner=other)
        self.store.allow(user.username, pool1, "view")
        # Even with view-all `NodePermission.edit` should not include the
        # nodes owned by others because the user cannot edit those nodes.
        self.store.allow(user.username, pool1, "view-all")
        self.store.allow(user.username, pool1, "deploy-machines")
        self.assertCountEqual(
            [owned_node], Node.objects.get_nodes(user, NodePermission.edit)
        )

    def test_get_nodes_edit_admin_permissions_unowned(self):
        user = factory.make_User()
        pool1 = self.make_ResourcePool()
        pool2 = self.make_ResourcePool()
        visible_node = factory.make_Node(pool=pool1)
        factory.make_Node(pool=pool2)
        self.store.allow(user.username, pool1, "view")
        self.store.allow(user.username, pool1, "admin-machines")
        self.assertCountEqual(
            [visible_node], Node.objects.get_nodes(user, NodePermission.edit)
        )

    def test_get_nodes_edit_admin_permissions_owned_self(self):
        user = factory.make_User()
        pool1 = self.make_ResourcePool()
        pool2 = self.make_ResourcePool()
        visible_node = factory.make_Node(pool=pool1, owner=user)
        factory.make_Node(pool=pool2)
        self.store.allow(user.username, pool1, "view")
        self.store.allow(user.username, pool1, "admin-machines")
        self.assertCountEqual(
            [visible_node], Node.objects.get_nodes(user, NodePermission.edit)
        )

    def test_get_nodes_edit_admin_permissions_owned_other(self):
        user = factory.make_User()
        other = factory.make_User()
        pool1 = self.make_ResourcePool()
        owned_node = factory.make_Node(pool=pool1, owner=user)
        other_node = factory.make_Node(pool=pool1, owner=other)
        self.store.allow(user.username, pool1, "view")
        self.store.allow(user.username, pool1, "admin-machines")
        self.assertCountEqual(
            [owned_node, other_node],
            Node.objects.get_nodes(user, NodePermission.edit),
        )

    def test_get_nodes_admin_view_permissions_unowned(self):
        user = factory.make_User()
        pool1 = self.make_ResourcePool()
        pool2 = self.make_ResourcePool()
        factory.make_Node(pool=pool1)
        factory.make_Node(pool=pool2)
        self.store.allow(user.username, pool1, "view")
        self.assertCountEqual(
            [], Node.objects.get_nodes(user, NodePermission.admin)
        )

    def test_get_nodes_admin_view_permissions_owned_self(self):
        user = factory.make_User()
        pool1 = self.make_ResourcePool()
        pool2 = self.make_ResourcePool()
        factory.make_Node(pool=pool1, owner=user)
        factory.make_Node(pool=pool2)
        self.store.allow(user.username, pool1, "view")
        self.assertCountEqual(
            [], Node.objects.get_nodes(user, NodePermission.admin)
        )

    def test_get_nodes_admin_view_permissions_owned_other(self):
        user = factory.make_User()
        other = factory.make_User()
        pool1 = self.make_ResourcePool()
        factory.make_Node(pool=pool1, owner=user)
        factory.make_Node(pool=pool1, owner=other)
        self.store.allow(user.username, pool1, "view")
        self.assertCountEqual(
            [], Node.objects.get_nodes(user, NodePermission.admin)
        )

    def test_get_nodes_admin_admin_permissions_unowned(self):
        user = factory.make_User()
        pool1 = self.make_ResourcePool()
        pool2 = self.make_ResourcePool()
        visible_node = factory.make_Node(pool=pool1)
        factory.make_Node(pool=pool2)
        self.store.allow(user.username, pool1, "view")
        self.store.allow(user.username, pool1, "admin-machines")
        self.assertCountEqual(
            [visible_node], Node.objects.get_nodes(user, NodePermission.admin)
        )

    def test_get_nodes_admin_admin_permissions_owned_self(self):
        user = factory.make_User()
        pool1 = self.make_ResourcePool()
        pool2 = self.make_ResourcePool()
        visible_node = factory.make_Node(pool=pool1, owner=user)
        factory.make_Node(pool=pool2)
        self.store.allow(user.username, pool1, "view")
        self.store.allow(user.username, pool1, "admin-machines")
        self.assertCountEqual(
            [visible_node], Node.objects.get_nodes(user, NodePermission.admin)
        )

    def test_get_nodes_admin_admin_permissions_owned_other(self):
        user = factory.make_User()
        other = factory.make_User()
        pool1 = self.make_ResourcePool()
        owned_node = factory.make_Node(pool=pool1, owner=user)
        other_node = factory.make_Node(pool=pool1, owner=other)
        self.store.allow(user.username, pool1, "view")
        self.store.allow(user.username, pool1, "admin-machines")
        self.assertCountEqual(
            [owned_node, other_node],
            Node.objects.get_nodes(user, NodePermission.admin),
        )


class TestNodeErase(MAASServerTestCase):
    def test_release_or_erase_erases_when_enabled(self):
        owner = factory.make_User()
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED, owner=owner)
        Config.objects.set_config("enable_disk_erasing_on_release", True)
        erase_mock = self.patch_autospec(node, "start_disk_erasing")
        release_mock = self.patch_autospec(node, "release")
        node.release_or_erase(owner)
        self.assertThat(
            erase_mock,
            MockCalledOnceWith(
                owner, None, secure_erase=None, quick_erase=None
            ),
        )
        self.assertThat(release_mock, MockNotCalled())

    def test_release_or_erase_erases_when_disabled_and_erase_param(self):
        owner = factory.make_User()
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED, owner=owner)
        Config.objects.set_config("enable_disk_erasing_on_release", False)
        erase_mock = self.patch_autospec(node, "start_disk_erasing")
        release_mock = self.patch_autospec(node, "release")
        secure_erase = factory.pick_bool()
        quick_erase = factory.pick_bool()
        node.release_or_erase(
            owner,
            erase=True,
            secure_erase=secure_erase,
            quick_erase=quick_erase,
        )
        self.assertThat(
            erase_mock,
            MockCalledOnceWith(
                owner, None, secure_erase=secure_erase, quick_erase=quick_erase
            ),
        )
        self.assertThat(release_mock, MockNotCalled())

    def test_release_or_erase_releases_when_disabled(self):
        owner = factory.make_User()
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED, owner=owner)
        Config.objects.set_config("enable_disk_erasing_on_release", False)
        erase_mock = self.patch_autospec(node, "start_disk_erasing")
        release_mock = self.patch_autospec(node, "release")
        node.release_or_erase(owner)
        self.assertThat(release_mock, MockCalledOnceWith(owner, None))
        self.assertThat(erase_mock, MockNotCalled())


class TestNodeParentRelationShip(MAASServerTestCase):
    def test_children_field_returns_children(self):
        parent = factory.make_Node()
        # Create other node.
        factory.make_Node()
        children = [factory.make_Node(parent=parent) for _ in range(2)]
        self.assertCountEqual(parent.children.all(), children)

    def test_children_get_deleted_when_parent_is_deleted(self):
        parent = factory.make_Node()
        # Create children.
        factory.make_Node(parent=parent)
        other_node = factory.make_Node()
        parent.delete()
        self.assertCountEqual([other_node], Node.objects.all())

    def test_device_children_get_deleted_when_parent_is_released(self):
        self.patch(Node, "_stop")
        self.patch(Node, "_set_status")
        owner = factory.make_User()
        # Create children.
        parent = factory.make_Node(status=NODE_STATUS.ALLOCATED, owner=owner)
        factory.make_Device(parent=parent)
        machine_child = factory.make_Machine(parent=parent)
        other_node = factory.make_Node()
        with post_commit_hooks:
            parent.release()
        self.assertCountEqual([machine_child], parent.children.all())
        self.assertCountEqual(
            [other_node, parent, machine_child], Node.objects.all()
        )


class TestNodeNetworking(MAASTransactionServerTestCase):
    def test_create_acquired_bridges_doesnt_call_on_bridge(self):
        mock_create_acquired_bridge = self.patch(
            Interface, "create_acquired_bridge"
        )
        node = factory.make_Node()
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        bridge = factory.make_Interface(
            INTERFACE_TYPE.BRIDGE, node=node, parents=[interface]
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO, interface=bridge
        )
        node._create_acquired_bridges()
        self.assertThat(mock_create_acquired_bridge, MockNotCalled())

    def test_create_acquired_bridges_calls_configured_interface(self):
        mock_create_acquired_bridge = self.patch(
            Interface, "create_acquired_bridge"
        )
        node = factory.make_Node()
        factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO, interface=interface
        )
        node._create_acquired_bridges()
        self.assertThat(
            mock_create_acquired_bridge,
            MockCalledOnceWith(
                bridge_type=None, bridge_stp=None, bridge_fd=None
            ),
        )

    def test_create_acquired_bridges_passes_options(self):
        mock_create_acquired_bridge = self.patch(
            Interface, "create_acquired_bridge"
        )
        node = factory.make_Node()
        factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO, interface=interface
        )
        bridge_type = factory.pick_choice(BRIDGE_TYPE_CHOICES)
        bridge_stp = factory.pick_bool()
        bridge_fd = random.randint(0, 500)
        node._create_acquired_bridges(
            bridge_type=bridge_type, bridge_stp=bridge_stp, bridge_fd=bridge_fd
        )
        self.assertThat(
            mock_create_acquired_bridge,
            MockCalledOnceWith(
                bridge_type=bridge_type,
                bridge_stp=bridge_stp,
                bridge_fd=bridge_fd,
            ),
        )

    @transactional
    def test_claim_auto_ips_works_with_multiple_auto_on_the_same_subnet(self):
        node = factory.make_Node()
        vlan = factory.make_VLAN()
        interfaces = [
            factory.make_Interface(
                INTERFACE_TYPE.PHYSICAL, node=node, vlan=vlan
            )
            for _ in range(3)
        ]
        subnet = factory.make_Subnet(
            vlan=vlan, host_bits=random.randint(4, 12)
        )
        for interface in interfaces:
            for _ in range(2):
                factory.make_StaticIPAddress(
                    alloc_type=IPADDRESS_TYPE.AUTO,
                    ip="",
                    subnet=subnet,
                    interface=interface,
                )
        # No serialization error should be raised.
        node.claim_auto_ips()
        # Each interface should have assigned AUTO IP addresses and none
        # should overlap.
        assigned_ips = set()
        for interface in interfaces:
            for auto_ip in interface.ip_addresses.filter(
                alloc_type=IPADDRESS_TYPE.AUTO
            ):
                assigned_ips.add(str(auto_ip.ip))
        self.assertEqual(6, len(assigned_ips))

    def test_claim_auto_ips_calls_claim_auto_ips_on_all_interfaces(self):
        node = factory.make_Node()
        interfaces = [
            factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
            for _ in range(3)
        ]
        mock_claim_auto_ips = self.patch_autospec(Interface, "claim_auto_ips")
        node.claim_auto_ips()
        # Since the interfaces are not ordered, which they dont need to be
        # we extract the passed interface to each call.
        observed_interfaces = [
            call[0][0] for call in mock_claim_auto_ips.call_args_list
        ]
        self.assertCountEqual(interfaces, observed_interfaces)

    def test_claim_auto_ips_calls_claim_auto_ips_on_new_added_interface(self):
        node = factory.make_Node()
        interfaces = [
            factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
            for _ in range(2)
        ]
        mock_claim_auto_ips = self.patch_autospec(Interface, "claim_auto_ips")
        node = (
            Node.objects.filter(id=node.id)
            .prefetch_related("current_config__interface_set")
            .first()
        )
        # Add in the third interface after we create the node with the cached
        # interface_set.
        new_iface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        interfaces.append(new_iface)
        node.claim_auto_ips()
        # Since the interfaces are not ordered, which they dont need to be
        # we extract the passed interface to each call.
        observed_interfaces = [
            call[0][0] for call in mock_claim_auto_ips.call_args_list
        ]
        self.assertCountEqual(interfaces, observed_interfaces)

    def test_release_interface_config_calls_release_auto_ips_on_all(self):
        node = factory.make_Node()
        interfaces = [
            factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
            for _ in range(3)
        ]
        mock_release_auto_ips = self.patch_autospec(
            Interface, "release_auto_ips"
        )
        node.release_interface_config()
        # Since the interfaces are not ordered, which they dont need to be
        # we extract the passed interface to each call.
        observed_interfaces = [
            call[0][0] for call in mock_release_auto_ips.call_args_list
        ]
        self.assertCountEqual(interfaces, observed_interfaces)

    def test_release_interface_config_handles_acquired_bridge(self):
        node = factory.make_Node()
        interfaces = [
            factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
            for _ in range(3)
        ]
        parent = interfaces[0]
        bridge = factory.make_Interface(
            INTERFACE_TYPE.BRIDGE, parents=[parent]
        )
        bridge.acquired = True
        bridge.save()
        subnet = factory.make_Subnet(vlan=parent.vlan)
        static_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO,
            ip=factory.pick_ip_in_Subnet(subnet),
            subnet=subnet,
            interface=bridge,
        )
        node.release_interface_config()
        self.assertIsNone(reload_object(bridge))
        self.assertEqual(
            [parent.id], [nic.id for nic in static_ip.interface_set.all()]
        )

    def test_release_interface_config_removes_acquired_vlan(self):
        node = factory.make_Node()
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        vlan_if = factory.make_Interface(
            INTERFACE_TYPE.VLAN, parents=[interface]
        )
        vlan_if.acquired = True
        vlan_if.save()
        subnet = factory.make_Subnet()
        static_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO,
            ip=factory.pick_ip_in_Subnet(subnet),
            subnet=subnet,
            interface=vlan_if,
        )
        node.release_interface_config()
        self.assertIsNone(reload_object(vlan_if))
        self.assertIsNone(reload_object(static_ip))

    def test_release_interface_config_removes_acquired_physical(self):
        node = factory.make_Node()
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        interface.acquired = True
        interface.save()
        subnet = factory.make_Subnet()
        static_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO,
            ip=factory.pick_ip_in_Subnet(subnet),
            subnet=subnet,
            interface=interface,
        )
        node.release_interface_config()
        self.assertIsNone(reload_object(interface))
        self.assertIsNone(reload_object(static_ip))

    def test_clear_networking_configuration(self):
        node = factory.make_Node()
        nic0 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        nic1 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        dhcp_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.DHCP, ip="", interface=nic0
        )
        static_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, interface=nic0
        )
        auto_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO, ip="", interface=nic1
        )
        mock_unlink_ip_address = self.patch_autospec(
            Interface, "unlink_ip_address"
        )
        node._clear_networking_configuration()
        # Since the interfaces are not ordered, which they dont need to be
        # we extract the passed interface to each call.
        observed_interfaces = {
            call[0][0] for call in mock_unlink_ip_address.call_args_list
        }
        # Since the IP address are not ordered, which they dont need to be
        # we extract the passed IP address to each call.
        observed_ip_address = [
            call[0][1] for call in mock_unlink_ip_address.call_args_list
        ]
        # Check that clearing_config is always sent as true.
        clearing_config = {
            call[1]["clearing_config"]
            for call in mock_unlink_ip_address.call_args_list
        }
        self.assertCountEqual([nic0, nic1], observed_interfaces)
        self.assertCountEqual(
            [dhcp_ip, static_ip, auto_ip], observed_ip_address
        )
        self.assertEqual({True}, clearing_config)

    def test_clear_networking_configuration_clears_gateways(self):
        node = factory.make_Node()
        nic0 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        nic1 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        ipv4_subnet = factory.make_Subnet(
            cidr="192.168.0.0/24", gateway_ip="192.168.0.1"
        )
        ipv6_subnet = factory.make_Subnet(
            cidr="2001:db8::/64", gateway_ip="2001:db8::1"
        )
        static_ipv4 = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            interface=nic0,
            subnet=ipv4_subnet,
        )
        static_ipv6 = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            interface=nic1,
            subnet=ipv6_subnet,
        )
        node.gateway_link_ipv4 = static_ipv4
        node.gateway_link_ipv6 = static_ipv6
        node.save()
        node = reload_object(node)
        nic0_gw = GatewayDefinition(
            interface_id=nic0.id,
            subnet_id=ipv4_subnet.id,
            gateway_ip=ipv4_subnet.gateway_ip,
        )
        nic1_gw = GatewayDefinition(
            interface_id=nic1.id,
            subnet_id=ipv6_subnet.id,
            gateway_ip=ipv6_subnet.gateway_ip,
        )
        expected_gateways = DefaultGateways(
            nic0_gw, nic1_gw, [nic0_gw, nic1_gw]
        )
        self.assertEqual(expected_gateways, node.get_default_gateways())
        node._clear_networking_configuration()
        self.assertIsNone(node.gateway_link_ipv4)
        self.assertIsNone(node.gateway_link_ipv6)

    def test_get_default_gateways_returns_priority_and_complete_list(self):
        node = factory.make_Node()
        nic0 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        nic1 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        nic2 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        ipv4_subnet = factory.make_Subnet(
            cidr="192.168.0.0/24", gateway_ip="192.168.0.1"
        )
        ipv6_subnet = factory.make_Subnet(
            cidr="2001:db8::/64", gateway_ip="2001:db8::1"
        )
        ipv4_subnet_2 = factory.make_Subnet(
            cidr="192.168.1.0/24", gateway_ip="192.168.1.1"
        )
        static_ipv4 = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            interface=nic0,
            subnet=ipv4_subnet,
        )
        static_ipv6 = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            interface=nic1,
            subnet=ipv6_subnet,
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            interface=nic2,
            subnet=ipv4_subnet_2,
        )
        node.gateway_link_ipv4 = static_ipv4
        node.gateway_link_ipv6 = static_ipv6
        node.save()
        node = reload_object(node)
        nic0_gw = GatewayDefinition(
            interface_id=nic0.id,
            subnet_id=ipv4_subnet.id,
            gateway_ip=ipv4_subnet.gateway_ip,
        )
        nic1_gw = GatewayDefinition(
            interface_id=nic1.id,
            subnet_id=ipv6_subnet.id,
            gateway_ip=ipv6_subnet.gateway_ip,
        )
        nic2_gw = GatewayDefinition(
            interface_id=nic2.id,
            subnet_id=ipv4_subnet_2.id,
            gateway_ip=ipv4_subnet_2.gateway_ip,
        )
        expected_gateways = DefaultGateways(
            nic0_gw, nic1_gw, [nic0_gw, nic2_gw, nic1_gw]
        )
        self.assertEqual(expected_gateways, node.get_default_gateways())

    def test_set_initial_net_config_does_nothing_if_skip_networking(self):
        node = factory.make_Node_with_Interface_on_Subnet(skip_networking=True)
        boot_interface = node.get_boot_interface()
        node.set_initial_networking_configuration()
        boot_interface = reload_object(boot_interface)
        auto_ip = boot_interface.ip_addresses.filter(
            alloc_type=IPADDRESS_TYPE.AUTO
        ).first()
        self.assertIsNone(auto_ip)

    def test_set_initial_net_config_asserts_proper_status(self):
        machine = factory.make_Machine_with_Interface_on_Subnet(
            status=random.choice([NODE_STATUS.DEPLOYING, NODE_STATUS.DEPLOYED])
        )
        self.assertRaises(
            AssertionError, machine.set_initial_networking_configuration
        )

    def test_set_initial_networking_configuration_auto_on_boot_nic(self):
        node = factory.make_Node_with_Interface_on_Subnet()
        boot_interface = node.get_boot_interface()
        subnet = (
            boot_interface.ip_addresses.filter(
                alloc_type=IPADDRESS_TYPE.DISCOVERED
            )
            .first()
            .subnet
        )
        node._clear_networking_configuration()
        node.set_initial_networking_configuration()
        boot_interface = reload_object(boot_interface)
        auto_ip = boot_interface.ip_addresses.filter(
            alloc_type=IPADDRESS_TYPE.AUTO
        ).first()
        self.assertIsNotNone(auto_ip)
        self.assertEqual(subnet, auto_ip.subnet)

    def test_set_initial_networking_configuration_auto_on_managed_subnet(self):
        node = factory.make_Node()
        boot_interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node
        )
        subnet = factory.make_Subnet(vlan=boot_interface.vlan, dhcp_on=True)
        node.set_initial_networking_configuration()
        boot_interface = reload_object(boot_interface)
        auto_ip = boot_interface.ip_addresses.filter(
            alloc_type=IPADDRESS_TYPE.AUTO
        ).first()
        self.assertIsNotNone(auto_ip)
        self.assertEqual(subnet, auto_ip.subnet)

    def test_set_initial_networking_configuration_link_up_on_enabled(self):
        node = factory.make_Node()
        factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        enabled_interfaces = [
            factory.make_Interface(
                INTERFACE_TYPE.PHYSICAL, node=node, enabled=True
            )
            for _ in range(3)
        ]
        for _ in range(3):
            factory.make_Interface(
                INTERFACE_TYPE.PHYSICAL, node=node, enabled=False
            )
        mock_ensure_link_up = self.patch_autospec(Interface, "ensure_link_up")
        node.set_initial_networking_configuration()
        # Since the interfaces are not ordered, which they dont need to be
        # we extract the passed interface to each call.
        observed_interfaces = {
            call[0][0] for call in mock_ensure_link_up.call_args_list
        }
        self.assertCountEqual(enabled_interfaces, observed_interfaces)

    def test_set_initial_networking_configuration_no_multiple_auto_ips(self):
        node = factory.make_Node_with_Interface_on_Subnet()
        boot_interface = node.get_boot_interface()
        subnet = (
            boot_interface.ip_addresses.filter(
                alloc_type=IPADDRESS_TYPE.DISCOVERED
            )
            .first()
            .subnet
        )
        boot_interface.link_subnet(INTERFACE_LINK_TYPE.AUTO, subnet)
        node.set_initial_networking_configuration()
        boot_interface = reload_object(boot_interface)
        auto_ips = boot_interface.ip_addresses.filter(
            alloc_type=IPADDRESS_TYPE.AUTO
        )
        self.assertEqual(1, auto_ips.count())

    def test_restore_commissioned_network_interfaces(self):
        node = factory.make_Node()
        lxd_script = factory.make_Script(
            name=COMMISSIONING_OUTPUT_NAME,
            script_type=SCRIPT_TYPE.COMMISSIONING,
        )
        commissioning_script_set = (
            ScriptSet.objects.create_commissioning_script_set(
                node, scripts=[lxd_script.name]
            )
        )
        node.current_commissioning_script_set = commissioning_script_set
        output = test_hooks.make_lxd_output_json()
        factory.make_ScriptResult(
            script_set=commissioning_script_set,
            script=lxd_script,
            exit_status=0,
            output=output,
            stdout=output,
        )
        # Create NUMA nodes.
        test_hooks.create_numa_nodes(node)
        # reset network intefaces from commissioning data
        node.restore_network_interfaces()
        self.assertCountEqual(
            ["eth0", "eth1", "eth2"],
            [
                interface.name
                for interface in node.current_config.interface_set.all()
            ],
        )

    def test_restore_commissioned_network_interfaces_missing_data(self):
        node = factory.make_Node()
        lxd_script = factory.make_Script(
            name=COMMISSIONING_OUTPUT_NAME,
            script_type=SCRIPT_TYPE.COMMISSIONING,
        )
        commissioning_script_set = (
            ScriptSet.objects.create_commissioning_script_set(
                node, scripts=[lxd_script.name]
            )
        )
        node.current_commissioning_script_set = commissioning_script_set
        data = test_hooks.make_lxd_output()
        # emulate missing networks information in LXD output (<<2.10)
        del data["networks"]
        output = json.dumps(data).encode()
        factory.make_ScriptResult(
            script_set=commissioning_script_set,
            script=lxd_script,
            exit_status=0,
            output=output,
            stdout=output,
        )
        # Create NUMA nodes.
        test_hooks.create_numa_nodes(node)
        self.assertRaises(
            NetworkingResetProblem, node.restore_network_interfaces
        )

    def test_restore_network_interfaces_ignores_stderr(self):
        node = factory.make_Node()
        lxd_script = factory.make_Script(
            name=COMMISSIONING_OUTPUT_NAME,
            script_type=SCRIPT_TYPE.COMMISSIONING,
        )
        commissioning_script_set = (
            ScriptSet.objects.create_commissioning_script_set(
                node, scripts=[lxd_script.name]
            )
        )
        node.current_commissioning_script_set = commissioning_script_set
        output = test_hooks.make_lxd_output_json()
        error_message = b"some error message"
        factory.make_ScriptResult(
            script_set=commissioning_script_set,
            script=lxd_script,
            exit_status=0,
            output=error_message + output,
            stdout=output,
            stderr=error_message,
        )
        # Create NUMA nodes.
        test_hooks.create_numa_nodes(node)
        # reset network intefaces from commissioning data
        node.restore_network_interfaces()
        self.assertCountEqual(
            ["eth0", "eth1", "eth2"],
            [
                interface.name
                for interface in node.current_config.interface_set.all()
            ],
        )

    def test_restore_network_interfaces_extra(self):
        node = factory.make_Node()
        lxd_script = factory.make_Script(
            name=COMMISSIONING_OUTPUT_NAME,
            script_type=SCRIPT_TYPE.COMMISSIONING,
        )
        commissioning_script_set = (
            ScriptSet.objects.create_commissioning_script_set(
                node, scripts=[lxd_script.name]
            )
        )
        node.current_commissioning_script_set = commissioning_script_set
        output = test_hooks.make_lxd_output_json()
        factory.make_ScriptResult(
            script_set=commissioning_script_set,
            script=lxd_script,
            exit_status=0,
            output=output,
            stdout=output,
        )
        # Create NUMA nodes.
        test_hooks.create_numa_nodes(node)
        node.restore_network_interfaces()

        # If extra interfaces are added, they will be removed when
        # calling restore_network_interfaces().
        # Order the interfaces, so that the first interface has a VLAN.
        parents = list(
            node.current_config.interface_set.all().order_by("vlan")
        )
        factory.make_Interface(
            INTERFACE_TYPE.VLAN, node=node, parents=[parents[0]]
        )
        factory.make_Interface(
            INTERFACE_TYPE.BOND, node=node, parents=parents[1:]
        )
        factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        node.restore_network_interfaces()
        self.assertCountEqual(
            ["eth0", "eth1", "eth2"],
            [
                interface.name
                for interface in node.current_config.interface_set.all()
            ],
        )

    def test_restore_network_interfaces_includes_hardware_sync_discovered_physical_interfaces(
        self,
    ):
        node = factory.make_Node(
            enable_hw_sync=True, status=NODE_STATUS.DEPLOYED
        )
        lxd_script = factory.make_Script(
            name=COMMISSIONING_OUTPUT_NAME,
            script_type=SCRIPT_TYPE.COMMISSIONING,
        )
        commissioning_script_set = (
            ScriptSet.objects.create_commissioning_script_set(
                node, scripts=[lxd_script.name]
            )
        )
        node.current_commissioning_script_set = commissioning_script_set
        output = test_hooks.make_lxd_output_json()
        factory.make_ScriptResult(
            script_set=commissioning_script_set,
            script=lxd_script,
            exit_status=0,
            output=output,
            stdout=output,
        )
        # Create NUMA nodes.
        test_hooks.create_numa_nodes(node)
        iface_name = factory.make_name()
        factory.make_Interface(name=iface_name, node=node)
        node.restore_network_interfaces()
        self.assertIn(
            iface_name,
            [iface.name for iface in node.current_config.interface_set.all()],
        )


class TestGetGatewaysByPriority(MAASServerTestCase):
    def assertGatewayPriorities(self, expected, actual):
        """Verifies the IPv4 and IPv6 gateways are in the correct order."""
        for expected_gw in expected:
            family = IPAddress(
                GatewayDefinition(*expected_gw).gateway_ip
            ).version
            for actual_gw in actual:
                if IPAddress(actual_gw.gateway_ip).version == family:
                    self.assertEqual(expected_gw, actual_gw)
                    return
                else:
                    continue
            self.assertIsNotNone(expected_gw)

    def test_simple(self):
        node = factory.make_Node_with_Interface_on_Subnet(
            status=NODE_STATUS.READY
        )
        boot_interface = node.get_boot_interface()
        managed_subnet = (
            boot_interface.ip_addresses.filter(alloc_type=IPADDRESS_TYPE.AUTO)
            .first()
            .subnet
        )
        gateway_ip = managed_subnet.gateway_ip
        self.assertGatewayPriorities(
            [(boot_interface.id, managed_subnet.id, gateway_ip)],
            node.get_gateways_by_priority(),
        )

    def test_ipv4_and_ipv6(self):
        node = factory.make_Node(status=NODE_STATUS.READY)
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        network_v4 = factory.make_ipv4_network()
        subnet_v4 = factory.make_Subnet(cidr=str(network_v4.cidr))
        network_v6 = factory.make_ipv6_network()
        subnet_v6 = factory.make_Subnet(cidr=str(network_v6.cidr))
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_network(network_v4),
            subnet=subnet_v4,
            interface=interface,
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_network(network_v6),
            subnet=subnet_v6,
            interface=interface,
        )
        self.assertGatewayPriorities(
            [
                (interface.id, subnet_v4.id, subnet_v4.gateway_ip),
                (interface.id, subnet_v6.id, subnet_v6.gateway_ip),
            ],
            node.get_gateways_by_priority(),
        )

    def test_only_one(self):
        node = factory.make_Node_with_Interface_on_Subnet(
            status=NODE_STATUS.READY
        )
        boot_interface = node.get_boot_interface()
        managed_subnet = (
            boot_interface.ip_addresses.filter(alloc_type=IPADDRESS_TYPE.AUTO)
            .first()
            .subnet
        )
        # Give it two IP addresses on the same subnet.
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_network(managed_subnet.get_ipnetwork()),
            subnet=managed_subnet,
            interface=boot_interface,
        )
        gateway_ip = managed_subnet.gateway_ip
        self.assertGatewayPriorities(
            [(boot_interface.id, managed_subnet.id, gateway_ip)],
            node.get_gateways_by_priority(),
        )

    def test_managed_subnet_over_unmanaged(self):
        node = factory.make_Node(status=NODE_STATUS.READY)
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        unmanaged_network = factory.make_ipv4_network()
        unmanaged_subnet = factory.make_Subnet(
            cidr=str(unmanaged_network.cidr)
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_network(unmanaged_network),
            subnet=unmanaged_subnet,
            interface=interface,
        )
        managed_network = factory.make_ipv4_network()
        managed_subnet = factory.make_ipv4_Subnet_with_IPRanges(
            cidr=str(managed_network.cidr), dhcp_on=True
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_network(managed_network),
            subnet=managed_subnet,
            interface=interface,
        )
        gateway_ip = managed_subnet.gateway_ip
        self.assertGatewayPriorities(
            [(interface.id, managed_subnet.id, gateway_ip)],
            node.get_gateways_by_priority(),
        )

    def test_bond_over_physical_interface(self):
        node = factory.make_Node(status=NODE_STATUS.READY)
        physical_interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node
        )
        physical_network = factory.make_ipv4_network()
        physical_subnet = factory.make_Subnet(cidr=str(physical_network.cidr))
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_network(physical_network),
            subnet=physical_subnet,
            interface=physical_interface,
        )
        parent_interfaces = [
            factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
            for _ in range(2)
        ]
        bond_interface = factory.make_Interface(
            INTERFACE_TYPE.BOND, node=node, parents=parent_interfaces
        )
        bond_network = factory.make_ipv4_network()
        bond_subnet = factory.make_Subnet(cidr=str(bond_network.cidr))
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_network(bond_network),
            subnet=bond_subnet,
            interface=bond_interface,
        )
        gateway_ip = bond_subnet.gateway_ip
        self.assertGatewayPriorities(
            [(bond_interface.id, bond_subnet.id, gateway_ip)],
            node.get_gateways_by_priority(),
        )

    def test_physical_over_vlan_interface(self):
        node = factory.make_Node(status=NODE_STATUS.READY)
        physical_interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node
        )
        physical_network = factory.make_ipv4_network()
        physical_subnet = factory.make_Subnet(cidr=str(physical_network.cidr))
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_network(physical_network),
            subnet=physical_subnet,
            interface=physical_interface,
        )
        vlan_interface = factory.make_Interface(
            INTERFACE_TYPE.VLAN, node=node, parents=[physical_interface]
        )
        vlan_network = factory.make_ipv4_network()
        vlan_subnet = factory.make_Subnet(cidr=str(vlan_network.cidr))
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_network(vlan_network),
            subnet=vlan_subnet,
            interface=vlan_interface,
        )
        gateway_ip = physical_subnet.gateway_ip
        self.assertGatewayPriorities(
            [(physical_interface.id, physical_subnet.id, gateway_ip)],
            node.get_gateways_by_priority(),
        )

    def test_boot_interface_over_other_interfaces(self):
        node = factory.make_Node(status=NODE_STATUS.READY)
        physical_interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node
        )
        physical_network = factory.make_ipv4_network()
        physical_subnet = factory.make_Subnet(cidr=str(physical_network.cidr))
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_network(physical_network),
            subnet=physical_subnet,
            interface=physical_interface,
        )
        boot_interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node
        )
        boot_network = factory.make_ipv4_network()
        boot_subnet = factory.make_Subnet(cidr=str(boot_network.cidr))
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_network(boot_network),
            subnet=boot_subnet,
            interface=boot_interface,
        )
        node.boot_interface = boot_interface
        node.save()
        gateway_ip = boot_subnet.gateway_ip
        self.assertGatewayPriorities(
            [(boot_interface.id, boot_subnet.id, gateway_ip)],
            node.get_gateways_by_priority(),
        )

    def test_sticky_ip_over_user_reserved(self):
        node = factory.make_Node(status=NODE_STATUS.READY)
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        sticky_network = factory.make_ipv4_network()
        sticky_subnet = factory.make_Subnet(cidr=str(sticky_network.cidr))
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_network(sticky_network),
            subnet=sticky_subnet,
            interface=interface,
        )
        user_reserved_network = factory.make_ipv4_network()
        user_reserved_subnet = factory.make_Subnet(
            cidr=str(user_reserved_network.cidr)
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.USER_RESERVED,
            user=factory.make_User(),
            ip=factory.pick_ip_in_network(user_reserved_network),
            subnet=user_reserved_subnet,
            interface=interface,
        )
        gateway_ip = sticky_subnet.gateway_ip
        self.assertGatewayPriorities(
            [(interface.id, sticky_subnet.id, gateway_ip)],
            node.get_gateways_by_priority(),
        )

    def test_user_reserved_ip_over_auto(self):
        node = factory.make_Node(status=NODE_STATUS.READY)
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        user_reserved_network = factory.make_ipv4_network()
        user_reserved_subnet = factory.make_Subnet(
            cidr=str(user_reserved_network.cidr)
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.USER_RESERVED,
            user=factory.make_User(),
            ip=factory.pick_ip_in_network(user_reserved_network),
            subnet=user_reserved_subnet,
            interface=interface,
        )
        auto_network = factory.make_ipv4_network()
        auto_subnet = factory.make_Subnet(cidr=str(auto_network.cidr))
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO,
            ip=factory.pick_ip_in_network(auto_network),
            subnet=auto_subnet,
            interface=interface,
        )
        gateway_ip = user_reserved_subnet.gateway_ip
        self.assertGatewayPriorities(
            [(interface.id, user_reserved_subnet.id, gateway_ip)],
            node.get_gateways_by_priority(),
        )


def MatchesDefaultGateways(ipv4, ipv6):
    # Matches a `DefaultGateways` instance, which must contain
    # `GatewayDefinition` instances, not just plain tuples.
    return MatchesAll(
        IsInstance(DefaultGateways),
        MatchesStructure(
            ipv4=MatchesAll(IsInstance(GatewayDefinition), Equals(ipv4)),
            ipv6=MatchesAll(IsInstance(GatewayDefinition), Equals(ipv6)),
            all=MatchesAll(IsInstance(list)),
        ),
    )


class TestGetDefaultGateways(MAASServerTestCase):
    def test_return_set_ipv4_and_ipv6(self):
        node = factory.make_Node(status=NODE_STATUS.READY)
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        network_v4 = factory.make_ipv4_network()
        subnet_v4 = factory.make_Subnet(cidr=str(network_v4.cidr))
        network_v4_2 = factory.make_ipv4_network()
        subnet_v4_2 = factory.make_Subnet(
            cidr=str(network_v4_2.cidr), dhcp_on=True
        )
        network_v6 = factory.make_ipv6_network()
        subnet_v6 = factory.make_Subnet(cidr=str(network_v6.cidr))
        network_v6_2 = factory.make_ipv6_network()
        subnet_v6_2 = factory.make_Subnet(
            cidr=str(network_v6_2.cidr), dhcp_on=True
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_network(network_v4),
            subnet=subnet_v4,
            interface=interface,
        )
        link_v4 = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_network(network_v4_2),
            subnet=subnet_v4_2,
            interface=interface,
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_network(network_v6),
            subnet=subnet_v6,
            interface=interface,
        )
        link_v6 = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_network(network_v6_2),
            subnet=subnet_v6_2,
            interface=interface,
        )
        node.gateway_link_ipv4 = link_v4
        node.gateway_link_ipv6 = link_v6
        node.save()
        self.assertThat(
            node.get_default_gateways(),
            MatchesDefaultGateways(
                (interface.id, subnet_v4_2.id, subnet_v4_2.gateway_ip),
                (interface.id, subnet_v6_2.id, subnet_v6_2.gateway_ip),
            ),
        )

    def test_return_set_ipv4_and_guess_ipv6(self):
        node = factory.make_Node(status=NODE_STATUS.READY)
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        network_v4 = factory.make_ipv4_network()
        subnet_v4 = factory.make_Subnet(cidr=str(network_v4.cidr))
        network_v4_2 = factory.make_ipv4_network()
        subnet_v4_2 = factory.make_Subnet(
            cidr=str(network_v4_2.cidr), dhcp_on=True
        )
        network_v6 = factory.make_ipv6_network()
        subnet_v6 = factory.make_Subnet(cidr=str(network_v6.cidr))
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_network(network_v4),
            subnet=subnet_v4,
            interface=interface,
        )
        link_v4 = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_network(network_v4_2),
            subnet=subnet_v4_2,
            interface=interface,
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_network(network_v6),
            subnet=subnet_v6,
            interface=interface,
        )
        node.gateway_link_ipv4 = link_v4
        node.save()
        self.assertThat(
            node.get_default_gateways(),
            MatchesDefaultGateways(
                (interface.id, subnet_v4_2.id, subnet_v4_2.gateway_ip),
                (interface.id, subnet_v6.id, subnet_v6.gateway_ip),
            ),
        )

    def test_return_set_ipv6_and_guess_ipv4(self):
        node = factory.make_Node(status=NODE_STATUS.READY)
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        network_v4 = factory.make_ipv4_network()
        subnet_v4 = factory.make_Subnet(cidr=str(network_v4.cidr))
        network_v6 = factory.make_ipv6_network()
        subnet_v6 = factory.make_Subnet(cidr=str(network_v6.cidr))
        network_v6_2 = factory.make_ipv6_network()
        subnet_v6_2 = factory.make_Subnet(
            cidr=str(network_v6_2.cidr), dhcp_on=True
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_network(network_v4),
            subnet=subnet_v4,
            interface=interface,
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_network(network_v6),
            subnet=subnet_v6,
            interface=interface,
        )
        link_v6 = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_network(network_v6_2),
            subnet=subnet_v6_2,
            interface=interface,
        )
        node.gateway_link_ipv6 = link_v6
        node.save()
        self.assertThat(
            node.get_default_gateways(),
            MatchesDefaultGateways(
                (interface.id, subnet_v4.id, subnet_v4.gateway_ip),
                (interface.id, subnet_v6_2.id, subnet_v6_2.gateway_ip),
            ),
        )

    def test_return_guess_ipv4_and_ipv6(self):
        node = factory.make_Node(status=NODE_STATUS.READY)
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        network_v4 = factory.make_ipv4_network()
        subnet_v4 = factory.make_Subnet(cidr=str(network_v4.cidr))
        network_v6 = factory.make_ipv6_network()
        subnet_v6 = factory.make_Subnet(cidr=str(network_v6.cidr))
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_network(network_v4),
            subnet=subnet_v4,
            interface=interface,
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_network(network_v6),
            subnet=subnet_v6,
            interface=interface,
        )
        self.assertThat(
            node.get_default_gateways(),
            MatchesDefaultGateways(
                (interface.id, subnet_v4.id, subnet_v4.gateway_ip),
                (interface.id, subnet_v6.id, subnet_v6.gateway_ip),
            ),
        )


class TestGetDefaultDNSServers(MAASServerTestCase):
    def make_Node_with_RackController(
        self,
        ipv4=True,
        ipv6=True,
        ipv4_gateway=True,
        ipv6_gateway=True,
        ipv4_subnet_dns=None,
        ipv6_subnet_dns=None,
    ):
        ipv4_subnet_dns = [] if ipv4_subnet_dns is None else ipv4_subnet_dns
        ipv6_subnet_dns = [] if ipv6_subnet_dns is None else ipv6_subnet_dns
        rack_v4 = None
        rack_v6 = None
        fabric = factory.make_Fabric()
        vlan = fabric.get_default_vlan()
        if ipv4:
            gateway_ip = RANDOM if ipv4_gateway else ""
            v4_subnet = factory.make_Subnet(
                version=4,
                vlan=vlan,
                dns_servers=ipv4_subnet_dns,
                gateway_ip=gateway_ip,
            )
        if ipv6:
            gateway_ip = RANDOM if ipv6_gateway else ""
            v6_subnet = factory.make_Subnet(
                version=6,
                vlan=vlan,
                dns_servers=ipv6_subnet_dns,
                gateway_ip=gateway_ip,
            )
        rack = factory.make_RegionRackController()
        vlan.primary_rack = rack
        vlan.dhcp_on = True
        vlan.save()
        # In order to determine the correct IP address per-address-family,
        # a name lookup is performed on the hostname part of the URL.
        # We need to mock that so we can return whatever IP addresses it
        # resolves to.
        rack.url = "http://region:5240/MAAS/"
        if ipv4:
            rack_v4 = factory.pick_ip_in_Subnet(v4_subnet)
        if ipv6:
            rack_v6 = factory.pick_ip_in_Subnet(v6_subnet)

        def get_address(hostname, ip_version=4):
            """Mock function to return the IP address of the rack based on the
            given address family.
            """
            if ip_version == 0:
                if rack_v4:
                    return {IPAddress(rack_v4)}
                if rack_v6:
                    return {IPAddress(rack_v6)}
                return set()
            if ip_version == 4:
                return {IPAddress(rack_v4)} if rack_v4 else set()
            elif ip_version == 6:
                return {IPAddress(rack_v6)} if rack_v6 else set()

        resolve_hostname = self.patch(server_address, "resolve_hostname")
        resolve_hostname.side_effect = get_address
        rack.current_config.interface_set.all().delete()
        rackif = factory.make_Interface(vlan=vlan, node=rack)
        if ipv4:
            rackif.link_subnet(INTERFACE_LINK_TYPE.STATIC, v4_subnet, rack_v4)
        if ipv6:
            rackif.link_subnet(INTERFACE_LINK_TYPE.STATIC, v6_subnet, rack_v6)
        rack.boot_interface = rackif
        rack.save()
        node = factory.make_Node(status=NODE_STATUS.READY)
        nodeif = factory.make_Interface(vlan=vlan, node=node)
        if ipv4:
            nodeif.link_subnet(INTERFACE_LINK_TYPE.STATIC, v4_subnet)
        if ipv6:
            nodeif.link_subnet(INTERFACE_LINK_TYPE.STATIC, v6_subnet)
        node.boot_interface = nodeif
        node.save()
        return rack_v4, rack_v6, node

    def make_RackController_routable_to_node(self, node, subnet=None):
        other_rack = factory.make_RackController()
        vlan = node.boot_interface.vlan
        subnet = vlan.subnet_set.first()
        other_rack.current_config.interface_set.all().delete()
        other_rackif = factory.make_Interface(vlan=vlan, node=other_rack)
        other_rackif_ip = factory.pick_ip_in_Subnet(subnet)
        other_rackif.link_subnet(
            INTERFACE_LINK_TYPE.STATIC, subnet, other_rackif_ip
        )
        return other_rackif_ip, other_rack

    def test_uses_rack_ipv4_if_ipv4_only_with_no_gateway(self):
        rack_v4, rack_v6, node = self.make_Node_with_RackController(
            ipv4=True, ipv4_gateway=False, ipv6=False, ipv6_gateway=False
        )
        self.assertEqual([rack_v4], node.get_default_dns_servers())

    def test_uses_rack_ipv4_if_ipv4_only_with_no_gateway_v4_dns(self):
        ipv4_subnet_dns = factory.make_ip_address(ipv6=False)
        rack_v4, rack_v6, node = self.make_Node_with_RackController(
            ipv4=True,
            ipv4_gateway=False,
            ipv6=False,
            ipv6_gateway=False,
            ipv4_subnet_dns=[ipv4_subnet_dns],
        )
        self.assertEqual([rack_v4], node.get_default_dns_servers())

    def test_uses_rack_ipv6_if_ipv6_only_with_no_gateway_v6_dns(self):
        ipv6_subnet_dns = factory.make_ip_address(ipv6=True)
        rack_v4, rack_v6, node = self.make_Node_with_RackController(
            ipv4=False,
            ipv4_gateway=False,
            ipv6=True,
            ipv6_gateway=False,
            ipv6_subnet_dns=[ipv6_subnet_dns],
        )
        self.assertEqual([rack_v6], node.get_default_dns_servers())

    def test_uses_rack_ipv6_if_dual_stack_with_no_gateway_and_told(self):
        rack_v4, rack_v6, node = self.make_Node_with_RackController(
            ipv4=True, ipv4_gateway=False, ipv6=True, ipv6_gateway=False
        )
        self.assertEqual([rack_v6], node.get_default_dns_servers(ipv4=False))

    def test_uses_rack_ipv6_if_dual_stack_with_dual_gateway_and_told(self):
        rack_v4, rack_v6, node = self.make_Node_with_RackController(
            ipv4=True, ipv4_gateway=True, ipv6=True, ipv6_gateway=True
        )
        self.assertEqual([rack_v6], node.get_default_dns_servers(ipv4=False))

    def test_uses_rack_ipv4_if_dual_stack_with_no_gateway(self):
        rack_v4, rack_v6, node = self.make_Node_with_RackController(
            ipv4=True, ipv4_gateway=False, ipv6=True, ipv6_gateway=False
        )
        self.assertEqual([rack_v4], node.get_default_dns_servers())

    def test_uses_rack_ipv4_if_dual_stack_with_ipv4_gateway(self):
        rack_v4, rack_v6, node = self.make_Node_with_RackController(
            ipv4=True, ipv4_gateway=True, ipv6=True, ipv6_gateway=False
        )
        self.assertEqual([rack_v4], node.get_default_dns_servers())

    def test_uses_subnet_ipv4_if_dual_stack_with_ipv4_gateway_with_dns(self):
        ipv4_subnet_dns = factory.make_ip_address(ipv6=False)
        ipv6_subnet_dns = factory.make_ip_address(ipv6=True)
        rack_v4, rack_v6, node = self.make_Node_with_RackController(
            ipv4=True,
            ipv4_gateway=True,
            ipv6=True,
            ipv6_gateway=False,
            ipv4_subnet_dns=[ipv4_subnet_dns],
            ipv6_subnet_dns=[ipv6_subnet_dns],
        )
        self.assertEqual(
            [rack_v4, ipv4_subnet_dns], node.get_default_dns_servers()
        )

    def test_uses_rack_ipv6_if_dual_stack_with_ipv6_gateway(self):
        rack_v4, rack_v6, node = self.make_Node_with_RackController(
            ipv4=True, ipv4_gateway=False, ipv6=True, ipv6_gateway=True
        )
        self.assertEqual([rack_v6], node.get_default_dns_servers())

    def test_uses_subnet_ipv6_if_dual_stack_with_ipv6_gateway(self):
        ipv4_subnet_dns = factory.make_ip_address(ipv6=False)
        ipv6_subnet_dns = factory.make_ip_address(ipv6=True)
        rack_v4, rack_v6, node = self.make_Node_with_RackController(
            ipv4=True,
            ipv4_gateway=False,
            ipv6=True,
            ipv6_gateway=True,
            ipv4_subnet_dns=[ipv4_subnet_dns],
            ipv6_subnet_dns=[ipv6_subnet_dns],
        )
        self.assertEqual(
            [rack_v6, ipv6_subnet_dns], node.get_default_dns_servers()
        )

    def test_uses_rack_ipv4_if_ipv4_with_ipv4_gateway(self):
        rack_v4, rack_v6, node = self.make_Node_with_RackController(
            ipv4=True, ipv4_gateway=True, ipv6=False, ipv6_gateway=False
        )
        self.assertEqual([rack_v4], node.get_default_dns_servers())

    def test_uses_subnet_ipv4_if_ipv4_stack_with_ipv4_gateway_and_dns(self):
        ipv4_subnet_dns = factory.make_ip_address(ipv6=False)
        ipv6_subnet_dns = factory.make_ip_address(ipv6=True)
        rack_v4, rack_v6, node = self.make_Node_with_RackController(
            ipv4=True,
            ipv4_gateway=True,
            ipv6=False,
            ipv6_gateway=False,
            ipv4_subnet_dns=[ipv4_subnet_dns],
            ipv6_subnet_dns=[ipv6_subnet_dns],
        )
        self.assertEqual(
            [rack_v4, ipv4_subnet_dns], node.get_default_dns_servers()
        )

    def test_uses_rack_ipv6_if_ipv6_with_ipv6_gateway(self):
        rack_v4, rack_v6, node = self.make_Node_with_RackController(
            ipv4=False, ipv4_gateway=False, ipv6=True, ipv6_gateway=True
        )
        self.assertEqual([rack_v6], node.get_default_dns_servers())

    def test_uses_subnet_ipv6_if_ipv6_with_ipv6_gateway_and_dns(self):
        ipv4_subnet_dns = factory.make_ip_address(ipv6=False)
        ipv6_subnet_dns = factory.make_ip_address(ipv6=True)
        rack_v4, rack_v6, node = self.make_Node_with_RackController(
            ipv4=False,
            ipv4_gateway=False,
            ipv6=True,
            ipv6_gateway=True,
            ipv4_subnet_dns=[ipv4_subnet_dns],
            ipv6_subnet_dns=[ipv6_subnet_dns],
        )
        self.assertEqual(
            [rack_v6, ipv6_subnet_dns], node.get_default_dns_servers()
        )

    def test_uses_other_routeable_rack_controllers_ipv4(self):
        rack_v4, rack_v6, node = self.make_Node_with_RackController(
            ipv4=True, ipv4_gateway=False, ipv6=False, ipv6_gateway=False
        )
        rack_ips = [rack_v4]
        for _ in range(3):
            rack_ip, _ = self.make_RackController_routable_to_node(node)
            rack_ips.append(rack_ip)
        self.assertCountEqual(node.get_default_dns_servers(), rack_ips)

    def test_uses_other_routeable_rack_controllers_ipv6(self):
        rack_v4, rack_v6, node = self.make_Node_with_RackController(
            ipv4=False, ipv4_gateway=False, ipv6=True, ipv6_gateway=False
        )
        rack_ips = [rack_v6]
        for _ in range(3):
            rack_ip, _ = self.make_RackController_routable_to_node(node)
            rack_ips.append(rack_ip)
        self.assertCountEqual(node.get_default_dns_servers(), rack_ips)

    def test_uses_subnet_ipv4_gateway_with_other_routeable_racks(self):
        rack_v4, rack_v6, node = self.make_Node_with_RackController(
            ipv4=True, ipv4_gateway=True, ipv6=False, ipv6_gateway=False
        )
        rack_ips = [rack_v4]
        for _ in range(3):
            rack_ip, _ = self.make_RackController_routable_to_node(node)
            rack_ips.append(rack_ip)
        self.assertCountEqual(node.get_default_dns_servers(), rack_ips)

    def test_uses_subnet_ipv6_gateway_with_other_routeable_racks(self):
        rack_v4, rack_v6, node = self.make_Node_with_RackController(
            ipv4=False, ipv4_gateway=False, ipv6=True, ipv6_gateway=True
        )
        rack_ips = [rack_v6]
        for _ in range(3):
            rack_ip, _ = self.make_RackController_routable_to_node(node)
            rack_ips.append(rack_ip)
        self.assertCountEqual(node.get_default_dns_servers(), rack_ips)

    def test_ignores_dns_servers_on_unallowed_subnets(self):
        # Regression test for LP:1847537
        rack_v4, rack_v6, node = self.make_Node_with_RackController()
        Subnet.objects.update(allow_dns=False)
        self.assertEqual([], node.get_default_dns_servers())

    def test_uses_subnet_ipv4_dns_only(self):
        # Regression test for LP:1847537
        ipv4_subnet_dns = factory.make_ip_address(ipv6=False)
        rack_v4, rack_v6, node = self.make_Node_with_RackController(
            ipv6=False, ipv4_subnet_dns=[ipv4_subnet_dns]
        )
        Subnet.objects.update(allow_dns=False)
        self.assertEqual(node.get_default_dns_servers(), [ipv4_subnet_dns])

    def test_uses_subnet_ipv6_dns_only(self):
        # Regression test for LP:1847537
        ipv6_subnet_dns = factory.make_ipv6_address()
        rack_v4, rack_v6, node = self.make_Node_with_RackController(
            ipv4=False, ipv6_subnet_dns=[ipv6_subnet_dns]
        )
        Subnet.objects.update(allow_dns=False)
        self.assertEqual(node.get_default_dns_servers(), [ipv6_subnet_dns])

    def test_ignores_other_unroutable_rack_controllers_ipv4(self):
        # Regression test for LP:1896684
        rack_v4, rack_v6, node = self.make_Node_with_RackController(
            ipv4=True, ipv4_gateway=False, ipv6=False, ipv6_gateway=False
        )
        rack = node.boot_interface.vlan.primary_rack
        mock_address_map = self.patch(node_module, "get_routable_address_map")
        mock_address_map.return_value = {rack: [IPAddress(rack_v4)]}
        self.assertEqual(node.get_default_dns_servers(), [rack_v4])


class TestNode_Start(MAASTransactionServerTestCase):
    used_nets: Set[IPNetwork] = set()

    def setUp(self):
        super().setUp()
        self.patch_autospec(node_module, "power_driver_check")

    def make_acquired_node_with_interface(
        self,
        user,
        bmc_connected_to=None,
        power_type="virsh",
        power_state=POWER_STATE.OFF,
        network=None,
        with_boot_disk=True,
        install_kvm=False,
        register_vmhost=False,
        ephemeral_deploy=False,
        architecture=None,
    ):
        if network is None:
            # can't use a link-local network as MAAS server IPs for those are
            # not reported
            network = factory.make_ip4_or_6_network(but_not=self.used_nets)
            self.used_nets.add(network)
            while network.is_link_local():
                network = factory.make_ip4_or_6_network(but_not=self.used_nets)

        cidr = str(network.cidr)
        # Make sure that the maas_server address is of the same addr family.
        gethost = self.patch(server_address, "get_maas_facing_server_host")
        gethost.return_value = str(IPAddress(network.first + 1))
        # Validation during start requires an OS to be set
        ubuntu = factory.make_default_ubuntu_release_bootable()
        osystem, distro_series = ubuntu.name.split("/")
        self.patch(
            boot_images, "get_common_available_boot_images"
        ).return_value = [
            {
                "osystem": osystem,
                "release": distro_series,
                "purpose": "xinstall",
            }
        ]
        node = factory.make_Node_with_Interface_on_Subnet(
            status=NODE_STATUS.READY,
            with_boot_disk=with_boot_disk,
            bmc_connected_to=bmc_connected_to,
            power_type=power_type,
            power_state=power_state,
            cidr=cidr,
            osystem=osystem,
            distro_series=distro_series,
            install_kvm=install_kvm,
            register_vmhost=register_vmhost,
            ephemeral_deploy=ephemeral_deploy,
            architecture=architecture,
        )
        node.acquire(user)
        return node

    def patch_post_commit(self):
        d = defer.succeed(None)
        self.patch(node_module, "post_commit").return_value = d
        return d

    def test_raises_PermissionDenied_if_user_doesnt_have_edit(self):
        user = factory.make_User()
        node = self.make_acquired_node_with_interface(user)
        self.assertRaises(PermissionDenied, node.start, factory.make_User())

    def test_raises_ValidationError_if_no_common_family(self):
        admin = factory.make_admin()
        node = self.make_acquired_node_with_interface(
            admin, power_type="manual"
        )
        gethost = self.patch(server_address, "get_maas_facing_server_host")
        subnet = node.get_boot_interface().ip_addresses.first().subnet
        # Force an address family mismatch.  See Bug#1630361.
        if IPNetwork(subnet.cidr).version == 6:
            gethost.return_value = "192.168.1.1"
        else:
            gethost.return_value = "2001:db8::3"
        with ExpectedException(ValidationError):
            node.start(admin)

    def test_raises_ValidationError_if_ephemeral_deploy_and_install_kvm(self):
        admin = factory.make_admin()
        node = self.make_acquired_node_with_interface(
            admin,
            power_type="manual",
            with_boot_disk=False,
            ephemeral_deploy=True,
            install_kvm=True,
        )
        with ExpectedException(ValidationError):
            node.start(admin)

    def test_raises_ValidationError_if_ephemeral_deploy_and_register_vmhost(
        self,
    ):
        admin = factory.make_admin()
        node = self.make_acquired_node_with_interface(
            admin,
            power_type="manual",
            with_boot_disk=False,
            ephemeral_deploy=True,
            register_vmhost=True,
        )
        with ExpectedException(ValidationError):
            node.start(admin)

    def test_raises_ValidationError_if_ephemeral_deployment_not_supported(
        self,
    ):
        admin = factory.make_admin()
        with transaction.atomic():
            factory.make_custom_boot_resource(
                name="rhel/9.1",
                filetype=BOOT_RESOURCE_FILE_TYPE.ROOT_DD,
                architecture="amd64/generic",
            )
        node = self.make_acquired_node_with_interface(
            admin,
            power_type="manual",
            with_boot_disk=False,
            ephemeral_deploy=True,
            architecture="amd64/generic",
        )
        node.osystem = "rhel"
        node.distro_series = "9.1"
        self.patch(
            boot_images, "get_common_available_boot_images"
        ).return_value = [
            {
                "osystem": "ubuntu",
                "release": "focal",
                "purpose": "xinstall",
            },
            {
                "osystem": "rhel",
                "release": "9.1",
                "purpose": "xinstall",
            },
        ]
        with ExpectedException(ValidationError):
            node.start(admin)

    def test_no_ValidationError_if_ephemeral_deployment_supported(self):
        admin = factory.make_admin()
        with transaction.atomic():
            factory.make_usable_boot_resource(
                name="ubuntu/focal",
                architecture="amd64/generic",
            )
            factory.make_custom_boot_resource(
                name="rhel/9.1",
                filetype=BOOT_RESOURCE_FILE_TYPE.ROOT_TGZ,
                architecture="amd64/generic",
            )
        node = self.make_acquired_node_with_interface(
            admin,
            power_type="manual",
            with_boot_disk=False,
            ephemeral_deploy=True,
            architecture="amd64/generic",
        )
        node.osystem = "rhel"
        node.distro_series = "9.1"
        self.patch(
            boot_images, "get_common_available_boot_images"
        ).return_value = [
            {
                "osystem": "ubuntu",
                "release": "focal",
                "purpose": "xinstall",
            },
            {
                "osystem": "rhel",
                "release": "9.1",
                "purpose": "xinstall",
            },
        ]
        node.start(admin)
        self.assertEqual(NODE_STATUS.DEPLOYING, node.status)

    def test_no_ValidationError_if_ephemeral_deployment_ubuntu(self):
        admin = factory.make_admin()
        with transaction.atomic():
            factory.make_RegionController()
            # For Ubuntu, we don't store images for 'generic', but for
            # each specific kernel.
            factory.make_usable_boot_resource(
                name="ubuntu/focal",
                architecture="amd64/ga-20.04",
                rtype=BOOT_RESOURCE_TYPE.SYNCED,
            )
        node = self.make_acquired_node_with_interface(
            admin,
            power_type="manual",
            with_boot_disk=False,
            ephemeral_deploy=True,
            architecture="amd64/generic",
        )
        node.osystem = "ubuntu"
        node.distro_series = "focal"
        self.patch(
            boot_images, "get_common_available_boot_images"
        ).return_value = [
            {
                "osystem": "ubuntu",
                "release": "focal",
                "purpose": "xinstall",
            },
        ]
        node.start(admin)
        self.assertEqual(NODE_STATUS.DEPLOYING, node.status)

    def test_doesnt_raise_network_validation_when_all_dhcp(self):
        admin = factory.make_admin()
        node = self.make_acquired_node_with_interface(
            admin, power_type="manual"
        )
        gethost = self.patch(server_address, "get_maas_facing_server_host")
        ip_address = node.get_boot_interface().ip_addresses.first()
        orig_subnet = ip_address.subnet
        ip_address.alloc_type = IPADDRESS_TYPE.DHCP
        ip_address.subnet = None
        ip_address.save()
        # Force an address family mismatch.  See Bug#1630361.
        if IPNetwork(orig_subnet.cidr).version == 6:
            gethost.return_value = "192.168.1.1"
        else:
            gethost.return_value = "2001:db8::3"
        register_event = self.patch(node, "_register_request_event")
        node.start(admin)
        self.assertThat(
            register_event,
            MockCalledOnceWith(
                admin,
                EVENT_TYPES.REQUEST_NODE_START_DEPLOYMENT,
                action="start",
                comment=None,
            ),
        )

    def test_treats_ipv4_mapped_address_as_ipv4(self):
        admin = factory.make_admin()
        network = factory.make_ipv4_network()
        node = self.make_acquired_node_with_interface(
            admin, power_type="manual", network=network
        )
        gethost = self.patch(server_address, "get_maas_facing_server_host")
        subnet = node.get_boot_interface().ip_addresses.first().subnet
        # Force an address family mismatch.  See Bug#1630361.
        gethost.return_value = str(
            IPAddress(IPNetwork(subnet.cidr).first + 1).ipv6()
        )
        register_event = self.patch(node, "_register_request_event")
        node.start(admin)
        self.assertThat(
            register_event,
            MockCalledOnceWith(
                admin,
                EVENT_TYPES.REQUEST_NODE_START_DEPLOYMENT,
                action="start",
                comment=None,
            ),
        )

    def test_rejects_ipv6_only_host_when_url_is_ipv4_mapped(self):
        admin = factory.make_admin()
        network = factory.make_ipv6_network()
        node = self.make_acquired_node_with_interface(
            admin, power_type="manual", network=network
        )
        gethost = self.patch(server_address, "get_maas_facing_server_host")
        # Force an address family mismatch.  See Bug#1630361.
        gethost.return_value = "::ffff:192.168.1.1"
        with ExpectedException(ValidationError):
            node.start(admin)

    def test_checks_all_interfaces_for_common_family(self):
        admin = factory.make_admin()
        node = self.make_acquired_node_with_interface(
            admin, power_type="manual"
        )
        gethost = self.patch(server_address, "get_maas_facing_server_host")
        subnet = node.get_boot_interface().ip_addresses.first().subnet
        # Force an address family mismatch.  See Bug#1630361.
        if IPNetwork(subnet.cidr).version == 6:
            gethost.return_value = "192.168.1.1"
            subnet2 = factory.make_Subnet(cidr="192.168.0.0/24")
        else:
            gethost.return_value = "2001:db8::3"
            subnet2 = factory.make_Subnet(cidr="2001:db8:1::/64")
        factory.make_StaticIPAddress(
            interface=factory.make_Interface(node=node), subnet=subnet2
        )
        # At this point, we have the boot interface and rack in different
        # address families, and a second interface on the node that is in the
        # same address family (but different subnet) than the rack controller.
        # Node.start should let this start.
        register_event = self.patch(node, "_register_request_event")
        node.start(admin)
        self.assertThat(
            register_event,
            MockCalledOnceWith(
                admin,
                EVENT_TYPES.REQUEST_NODE_START_DEPLOYMENT,
                action="start",
                comment=None,
            ),
        )

    def test_start_ignores_address_compatibility_when_no_rack(self):
        admin = factory.make_admin()
        node = self.make_acquired_node_with_interface(
            admin, power_type="manual"
        )
        get_rack = self.patch(node, "get_boot_primary_rack_controller")
        get_rack.return_value = None
        gethost = self.patch(server_address, "get_maas_facing_server_host")
        subnet = node.get_boot_interface().ip_addresses.first().subnet
        # Force an address family mismatch.  See Bug#1630361.
        if IPNetwork(subnet.cidr).version == 6:
            gethost.return_value = "192.168.1.1"
        else:
            gethost.return_value = "2001:db8::3"
        register_event = self.patch(node, "_register_request_event")
        node.start(admin)
        self.assertThat(
            register_event,
            MockCalledOnceWith(
                admin,
                EVENT_TYPES.REQUEST_NODE_START_DEPLOYMENT,
                action="start",
                comment=None,
            ),
        )

    def test_start_logs_user_request(self):
        admin = factory.make_admin()
        node = self.make_acquired_node_with_interface(
            admin, power_type="manual"
        )
        register_event = self.patch(node, "_register_request_event")
        node.start(admin)
        self.assertThat(
            register_event,
            MockCalledOnceWith(
                admin,
                EVENT_TYPES.REQUEST_NODE_START_DEPLOYMENT,
                action="start",
                comment=None,
            ),
        )

    def test_sets_user_data(self):
        user = factory.make_User()
        node = self.make_acquired_node_with_interface(
            user, power_type="manual"
        )
        user_data = factory.make_bytes()
        node.start(user, user_data=user_data)
        nud = NodeUserData.objects.get(node=node)
        self.assertEqual(user_data, nud.data)

    def test_resets_user_data(self):
        user = factory.make_User()
        node = self.make_acquired_node_with_interface(
            user, power_type="manual"
        )
        user_data = factory.make_bytes()
        NodeUserData.objects.set_user_data(node, user_data)
        node.start(user, user_data=None)
        self.assertFalse(NodeUserData.objects.filter(node=node).exists())

    def test_sets_to_deploying(self):
        user = factory.make_User()
        node = self.make_acquired_node_with_interface(
            user, power_type="manual"
        )
        node.start(user)
        self.assertEqual(NODE_STATUS.DEPLOYING, node.status)

    def test_creates_acquired_bridges_for_install_kvm(self):
        user = factory.make_User()
        node = self.make_acquired_node_with_interface(
            user, power_type="manual"
        )
        bridge_type = factory.pick_choice(BRIDGE_TYPE_CHOICES)
        bridge_stp = factory.pick_bool()
        bridge_fd = random.randint(0, 500)
        node.start(
            user,
            install_kvm=True,
            bridge_type=bridge_type,
            bridge_stp=bridge_stp,
            bridge_fd=bridge_fd,
        )
        node = reload_object(node)
        bridge = BridgeInterface.objects.get(node_config=node.current_config)
        interface = node.current_config.interface_set.first()
        self.assertEqual(NODE_STATUS.DEPLOYING, node.status)
        self.assertEqual(bridge.mac_address, interface.mac_address)
        self.assertEqual(bridge.params["bridge_type"], bridge_type)
        self.assertEqual(bridge.params["bridge_stp"], bridge_stp)
        self.assertEqual(bridge.params["bridge_fd"], bridge_fd)
        self.assertTrue(node.install_kvm)

    def test_creates_acquired_bridges_for_register_vmhost(self):
        user = factory.make_User()
        node = self.make_acquired_node_with_interface(
            user, power_type="manual"
        )
        bridge_type = factory.pick_choice(BRIDGE_TYPE_CHOICES)
        bridge_stp = factory.pick_bool()
        bridge_fd = random.randint(0, 500)
        node.start(
            user,
            register_vmhost=True,
            bridge_type=bridge_type,
            bridge_stp=bridge_stp,
            bridge_fd=bridge_fd,
        )
        node = reload_object(node)
        bridge = BridgeInterface.objects.get(node_config=node.current_config)
        interface = node.current_config.interface_set.first()
        self.assertEqual(NODE_STATUS.DEPLOYING, node.status)
        self.assertEqual(bridge.mac_address, interface.mac_address)
        self.assertEqual(bridge.params["bridge_type"], bridge_type)
        self.assertEqual(bridge.params["bridge_stp"], bridge_stp)
        self.assertEqual(bridge.params["bridge_fd"], bridge_fd)
        self.assertTrue(node.register_vmhost)

    def test_doesnt_change_broken(self):
        user = factory.make_User()
        node = self.make_acquired_node_with_interface(
            user, power_type="manual"
        )
        node.update_status(NODE_STATUS.BROKEN)
        node.save()
        node.start(user)
        self.assertEqual(NODE_STATUS.BROKEN, node.status)

    def test_claims_auto_ip_addresses(self):
        user = factory.make_User()
        node = self.make_acquired_node_with_interface(
            user, power_type="manual"
        )
        claim_auto_ips = self.patch_autospec(node, "_claim_auto_ips")
        node.start(user)

        self.expectThat(claim_auto_ips, MockCalledOnce())

    def test_only_claims_auto_addresses_when_allocated(self):
        user = factory.make_User()
        node = self.make_acquired_node_with_interface(
            user, power_type="manual"
        )
        node.update_status(NODE_STATUS.BROKEN)
        node.save()

        claim_auto_ips = self.patch_autospec(
            node, "claim_auto_ips", spec_set=False
        )
        with post_commit_hooks:
            node.start(user)

        # No calls are made to claim_auto_ips, since the node
        # isn't ALLOCATED.
        self.assertThat(claim_auto_ips, MockNotCalled())

    def test_claims_auto_ip_addresses_assigns_without_no_racks(self):
        user = factory.make_User()
        node = self.make_acquired_node_with_interface(
            user, power_type="manual"
        )

        # No rack controllers are currently connected to the test region
        # so no IP address checking will be performed.
        with post_commit_hooks:
            node.start(user)

        interface = node.get_boot_interface()
        [ip] = interface.ip_addresses.filter(alloc_type=IPADDRESS_TYPE.AUTO)
        self.assertIsNotNone(ip.ip)
        self.assertIsNone(ip.temp_expires_on)

    def test_claims_auto_ip_addresses_skips_used_ip_from_rack(self):
        user = factory.make_User()
        node = self.make_acquired_node_with_interface(
            user, power_type="manual"
        )
        node_interface = node.get_boot_interface()
        [auto_ip] = node_interface.ip_addresses.filter(
            alloc_type=IPADDRESS_TYPE.AUTO
        )

        # Create a rack controller that has an interface on the same subnet
        # as the node.
        rack = factory.make_RackController()
        rack.current_config.interface_set.all().delete()
        rackif = factory.make_Interface(vlan=node_interface.vlan, node=rack)
        rackif.neighbour_discovery_state = True
        rackif.save()
        rackif_ip = factory.pick_ip_in_Subnet(auto_ip.subnet)
        rackif.link_subnet(
            INTERFACE_LINK_TYPE.STATIC, auto_ip.subnet, rackif_ip
        )

        # Mock the rack controller connected to the region controller.
        client = Mock()
        client.ident = rack.system_id
        self.patch(node_module, "getAllClients").return_value = [client]

        # Must be executed in a transaction as `allocate_new` uses savepoints.
        with transaction.atomic():
            # Allocate 2 AUTO IP addresses and set the first as temp expired
            # and free the second IP address.
            first_ip = StaticIPAddress.objects.allocate_new(
                subnet=auto_ip.subnet, alloc_type=IPADDRESS_TYPE.AUTO
            )
            first_ip.temp_expires_on = datetime.utcnow() - timedelta(minutes=5)
            first_ip.save()
            second_ip = StaticIPAddress.objects.allocate_new(
                subnet=auto_ip.subnet,
                alloc_type=IPADDRESS_TYPE.AUTO,
                exclude_addresses=[first_ip.ip],
            )
            second_ip.delete()

            # This is the next IP address that will actaully get picked for the
            # machine as it will be free from the database and will no be
            # reported as used from the rack controller.
            third_ip = StaticIPAddress.objects.allocate_new(
                subnet=auto_ip.subnet,
                alloc_type=IPADDRESS_TYPE.AUTO,
                exclude_addresses=[first_ip.ip, second_ip.ip],
            )
            third_ip.delete()

        # 2 tries will be made on the rack controller, both IP will be
        # used.
        client.side_effect = [
            defer.succeed(
                {
                    "ip_addresses": [
                        {
                            "ip_address": first_ip.ip,
                            "used": True,
                            "mac_address": factory.make_mac_address(),
                        }
                    ]
                }
            ),
            defer.succeed(
                {
                    "ip_addresses": [
                        {
                            "ip_address": second_ip.ip,
                            "used": True,
                            "mac_address": factory.make_mac_address(),
                        }
                    ]
                }
            ),
            defer.succeed(
                {"ip_addresses": [{"ip_address": third_ip.ip, "used": False}]}
            ),
        ]

        with post_commit_hooks:
            node.start(user)

        auto_ip = reload_object(auto_ip)
        self.assertEqual(third_ip.ip, auto_ip.ip)
        self.assertIsNone(auto_ip.temp_expires_on)

    def test_claims_auto_ip_addresses_skips_used_ip_discovery_disabled(self):
        user = factory.make_User()
        node = self.make_acquired_node_with_interface(
            user, power_type="manual"
        )
        node_interface = node.get_boot_interface()
        [auto_ip] = node_interface.ip_addresses.filter(
            alloc_type=IPADDRESS_TYPE.AUTO
        )

        # Create a rack controller that has an interface on the same subnet
        # as the node. Don't enable neighbour discovery
        rack = factory.make_RackController()
        rack.current_config.interface_set.all().delete()
        rackif = factory.make_Interface(vlan=node_interface.vlan, node=rack)
        rackif_ip = factory.pick_ip_in_Subnet(auto_ip.subnet)
        rackif.link_subnet(
            INTERFACE_LINK_TYPE.STATIC, auto_ip.subnet, rackif_ip
        )

        # Mock the rack controller connected to the region controller.
        client = Mock()
        client.ident = rack.system_id
        self.patch(node_module, "getAllClients").return_value = [client]

        # Must be executed in a transaction as `allocate_new` uses savepoints.
        with transaction.atomic():
            # Get two IPs and remove them so they're unknown
            ip = StaticIPAddress.objects.allocate_new(
                subnet=auto_ip.subnet, alloc_type=IPADDRESS_TYPE.AUTO
            )
            ip1 = ip.ip
            ip.delete()
            ip = StaticIPAddress.objects.allocate_new(
                subnet=auto_ip.subnet,
                alloc_type=IPADDRESS_TYPE.AUTO,
                exclude_addresses=[ip1],
            )
            ip2 = ip.ip
            ip.delete()

        client.side_effect = [
            defer.succeed(
                {
                    "ip_addresses": [
                        {
                            "ip_address": ip1,
                            "used": True,
                            "mac_address": factory.make_mac_address(),
                        }
                    ]
                }
            ),
            defer.succeed(
                {"ip_addresses": [{"ip_address": ip2, "used": False}]}
            ),
        ]

        with post_commit_hooks:
            node.start(user)

        auto_ip = reload_object(auto_ip)
        self.assertEqual(ip2, auto_ip.ip)
        self.assertIsNone(auto_ip.temp_expires_on)
        # lp:2024242: claims auto ip should not add any neighbour if the ip
        # is already used.
        self.assertEqual(0, Neighbour.objects.count())

    def test_claims_auto_ip_addresses_retries_on_failure_from_rack(self):
        user = factory.make_User()
        node = self.make_acquired_node_with_interface(
            user, power_type="manual"
        )
        node_interface = node.get_boot_interface()
        [auto_ip] = node_interface.ip_addresses.filter(
            alloc_type=IPADDRESS_TYPE.AUTO
        )

        # Create a rack controller that has an interface on the same subnet
        # as the node.
        rack = factory.make_RackController()
        rack.current_config.interface_set.all().delete()
        rackif = factory.make_Interface(vlan=node_interface.vlan, node=rack)
        rackif.neighbour_discovery_state = True
        rackif.save()
        rackif_ip = factory.pick_ip_in_Subnet(auto_ip.subnet)
        rackif.link_subnet(
            INTERFACE_LINK_TYPE.STATIC, auto_ip.subnet, rackif_ip
        )

        # Mock the rack controller connected to the region controller.
        client = Mock()
        client.ident = rack.system_id
        self.patch(node_module, "getAllClients").return_value = [client]

        # Must be executed in a transaction as `allocate_new` uses savepoints.
        with transaction.atomic():
            first_ip = StaticIPAddress.objects.allocate_new(
                subnet=auto_ip.subnet, alloc_type=IPADDRESS_TYPE.AUTO
            )
            first_ip.temp_expires_on = datetime.utcnow() - timedelta(minutes=5)
            first_ip.save()
        last_ip = str(first_ip.get_ipaddress())

        client.side_effect = [
            defer.fail(Exception()),
            defer.fail(Exception()),
            defer.succeed(
                {"ip_addresses": [{"ip_address": last_ip, "used": False}]}
            ),
        ]

        with post_commit_hooks:
            node.start(user)

        auto_ip = reload_object(auto_ip)
        self.assertEqual(last_ip, auto_ip.ip)
        self.assertIsNone(auto_ip.temp_expires_on)

    def test_claims_auto_ip_addresses_fails_on_three_failures(self):
        user = factory.make_User()
        node = self.make_acquired_node_with_interface(
            user, power_type="manual"
        )
        node_interface = node.get_boot_interface()
        [auto_ip] = node_interface.ip_addresses.filter(
            alloc_type=IPADDRESS_TYPE.AUTO
        )

        # Create a rack controller that has an interface on the same subnet
        # as the node.
        rack = factory.make_RackController()
        rack.current_config.interface_set.all().delete()
        rackif = factory.make_Interface(vlan=node_interface.vlan, node=rack)
        rackif.neighbour_discovery_state = True
        rackif.save()
        rackif_ip = factory.pick_ip_in_Subnet(auto_ip.subnet)
        rackif.link_subnet(
            INTERFACE_LINK_TYPE.STATIC, auto_ip.subnet, rackif_ip
        )

        # Mock the rack controller connected to the region controller.
        client = Mock()
        client.ident = rack.system_id
        self.patch(node_module, "getAllClients").return_value = [client]

        # Must be executed in a transaction as `allocate_new` uses savepoints.
        with transaction.atomic():
            first_ip = StaticIPAddress.objects.allocate_new(
                subnet=auto_ip.subnet, alloc_type=IPADDRESS_TYPE.AUTO
            )
            first_ip.temp_expires_on = datetime.utcnow() - timedelta(minutes=5)
            first_ip.save()

        client.side_effect = [
            defer.fail(Exception()),
            defer.fail(Exception()),
            defer.fail(Exception()),
        ]

        with ExpectedException(IPAddressCheckFailed):
            with post_commit_hooks:
                node.start(user)

        auto_ip = reload_object(auto_ip)
        last_ip = str(first_ip.get_ipaddress())
        self.assertEqual(last_ip, auto_ip.ip)
        self.assertIsNone(auto_ip.temp_expires_on)

    def test_claims_auto_ip_addresses_eventually_succeds_with_many_used(self):
        user = factory.make_User()
        node = self.make_acquired_node_with_interface(
            user, power_type="manual"
        )
        node_interface = node.get_boot_interface()
        auto_ip = node_interface.ip_addresses.get(
            alloc_type=IPADDRESS_TYPE.AUTO
        )

        # Create a rack controller that has an interface on the same subnet
        # as the node.
        rack = factory.make_RackController()
        rack.current_config.interface_set.all().delete()
        rackif = factory.make_Interface(vlan=node_interface.vlan, node=rack)
        rackif.neighbour_discovery_state = True
        rackif.save()
        rackif_ip = factory.pick_ip_in_Subnet(auto_ip.subnet)
        rackif.link_subnet(
            INTERFACE_LINK_TYPE.STATIC, auto_ip.subnet, rackif_ip
        )

        # Mock the rack controller connected to the region controller.
        client = Mock()
        client.ident = rack.system_id
        self.patch(node_module, "getAllClients").return_value = [client]

        # Must be executed in a transaction as `allocate_new` uses savepoints.
        with transaction.atomic():
            # Allocate 2 AUTO IP addresses and set the first as temp expired
            # and free the second IP address.
            first_ip = StaticIPAddress.objects.allocate_new(
                subnet=auto_ip.subnet, alloc_type=IPADDRESS_TYPE.AUTO
            )
            first_ip.temp_expires_on = datetime.utcnow() - timedelta(minutes=5)
            first_ip.save()
            second_ip = StaticIPAddress.objects.allocate_new(
                subnet=auto_ip.subnet,
                alloc_type=IPADDRESS_TYPE.AUTO,
                exclude_addresses=[first_ip.ip],
            )
            second_ip.delete()
            third_ip = StaticIPAddress.objects.allocate_new(
                subnet=auto_ip.subnet,
                alloc_type=IPADDRESS_TYPE.AUTO,
                exclude_addresses=[first_ip.ip, second_ip.ip],
            )
            third_ip.delete()
            # This is the next IP address that will actually get picked for the
            # machine as it will be free from the database and will not be
            # reported as used from the rack controller.
            fourth_ip = StaticIPAddress.objects.allocate_new(
                subnet=auto_ip.subnet,
                alloc_type=IPADDRESS_TYPE.AUTO,
                exclude_addresses=[first_ip.ip, second_ip.ip, third_ip.ip],
            )
            fourth_ip.delete()

        # 2 tries will be made on the rack controller, both IP will be
        # used.
        client.side_effect = [
            defer.succeed(
                {"ip_addresses": [{"ip_address": first_ip.ip, "used": True}]}
            ),
            defer.succeed(
                {"ip_addresses": [{"ip_address": second_ip.ip, "used": True}]}
            ),
            defer.succeed(
                {"ip_addresses": [{"ip_address": third_ip.ip, "used": True}]}
            ),
            defer.succeed(
                {"ip_addresses": [{"ip_address": fourth_ip.ip, "used": False}]}
            ),
        ]

        with post_commit_hooks:
            node.start(user)

        auto_ip = reload_object(auto_ip)
        self.assertEqual(auto_ip.ip, fourth_ip.ip)
        self.assertIsNone(auto_ip.temp_expires_on)

    def test_claims_auto_ip_doesnt_retry_in_use(self):
        user = factory.make_User()
        node = self.make_acquired_node_with_interface(
            user, power_type="manual"
        )
        node_interface = node.get_boot_interface()
        [auto_ip] = node_interface.ip_addresses.filter(
            alloc_type=IPADDRESS_TYPE.AUTO
        )

        # Create a rack controller that has an interface on the same subnet
        # as the node.
        rack = factory.make_RackController()
        rack.current_config.interface_set.all().delete()
        rackif = factory.make_Interface(vlan=node_interface.vlan, node=rack)
        rackif.neighbour_discovery_state = True
        rackif.save()
        rackif_ip = factory.pick_ip_in_Subnet(auto_ip.subnet)
        rackif.link_subnet(
            INTERFACE_LINK_TYPE.STATIC, auto_ip.subnet, rackif_ip
        )

        # Mock the rack controller connected to the region controller.
        client = Mock()
        client.ident = rack.system_id
        self.patch(node_module, "getAllClients").return_value = [client]

        # Must be executed in a transaction as `allocate_new` uses savepoints.
        with transaction.atomic():
            used_ip = StaticIPAddress.objects.allocate_new(
                subnet=auto_ip.subnet, alloc_type=IPADDRESS_TYPE.AUTO
            )
            # save the address for now, so it doesn't show in free ranges
            used_ip.save()

        # reserve all available ranges
        subnet_ranges = auto_ip.subnet.get_ipranges_not_in_use()
        for rng in subnet_ranges.ranges:
            factory.make_IPRange(
                subnet=auto_ip.subnet,
                start_ip=inet_ntop(rng.first),
                end_ip=inet_ntop(rng.last),
                alloc_type=IPRANGE_TYPE.RESERVED,
            )
        # remove the used IP, MAAS thinks it's available, but return it as used
        # in checks
        used_ip.delete()
        client.return_value = defer.succeed(
            {"ip_addresses": [{"ip_address": used_ip.ip, "used": True}]}
        )

        with ExpectedException(StaticIPAddressExhaustion):
            with post_commit_hooks:
                node.start(user)

    def test_claims_auto_ip_ignores_staticly_assigned_addresses(self):
        user = factory.make_User()
        node = self.make_acquired_node_with_interface(
            user, power_type="manual"
        )

        # set a static IP on the node interface
        node_interface = node.get_boot_interface()
        [ip] = node_interface.ip_addresses.filter(
            alloc_type=IPADDRESS_TYPE.AUTO
        )

        static_ip = factory.pick_ip_in_Subnet(ip.subnet)
        ip.alloc_type = IPADDRESS_TYPE.STICKY
        ip.ip = static_ip
        ip.save()

        with post_commit_hooks:
            node.start(user)

        ip = reload_object(ip)
        self.assertEqual(ip.ip, static_ip)

    def test_sets_deploying_before_claiming_auto_ips(self):
        user = factory.make_User()
        node = self.make_acquired_node_with_interface(
            user, power_state=POWER_STATE.ON
        )

        mock_claim_auto_ips = self.patch(Node, "_claim_auto_ips")
        mock_power_control = self.patch(Node, "_power_control_node")

        node.start(user)

        # Now DEPLOYING.
        self.assertEqual(NODE_STATUS.DEPLOYING, node.status)

        # Calls _claim_auto_ips.
        self.assertThat(mock_claim_auto_ips, MockCalledOnce())

        # Calls _power_control_node when power_cycle.
        mock_power_control.assert_called_once_with(ANY, "power_cycle", ANY, [])

    def test_claims_auto_ips_when_script_needs_it(self):
        user = factory.make_User()
        node = factory.make_Node_with_Interface_on_Subnet(
            owner=user, status=random.choice(COMMISSIONING_LIKE_STATUSES)
        )
        # Validation during start requires an OS to be set
        ubuntu = factory.make_default_ubuntu_release_bootable()
        osystem, distro_series = ubuntu.name.split("/")
        self.patch(
            boot_images, "get_common_available_boot_images"
        ).return_value = [
            {
                "osystem": osystem,
                "release": distro_series,
                "purpose": "xinstall",
            }
        ]
        script_result = factory.make_ScriptResult()
        script_result.script.apply_configured_networking = True
        script_result.script.save()
        setattr(
            node,
            random.choice(
                [
                    "current_commissioning_script_set",
                    "current_testing_script_set",
                ]
            ),
            script_result.script_set,
        )
        node.save()

        self.patch(Node, "_power_control_node")
        mock_claim_auto_ips = self.patch(Node, "_claim_auto_ips")

        node._start(user)
        self.assertThat(mock_claim_auto_ips, MockCalledOnce())

    def test_doesnt_claims_auto_ips_when_script_doenst_need_it(self):
        user = factory.make_User()
        node = factory.make_Node_with_Interface_on_Subnet(
            owner=user, status=random.choice(COMMISSIONING_LIKE_STATUSES)
        )
        # Validation during start requires an OS to be set
        ubuntu = factory.make_default_ubuntu_release_bootable()
        osystem, distro_series = ubuntu.name.split("/")
        self.patch(
            boot_images, "get_common_available_boot_images"
        ).return_value = [
            {
                "osystem": osystem,
                "release": distro_series,
                "purpose": "xinstall",
            }
        ]
        script_result = factory.make_ScriptResult()
        setattr(
            node,
            random.choice(
                [
                    "current_commissioning_script_set",
                    "current_testing_script_set",
                ]
            ),
            script_result.script_set,
        )
        node.save()

        post_commit_defer = self.patch(node_module, "post_commit")
        mock_claim_auto_ips = self.patch(Node, "_claim_auto_ips")
        mock_claim_auto_ips.return_value = post_commit_defer
        mock_power_control = self.patch(Node, "_power_control_node")
        mock_power_control.return_value = post_commit_defer

        node._start(user)

        self.assertThat(mock_claim_auto_ips, MockNotCalled())

    def test_includes_boot_order_when_supported_by_power_driver(self):
        user = factory.make_User()
        on = factory.pick_bool()
        node = self.make_acquired_node_with_interface(
            user,
            power_type="hmcz",
            power_state=POWER_STATE.ON if on else POWER_STATE.OFF,
        )
        self.patch(Node, "_claim_auto_ips")
        mock_power_control = self.patch(Node, "_power_control_node")

        node.start(user)

        mock_power_control.assert_called_once_with(
            ANY,
            "power_cycle" if on else "power_on",
            node.get_effective_power_info(),
            node._get_boot_order(True),
        )

    def test_manual_power_type_doesnt_call__power_control_node(self):
        user = factory.make_User()
        node = self.make_acquired_node_with_interface(
            user, power_type="manual"
        )
        node.save()
        mock_power_control = self.patch(node, "_power_control_node")
        node.start(user)

        self.assertThat(mock_power_control, MockNotCalled())

    def test_adds_callbacks_and_errbacks_to_post_commit(self):
        user = factory.make_User()
        node = self.make_acquired_node_with_interface(user)
        old_status = node.status

        post_commit_defer = self.patch(node_module, "post_commit")
        mock_power_control = self.patch(Node, "_power_control_node")
        mock_power_control.return_value = post_commit_defer

        node.start(user)

        # Adds callback to set status expires.
        self.assertThat(
            post_commit_defer.addCallback,
            MockCalledOnceWith(
                callOutToDatabase,
                Node._set_status_expires,
                node.system_id,
                NODE_STATUS.DEPLOYING,
            ),
        )

        # Adds errback to reset status and release auto ips.
        self.assertThat(
            post_commit_defer.addErrback,
            MockCallsMatch(
                call(
                    callOutToDatabase,
                    node._start_bmc_unavailable,
                    user,
                    old_status,
                ),
                call(callOutToDatabase, node.release_interface_config),
            ),
        )

    def test_calls_power_cycle_when_cycling_allowed(self):
        user = factory.make_User()
        node = self.make_acquired_node_with_interface(
            user, power_state=POWER_STATE.ON
        )

        post_commit_defer = self.patch(node_module, "post_commit")
        mock_power_control = self.patch(Node, "_power_control_node")
        mock_power_control.return_value = post_commit_defer

        # Power cycling is allowed when starting deployment. This node is
        # allocated and the power_state is ON. Power cycle should be called
        # instead of power_on.
        node.start(user)

        # Calls _power_control_node when power_cycle.
        mock_power_control.assert_called_once_with(ANY, "power_cycle", ANY, [])

    def test_aborts_all_scripts_and_logs(self):
        user = factory.make_User()
        node = factory.make_Node(owner=user, status=NODE_STATUS.NEW)
        script_set = factory.make_ScriptSet(node=node)
        script_results = [
            factory.make_ScriptResult(
                script_set=script_set, status=SCRIPT_STATUS.PENDING
            )
            for _ in range(10)
        ]
        node._start_bmc_unavailable(user, NODE_STATUS.NEW)

        event_type = EventType.objects.get(
            name=EVENT_TYPES.NODE_POWER_QUERY_FAILED
        )
        event = node.event_set.get(type=event_type)
        self.assertEqual(
            "(%s) - Aborting NEW and reverting to NEW. Unable to power "
            "control the node. Please check power credentials." % user,
            event.description,
        )

        for script_result in script_results:
            self.assertEqual(
                SCRIPT_STATUS.ABORTED, reload_object(script_result).status
            )

    def test_storage_layout_issues_is_invalid_no_boot_arm64_non_efi(self):
        node = factory.make_Node(
            osystem="ubuntu",
            architecture="arm64/generic",
            bios_boot_method="pxe",
        )
        self.assertEqual(
            [
                "This node cannot be deployed because it needs a separate "
                "/boot partition.  Mount /boot on a device to be able to "
                "deploy this node."
            ],
            node.storage_layout_issues(),
        )

    def test_storage_layout_issues_none_non_vmfs_on_esxi(self):
        node = factory.make_Node(osystem="esxi", distro_series="6.7")
        self.assertCountEqual([], node.storage_layout_issues())

    def test_storage_layout_issues_none_for_esxi_default(self):
        node = factory.make_Node(
            osystem="esxi", distro_series="6.7", with_boot_disk=False
        )
        factory.make_PhysicalBlockDevice(node=node, size=(100 * 1024**3))
        layout_class = random.choice([VMFS6StorageLayout, VMFS7StorageLayout])
        layout = layout_class(node)
        layout.configure()
        self.assertCountEqual([], node.storage_layout_issues())

    def test_storage_layout_issues_is_invalid_no_datastore_on_esxi(self):
        node = factory.make_Node(
            osystem="esxi", distro_series="6.7", with_boot_disk=False
        )
        factory.make_PhysicalBlockDevice(node=node, size=(100 * 1024**3))
        layout_class = random.choice([VMFS6StorageLayout, VMFS7StorageLayout])
        layout = layout_class(node)
        layout.configure()
        node.virtualblockdevice_set.delete()
        self.assertEqual(
            ["A datastore must be defined when deploying VMware ESXi."],
            node.storage_layout_issues(),
        )

    def test_storage_layout_issues_vmfs_not_esxi(self):
        node = factory.make_Node(
            osystem=random.choice(["ubuntu", "centos", "rhel"]),
            with_boot_disk=False,
        )
        factory.make_PhysicalBlockDevice(node=node, size=(100 * 1024**3))
        layout_class = random.choice([VMFS6StorageLayout, VMFS7StorageLayout])
        layout = layout_class(node)
        layout.configure()
        self.assertEqual(
            [
                "Mount the root '/' filesystem to be able to deploy this node.",
                "This node cannot be deployed because the selected "
                "deployment OS, %s, does not support VMFS6." % node.osystem,
            ],
            node.storage_layout_issues(),
        )


class TestGetBMCClientConnectionInfo(MAASServerTestCase):
    def test_returns_bmc_identifiers(self):
        node = factory.make_Node()

        mock_bmcs = self.patch(node.bmc, "get_client_identifiers")
        fake_bmc_id = factory.make_name("system_id")
        mock_bmcs.return_value = [fake_bmc_id]

        mock_fallbacks = self.patch(node, "get_boot_rack_controllers")
        fake_fallback_id = factory.make_name("system_id")
        fallback = MagicMock()
        fallback.system_id = fake_fallback_id
        mock_fallbacks.return_value = [fallback]

        self.assertEqual(
            ([fake_bmc_id], [fake_fallback_id]),
            node._get_bmc_client_connection_info(),
        )

    def test_creates_event_on_error(self):
        node = factory.make_Node()

        self.assertRaises(PowerProblem, node._get_bmc_client_connection_info)
        event_type = EventType.objects.get(
            name=EVENT_TYPES.NODE_POWER_QUERY_FAILED
        )
        event = node.event_set.get(type=event_type)
        self.assertEqual(
            (
                "No rack controllers can access the BMC of node %s"
                % node.hostname
            ),
            event.description,
        )


class TestNode_Stop(MAASServerTestCase):
    def setUp(self):
        super().setUp()
        self.patch_autospec(node_module, "power_driver_check")

    def make_acquired_node_with_interface(
        self, user, bmc_connected_to=None, power_type="virsh"
    ):
        node = factory.make_Node_with_Interface_on_Subnet(
            status=NODE_STATUS.READY,
            with_boot_disk=True,
            bmc_connected_to=bmc_connected_to,
            power_type=power_type,
        )
        node.acquire(user)
        return node

    def patch_post_commit(self):
        d = defer.succeed(None)
        self.patch(node_module, "post_commit").return_value = d
        return d

    def test_raises_PermissionDenied_if_user_doesnt_have_edit(self):
        user = factory.make_User()
        node = self.make_acquired_node_with_interface(user)
        other_user = factory.make_User()
        self.assertRaises(PermissionDenied, node.stop, other_user)

    def test_logs_user_request(self):
        self.patch_post_commit()
        admin = factory.make_admin()
        node = self.make_acquired_node_with_interface(admin)
        self.patch_autospec(node, "_power_control_node")
        register_event = self.patch(node, "_register_request_event")
        node.stop(admin)
        self.assertThat(
            register_event,
            MockCalledOnceWith(
                admin,
                EVENT_TYPES.REQUEST_NODE_STOP,
                action="stop",
                comment=None,
            ),
        )

    def test_doesnt_call__power_control_node_if_cant_be_stopped(self):
        admin = factory.make_admin()
        node = self.make_acquired_node_with_interface(
            admin, power_type="manual"
        )
        mock_power_control = self.patch_autospec(node, "_power_control_node")
        node.stop(admin)
        self.assertThat(mock_power_control, MockNotCalled())

    def test_calls__power_control_node_with_stop_mode(self):
        d = self.patch_post_commit()
        admin = factory.make_admin()
        stop_mode = factory.make_name("stop")
        node = self.make_acquired_node_with_interface(admin, power_type="ipmi")
        mock_power_control = self.patch_autospec(node, "_power_control_node")
        node.stop(admin, stop_mode=stop_mode)
        expected_power_info = node.get_effective_power_info()
        expected_power_info.power_parameters["power_off_mode"] = stop_mode
        mock_power_control.assert_called_once_with(
            d, "power_off", expected_power_info, []
        )

    def test_stop_allows_no_user(self):
        d = self.patch_post_commit()
        admin = factory.make_admin()
        stop_mode = factory.make_name("stop")
        node = self.make_acquired_node_with_interface(admin, power_type="ipmi")
        mock_power_control = self.patch_autospec(node, "_power_control_node")
        node.stop(stop_mode=stop_mode)
        expected_power_info = node.get_effective_power_info()
        expected_power_info.power_parameters["power_off_mode"] = stop_mode
        mock_power_control.assert_called_once_with(
            d, "power_off", expected_power_info, []
        )


class TestNode_PowerQuery(MAASTransactionServerTestCase):
    @wait_for_reactor
    @defer.inlineCallbacks
    def test_updates_power_state(self):
        node = yield deferToDatabase(
            transactional(factory.make_Node),
            power_state=POWER_STATE.ON,
            status=NODE_STATUS.READY,
        )
        mock_power_control = self.patch(node, "_power_control_node")
        mock_power_control.return_value = defer.succeed(
            {"state": POWER_STATE.OFF}
        )
        # Simulate a deploy workflow changing the status to DEPLOYING
        yield deferToDatabase(
            transactional(
                lambda: Node.objects.filter(id=node.id).update(
                    status=NODE_STATUS.DEPLOYING
                )
            )
        )
        observed_state = yield node.power_query()
        yield deferToDatabase(transactional(node.refresh_from_db))
        self.assertEqual(POWER_STATE.OFF, observed_state)
        self.assertEqual(POWER_STATE.OFF, node.power_state)
        mock_power_control.assert_called_once_with(ANY, "power_query", ANY)
        self.assertEqual(NODE_STATUS.DEPLOYING, node.status)

    @wait_for_reactor
    @defer.inlineCallbacks
    def test_does_not_update_power_state_when_same(self):
        node = yield deferToDatabase(
            transactional(factory.make_Node), power_state=POWER_STATE.ON
        )
        mock_power_control = self.patch(node, "_power_control_node")
        mock_power_control.return_value = defer.succeed(
            {"state": POWER_STATE.ON}
        )
        mock_update_power_state = self.patch(node, "update_power_state")
        observed_state = yield node.power_query()
        self.assertEqual(POWER_STATE.ON, observed_state)
        mock_power_control.assert_called_once_with(ANY, "power_query", ANY)
        self.assertThat(mock_update_power_state, MockNotCalled())

    @wait_for_reactor
    @defer.inlineCallbacks
    def test_updates_power_state_unknown_for_non_queryable_power_type(self):
        node = yield deferToDatabase(
            transactional(factory.make_Node),
            power_type="manual",
            power_state=POWER_STATE.ON,
            status=NODE_STATUS.READY,
        )
        mock_power_control = self.patch(node, "_power_control_node")
        mock_power_control.return_value = defer.succeed(
            {"state": POWER_STATE.OFF}
        )
        # Simulate a deploy workflow changing the status to DEPLOYING
        yield deferToDatabase(
            transactional(
                lambda: Node.objects.filter(id=node.id).update(
                    status=NODE_STATUS.DEPLOYING
                )
            )
        )
        observed_state = yield node.power_query()

        yield deferToDatabase(transactional(node.refresh_from_db))
        self.assertEqual(POWER_STATE.UNKNOWN, observed_state)
        mock_power_control.assert_called_once_with(ANY, "power_query", ANY)
        self.assertEqual(POWER_STATE.UNKNOWN, node.power_state)
        self.assertEqual(NODE_STATUS.DEPLOYING, node.status)

    @wait_for_reactor
    @defer.inlineCallbacks
    def test_creates_node_event_with_power_error(self):
        node = yield deferToDatabase(
            transactional(factory.make_Node), power_state=POWER_STATE.ERROR
        )
        mock_create_node_event = self.patch(Event.objects, "create_node_event")
        mock_power_control = self.patch(node, "_power_control_node")
        power_error = factory.make_name("Power Error")
        mock_power_control.return_value = defer.succeed(
            {"state": POWER_STATE.ERROR, "error_msg": power_error}
        )
        observed_state = yield node.power_query()

        self.assertEqual(POWER_STATE.ERROR, observed_state)
        mock_power_control.assert_called_once_with(ANY, "power_query", ANY)
        self.assertThat(
            mock_create_node_event,
            MockCalledOnceWith(
                node,
                EVENT_TYPES.NODE_POWER_QUERY_FAILED,
                event_description=power_error,
            ),
        )


class TestNode_PowerCycle(MAASServerTestCase):
    def make_acquired_node_with_interface(
        self, user, bmc_connected_to=None, power_type="virsh"
    ):
        node = factory.make_Node_with_Interface_on_Subnet(
            status=NODE_STATUS.READY,
            with_boot_disk=True,
            bmc_connected_to=bmc_connected_to,
            power_type=power_type,
        )
        node.acquire(user)
        return node

    def patch_post_commit(self):
        d = defer.succeed(None)
        self.patch(node_module, "post_commit").return_value = d
        return d

    def test_calls__power_control_node_with_power_cycle(self):
        d = self.patch_post_commit()
        admin = factory.make_admin()
        node = self.make_acquired_node_with_interface(admin)
        mock_power_control = self.patch_autospec(node, "_power_control_node")
        node._power_cycle()
        expected_power_info = node.get_effective_power_info()
        mock_power_control.assert_called_once_with(
            d, "power_cycle", expected_power_info, []
        )

    def test_calls__power_control_node_with_power_cycle_and_boot_order(self):
        d = self.patch_post_commit()
        admin = factory.make_admin()
        node = self.make_acquired_node_with_interface(admin, power_type="hmcz")
        mock_power_control = self.patch_autospec(node, "_power_control_node")
        node._power_cycle()
        expected_power_info = node.get_effective_power_info()
        mock_power_control.assert_called_once_with(
            d, "power_cycle", expected_power_info, node._get_boot_order(True)
        )


class TestNode_PostCommit_PowerControl(MAASTransactionServerTestCase):
    @transactional
    def make_node(
        self,
        power_type="virsh",
        layer2_rack=None,
        routable_racks=None,
        primary_rack=None,
        with_dhcp_rack_primary=True,
    ):
        user = factory.make_User()
        node = factory.make_Node_with_Interface_on_Subnet(
            status=NODE_STATUS.READY,
            power_type=power_type,
            with_boot_disk=True,
            bmc_connected_to=layer2_rack,
            primary_rack=primary_rack,
        )
        node.acquire(user)
        if routable_racks is not None:
            for rack in routable_racks:
                BMCRoutableRackControllerRelationship(
                    bmc=node.bmc, rack_controller=rack, routable=True
                ).save()
        return node, node.get_effective_power_info()

    @transactional
    def make_rack_controller(self):
        return factory.make_RackController()

    @transactional
    def make_rack_controllers_with_clients(self, count):
        racks = []
        clients = []
        for _ in range(count):
            rack = factory.make_RackController()
            client = Mock()
            client.ident = rack.system_id
            racks.append(rack)
            clients.append(client)
        return racks, clients

    def patch_post_commit(self):
        d = defer.succeed(None)
        self.patch(node_module, "post_commit").return_value = d
        return d

    @wait_for_reactor
    @defer.inlineCallbacks
    def test_bmc_is_accessible_uses_directly_connected_client(self):
        d = self.patch_post_commit()
        rack_controller = yield deferToDatabase(self.make_rack_controller)
        node, power_info = yield deferToDatabase(
            self.make_node, layer2_rack=rack_controller
        )

        client = Mock()
        client.ident = rack_controller.system_id
        mock_getClientFromIdentifiers = self.patch(
            node_module, "getClientFromIdentifiers"
        )
        mock_getClientFromIdentifiers.return_value = defer.succeed(client)

        # Add the client to getAllClients in so that its considered a to be a
        # valid connection.
        self.patch(node_module, "getAllClients").return_value = [client]

        # Mock the confirm power driver check, we check in the test to make
        # sure it gets called.
        mock_confirm_power_driver = self.patch(
            Node, "confirm_power_driver_operable"
        )
        mock_confirm_power_driver.return_value = defer.succeed(None)

        # Testing only allows one thread at a time, but the way we are testing
        # this would actually require multiple to be started at once. To
        # by-pass this issue we mock `is_accessible` on the BMC model to return
        # the value we are expecting.
        self.patch(node.bmc, "is_accessible").return_value = True

        self.patch(workflow_module, "temporal_wrapper")
        self.patch(node_module, "execute_workflow").return_value = {
            "state": "on"
        }

        yield node._power_control_node(d, "power_query", power_info)

        self.assertThat(
            mock_getClientFromIdentifiers,
            MockCalledOnceWith([rack_controller.system_id]),
        )
        self.assertThat(
            mock_confirm_power_driver,
            MockCalledOnceWith(client, power_info.power_type, client.ident),
        )

    @wait_for_reactor
    @defer.inlineCallbacks
    def test_bmc_is_accessible_raises_PowerActionFail_for_bad_software(self):
        d = self.patch_post_commit()
        rack_controller = yield deferToDatabase(self.make_rack_controller)
        rack_controller_fqdn = yield deferToDatabase(
            lambda: rack_controller.fqdn
        )
        node, power_info = yield deferToDatabase(
            self.make_node, layer2_rack=rack_controller
        )

        client = Mock()
        client.ident = rack_controller.system_id
        mock_getClientFromIdentifiers = self.patch(
            node_module, "getClientFromIdentifiers"
        )
        mock_getClientFromIdentifiers.return_value = defer.succeed(client)

        # Add the client to getAllClients in so that its considered a to be a
        # valid connection.
        self.patch(node_module, "getAllClients").return_value = [client]

        # Mock power_driver_check to cause the PowerActionFail.
        missing_packages = [factory.make_name("package") for _ in range(3)]
        missing_packages = sorted(missing_packages)
        if len(missing_packages) > 2:
            missing_packages = [
                ", ".join(missing_packages[:-1]),
                missing_packages[-1],
            ]
        package_list = " and ".join(missing_packages)
        self.patch(
            node_module, "power_driver_check"
        ).return_value = defer.succeed(missing_packages)

        # Testing only allows one thread at a time, but the way we are testing
        # this would actually require multiple to be started at once. To
        # by-pass this issue we mock `is_accessible` on the BMC model to return
        # the value we are expecting.
        self.patch(node.bmc, "is_accessible").return_value = True

        with ExpectedException(
            PowerActionFail,
            re.escape(
                "Power control software is missing from the rack "
                "controller '%s'. To proceed, "
                "install the %s packages."
                % (rack_controller_fqdn, package_list)
            ),
        ):
            yield node._power_control_node(d, "power_query", power_info)

    @wait_for_reactor
    @defer.inlineCallbacks
    def test_bmc_is_accessible_falls_back_to_fallback_clients(self):
        d = self.patch_post_commit()
        layer2_rack_controller = yield deferToDatabase(
            self.make_rack_controller
        )
        primary_rack = yield deferToDatabase(self.make_rack_controller)
        node, power_info = yield deferToDatabase(
            self.make_node,
            layer2_rack=layer2_rack_controller,
            primary_rack=primary_rack,
        )

        client = Mock()
        client.ident = primary_rack.system_id
        mock_getClientFromIdentifiers = self.patch(
            node_module, "getClientFromIdentifiers"
        )
        mock_getClientFromIdentifiers.side_effect = [
            defer.fail(NoConnectionsAvailable()),
            defer.succeed(client),
        ]

        # Add the client to getAllClients in so that its considered a to be a
        # valid connection, but will actually fail.
        bad_client = Mock()
        bad_client.ident = layer2_rack_controller.system_id
        self.patch(node_module, "getAllClients").return_value = [bad_client]

        # Mock the confirm power driver check, we check in the test to make
        # sure it gets called.
        mock_confirm_power_driver = self.patch(
            Node, "confirm_power_driver_operable"
        )
        mock_confirm_power_driver.return_value = defer.succeed(None)

        # Testing only allows one thread at a time, but the way we are testing
        # this would actually require multiple to be started at once. To
        # by-pass this issue we mock `is_accessible` on the BMC model to return
        # the value we are expecting.
        self.patch(node.bmc, "is_accessible").return_value = True

        self.patch(workflow_module, "temporal_wrapper")
        self.patch(node_module, "execute_workflow").return_value = {
            "state": "on"
        }

        yield node._power_control_node(d, "power_query", power_info)

        self.assertThat(
            mock_getClientFromIdentifiers,
            MockCallsMatch(
                call([layer2_rack_controller.system_id]),
                call([primary_rack.system_id]),
            ),
        )
        self.assertThat(
            mock_confirm_power_driver,
            MockCalledOnceWith(client, power_info.power_type, client.ident),
        )

    @wait_for_reactor
    @defer.inlineCallbacks
    def test_bmc_is_not_accessible_updates_routable_racks_and_powers(self):
        node, power_info = yield deferToDatabase(
            self.make_node, with_dhcp_rack_primary=False
        )

        routable_racks, routable_clients = yield deferToDatabase(
            self.make_rack_controllers_with_clients, 3
        )
        routable_racks_system_ids = [rack.system_id for rack in routable_racks]
        none_routable_racks, none_routable_clients = yield deferToDatabase(
            self.make_rack_controllers_with_clients, 3
        )
        none_routable_racks_system_ids = [
            rack.system_id for rack in none_routable_racks
        ]
        all_clients = routable_clients + none_routable_clients
        all_clients_by_ident = {client.ident: client for client in all_clients}

        new_power_state = factory.pick_enum(
            POWER_STATE, but_not=[node.power_state]
        )
        mock_power_query_all = self.patch(node_module, "power_query_all")
        mock_power_query_all.return_value = defer.succeed(
            (
                new_power_state,
                routable_racks_system_ids,
                none_routable_racks_system_ids,
            )
        )

        # Holds the selected client.
        selected_client = []

        def fake_get_client(identifiers):
            for ident in identifiers:
                if ident in all_clients_by_ident:
                    client = all_clients_by_ident[ident]
                    selected_client.append(client)
                    return defer.succeed(client)
            return defer.fail(NoConnectionsAvailable())

        mock_getClientFromIdentifiers = self.patch(
            node_module, "getClientFromIdentifiers"
        )
        mock_getClientFromIdentifiers.side_effect = fake_get_client

        # Add the clients to getAllClients in so that its considered a to be a
        # valid connections.
        self.patch(node_module, "getAllClients").return_value = all_clients
        self.patch(bmc_module, "getAllClients").return_value = all_clients

        self.patch(workflow_module, "temporal_wrapper")
        self.patch(node_module, "execute_workflow").return_value = {
            "state": new_power_state
        }

        # Mock the confirm power driver check, we check in the test to make
        # sure it gets called.
        mock_confirm_power_driver = self.patch(
            Node, "confirm_power_driver_operable"
        )
        mock_confirm_power_driver.return_value = defer.succeed(None)

        d = defer.succeed(None)
        yield node._power_control_node(d, "power_query", power_info)

        # Makes the correct calls.
        client = selected_client[0]
        self.assertThat(
            mock_power_query_all,
            MockCalledOnceWith(node.system_id, node.hostname, power_info),
        )
        self.assertThat(
            mock_getClientFromIdentifiers,
            MockCalledOnceWith(routable_racks_system_ids),
        )
        self.assertThat(
            mock_confirm_power_driver,
            MockCalledOnceWith(client, power_info.power_type, client.ident),
        )

        # Test that the node and the BMC routable rack information was
        # updated.
        @transactional
        def updates_node_and_bmc(
            node, power_state, routable_racks, none_routable_racks
        ):
            node = reload_object(node)
            self.expectThat(node.power_state, Equals(power_state))
            self.expectThat(
                BMCRoutableRackControllerRelationship.objects.filter(
                    bmc=node.bmc,
                    rack_controller__in=routable_racks,
                    routable=True,
                ),
                HasLength(len(routable_racks)),
            )
            self.expectThat(
                BMCRoutableRackControllerRelationship.objects.filter(
                    bmc=node.bmc,
                    rack_controller__in=none_routable_racks,
                    routable=False,
                ),
                HasLength(len(none_routable_racks)),
            )

        yield deferToDatabase(
            updates_node_and_bmc,
            node,
            new_power_state,
            routable_racks,
            none_routable_racks,
        )

    @wait_for_reactor
    @defer.inlineCallbacks
    def test_sets_boot_order_if_given(self):
        d = self.patch_post_commit()
        rack_controller = yield deferToDatabase(self.make_rack_controller)
        node, power_info = yield deferToDatabase(
            self.make_node,
            layer2_rack=rack_controller,
        )
        boot_order = yield deferToDatabase(node._get_boot_order)

        client = Mock()
        client.ident = rack_controller.system_id
        mock_getClientFromIdentifiers = self.patch(
            node_module, "getClientFromIdentifiers"
        )
        mock_getClientFromIdentifiers.return_value = defer.succeed(client)

        # Add the client to getAllClients in so that its considered a to be a
        # valid connection.
        self.patch(node_module, "getAllClients").return_value = [client]

        # Mock the confirm power driver check, we check in the test to make
        # sure it gets called.
        mock_confirm_power_driver = self.patch(
            Node, "confirm_power_driver_operable"
        )
        mock_confirm_power_driver.return_value = defer.succeed(None)

        mock_set_boot_order = self.patch(node_module, "set_boot_order")
        mock_set_boot_order.return_value = defer.succeed(client)

        # Testing only allows one thread at a time, but the way we are testing
        # this would actually require multiple to be started at once. To
        # by-pass this issue we mock `is_accessible` on the BMC model to return
        # the value we are expecting.
        self.patch(node.bmc, "is_accessible").return_value = True

        self.patch(workflow_module, "temporal_wrapper")
        self.patch(node_module, "execute_workflow").return_value = {
            "state": "on"
        }

        yield node._power_control_node(
            d, "power_query", power_info, boot_order
        )

        mock_getClientFromIdentifiers.assert_called_with(
            [rack_controller.system_id]
        )
        mock_confirm_power_driver.assert_called_with(
            client, power_info.power_type, client.ident
        )
        mock_set_boot_order.assert_called_with(
            client, node.system_id, node.hostname, power_info, boot_order
        )

    @wait_for_reactor
    @defer.inlineCallbacks
    def test_sets_boot_order_if_given_with_no_power_method(self):
        d = self.patch_post_commit()
        rack_controller = yield deferToDatabase(self.make_rack_controller)
        node, power_info = yield deferToDatabase(
            self.make_node,
            layer2_rack=rack_controller,
        )
        boot_order = yield deferToDatabase(node._get_boot_order)

        client = Mock()
        client.ident = rack_controller.system_id
        mock_getClientFromIdentifiers = self.patch(
            node_module, "getClientFromIdentifiers"
        )
        mock_getClientFromIdentifiers.return_value = defer.succeed(client)

        # Add the client to getAllClients in so that its considered a to be a
        # valid connection.
        self.patch(node_module, "getAllClients").return_value = [client]

        # Mock the confirm power driver check, we check in the test to make
        # sure it gets called.
        mock_confirm_power_driver = self.patch(
            Node, "confirm_power_driver_operable"
        )
        mock_confirm_power_driver.return_value = defer.succeed(None)

        mock_set_boot_order = self.patch(node_module, "set_boot_order")
        mock_set_boot_order.return_value = defer.succeed(client)

        # Testing only allows one thread at a time, but the way we are testing
        # this would actually require multiple to be started at once. To
        # by-pass this issue we mock `is_accessible` on the BMC model to return
        # the value we are expecting.
        self.patch(node.bmc, "is_accessible").return_value = True

        yield node._power_control_node(d, None, power_info, boot_order)

        mock_getClientFromIdentifiers.assert_called_with(
            [rack_controller.system_id]
        )
        mock_confirm_power_driver.assert_called_with(
            client, power_info.power_type, client.ident
        )
        mock_set_boot_order.assert_called_with(
            client, node.system_id, node.hostname, power_info, boot_order
        )


class TestNode_Delete_With_Transactional_Events(MAASTransactionServerTestCase):
    """
    Test deleting a node where the releated `Event`'s do not get deleted.

    This simulates the failure reported in lp:1726474.
    """

    @wait_for_reactor
    @defer.inlineCallbacks
    def test_integrity_error_is_retried(self):
        # This doesn't simulate the actual way the failure is caused, but it
        # does simulate it to cause the same effect.
        #
        # The `calls` below is used to hold the context inside of the retry
        # loop. The first call will fail as `_clear_events` will be called,
        # the first retry will not call `_clear_events` which will allow the
        # transaction to be committed.
        calls = []

        def _clear_events(collector):
            for idx, objs in enumerate(collector.fast_deletes):
                if len(objs) > 0 and isinstance(objs[0], Event):
                    collector.fast_deletes[idx] = Event.objects.none()

        @transactional
        def _in_database():
            node = factory.make_Node()
            for _ in range(10):
                factory.make_Event(node=node)

            # Use the collector directly instead of calling `delete`.
            collector = Collector(using="default")
            collector.collect([node])
            if calls == 0:
                _clear_events(collector)
            calls.append(None)
            collector.delete()

        # Test is that no exception is raised. If this doesn't work then a
        # `django.db.utils.IntegrityError` will be raised.
        yield deferToDatabase(_in_database)


class TestController(MAASServerTestCase):
    def test_should_be_dynamically_deleted_false(self):
        rack = factory.make_RackController(status=NODE_STATUS.DEPLOYED)
        rack.bmc = factory.make_BMC()
        rack.save()
        self.assertFalse(rack.should_be_dynamically_deleted())

    def test_should_be_dynamically_deleted_true(self):
        self.assertTrue(
            factory.make_RackController(
                dynamic=True
            ).should_be_dynamically_deleted()
        )


class TestControllerUpdateDiscoveryState(MAASServerTestCase):
    def test_calls_update_discovery_state_per_interface(self):
        controller = factory.make_RegionRackController()
        eth1 = factory.make_Interface(
            node=controller,
            neighbour_discovery_state=False,
            mdns_discovery_state=False,
        )
        eth1_vlan = factory.make_Interface(
            iftype=INTERFACE_TYPE.VLAN,
            node=controller,
            parents=[eth1],
            neighbour_discovery_state=False,
            mdns_discovery_state=False,
        )
        discovery_config = NetworkDiscoveryConfig(
            passive=True, active=random.choice([True, False])
        )
        controller.update_discovery_state(discovery_config)
        eth1 = reload_object(eth1)
        eth1_vlan = reload_object(eth1_vlan)
        self.assertTrue(eth1.neighbour_discovery_state)
        self.assertFalse(eth1_vlan.neighbour_discovery_state)
        self.assertTrue(eth1.mdns_discovery_state)
        self.assertTrue(eth1_vlan.mdns_discovery_state)


class TestReportNeighbours(MAASServerTestCase):
    def test_no_update_neighbours_calls_if_discovery_disabled(self):
        rack = factory.make_RackController()
        factory.make_Interface(name="eth0", node=rack)
        update_neighbour = self.patch(
            interface_module.Interface, "update_neighbour"
        )
        neighbours = [
            {
                "interface": "eth0",
                "mac": factory.make_mac_address(),
                "ip": factory.make_ipv4_address(),
                "time": datetime.now(),
            },
        ]
        rack.report_neighbours(neighbours)
        update_neighbour.assert_not_called()

    def test_calls_update_neighbour_for_each_neighbour(self):
        rack = factory.make_RackController()
        if1 = factory.make_Interface(name="eth0", node=rack)
        if1.neighbour_discovery_state = True
        if1.save()
        if2 = factory.make_Interface(name="eth1", node=rack)
        if2.neighbour_discovery_state = True
        if2.save()
        update_neighbour = self.patch(
            interface_module.Interface, "update_neighbour"
        )
        neighbours = [
            {
                "interface": "eth0",
                "mac": factory.make_mac_address(),
                "ip": factory.make_ipv4_address(),
                "time": datetime.now(),
            },
            {
                "interface": "eth1",
                "mac": factory.make_mac_address(),
                "ip": factory.make_ipv4_address(),
                "time": datetime.now(),
            },
        ]
        rack.report_neighbours(neighbours)
        update_neighbour.assert_has_calls(
            [call(n["ip"], n["mac"], n["time"], vid=None) for n in neighbours]
        )

    def test_calls_report_vid_for_each_vid(self):
        rack = factory.make_RackController()
        factory.make_Interface(name="eth0", node=rack)
        factory.make_Interface(name="eth1", node=rack)
        # Just make this a no-op for simplicity.
        self.patch(interface_module.Interface, "update_neighbour")
        report_vid = self.patch(interface_module.Interface, "report_vid")
        neighbours = [
            {
                "interface": "eth0",
                "ip": factory.make_ipv4_address(),
                "time": datetime.now(),
                "mac": factory.make_mac_address(),
                "vid": 3,
            },
            {
                "interface": "eth1",
                "ip": factory.make_ipv4_address(),
                "time": datetime.now(),
                "mac": factory.make_mac_address(),
                "vid": 7,
            },
        ]
        rack.report_neighbours(neighbours)
        report_vid.assert_has_calls(
            [call(3, ip=neighbours[0]["ip"]), call(7, ip=neighbours[1]["ip"])]
        )

    def test_does_not_updates_fabric_of_existing_vlan(self):
        rack = factory.make_RackController()
        observing_fabric = factory.make_Fabric()
        other_fabric = factory.make_Fabric()
        vlan = factory.make_VLAN(fabric=observing_fabric)
        observed_vlan = factory.make_VLAN(fabric=other_fabric)
        subnet1 = factory.make_Subnet(vlan=vlan)
        subnet2 = factory.make_Subnet(vlan=observed_vlan)
        factory.make_Interface(name="eth0", subnet=subnet1, node=rack)
        iface2 = factory.make_Interface(name="eth1", node=rack)
        neighbours = [
            {
                "interface": "eth0",
                "ip": subnet2.get_next_ip_for_allocation()[0],
                "time": datetime.now(),
                "mac": iface2.mac_address,
                "vid": observed_vlan.vid,
            }
        ]
        rack.report_neighbours(neighbours)
        observed_vlan.refresh_from_db()
        self.assertEqual(other_fabric, observed_vlan.fabric)
        self.assertEqual(
            VLAN.objects.filter(
                vid=observed_vlan.vid, fabric=other_fabric
            ).count(),
            1,
        )


class TestReportMDNSEntries(MAASServerTestCase):
    def test_calls_update_mdns_entry_for_each_entry(self):
        rack = factory.make_RackController()
        factory.make_Interface(name="eth0", node=rack)
        factory.make_Interface(name="eth1", node=rack)
        update_mdns_entry = self.patch(
            interface_module.Interface, "update_mdns_entry"
        )
        entries = [
            {"interface": "eth0", "hostname": factory.make_name("eth0")},
            {"interface": "eth1", "hostname": factory.make_name("eth1")},
        ]
        rack.report_mdns_entries(entries)
        self.assertThat(
            update_mdns_entry,
            MockCallsMatch(*[call(entry) for entry in entries]),
        )


class TestRackControllerRefresh(MAASTransactionServerTestCase):
    def setUp(self):
        super().setUp()
        self.useFixture(RegionEventLoopFixture("rpc"))
        self.useFixture(RunningEventLoopFixture())
        self.rpc = self.useFixture(MockLiveRegionToClusterRPCFixture())
        self.rackcontroller = factory.make_RackController()

    @wait_for_reactor
    @defer.inlineCallbacks
    def test_prepares_for_refresh(self):
        def get_events(rack):
            return [
                (event.type.name, event.owner, event.action)
                for event in Event.objects.filter(
                    node_system_id=rack.system_id
                )
            ]

        rack = yield deferToDatabase(factory.make_RackController)
        credentials = yield rack.start_refresh()
        self.assertCountEqual(
            ["consumer_key", "token_key", "token_secret"], credentials.keys()
        )

        events = yield deferToDatabase(get_events, rack)
        [(event_name, event_owner, event_action)] = [
            (event_name, event_owner, event_action)
            for (event_name, event_owner, event_action) in events
            if event_name == "REQUEST_CONTROLLER_REFRESH"
        ]
        self.assertEqual(rack.owner.username, event_owner)
        self.assertEqual("starting refresh", event_action)


class TestRackController(MAASTransactionServerTestCase):
    def test_add_chassis_issues_rpc_call(self):
        rackcontroller = factory.make_RackController()

        self.useFixture(RegionEventLoopFixture("rpc"))
        self.useFixture(RunningEventLoopFixture())
        fixture = self.useFixture(MockLiveRegionToClusterRPCFixture())
        protocol = fixture.makeCluster(rackcontroller, AddChassis)
        protocol.AddChassis.return_value = defer.succeed({})

        user = factory.make_name("user")
        chassis_type = factory.make_name("chassis_type")
        hostname = factory.make_url()
        username = factory.make_name("username")
        password = factory.make_name("password")
        accept_all = factory.pick_bool()
        domain = factory.make_name("domain")
        prefix_filter = factory.make_name("prefix_filter")
        power_control = factory.make_name("power_control")
        port = random.randint(0, 65535)
        given_protocol = factory.make_name("protocol")
        token_name = factory.make_name("token_name")
        token_secret = factory.make_name("token_secret")
        verify_ssl = factory.pick_bool()

        rackcontroller.add_chassis(
            user,
            chassis_type,
            hostname,
            username,
            password,
            accept_all,
            domain,
            prefix_filter,
            power_control,
            port,
            given_protocol,
            token_name,
            token_secret,
            verify_ssl,
        )

        self.expectThat(
            protocol.AddChassis,
            MockCalledOnceWith(
                ANY,
                user=user,
                chassis_type=chassis_type,
                hostname=hostname,
                username=username,
                password=password,
                accept_all=accept_all,
                domain=domain,
                prefix_filter=prefix_filter,
                power_control=power_control,
                port=port,
                protocol=given_protocol,
                token_name=token_name,
                token_secret=token_secret,
                verify_ssl=verify_ssl,
            ),
        )

    def test_add_chassis_logs_user_request(self):
        rackcontroller = factory.make_RackController()

        self.useFixture(RegionEventLoopFixture("rpc"))
        self.useFixture(RunningEventLoopFixture())
        fixture = self.useFixture(MockLiveRegionToClusterRPCFixture())
        protocol = fixture.makeCluster(rackcontroller, AddChassis)
        protocol.AddChassis.return_value = defer.succeed({})

        user = factory.make_name("user")
        chassis_type = factory.make_name("chassis_type")
        hostname = factory.make_url()
        username = factory.make_name("username")
        password = factory.make_name("password")
        accept_all = factory.pick_bool()
        domain = factory.make_name("domain")
        prefix_filter = factory.make_name("prefix_filter")
        power_control = factory.make_name("power_control")
        port = random.randint(0, 65535)
        given_protocol = factory.make_name("protocol")
        token_name = factory.make_name("token_name")
        token_secret = factory.make_name("token_secret")
        verify_ssl = factory.pick_bool()

        register_event = self.patch(rackcontroller, "_register_request_event")
        rackcontroller.add_chassis(
            user,
            chassis_type,
            hostname,
            username,
            password,
            accept_all,
            domain,
            prefix_filter,
            power_control,
            port,
            given_protocol,
            token_name,
            token_secret,
            verify_ssl,
        )
        post_commit_hooks.reset()  # Ignore these for now.
        self.assertThat(
            register_event,
            MockCalledOnceWith(
                rackcontroller.owner,
                EVENT_TYPES.REQUEST_RACK_CONTROLLER_ADD_CHASSIS,
                action="Adding chassis %s" % hostname,
            ),
        )

    def test_allows_delete_when_not_connected(self):
        rackcontroller = factory.make_RackController()
        rackcontroller.delete()
        self.assertIsNone(reload_object(rackcontroller))

    def test_disables_and_disconn_when_secondary_connected(self):
        rackcontroller = factory.make_RackController()
        factory.make_VLAN(secondary_rack=rackcontroller)

        self.useFixture(RegionEventLoopFixture("rpc"))
        self.useFixture(RunningEventLoopFixture())
        fixture = self.useFixture(MockLiveRegionToClusterRPCFixture())
        protocol = fixture.makeCluster(rackcontroller, DisableAndShutoffRackd)
        protocol.DisableAndShutoffRackd.return_value = defer.succeed({})

        rackcontroller.delete()
        self.expectThat(protocol.DisableAndShutoffRackd, MockCalledOnce())

    def test_disables_and_disconn_ignores_timeout(self):
        rackcontroller = factory.make_RackController()
        factory.make_VLAN(secondary_rack=rackcontroller)

        self.useFixture(RegionEventLoopFixture("rpc"))
        self.useFixture(RunningEventLoopFixture())
        fixture = self.useFixture(MockLiveRegionToClusterRPCFixture())
        fixture.makeCluster(rackcontroller, DisableAndShutoffRackd)
        self.patch(
            crochet._eventloop.EventualResult, "wait"
        ).side_effect = TimeoutError()

        rackcontroller.delete()
        self.assertIsNone(reload_object(rackcontroller))

    def test_disables_and_disconn_ignores_connectiondone(self):
        # Regression test for LP:1729649
        rackcontroller = factory.make_RackController()
        factory.make_VLAN(secondary_rack=rackcontroller)

        self.useFixture(RegionEventLoopFixture("rpc"))
        self.useFixture(RunningEventLoopFixture())
        fixture = self.useFixture(MockLiveRegionToClusterRPCFixture())
        fixture.makeCluster(rackcontroller, DisableAndShutoffRackd)
        self.patch(
            crochet._eventloop.EventualResult, "wait"
        ).side_effect = ConnectionDone()

        rackcontroller.delete()
        self.assertIsNone(reload_object(rackcontroller))

    def test_disables_and_disconn_when_secondary_connected_fails(self):
        rackcontroller = factory.make_RackController()
        factory.make_VLAN(secondary_rack=rackcontroller)

        self.useFixture(RegionEventLoopFixture("rpc"))
        self.useFixture(RunningEventLoopFixture())
        fixture = self.useFixture(MockLiveRegionToClusterRPCFixture())
        protocol = fixture.makeCluster(rackcontroller, DisableAndShutoffRackd)
        protocol.DisableAndShutoffRackd.return_value = defer.fail(
            CannotDisableAndShutoffRackd()
        )

        self.assertRaises(CannotDisableAndShutoffRackd, rackcontroller.delete)
        self.expectThat(protocol.DisableAndShutoffRackd, MockCalledOnce())

    def test_migrate_dhcp_from_rack_sets_new_primary_and_secondary(self):
        rack = factory.make_RackController()
        secondary_rack = factory.make_RackController()
        vlan = factory.make_VLAN(
            dhcp_on=True, primary_rack=rack, secondary_rack=secondary_rack
        )
        new_secondary = factory.make_RackController()
        factory.make_Interface(node=new_secondary, vlan=vlan)
        changes = rack.migrate_dhcp_from_rack()
        self.assertEqual([(vlan, secondary_rack, new_secondary)], changes)
        vlan = reload_object(vlan)
        self.assertEqual(secondary_rack, vlan.primary_rack)
        self.assertEqual(new_secondary, vlan.secondary_rack)

    def test_migrate_dhcp_from_rack_sets_new_primary(self):
        rack = factory.make_RackController()
        vlan = factory.make_VLAN(dhcp_on=True, primary_rack=rack)
        new_primary = factory.make_RackController()
        factory.make_Interface(node=new_primary, vlan=vlan)
        changes = rack.migrate_dhcp_from_rack()
        self.assertEqual([(vlan, new_primary, None)], changes)
        vlan = reload_object(vlan)
        self.assertEqual(new_primary, vlan.primary_rack)
        self.assertIsNone(vlan.secondary_rack)

    def test_migrate_dhcp_from_rack_stops_dhcp(self):
        rack = factory.make_RackController()
        vlan = factory.make_VLAN(dhcp_on=True, primary_rack=rack)
        changes = rack.migrate_dhcp_from_rack()
        self.assertEqual([(vlan, None, None)], changes)
        vlan = reload_object(vlan)
        self.assertFalse(vlan.dhcp_on)
        self.assertIsNone(vlan.primary_rack)
        self.assertIsNone(vlan.secondary_rack)

    def test_migrate_dhcp_from_rack_sets_new_secondary(self):
        primary_rack = factory.make_RackController()
        secondary_rack = factory.make_RackController()
        vlan = factory.make_VLAN(
            dhcp_on=True,
            primary_rack=primary_rack,
            secondary_rack=secondary_rack,
        )
        new_secondary = factory.make_RackController()
        factory.make_Interface(node=new_secondary, vlan=vlan)
        changes = secondary_rack.migrate_dhcp_from_rack()
        self.assertEqual([(vlan, primary_rack, new_secondary)], changes)
        vlan = reload_object(vlan)
        self.assertEqual(primary_rack, vlan.primary_rack)
        self.assertEqual(new_secondary, vlan.secondary_rack)

    def test_migrate_dhcp_from_rack_sets_to_None(self):
        primary_rack = factory.make_RackController()
        secondary_rack = factory.make_RackController()
        vlan = factory.make_VLAN(
            dhcp_on=True,
            primary_rack=primary_rack,
            secondary_rack=secondary_rack,
        )
        changes = secondary_rack.migrate_dhcp_from_rack()
        self.assertEqual([(vlan, primary_rack, None)], changes)
        vlan = reload_object(vlan)
        self.assertEqual(primary_rack, vlan.primary_rack)
        self.assertIsNone(vlan.secondary_rack)

    def test_migrate_dhcp_no_commit(self):
        primary_rack = factory.make_RackController()
        secondary_rack = factory.make_RackController()
        vlan = factory.make_VLAN(
            dhcp_on=True,
            primary_rack=primary_rack,
            secondary_rack=secondary_rack,
        )
        changes = secondary_rack.migrate_dhcp_from_rack(commit=False)
        self.assertEqual([(vlan, primary_rack, None)], changes)
        vlan = reload_object(vlan)
        self.assertEqual(primary_rack, vlan.primary_rack)
        self.assertEqual(secondary_rack, vlan.secondary_rack)

    def test_prevents_delete_when_primary_rack(self):
        rackcontroller = factory.make_RackController()
        factory.make_VLAN(dhcp_on=True, primary_rack=rackcontroller)
        self.assertRaises(ValidationError, rackcontroller.delete)

    def test_delete_removes_secondary_link(self):
        primary_rack = factory.make_RackController()
        rackcontroller = factory.make_RackController()
        vlan = factory.make_VLAN(
            dhcp_on=True,
            primary_rack=primary_rack,
            secondary_rack=rackcontroller,
        )
        rackcontroller.delete()
        self.assertIsNone(reload_object(vlan).secondary_rack)
        self.assertRaises(
            RackController.DoesNotExist,
            RackController.objects.get,
            system_id=rackcontroller.system_id,
        )

    def test_deletes_services(self):
        rack = factory.make_RackController()
        service = factory.make_Service(rack)
        rack.delete()
        self.assertIsNone(reload_object(service))

    def test_deletes_region_rack_rpc_connections(self):
        rack = factory.make_RackController()
        factory.make_RegionRackRPCConnection(rack_controller=rack)
        rack.delete()
        self.assertCountEqual([], RegionRackRPCConnection.objects.all())

    def test_delete_converts_region_and_rack_to_region(self):
        region_and_rack = factory.make_Node(
            node_type=NODE_TYPE.REGION_AND_RACK_CONTROLLER
        )
        system_id = region_and_rack.system_id
        region_and_rack.as_rack_controller().delete()
        self.assertEqual(
            NODE_TYPE.REGION_CONTROLLER,
            Node.objects.get(system_id=system_id).node_type,
        )

    def test_delete_converts_rack_to_machine(self):
        rack = factory.make_RackController(status=NODE_STATUS.DEPLOYED)
        rack.bmc = factory.make_BMC()
        rack.save()
        rack.delete()
        self.assertEqual(
            NODE_TYPE.MACHINE,
            Node.objects.get(system_id=rack.system_id).node_type,
        )

    def test_update_rackd_status_calls_mark_dead_when_no_connections(self):
        rack_controller = factory.make_RackController()
        mock_mark_dead = self.patch(Service.objects, "mark_dead")
        rack_controller.update_rackd_status()
        self.assertThat(
            mock_mark_dead, MockCalledOnceWith(rack_controller, dead_rack=True)
        )

    def test_update_rackd_status_sets_rackd_running_when_all_connected(self):
        rack_controller = factory.make_RackController()
        endpoint = factory.make_RegionControllerProcessEndpoint()
        RegionRackRPCConnection.objects.create(
            endpoint=endpoint, rack_controller=rack_controller
        )
        rack_controller.update_rackd_status()
        self.assertThat(
            rack_controller.service_set.get(name="rackd"),
            MatchesStructure.byEquality(
                status=SERVICE_STATUS.RUNNING, status_info=""
            ),
        )

    def test_update_rackd_status_sets_rackd_degraded(self):
        rack_controller = factory.make_RackController()
        region = factory.make_RegionController()
        process = factory.make_RegionControllerProcess(region=region)
        factory.make_RegionControllerProcessEndpoint(process=process)

        factory.make_RegionController()
        connected_endpoint = factory.make_RegionControllerProcessEndpoint()
        RegionRackRPCConnection.objects.create(
            endpoint=connected_endpoint, rack_controller=rack_controller
        )
        rack_controller.update_rackd_status()
        # (num disconnected * 4 + 1) / (total * 4)
        percentage = (4 + 1) / (3 * 4)
        rack_controller_service = rack_controller.service_set.get(name="rackd")
        self.assertEqual(
            rack_controller_service.status, SERVICE_STATUS.DEGRADED
        )
        self.assertEqual(
            rack_controller_service.status_info,
            "{:.0%} connected to region controllers.".format(1.0 - percentage),
        )

    fake_images = [
        {
            "release": "custom_os",
            "osystem": "custom",
            "architecture": "amd64",
            "subarchitecture": "generic",
        },
        {
            "release": "trusty",
            "osystem": "ubuntu",
            "architecture": "amd64",
            "subarchitecture": "generic",
        },
        {
            "release": "trusty",
            "osystem": "ubuntu",
            "architecture": "amd64",
            "subarchitecture": "hwe-t",
        },
        {
            "release": "trusty",
            "osystem": "ubuntu",
            "architecture": "amd64",
            "subarchitecture": "hwe-x",
        },
    ]

    expected_images = [
        {
            "name": "ubuntu/trusty",
            "architecture": "amd64",
            "subarches": ["generic", "hwe-t", "hwe-x"],
        },
        {
            "name": "custom_os",
            "architecture": "amd64",
            "subarches": ["generic"],
        },
    ]

    def test_list_boot_images(self):
        rack_controller = factory.make_RackController()
        self.patch(
            boot_images, "get_boot_images"
        ).return_value = self.fake_images
        self.patch(
            BootResource.objects, "boot_images_are_in_sync"
        ).return_value = True
        images = rack_controller.list_boot_images()
        self.assertTrue(images["connected"])
        self.assertCountEqual(self.expected_images, images["images"])
        self.assertEqual("synced", images["status"])
        self.assertEqual("synced", rack_controller.get_image_sync_status())

    def test_list_boot_images_when_disconnected(self):
        rack_controller = factory.make_RackController()
        images = rack_controller.list_boot_images()
        self.assertFalse(images["connected"])
        self.assertCountEqual([], images["images"])
        self.assertEqual("unknown", images["status"])
        self.assertEqual("unknown", rack_controller.get_image_sync_status())

    def test_list_boot_images_when_connection_closed(self):
        rack_controller = factory.make_RackController()
        self.patch(
            boot_images, "get_boot_images"
        ).side_effect = ConnectionClosed()
        images = rack_controller.list_boot_images()
        self.assertFalse(images["connected"])
        self.assertCountEqual([], images["images"])
        self.assertEqual("unknown", images["status"])
        self.assertEqual("unknown", rack_controller.get_image_sync_status())

    def test_list_boot_images_region_importing(self):
        rack_controller = factory.make_RackController()
        self.patch(
            boot_images, "get_boot_images"
        ).return_value = self.fake_images
        fake_is_import_resources_running = self.patch(
            bootresources, "is_import_resources_running"
        )
        fake_is_import_resources_running.return_value = True
        images = rack_controller.list_boot_images()
        self.assertThat(fake_is_import_resources_running, MockCalledOnce())
        self.assertTrue(images["connected"])
        self.assertCountEqual(self.expected_images, images["images"])
        self.assertEqual("region-importing", images["status"])
        self.assertEqual(
            "region-importing", rack_controller.get_image_sync_status()
        )

    def test_list_boot_images_syncing(self):
        rack_controller = factory.make_RackController()
        self.patch(
            boot_images, "get_boot_images"
        ).return_value = self.fake_images
        self.patch(
            BootResource.objects, "boot_images_are_in_sync"
        ).return_value = False
        self.patch(
            rack_controller, "is_import_boot_images_running"
        ).return_value = True
        images = rack_controller.list_boot_images()
        self.assertTrue(images["connected"])
        self.assertCountEqual(self.expected_images, images["images"])
        self.assertEqual("syncing", images["status"])
        self.assertEqual("syncing", rack_controller.get_image_sync_status())

    def test_list_boot_images_out_of_sync(self):
        rack_controller = factory.make_RackController()
        self.patch(
            boot_images, "get_boot_images"
        ).return_value = self.fake_images
        self.patch(
            BootResource.objects, "boot_images_are_in_sync"
        ).return_value = False
        self.patch(
            rack_controller, "is_import_boot_images_running"
        ).return_value = False
        images = rack_controller.list_boot_images()
        self.assertTrue(images["connected"])
        self.assertCountEqual(self.expected_images, images["images"])
        self.assertEqual("out-of-sync", images["status"])
        self.assertEqual(
            "out-of-sync", rack_controller.get_image_sync_status()
        )

    def test_list_boot_images_when_empty(self):
        rack_controller = factory.make_RackController()
        self.patch(boot_images, "get_boot_images").return_value = []
        self.patch(
            BootResource.objects, "boot_images_are_in_sync"
        ).return_value = False
        self.patch(
            rack_controller, "is_import_boot_images_running"
        ).return_value = True
        images = rack_controller.list_boot_images()
        self.assertTrue(images["connected"])
        self.assertCountEqual([], images["images"])
        self.assertEqual("syncing", images["status"])

    def test_is_import_images_running(self):
        running = factory.pick_bool()
        rackcontroller = factory.make_RackController()
        self.useFixture(RegionEventLoopFixture("rpc"))
        self.useFixture(RunningEventLoopFixture())
        fixture = self.useFixture(MockLiveRegionToClusterRPCFixture())
        protocol = fixture.makeCluster(
            rackcontroller, IsImportBootImagesRunning
        )
        protocol.IsImportBootImagesRunning.return_value = defer.succeed(
            {"running": running}
        )
        self.assertEqual(
            running, rackcontroller.is_import_boot_images_running()
        )


class TestRegionController(MAASServerTestCase):
    def test_delete_prevented_when_running(self):
        region = factory.make_RegionController()
        factory.make_RegionControllerProcess(region=region)
        self.assertRaises(ValidationError, region.delete)

    def test_delete_converts_region_and_rack_to_rack(self):
        region_and_rack = factory.make_Node(
            node_type=NODE_TYPE.REGION_AND_RACK_CONTROLLER
        )
        region_and_rack.as_region_controller().delete()
        self.assertEqual(
            NODE_TYPE.RACK_CONTROLLER,
            Node.objects.get(system_id=region_and_rack.system_id).node_type,
        )

    def test_delete_converts_region_to_machine(self):
        region = factory.make_RegionController(status=NODE_STATUS.DEPLOYED)
        region.bmc = factory.make_BMC()
        region.save()
        region.delete()
        self.assertEqual(
            NODE_TYPE.MACHINE,
            Node.objects.get(system_id=region.system_id).node_type,
        )

    def test_delete(self):
        region = factory.make_RegionController()
        region.delete()
        self.assertIsNone(reload_object(region))


class TestControllerGetDiscoveryState(MAASServerTestCase):
    def test_gets_discovery_state_for_each_interface(self):
        rack = factory.make_RegionRackController(ifname="eth0")
        eth1 = factory.make_Interface(node=rack, name="eth1")
        factory.make_Interface(node=rack, name="eth2")
        monitoring_state = rack.get_discovery_state()
        self.assertIn("eth0", monitoring_state)
        self.assertIn("eth1", monitoring_state)
        self.assertIn("eth2", monitoring_state)
        self.assertEqual(eth1.get_discovery_state(), monitoring_state["eth1"])


class TestNodeGetHostedPods(MAASServerTestCase):
    def test_returns_queryset(self):
        node = factory.make_Node()
        pods = node.get_hosted_pods()
        self.assertIsInstance(pods, QuerySet)

    def test_returns_related_pods_by_ip(self):
        node = factory.make_Node_with_Interface_on_Subnet()
        ip = factory.make_StaticIPAddress(interface=node.boot_interface)
        pod = factory.make_Pod(ip_address=ip)
        pods = node.get_hosted_pods()
        self.assertIn(pod, pods)

    def test_returns_related_pods_by_association(self):
        pod = factory.make_Pod()
        node = factory.make_Node()
        pod.hints.nodes.add(node)
        pods = node.get_hosted_pods()
        self.assertIn(pod, pods)


class TestNodeStorageClone__MappingBetweenNodes(MAASServerTestCase):
    def test_identical_size_tags(self):
        node1 = factory.make_Node(with_boot_disk=False)
        node1_sda = factory.make_PhysicalBlockDevice(
            node=node1, size=8 * 1024**3, name="sda", tags=["hdd"]
        )
        node1_sdb = factory.make_PhysicalBlockDevice(
            node=node1, size=8 * 1024**3, name="sdb", tags=["sdd"]
        )
        node1_sdc = factory.make_PhysicalBlockDevice(
            node=node1, size=8 * 1024**3, name="sdc", tags=["sdd"]
        )
        node2 = factory.make_Node(with_boot_disk=False)
        node2_sda = factory.make_PhysicalBlockDevice(
            node=node2, size=8 * 1024**3, name="sda", tags=["hdd"]
        )
        node2_sdb = factory.make_PhysicalBlockDevice(
            node=node2, size=8 * 1024**3, name="sdb", tags=["sdd"]
        )
        node2_sdc = factory.make_PhysicalBlockDevice(
            node=node2, size=8 * 1024**3, name="sdc", tags=["sdd"]
        )
        self.assertEqual(
            {node2_sda: node1_sda, node2_sdb: node1_sdb, node2_sdc: node1_sdc},
            node2._get_storage_mapping_between_nodes(node1),
        )

    def test_larger_size_identical_tags(self):
        node1 = factory.make_Node(with_boot_disk=False)
        node1_sda = factory.make_PhysicalBlockDevice(
            node=node1, size=8 * 1024**3, name="sda", tags=["hdd"]
        )
        node1_sdb = factory.make_PhysicalBlockDevice(
            node=node1, size=8 * 1024**3, name="sdb", tags=["sdd", "match"]
        )
        node1_sdc = factory.make_PhysicalBlockDevice(
            node=node1, size=8 * 1024**3, name="sdc", tags=["sdd"]
        )
        node2 = factory.make_Node(with_boot_disk=False)
        node2_sda = factory.make_PhysicalBlockDevice(
            node=node2, size=8 * 1024**3, name="sda", tags=["hdd"]
        )
        node2_sdb = factory.make_PhysicalBlockDevice(
            node=node2, size=10 * 1024**3, name="sdb", tags=["sdd", "match"]
        )
        node2_sdc = factory.make_PhysicalBlockDevice(
            node=node2, size=8 * 1024**3, name="sdc", tags=["sdd"]
        )
        self.assertEqual(
            {node2_sda: node1_sda, node2_sdb: node1_sdb, node2_sdc: node1_sdc},
            node2._get_storage_mapping_between_nodes(node1),
        )

    def test_larger_size_diff_tags(self):
        node1 = factory.make_Node(with_boot_disk=False)
        node1_sda = factory.make_PhysicalBlockDevice(
            node=node1, size=8 * 1024**3, name="sda", tags=["hdd"]
        )
        node1_sdb = factory.make_PhysicalBlockDevice(
            node=node1, size=8 * 1024**3, name="sdb", tags=["sdd", "match"]
        )
        node1_sdc = factory.make_PhysicalBlockDevice(
            node=node1, size=8 * 1024**3, name="sdc", tags=["sdd"]
        )
        node2 = factory.make_Node(with_boot_disk=False)
        node2_sda = factory.make_PhysicalBlockDevice(
            node=node2, size=8 * 1024**3, name="sda", tags=["hdd"]
        )
        node2_sdb = factory.make_PhysicalBlockDevice(
            node=node2, size=10 * 1024**3, name="sdb", tags=["sdd", "other"]
        )
        node2_sdc = factory.make_PhysicalBlockDevice(
            node=node2, size=8 * 1024**3, name="sdc", tags=["diff"]
        )
        self.assertEqual(
            {node2_sda: node1_sda, node2_sdb: node1_sdc, node2_sdc: node1_sdb},
            node2._get_storage_mapping_between_nodes(node1),
        )

    def test_small_size_fails(self):
        node1 = factory.make_Node(with_boot_disk=False)
        factory.make_PhysicalBlockDevice(
            node=node1, size=8 * 1024**3, name="sda", tags=["hdd"]
        )
        factory.make_PhysicalBlockDevice(
            node=node1, size=8 * 1024**3, name="sdb", tags=["sdd", "match"]
        )
        factory.make_PhysicalBlockDevice(
            node=node1, size=8 * 1024**3, name="sdc", tags=["sdd"]
        )
        node2 = factory.make_Node(with_boot_disk=False)
        factory.make_PhysicalBlockDevice(
            node=node2, size=8 * 1024**3, name="sda", tags=["hdd"]
        )
        factory.make_PhysicalBlockDevice(
            node=node2, size=6 * 1024**3, name="sdb", tags=["sdd", "other"]
        )
        factory.make_PhysicalBlockDevice(
            node=node2, size=8 * 1024**3, name="sdc", tags=["diff"]
        )
        self.assertRaises(
            ValidationError, node2._get_storage_mapping_between_nodes, node1
        )


class TestNodeStorageClone_SimpleMBRLayout(
    MAASServerTestCase, AssertStorageConfigMixin
):
    STORAGE_CONFIG = dedent(
        """\
        config:
          - id: sda
            name: sda
            type: disk
            wipe: superblock
            ptable: msdos
            model: QEMU HARDDISK
            serial: QM00001
            grub_device: true
          - id: sda-part1
            name: sda-part1
            type: partition
            number: 1
            size: 536870912B
            device: sda
            wipe: superblock
            offset: 4194304B
            flag: boot
          - id: sda-part2
            name: sda-part2
            type: partition
            number: 2
            size: 1073741824B
            wipe: superblock
            device: sda
            flag: boot
          - id: sda-part3
            name: sda-part3
            type: partition
            number: 3
            size: 2684354560B
            wipe: superblock
            device: sda
          - id: sda-part4
            type: partition
            number: 4
            device: sda
            flag: extended
            size: 4287627264B
          - id: sda-part5
            name: sda-part5
            type: partition
            number: 5
            size: 2146435072B
            device: sda
            wipe: superblock
            flag: logical
          - id: sda-part6
            name: sda-part6
            type: partition
            number: 6
            size: 2138046464B
            device: sda
            wipe: superblock
            flag: logical
          - id: sda-part1_format
            type: format
            fstype: fat32
            label: efi
            volume: sda-part1
          - id: sda-part2_format
            type: format
            fstype: ext4
            label: boot
            volume: sda-part2
          - id: sda-part3_format
            type: format
            fstype: ext4
            label: root
            volume: sda-part3
          - id: sda-part5_format
            type: format
            fstype: ext4
            label: srv
            volume: sda-part5
          - id: sda-part6_format
            type: format
            fstype: ext4
            label: srv-data
            volume: sda-part6
          - id: sda-part3_mount
            type: mount
            path: /
            device: sda-part3_format
          - id: sda-part2_mount
            type: mount
            path: /boot
            options: rw,relatime,block_validity,barrier,acl
            device: sda-part2_format
          - id: sda-part1_mount
            type: mount
            path: /boot/efi
            options: rw,nosuid,nodev
            device: sda-part1_format
          - id: sda-part5_mount
            type: mount
            path: /srv
            options: rw,nosuid,nodev,noexec,relatime
            device: sda-part5_format
          - id: sda-part6_mount
            type: mount
            path: /srv/data
            options: rw,nosuid,nodev,noexec,relatime
            device: sda-part6_format
        """
    )

    def create_physical_disks(self, node):
        return factory.make_PhysicalBlockDevice(
            node=node,
            size=8 * 1024**3,
            name="sda",
            model="QEMU HARDDISK",
            serial="QM00001",
        )  # 8 GiB

    def test_copy(self):
        node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, with_boot_disk=False
        )
        boot_disk = self.create_physical_disks(node)
        partition_table = factory.make_PartitionTable(
            table_type=PARTITION_TABLE_TYPE.MBR, block_device=boot_disk
        )
        efi_partition = factory.make_Partition(
            partition_table=partition_table,
            uuid="6efc2c3d-bc9d-4ee5-a7ed-c6e1574d5398",
            size=512 * 1024**2,
            bootable=True,
        )
        boot_partition = factory.make_Partition(
            partition_table=partition_table,
            uuid="0c1c1c3a-1e9d-4047-8ef6-328a03d513e5",
            size=1 * 1024**3,
            bootable=True,
        )
        root_partition = factory.make_Partition(
            partition_table=partition_table,
            uuid="f74ff260-2a5b-4a36-b1b8-37f746b946bf",
            size=2.5 * 1024**3,
            bootable=False,
        )
        partition_five = factory.make_Partition(
            partition_table=partition_table,
            uuid="1b59e74f-6189-41a1-ba8e-fbf38df19820",
            size=2 * 1024**3,
            bootable=False,
        )
        partition_six = factory.make_Partition(
            partition_table=partition_table,
            uuid="8c365c80-900b-40a1-a8c7-1e445878d19a",
            size=(2 * 1024**3) - PARTITION_TABLE_EXTRA_SPACE,
            bootable=False,
        )
        factory.make_Filesystem(
            partition=efi_partition,
            fstype=FILESYSTEM_TYPE.FAT32,
            uuid="bf34f38c-02b7-4b4b-bb7c-e73521f9ead7",
            label="efi",
            mount_point="/boot/efi",
            mount_options="rw,nosuid,nodev",
        )
        factory.make_Filesystem(
            partition=boot_partition,
            fstype=FILESYSTEM_TYPE.EXT4,
            uuid="f98e5b7b-cbb1-437e-b4e5-1769f81f969f",
            label="boot",
            mount_point="/boot",
            mount_options="rw,relatime,block_validity,barrier,acl",
        )
        factory.make_Filesystem(
            partition=root_partition,
            fstype=FILESYSTEM_TYPE.EXT4,
            uuid="90a69b22-e281-4c5b-8df9-b09514f27ba1",
            label="root",
            mount_point="/",
            mount_options=None,
        )
        factory.make_Filesystem(
            partition=partition_five,
            fstype=FILESYSTEM_TYPE.EXT4,
            uuid="9c1764f0-2b48-4127-b719-ec61ac7d5f4c",
            label="srv",
            mount_point="/srv",
            mount_options="rw,nosuid,nodev,noexec,relatime",
        )
        factory.make_Filesystem(
            partition=partition_six,
            fstype=FILESYSTEM_TYPE.EXT4,
            uuid="bcac8449-3a45-4586-bdfb-c21e6ba47902",
            label="srv-data",
            mount_point="/srv/data",
            mount_options="rw,nosuid,nodev,noexec,relatime",
        )

        dest_node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, with_boot_disk=False
        )
        self.create_physical_disks(dest_node)
        dest_node.set_storage_configuration_from_node(node)

        node._create_acquired_filesystems()
        dest_node._create_acquired_filesystems()
        self.assertStorageConfig(
            self.STORAGE_CONFIG,
            compose_curtin_storage_config(node),
            strip_uuids=True,
        )
        self.assertStorageConfig(
            self.STORAGE_CONFIG,
            compose_curtin_storage_config(dest_node),
            strip_uuids=True,
        )


class TestNodeStorageClone_ComplexDiskLayout(
    MAASServerTestCase, AssertStorageConfigMixin
):
    STORAGE_CONFIG = dedent(
        """\
        config:
          - id: sda
            name: sda
            type: disk
            wipe: superblock
            ptable: gpt
            model: QEMU HARDDISK
            serial: QM00001
            grub_device: true
          - id: sdb
            name: sdb
            type: disk
            wipe: superblock
            ptable: gpt
            model: QEMU SSD
            serial: QM00002
          - id: sdc
            name: sdc
            type: disk
            wipe: superblock
            model: QEMU HARDDISK
            serial: QM00003
          - id: sdd
            name: sdd
            type: disk
            wipe: superblock
            model: QEMU HARDDISK
            serial: QM00004
          - id: sde
            name: sde
            type: disk
            wipe: superblock
            model: QEMU HARDDISK
            serial: QM00005
          - id: sdf
            name: sdf
            type: disk
            wipe: superblock
            model: QEMU HARDDISK
            serial: QM00006
          - id: sdg
            name: sdg
            type: disk
            wipe: superblock
            model: QEMU HARDDISK
            serial: QM00007
          - id: md0
            name: md0
            type: raid
            raidlevel: 5
            devices:
              - sdc
              - sdd
              - sde
            spare_devices:
              - sdf
              - sdg
            ptable: gpt
          - id: sda-part1
            name: sda-part1
            type: partition
            number: 1
            size: 536870912B
            device: sda
            wipe: superblock
            offset: 4194304B
            flag: boot
          - id: sda-part2
            name: sda-part2
            type: partition
            number: 2
            size: 1073741824B
            device: sda
            wipe: superblock
            flag: boot
          - id: sda-part3
            name: sda-part3
            type: partition
            number: 3
            size: 6970933248B
            device: sda
            wipe: superblock
          - id: sdb-part1
            name: sdb-part1
            type: partition
            number: 1
            offset: 4194304B
            size: 2139095040B
            wipe: superblock
            device: sdb
          - id: bcache0
            name: bcache0
            type: bcache
            backing_device: sda-part3
            cache_device: sdb-part1
            cache_mode: writethrough
          - id: sdb-part2
            name: sdb-part2
            type: partition
            number: 2
            size: 6442450944B
            wipe: superblock
            device: sdb
          - id: vgroot
            name: vgroot
            type: lvm_volgroup
            devices:
              - sdb-part2
          - id: vgroot-lvextra
            name: lvextra
            type: lvm_partition
            volgroup: vgroot
            size: 2147483648B
          - id: vgroot-lvroot
            name: lvroot
            type: lvm_partition
            volgroup: vgroot
            size: 2147483648B
          - id: md0-part1
            name: md0-part1
            type: partition
            number: 1
            offset: 4194304B
            size: 2199014866944B
            wipe: superblock
            device: md0
          - id: sda-part1_format
            type: format
            fstype: fat32
            label: efi
            volume: sda-part1
          - id: sda-part2_format
            type: format
            fstype: ext4
            label: boot
            volume: sda-part2
          - id: vgroot-lvroot_format
            type: format
            fstype: ext4
            label: root
            volume: vgroot-lvroot
          - id: md0-part1_format
            type: format
            fstype: ext4
            label: data
            volume: md0-part1
          - id: vgroot-lvroot_mount
            type: mount
            path: /
            options: rw,relatime,errors=remount-ro,data=random
            device: vgroot-lvroot_format
          - id: sda-part2_mount
            type: mount
            path: /boot
            options: rw,relatime,block_invalidity,barrier,user_xattr,acl
            device: sda-part2_format
          - id: sda-part1_mount
            type: mount
            path: /boot/efi
            options: rw,relatime,pids
            device: sda-part1_format
          - id: md0-part1_mount
            type: mount
            path: /srv/data
            device: md0-part1_format
        """
    )

    def create_physical_disks(self, node):
        boot_disk = factory.make_PhysicalBlockDevice(
            node=node,
            size=8 * 1024**3,
            name="sda",
            model="QEMU HARDDISK",
            serial="QM00001",
            tags=["hdd"],
        )  # 8 GiB
        ssd_disk = factory.make_PhysicalBlockDevice(
            node=node,
            size=8 * 1024**3,
            name="sdb",
            model="QEMU SSD",
            serial="QM00002",
            tags=["ssd"],
        )  # 8 GiB
        raid_5_disk_1 = factory.make_PhysicalBlockDevice(
            node=node,
            size=1 * 1024**4,
            name="sdc",
            model="QEMU HARDDISK",
            serial="QM00003",
            tags=["hdd"],
        )  # 1 TiB
        raid_5_disk_2 = factory.make_PhysicalBlockDevice(
            node=node,
            size=1 * 1024**4,
            name="sdd",
            model="QEMU HARDDISK",
            serial="QM00004",
            tags=["hdd"],
        )  # 1 TiB
        raid_5_disk_3 = factory.make_PhysicalBlockDevice(
            node=node,
            size=1 * 1024**4,
            name="sde",
            model="QEMU HARDDISK",
            serial="QM00005",
            tags=["hdd"],
        )  # 1 TiB
        raid_5_disk_4 = factory.make_PhysicalBlockDevice(
            node=node,
            size=1 * 1024**4,
            name="sdf",
            model="QEMU HARDDISK",
            serial="QM00006",
            tags=["hdd"],
        )  # 1 TiB
        raid_5_disk_5 = factory.make_PhysicalBlockDevice(
            node=node,
            size=1 * 1024**4,
            name="sdg",
            model="QEMU HARDDISK",
            serial="QM00007",
            tags=["hdd"],
        )  # 1 TiB
        return (
            boot_disk,
            ssd_disk,
            raid_5_disk_1,
            raid_5_disk_2,
            raid_5_disk_3,
            raid_5_disk_4,
            raid_5_disk_5,
        )

    def test_copy(self):
        node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED,
            bios_boot_method="uefi",
            with_boot_disk=False,
        )
        (
            boot_disk,
            ssd_disk,
            raid_5_disk_1,
            raid_5_disk_2,
            raid_5_disk_3,
            raid_5_disk_4,
            raid_5_disk_5,
        ) = self.create_physical_disks(node)
        boot_partition_table = factory.make_PartitionTable(
            table_type=PARTITION_TABLE_TYPE.GPT, block_device=boot_disk
        )
        efi_partition = factory.make_Partition(
            partition_table=boot_partition_table,
            uuid="6efc2c3d-bc9d-4ee5-a7ed-c6e1574d5398",
            size=512 * 1024**2,
            bootable=True,
        )
        boot_partition = factory.make_Partition(
            partition_table=boot_partition_table,
            uuid="0c1c1c3a-1e9d-4047-8ef6-328a03d513e5",
            size=1 * 1024**3,
            bootable=True,
        )
        root_partition = factory.make_Partition(
            partition_table=boot_partition_table,
            uuid="f74ff260-2a5b-4a36-b1b8-37f746b946bf",
            size=(6.5 * 1024**3) - PARTITION_TABLE_EXTRA_SPACE,
            bootable=False,
        )
        factory.make_Filesystem(
            partition=efi_partition,
            fstype=FILESYSTEM_TYPE.FAT32,
            uuid="bf34f38c-02b7-4b4b-bb7c-e73521f9ead7",
            label="efi",
            mount_point="/boot/efi",
            mount_options="rw,relatime,pids",
        )
        factory.make_Filesystem(
            partition=boot_partition,
            fstype=FILESYSTEM_TYPE.EXT4,
            uuid="f98e5b7b-cbb1-437e-b4e5-1769f81f969f",
            label="boot",
            mount_point="/boot",
            mount_options=(
                "rw,relatime,block_invalidity,barrier,user_xattr,acl"
            ),
        )
        ssd_partition_table = factory.make_PartitionTable(
            table_type=PARTITION_TABLE_TYPE.GPT, block_device=ssd_disk
        )
        cache_partition = factory.make_Partition(
            partition_table=ssd_partition_table,
            uuid="f3281144-a0b6-46f1-90af-8541f97f7b1f",
            size=(2 * 1024**3) - PARTITION_TABLE_EXTRA_SPACE,
            bootable=False,
        )
        cache_set = factory.make_CacheSet(partition=cache_partition)
        Bcache.objects.create_bcache(
            name="bcache0",
            uuid="9e7bdc2d-1567-4e1c-a89a-4e20df099458",
            backing_partition=root_partition,
            cache_set=cache_set,
            cache_mode=CACHE_MODE_TYPE.WRITETHROUGH,
        )
        lvm_partition = factory.make_Partition(
            partition_table=ssd_partition_table,
            uuid="ea7f96d0-b508-40d9-8495-b2163df35c9b",
            size=(6 * 1024**3),
            bootable=False,
        )
        vgroot = VolumeGroup.objects.create_volume_group(
            name="vgroot",
            uuid="1793be1b-890a-44cb-9322-057b0d53b53c",
            block_devices=[],
            partitions=[lvm_partition],
        )
        lvroot = vgroot.create_logical_volume(
            name="lvroot",
            uuid="98fac182-45a4-4afc-ba57-a1ace0396679",
            size=2 * 1024**3,
        )
        vgroot.create_logical_volume(
            name="lvextra",
            uuid="0d960ec6-e6d0-466f-8f83-ee9c11e5b9ba",
            size=2 * 1024**3,
        )
        factory.make_Filesystem(
            block_device=lvroot,
            fstype=FILESYSTEM_TYPE.EXT4,
            label="root",
            uuid="90a69b22-e281-4c5b-8df9-b09514f27ba1",
            mount_point="/",
            mount_options="rw,relatime,errors=remount-ro,data=random",
        )
        raid_5 = RAID.objects.create_raid(
            level=FILESYSTEM_GROUP_TYPE.RAID_5,
            name="md0",
            uuid="ec7816a7-129e-471e-9735-4e27c36fa10b",
            block_devices=[raid_5_disk_1, raid_5_disk_2, raid_5_disk_3],
            spare_devices=[raid_5_disk_4, raid_5_disk_5],
        )
        raid_5_partition_table = factory.make_PartitionTable(
            table_type=PARTITION_TABLE_TYPE.GPT,
            block_device=raid_5.virtual_device,
        )
        raid_5_partition = factory.make_Partition(
            partition_table=raid_5_partition_table,
            uuid="18a6e885-3e6d-4505-8a0d-cf34df11a8b0",
            size=(2 * 1024**4) - PARTITION_TABLE_EXTRA_SPACE,
            bootable=False,
        )
        factory.make_Filesystem(
            partition=raid_5_partition,
            fstype=FILESYSTEM_TYPE.EXT4,
            uuid="a8ad29a3-6083-45af-af8b-06ead59f108b",
            label="data",
            mount_point="/srv/data",
            mount_options=None,
        )

        dest_node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED,
            bios_boot_method="uefi",
            with_boot_disk=False,
        )
        self.create_physical_disks(dest_node)
        dest_node.set_storage_configuration_from_node(node)

        node._create_acquired_filesystems()
        dest_node._create_acquired_filesystems()
        self.assertStorageConfig(
            self.STORAGE_CONFIG,
            compose_curtin_storage_config(node),
            strip_uuids=True,
        )
        self.assertStorageConfig(
            self.STORAGE_CONFIG,
            compose_curtin_storage_config(dest_node),
            strip_uuids=True,
        )


class TestNodeStorageClone_SpecialFilesystems(
    MAASServerTestCase, AssertStorageConfigMixin
):
    STORAGE_CONFIG = dedent(
        """\
        config:
          - grub_device: true
            id: sda
            model: QEMU HARDDISK
            name: sda
            ptable: msdos
            serial: QM00001
            type: disk
            wipe: superblock
          - fstype: ramfs
            id: mnt-ramfs_mount
            path: /mnt/ramfs
            spec: ramfs
            type: mount
          - fstype: tmpfs
            id: mnt-tmpfs_mount
            path: /mnt/tmpfs
            spec: tmpfs
            options: noexec,size=1024k
            type: mount
    """
    )

    def create_physical_disks(self, node):
        return factory.make_PhysicalBlockDevice(
            node=node,
            size=8 * 1024**3,
            name="sda",
            model="QEMU HARDDISK",
            serial="QM00001",
        )

    def test_copy(self):
        node = factory.make_Node(with_boot_disk=False)
        self.create_physical_disks(node)
        factory.make_Filesystem(
            node_config=node.current_config,
            fstype="tmpfs",
            mount_options="noexec,size=1024k",
            mount_point="/mnt/tmpfs",
        )
        factory.make_Filesystem(
            node_config=node.current_config,
            fstype="ramfs",
            mount_options=None,
            mount_point="/mnt/ramfs",
        )

        dest_node = factory.make_Node(with_boot_disk=False)
        self.create_physical_disks(dest_node)
        dest_node.set_storage_configuration_from_node(node)

        node._create_acquired_filesystems()
        dest_node._create_acquired_filesystems()
        self.assertStorageConfig(
            self.STORAGE_CONFIG,
            compose_curtin_storage_config(node),
            strip_uuids=True,
        )
        self.assertStorageConfig(
            self.STORAGE_CONFIG,
            compose_curtin_storage_config(dest_node),
            strip_uuids=True,
        )


class TestNodeInterfaceClone__MappingBetweenNodes(MAASServerTestCase):
    def test_match_by_name(self):
        node1 = factory.make_Node()
        node1_eth0 = factory.make_Interface(node=node1, name="eth0")
        node1_ens3 = factory.make_Interface(node=node1, name="ens3")
        node1_br0 = factory.make_Interface(node=node1, name="br0")
        node2 = factory.make_Node()
        node2_eth0 = factory.make_Interface(node=node2, name="eth0")
        node2_ens3 = factory.make_Interface(node=node2, name="ens3")
        node2_br0 = factory.make_Interface(node=node2, name="br0")
        factory.make_Interface(node=node2, name="other")
        self.assertEqual(
            {
                node2_eth0: node1_eth0,
                node2_ens3: node1_ens3,
                node2_br0: node1_br0,
            },
            node2._get_interface_mapping_between_nodes(node1),
        )

    def test_fail_when_source_no_match(self):
        node1 = factory.make_Node()
        factory.make_Interface(node=node1, name="eth0")
        factory.make_Interface(node=node1, name="ens3")
        factory.make_Interface(node=node1, name="br0")
        factory.make_Interface(node=node1, name="other")
        factory.make_Interface(node=node1, name="match")
        node2 = factory.make_Node()
        factory.make_Interface(node=node2, name="eth0")
        factory.make_Interface(node=node2, name="ens3")
        factory.make_Interface(node=node2, name="br0")
        error = self.assertRaises(
            ValidationError, node2._get_interface_mapping_between_nodes, node1
        )
        self.assertEqual(
            "destination node physical interfaces do not match the "
            "source nodes physical interfaces: other, match",
            error.message,
        )


class TestNodeInterfaceClone__IPCloning(MAASServerTestCase):
    def test_auto_ip_assigned_on_clone_when_source_has_ip(self):
        node = factory.make_Node()
        node_eth0 = factory.make_Interface(node=node, name="eth0")
        node_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO, interface=node_eth0
        )
        self.assertIsNotNone(node_ip.ip)

        dest_node = factory.make_Node()
        dest_node_eth0 = factory.make_Interface(node=dest_node, name="eth0")
        dest_node.set_networking_configuration_from_node(node)
        dest_ip = dest_node_eth0.ip_addresses.first()
        self.assertIsNotNone(dest_ip.ip)
        self.assertNotEqual(node_ip.ip, dest_ip.ip)

    def test_auto_ip_unassigned_on_clone_when_source_has_no_ip(self):
        node = factory.make_Node()
        node_eth0 = factory.make_Interface(node=node, name="eth0")
        node_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO, interface=node_eth0, ip=None
        )
        self.assertIsNone(node_ip.ip)

        dest_node = factory.make_Node()
        dest_node_eth0 = factory.make_Interface(node=dest_node, name="eth0")
        dest_node.set_networking_configuration_from_node(node)
        dest_ip = dest_node_eth0.ip_addresses.first()
        self.assertIsNone(dest_ip.ip)

    def test_sticky_ip_assigned_on_clone(self):
        node = factory.make_Node()
        node_eth0 = factory.make_Interface(node=node, name="eth0")
        node_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, interface=node_eth0
        )
        self.assertIsNotNone(node_ip.ip)

        dest_node = factory.make_Node()
        dest_node_eth0 = factory.make_Interface(node=dest_node, name="eth0")
        dest_node.set_networking_configuration_from_node(node)
        dest_ip = dest_node_eth0.ip_addresses.first()
        self.assertIsNotNone(dest_ip.ip)
        self.assertNotEqual(node_ip.ip, dest_ip.ip)

    def test_user_reserved_ip_assigned_on_clone(self):
        user = factory.make_User()
        subnet = factory.make_Subnet()
        node = factory.make_Node()
        node_eth0 = factory.make_Interface(node=node, name="eth0")
        node_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.USER_RESERVED,
            interface=node_eth0,
            user=user,
            subnet=subnet,
        )
        self.assertIsNotNone(node_ip.ip)

        dest_node = factory.make_Node()
        dest_node_eth0 = factory.make_Interface(node=dest_node, name="eth0")
        dest_node.set_networking_configuration_from_node(node)
        dest_ip = dest_node_eth0.ip_addresses.first()
        self.assertIsNotNone(dest_ip.ip)
        self.assertNotEqual(node_ip.ip, dest_ip.ip)
        self.assertEqual(user, dest_ip.user)

    def test_dhcp_assigned_on_clone(self):
        node = factory.make_Node()
        node_eth0 = factory.make_Interface(node=node, name="eth0")
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.DHCP, interface=node_eth0, ip=None
        )

        dest_node = factory.make_Node()
        dest_node_eth0 = factory.make_Interface(node=dest_node, name="eth0")
        dest_node.set_networking_configuration_from_node(node)
        dest_ip = dest_node_eth0.ip_addresses.first()
        self.assertEqual(IPADDRESS_TYPE.DHCP, dest_ip.alloc_type)

    def test_discovered_not_assigned_on_clone(self):
        node = factory.make_Node()
        node_eth0 = factory.make_Interface(node=node, name="eth0")
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.DISCOVERED, interface=node_eth0
        )

        dest_node = factory.make_Node()
        dest_node_eth0 = factory.make_Interface(node=dest_node, name="eth0")
        dest_node.set_networking_configuration_from_node(node)
        dest_ip = dest_node_eth0.ip_addresses.first()
        self.assertIsNone(dest_ip)


class TestNodeInterfaceClone_SimpleNetworkLayout(
    MAASServerTestCase, AssertNetworkConfigMixin
):
    def create_staticipaddresses(self, node):
        for iface in node.current_config.interface_set.filter(enabled=True):
            factory.make_StaticIPAddress(
                interface=iface, subnet=iface.vlan.subnet_set.first()
            )
            iface.params = {
                "mtu": random.randint(600, 1400),
                "accept-ra": factory.pick_bool(),
            }
            iface.save()
        extra_interface = node.current_config.interface_set.all()[1]
        sip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip="",
            subnet=None,
            interface=extra_interface,
        )
        sip.subnet = None
        sip.save()

    def test_copy(self):
        # Keep them in the same domain to make the checking of configuraton
        # easy. A copy to destination doesn't move the destinations nodes
        # domain.
        domain = factory.make_Domain("bbb")
        node = factory.make_Node_with_Interface_on_Subnet(
            interface_count=2,
            ifname="eth0",
            extra_ifnames=["eth1"],
            domain=domain,
        )
        self.create_staticipaddresses(node)
        node_config = self.collect_interface_config(node)
        node_config += self.collect_dns_config(node)

        dest_node = factory.make_Node_with_Interface_on_Subnet(
            interface_count=2,
            ifname="eth0",
            extra_ifnames=["eth1"],
            domain=domain,
        )
        dest_node.set_networking_configuration_from_node(node)
        dest_config = self.collect_interface_config(dest_node)
        dest_config += self.collect_dns_config(dest_node)

        node_composed_config = compose_curtin_network_config(node)
        dest_composed_config = compose_curtin_network_config(dest_node)
        self.assertNetworkConfig(
            node_config, dest_composed_config, strip_macs=True, strip_ips=True
        )
        self.assertNetworkConfig(
            dest_config, node_composed_config, strip_macs=True, strip_ips=True
        )


class TestNodeInterfaceClone_VLANOnBondNetworkLayout(
    MAASServerTestCase, AssertNetworkConfigMixin
):
    def test_copy(self):
        domain = factory.make_Domain("bbb")
        node = factory.make_Node_with_Interface_on_Subnet(
            interface_count=2,
            ifname="eth0",
            extra_ifnames=["eth1"],
            domain=domain,
        )
        phys_ifaces = list(node.current_config.interface_set.all())
        phys_vlan = node.current_config.interface_set.first().vlan
        bond_iface = factory.make_Interface(
            iftype=INTERFACE_TYPE.BOND,
            node=node,
            vlan=phys_vlan,
            parents=phys_ifaces,
        )
        bond_iface.params = {"bond_mode": "balance-rr"}
        bond_iface.save()
        vlan_iface = factory.make_Interface(
            iftype=INTERFACE_TYPE.VLAN, node=node, parents=[bond_iface]
        )
        subnet = factory.make_Subnet(vlan=vlan_iface.vlan)
        factory.make_StaticIPAddress(interface=vlan_iface, subnet=subnet)
        node_config = self.collect_interface_config(node, filter="physical")
        node_config += self.collect_interface_config(node, filter="bond")
        node_config += self.collect_interface_config(node, filter="vlan")
        node_config += self.collect_dns_config(node)

        dest_node = factory.make_Node_with_Interface_on_Subnet(
            interface_count=2,
            ifname="eth0",
            extra_ifnames=["eth1"],
            domain=domain,
        )
        dest_node.set_networking_configuration_from_node(node)
        dest_config = self.collect_interface_config(
            dest_node, filter="physical"
        )
        dest_config += self.collect_interface_config(dest_node, filter="bond")
        dest_config += self.collect_interface_config(dest_node, filter="vlan")
        dest_config += self.collect_dns_config(dest_node)

        node_composed_config = compose_curtin_network_config(node)
        dest_composed_config = compose_curtin_network_config(dest_node)
        self.assertNetworkConfig(
            node_config, dest_composed_config, strip_macs=True, strip_ips=True
        )
        self.assertNetworkConfig(
            dest_config, node_composed_config, strip_macs=True, strip_ips=True
        )

        # Bond configuration should have different MAC addresses.
        node_bond = yaml.safe_load(
            self.collect_interface_config(node, filter="bond")
        )
        dest_bond = yaml.safe_load(
            self.collect_interface_config(dest_node, filter="bond")
        )
        self.assertNotEqual(
            node_bond[0]["mac_address"], dest_bond[0]["mac_address"]
        )


class TestNodeInterfaceClone_BridgeNetworkLayout(
    MAASServerTestCase, AssertNetworkConfigMixin
):
    def test_renders_expected_output(self):
        node = factory.make_Node_with_Interface_on_Subnet(ifname="eth0")
        boot_interface = node.get_boot_interface()
        vlan = boot_interface.vlan
        mac_address = factory.make_mac_address()
        bridge_iface = factory.make_Interface(
            iftype=INTERFACE_TYPE.BRIDGE,
            node=node,
            vlan=vlan,
            parents=[boot_interface],
            mac_address=mac_address,
        )
        bridge_iface.params = {"bridge_fd": 0, "bridge_stp": True}
        bridge_iface.save()
        factory.make_StaticIPAddress(
            interface=bridge_iface,
            alloc_type=IPADDRESS_TYPE.STICKY,
            subnet=bridge_iface.vlan.subnet_set.first(),
        )
        node_config = self.collect_interface_config(node, filter="physical")
        node_config += self.collect_interface_config(node, filter="bridge")
        node_config += self.collect_dns_config(node)

        dest_node = factory.make_Node_with_Interface_on_Subnet(ifname="eth0")
        dest_node.set_networking_configuration_from_node(node)
        dest_config = self.collect_interface_config(
            dest_node, filter="physical"
        )
        dest_config += self.collect_interface_config(
            dest_node, filter="bridge"
        )
        dest_config += self.collect_dns_config(dest_node)

        node_composed_config = compose_curtin_network_config(node)
        dest_composed_config = compose_curtin_network_config(dest_node)
        self.assertNetworkConfig(
            node_config, dest_composed_config, strip_macs=True, strip_ips=True
        )
        self.assertNetworkConfig(
            dest_config, node_composed_config, strip_macs=True, strip_ips=True
        )

        # Bridge configuration should have different MAC addresses.
        node_bridge = yaml.safe_load(
            self.collect_interface_config(node, filter="bridge")
        )
        dest_bridge = yaml.safe_load(
            self.collect_interface_config(dest_node, filter="bridge")
        )
        self.assertNotEqual(
            node_bridge[0]["mac_address"], dest_bridge[0]["mac_address"]
        )


class TestNodeClone__Prefetches(MAASServerTestCase):
    def test_node_with_prefetch(self):
        source = factory.make_Machine(with_boot_disk=False)
        disk = factory.make_PhysicalBlockDevice(
            node=source, size=8 * 1024**3, name="sda"
        )
        ptable = factory.make_PartitionTable(block_device=disk)
        part1 = ptable.add_partition(size=2 * 1024**3)
        factory.make_Filesystem(partition=part1)
        part2 = ptable.add_partition(size=3 * 1024**3)
        factory.make_Filesystem(partition=part2)
        factory.make_Interface(node=source, name="eth0")
        destination = factory.make_Machine(
            status=random.choice(
                [NODE_STATUS.READY, NODE_STATUS.FAILED_TESTING]
            ),
            with_boot_disk=False,
        )
        factory.make_PhysicalBlockDevice(
            node=destination, size=8 * 1024**3, name="sda"
        )
        factory.make_Interface(node=destination, name="eth0")
        source = Machine.objects.prefetch_related(
            (
                "current_config__"
                "blockdevice_set__"
                "physicalblockdevice__"
                "partitiontable_set__"
                "partitions__"
                "filesystem_set"
            ),
            "current_config__interface_set",
        ).get(id=source.id)
        destination.set_storage_configuration_from_node(source)
        destination.set_networking_configuration_from_node(source)
