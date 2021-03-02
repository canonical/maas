# Copyright 2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.drivers.power.hmcz`."""

from twisted.internet.defer import inlineCallbacks
from zhmcclient_mock import FakedSession

from maastesting.factory import factory
from maastesting.matchers import (
    MockCalledOnce,
    MockCalledOnceWith,
    MockNotCalled,
)
from maastesting.testcase import MAASTestCase, MAASTwistedRunTest
from provisioningserver.drivers.power import hmcz as hmcz_module
from provisioningserver.drivers.power import PowerActionError


class TestHMCZPowerDriver(MAASTestCase):

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

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
    def test_power_off(self):
        mock_get_partition = self.patch(self.hmcz, "_get_partition")
        yield self.hmcz.power_off(None, self.make_context())
        self.assertThat(
            mock_get_partition.return_value.stop,
            MockCalledOnceWith(wait_for_completion=False),
        )

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
