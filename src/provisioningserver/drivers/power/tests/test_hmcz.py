# Copyright 2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.drivers.power.hmcz`."""

from dataclasses import dataclass
import json
import random
import typing
from unittest.mock import Mock

import pytest
from twisted.internet.defer import inlineCallbacks, returnValue, succeed
from zhmcclient import StatusTimeout
from zhmcclient_mock import FakedSession

from maastesting import get_testing_timeout
from maastesting.factory import factory
from maastesting.matchers import (
    MockCalledOnce,
    MockCalledOnceWith,
    MockNotCalled,
)
from maastesting.testcase import MAASTestCase, MAASTwistedRunTest
from provisioningserver.drivers.power import hmcz as hmcz_module
from provisioningserver.drivers.power import PowerActionError, PowerError
from provisioningserver.rpc import clusterservice, region
from provisioningserver.rpc.testing import MockLiveClusterToRegionRPCFixture

TIMEOUT = get_testing_timeout()


class TestHMCZPowerDriver(MAASTestCase):
    run_tests_with = MAASTwistedRunTest.make_factory(timeout=TIMEOUT)

    def setUp(self):
        super().setUp()
        self.power_address = factory.make_ip_address()
        self.fake_session = FakedSession(
            self.power_address,
            factory.make_name("hmc_name"),
            # The version and API version below were taken from
            # the test environment given by IBM.
            "2.14.1",
            "2.40",
        )
        self.patch(hmcz_module, "Session").return_value = self.fake_session
        self.hmcz = hmcz_module.HMCZPowerDriver()

    def make_context(self, power_partition_name=None):
        if power_partition_name is None:
            power_partition_name = factory.make_name("power_partition_name")
        return {
            "power_address": self.power_address,
            "power_user": factory.make_name("power_user"),
            "power_pass": factory.make_name("power_pass"),
            "power_partition_name": power_partition_name,
        }

    def test_detect_missing_packages(self):
        hmcz_module.no_zhmcclient = False
        self.assertEqual([], self.hmcz.detect_missing_packages())

    def test_detect_missing_packages_missing(self):
        hmcz_module.no_zhmcclient = True
        self.assertEqual(
            ["python3-zhmcclient"], self.hmcz.detect_missing_packages()
        )

    def test_get_partition(self):
        power_partition_name = factory.make_name("power_partition_name")
        cpc = self.fake_session.hmc.cpcs.add(
            {
                "name": factory.make_name("cpc"),
                "dpm-enabled": True,
            }
        )
        cpc.partitions.add({"name": power_partition_name})

        self.assertEqual(
            power_partition_name,
            self.hmcz._get_partition(
                self.make_context(power_partition_name)
            ).get_property("name"),
        )

    def test_get_partition_ignores_cpcs_with_no_dpm(self):
        mock_logger = self.patch(hmcz_module.maaslog, "warning")
        power_partition_name = factory.make_name("power_partition_name")
        self.fake_session.hmc.cpcs.add(
            {
                "name": factory.make_name("cpc"),
                "dpm-enabled": False,
            }
        )
        cpc = self.fake_session.hmc.cpcs.add({"dpm-enabled": True})
        cpc.partitions.add({"name": power_partition_name})

        self.assertEqual(
            power_partition_name,
            self.hmcz._get_partition(
                self.make_context(power_partition_name)
            ).get_property("name"),
        )
        self.assertThat(mock_logger, MockCalledOnce())

    def test_get_partition_doesnt_find_partition(self):
        cpc = self.fake_session.hmc.cpcs.add(
            {
                "name": factory.make_name("cpc"),
                "dpm-enabled": True,
            }
        )
        cpc.partitions.add({"name": factory.make_name("power_partition_name")})

        self.assertRaises(
            PowerActionError, self.hmcz._get_partition, self.make_context()
        )

    # zhmcclient_mock doesn't currently support async so MagicMock
    # must be used for power on/off

    @inlineCallbacks
    def test_power_on(self):
        mock_get_partition = self.patch(self.hmcz, "_get_partition")
        yield self.hmcz.power_on(None, self.make_context())
        self.assertThat(
            mock_get_partition.return_value.stop,
            MockNotCalled(),
        )
        self.assertThat(
            mock_get_partition.return_value.start,
            MockCalledOnceWith(wait_for_completion=False),
        )

    @inlineCallbacks
    def test_power_on_stops_in_a_paused_state(self):
        mock_get_partition = self.patch(self.hmcz, "_get_partition")
        mock_get_partition.return_value.get_property.return_value = "paused"
        yield self.hmcz.power_on(None, self.make_context())
        self.assertThat(
            mock_get_partition.return_value.stop,
            MockCalledOnceWith(wait_for_completion=True),
        )
        self.assertThat(
            mock_get_partition.return_value.start,
            MockCalledOnceWith(wait_for_completion=False),
        )

    @inlineCallbacks
    def test_power_on_stops_in_a_terminated_state(self):
        mock_get_partition = self.patch(self.hmcz, "_get_partition")
        mock_get_partition.return_value.get_property.return_value = (
            "terminated"
        )
        yield self.hmcz.power_on(None, self.make_context())
        self.assertThat(
            mock_get_partition.return_value.stop,
            MockCalledOnceWith(wait_for_completion=True),
        )
        self.assertThat(
            mock_get_partition.return_value.start,
            MockCalledOnceWith(wait_for_completion=False),
        )

    @inlineCallbacks
    def test_power_on_waits_for_stopping_state(self):
        mock_get_partition = self.patch(self.hmcz, "_get_partition")
        mock_get_partition.return_value.get_property.return_value = "stopping"
        yield self.hmcz.power_on(None, self.make_context())
        mock_get_partition.return_value.wait_for_status.assert_called_once_with(
            "stopped", 120
        )
        mock_get_partition.return_value.start.assert_called_once_with(
            wait_for_completion=False
        )

    @inlineCallbacks
    def test_power_on_times_out_waiting_for_stopping_state(self):
        mock_get_partition = self.patch(self.hmcz, "_get_partition")
        mock_get_partition.return_value.get_property.return_value = "stopping"
        mock_get_partition.return_value.wait_for_status.side_effect = (
            StatusTimeout(None, None, None, None)
        )
        with pytest.raises(PowerError):
            yield self.hmcz.power_on(None, self.make_context())

    @inlineCallbacks
    def test_power_off(self):
        mock_get_partition = self.patch(self.hmcz, "_get_partition")
        yield self.hmcz.power_off(None, self.make_context())
        self.assertThat(
            mock_get_partition.return_value.stop,
            MockCalledOnceWith(wait_for_completion=False),
        )

    @inlineCallbacks
    def test_power_off_waits_for_starting_state(self):
        mock_get_partition = self.patch(self.hmcz, "_get_partition")
        mock_get_partition.return_value.get_property.return_value = "starting"
        yield self.hmcz.power_off(None, self.make_context())
        mock_get_partition.return_value.wait_for_status.assert_called_once_with(
            "active", 120
        )
        mock_get_partition.return_value.stop.assert_called_once_with(
            wait_for_completion=False
        )

    @inlineCallbacks
    def test_power_off_timesout_waiting_for_stopping_state(self):
        mock_get_partition = self.patch(self.hmcz, "_get_partition")
        mock_get_partition.return_value.get_property.return_value = "starting"
        mock_get_partition.return_value.wait_for_status.side_effect = (
            StatusTimeout(None, None, None, None)
        )
        with pytest.raises(PowerError):
            yield self.hmcz.power_off(None, self.make_context())

    @inlineCallbacks
    def test_power_query_starting(self):
        power_partition_name = factory.make_name("power_partition_name")
        cpc = self.fake_session.hmc.cpcs.add(
            {
                "name": factory.make_name("cpc"),
                "dpm-enabled": True,
            }
        )
        cpc.partitions.add(
            {
                "name": power_partition_name,
                "status": "starting",
            }
        )

        status = yield self.hmcz.power_query(
            None, self.make_context(power_partition_name)
        )

        self.assertEqual("on", status)

    @inlineCallbacks
    def test_power_query_active(self):
        power_partition_name = factory.make_name("power_partition_name")
        cpc = self.fake_session.hmc.cpcs.add(
            {
                "name": factory.make_name("cpc"),
                "dpm-enabled": True,
            }
        )
        cpc.partitions.add(
            {
                "name": power_partition_name,
                "status": "active",
            }
        )

        status = yield self.hmcz.power_query(
            None, self.make_context(power_partition_name)
        )

        self.assertEqual("on", status)

    @inlineCallbacks
    def test_power_query_degraded(self):
        power_partition_name = factory.make_name("power_partition_name")
        cpc = self.fake_session.hmc.cpcs.add(
            {
                "name": factory.make_name("cpc"),
                "dpm-enabled": True,
            }
        )
        cpc.partitions.add(
            {
                "name": power_partition_name,
                "status": "degraded",
            }
        )

        status = yield self.hmcz.power_query(
            None, self.make_context(power_partition_name)
        )

        self.assertEqual("on", status)

    @inlineCallbacks
    def test_power_query_stopping(self):
        power_partition_name = factory.make_name("power_partition_name")
        cpc = self.fake_session.hmc.cpcs.add(
            {
                "name": factory.make_name("cpc"),
                "dpm-enabled": True,
            }
        )
        cpc.partitions.add(
            {
                "name": power_partition_name,
                "status": "stopping",
            }
        )

        status = yield self.hmcz.power_query(
            None, self.make_context(power_partition_name)
        )

        self.assertEqual("off", status)

    @inlineCallbacks
    def test_power_query_stopped(self):
        power_partition_name = factory.make_name("power_partition_name")
        cpc = self.fake_session.hmc.cpcs.add(
            {
                "name": factory.make_name("cpc"),
                "dpm-enabled": True,
            }
        )
        cpc.partitions.add(
            {
                "name": power_partition_name,
                "status": "stopped",
            }
        )

        status = yield self.hmcz.power_query(
            None, self.make_context(power_partition_name)
        )

        self.assertEqual("off", status)

    @inlineCallbacks
    def test_power_query_paused(self):
        power_partition_name = factory.make_name("power_partition_name")
        cpc = self.fake_session.hmc.cpcs.add(
            {
                "name": factory.make_name("cpc"),
                "dpm-enabled": True,
            }
        )
        cpc.partitions.add(
            {
                "name": power_partition_name,
                "status": "paused",
            }
        )

        status = yield self.hmcz.power_query(
            None, self.make_context(power_partition_name)
        )

        self.assertEqual("off", status)

    @inlineCallbacks
    def test_power_query_terminated(self):
        power_partition_name = factory.make_name("power_partition_name")
        cpc = self.fake_session.hmc.cpcs.add(
            {
                "name": factory.make_name("cpc"),
                "dpm-enabled": True,
            }
        )
        cpc.partitions.add(
            {
                "name": power_partition_name,
                "status": "terminated",
            }
        )

        status = yield self.hmcz.power_query(
            None, self.make_context(power_partition_name)
        )

        self.assertEqual("off", status)

    @inlineCallbacks
    def test_power_query_other(self):
        power_partition_name = factory.make_name("power_partition_name")
        cpc = self.fake_session.hmc.cpcs.add(
            {
                "name": factory.make_name("cpc"),
                "dpm-enabled": True,
            }
        )
        cpc.partitions.add(
            {
                "name": power_partition_name,
                "status": factory.make_name("status"),
            }
        )

        status = yield self.hmcz.power_query(
            None, self.make_context(power_partition_name)
        )

        self.assertEqual("unknown", status)

    @inlineCallbacks
    def test_set_boot_order_network(self):
        power_partition_name = factory.make_name("power_partition_name")
        mac_address = factory.make_mac_address()
        cpc = self.fake_session.hmc.cpcs.add(
            {
                "name": factory.make_name("cpc"),
                "dpm-enabled": True,
            }
        )
        partition = cpc.partitions.add(
            {
                "name": power_partition_name,
                "status": "terminated",
            }
        )
        partition.nics.add({"mac-address": factory.make_mac_address()})
        nic = partition.nics.add({"mac-address": mac_address})

        yield self.hmcz.set_boot_order(
            None,
            self.make_context(power_partition_name),
            [
                {
                    "id": random.randint(0, 100),
                    "name": factory.make_name("name"),
                    "mac_address": mac_address,
                    "vendor": factory.make_name("vendor"),
                    "product": factory.make_name("product"),
                }
            ]
            + [
                {
                    factory.make_name("key"): factory.make_name("value")
                    for _ in range(5)
                }
                for _ in range(5)
            ],
        )

        self.assertEqual(
            "network-adapter", partition.properties["boot-device"]
        )
        self.assertEqual(nic.uri, partition.properties["boot-network-device"])

    @inlineCallbacks
    def test_set_boot_order_storage_volume(self):
        # zhmcclient_mock doesn't support storage groups.
        serial = factory.make_UUID()
        mock_storage_group = Mock()
        mock_storage_group.storage_volumes.find.return_value.uri = serial
        mock_partition = Mock()
        mock_partition.list_attached_storage_groups.return_value = [
            mock_storage_group,
        ]
        mock_get_partition = self.patch(self.hmcz, "_get_partition")
        mock_get_partition.return_value = mock_partition

        yield self.hmcz.set_boot_order(
            None,
            self.make_context(),
            [
                {
                    "id": random.randint(0, 100),
                    "name": factory.make_name("name"),
                    "id_path": factory.make_name("id_path"),
                    "model": factory.make_name("model"),
                    "serial": serial,
                }
            ]
            + [
                {
                    factory.make_name("key"): factory.make_name("value")
                    for _ in range(5)
                }
                for _ in range(5)
            ],
        )

        mock_partition.update_properties.assert_called_once_with(
            {
                "boot-device": "storage-volume",
                "boot-storage-volume": serial,
            }
        )

    @inlineCallbacks
    def test_set_boot_order_waits_for_starting_state(self):
        # Mock must be used as partition.wait_for_status() hangs when not
        # connected to a real HMC
        mock_get_partition = self.patch(self.hmcz, "_get_partition")
        mock_get_partition.return_value.get_property.return_value = "starting"

        yield self.hmcz.set_boot_order(
            None,
            self.make_context(),
            [{"mac_address": factory.make_mac_address()}],
        )

        mock_get_partition.return_value.wait_for_status.assert_called_once_with(
            ["stopped", "active"], 120
        )

    @inlineCallbacks
    def test_set_boot_order_waits_for_stopping_state(self):
        # Mock must be used as partition.wait_for_status() hangs when not
        # connected to a real HMC
        mock_get_partition = self.patch(self.hmcz, "_get_partition")
        mock_get_partition.return_value.get_property.return_value = "stopping"

        yield self.hmcz.set_boot_order(
            None,
            self.make_context(),
            [{"mac_address": factory.make_mac_address()}],
        )

        mock_get_partition.return_value.wait_for_status.assert_called_once_with(
            ["stopped", "active"], 120
        )


@dataclass
class FakeNode:
    architecture: str
    power_type: str
    power_parameters: dict
    mac_addresses: typing.List[str]
    domain: str
    hostname: str
    status: str
    owner: str


class FakeRPCService:
    def __init__(self, testcase):
        self.testcase = testcase
        self.nodes = {}

    @inlineCallbacks
    def set_up(self):
        fixture = self.testcase.useFixture(MockLiveClusterToRegionRPCFixture())
        self.protocol, connecting = fixture.makeEventLoop(
            region.CreateNode, region.CommissionNode
        )
        self.testcase.addCleanup((yield connecting))
        self.protocol.CreateNode.side_effect = self.create_node
        self.protocol.CommissionNode.side_effect = self.commission_node

    @region.CreateNode.responder
    def create_node(
        self,
        protocol,
        architecture,
        power_type,
        power_parameters,
        mac_addresses,
        domain=None,
        hostname=None,
    ):
        system_id = factory.make_name("system_id")
        self.nodes[system_id] = FakeNode(
            architecture,
            power_type,
            json.loads(power_parameters),
            mac_addresses,
            domain,
            hostname,
            "new",
            None,
        )
        return succeed({"system_id": system_id})

    @region.CommissionNode.responder
    def commission_node(
        self,
        protocol,
        system_id,
        user,
    ):
        self.nodes[system_id].status = "commissioning"
        self.nodes[system_id].owner = user
        return succeed({})


class TestProbeHMCZAndEnlist(MAASTestCase):
    run_tests_with = MAASTwistedRunTest.make_factory(timeout=TIMEOUT)

    def setUp(self):
        super().setUp()
        self.patch(
            clusterservice, "get_all_interfaces_definition"
        ).return_value = {}
        self.user = factory.make_name("user")
        self.hostname = factory.make_ip_address()
        self.username = factory.make_name("username")
        self.password = factory.make_name("password")
        self.domain = factory.make_name("domain")
        self.fake_session = FakedSession(
            self.hostname,
            factory.make_name("hmc_name"),
            # The version and API version below were taken from
            # the test environment given by IBM.
            "2.14.1",
            "2.40",
        )
        self.patch(hmcz_module, "Session").return_value = self.fake_session

        # Add a CPC which does not have dpm enabled to verify its ignored.
        cpc = self.fake_session.hmc.cpcs.add(
            {
                "name": factory.make_name("cpc"),
                "dpm-enabled": False,
            }
        )
        cpc.partitions.add(
            {
                "name": factory.make_name("partition"),
                "status": "stopped",
            }
        )

        cpc = self.fake_session.hmc.cpcs.add(
            {
                "name": factory.make_name("cpc"),
                "dpm-enabled": True,
            }
        )
        self.partitions = {}
        for i in range(3):
            partition_name = f"partition_{i}"
            partition = cpc.partitions.add(
                {
                    "name": partition_name,
                    "status": "stopped",
                }
            )
            macs = [factory.make_mac_address() for _ in range(2)]
            for mac in macs:
                partition.nics.add({"mac-address": mac})
            self.partitions[partition_name] = macs

    @inlineCallbacks
    def create_fake_rpc_service(self):
        rpc = FakeRPCService(self)
        yield rpc.set_up()
        returnValue(rpc)

    def assertRPC(self, rpc, status, partition_names=None):
        if partition_names:
            partitions_len = len(partition_names)
        else:
            partitions_len = len(self.partitions)
        self.assertEqual(partitions_len, len(rpc.nodes))
        for partition_name, macs in self.partitions.items():
            if partition_names and partition_name not in partition_names:
                continue
            [node] = [
                node
                for node in rpc.nodes.values()
                if node.power_parameters["power_partition_name"]
                == partition_name
            ]
            self.assertCountEqual(macs, node.mac_addresses)
            self.assertEqual(node.status, status)

    @inlineCallbacks
    def test_probe_hmcz_and_enlist(self):
        rpc = yield self.create_fake_rpc_service()
        yield hmcz_module.probe_hmcz_and_enlist(
            self.user,
            self.hostname,
            self.username,
            self.password,
            accept_all=False,
            domain=self.domain,
        )
        self.assertRPC(rpc, "new")

    @inlineCallbacks
    def test_probe_hmcz_and_enlist_filters(self):
        rpc = yield self.create_fake_rpc_service()
        partition_name = random.choice(list(self.partitions.keys()))
        yield hmcz_module.probe_hmcz_and_enlist(
            self.user,
            self.hostname,
            self.username,
            self.password,
            accept_all=False,
            domain=self.domain,
            prefix_filter=partition_name,
        )
        self.assertRPC(rpc, "new", [partition_name])

    @inlineCallbacks
    def test_probe_hmcz_and_enlist_commissions(self):
        rpc = yield self.create_fake_rpc_service()
        yield hmcz_module.probe_hmcz_and_enlist(
            self.user,
            self.hostname,
            self.username,
            self.password,
            accept_all=True,
            domain=self.domain,
        )
        self.assertRPC(rpc, "commissioning")
