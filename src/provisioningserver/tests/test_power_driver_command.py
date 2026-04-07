# Copyright 2020-2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for register command code."""


from argparse import ArgumentParser, Namespace

from twisted.internet import reactor
from twisted.internet.defer import ensureDeferred, inlineCallbacks

from maastesting import get_testing_timeout
from maastesting.testcase import MAASTestCase, MAASTwistedRunTest
from provisioningserver import power_driver_command
from provisioningserver.drivers.power import PowerDriver
from provisioningserver.drivers.power.hmcz import HMCZPowerDriver


class FakeDriver(PowerDriver):
    # These are required by the base class, but unused in this test.
    chassis = False
    can_probe = False
    can_set_boot_order = False
    description = None
    detect_missing_packages = None
    ip_extractor = None
    name = None
    settings = []
    _state = "off"

    def __init__(self):
        super().__init__()
        self.calls = {"set_boot_order": []}

    def power_on(self, *args, **kwargs):
        self._state = "on"

    def power_off(self, *args, **kwargs):
        self._state = "off"

    def power_query(self, *args, **kwargs):
        return self._state


class FakeHMCZDriver(FakeDriver):
    can_set_boot_order = True
    settings = HMCZPowerDriver.settings

    async def set_boot_order(self, system_id, context, order):
        self.calls["set_boot_order"].append(
            {
                "system_id": system_id,
                "context": context,
                "order": order,
            }
        )


class TestPowerDriverCommand(MAASTestCase):
    run_tests_with = MAASTwistedRunTest.make_factory(
        timeout=get_testing_timeout()
    )

    @inlineCallbacks
    def test_run_set_boot_order_hmcz_uses_split_order(self):
        args = power_driver_command._parse_args(
            [
                "set-boot-order",
                "hmcz",
                "--power-address",
                "hmc.example",
                "--power-user",
                "maas",
                "--power-pass",
                "secret",
                "--power-partition-name",
                "partition-1",
                "--power-verify-ssl",
                "y",
            ]
        )
        args.order = "pxe,disk"

        driver = FakeHMCZDriver()
        status = yield ensureDeferred(
            power_driver_command._run(reactor, args, {"hmcz": driver})
        )

        self.assertEqual(status, "off")
        self.assertEqual(len(driver.calls["set_boot_order"]), 1)
        set_boot_order_call = driver.calls["set_boot_order"][0]
        self.assertEqual(set_boot_order_call["system_id"], None)
        self.assertEqual(set_boot_order_call["order"], ["pxe", "disk"])
        self.assertEqual(
            set_boot_order_call["context"],
            {
                "power_address": "hmc.example",
                "power_user": "maas",
                "power_pass": "secret",
                "power_partition_name": "partition-1",
                "power_verify_ssl": "y",
            },
        )

    def test_create_subparser(self):
        parser = ArgumentParser()
        driver_settings = [
            {
                "name": "password",
                "label": "Password",
                "required": True,
                "choices": [],
            },
            {
                "name": "version",
                "label": "Driver Version",
                "required": True,
                "field_type": "choice",
                "choices": [("1", "one"), ("2", "two")],
            },
            {
                "name": "multi_flag",
                "label": "Multiple flags",
                "required": True,
                "field_type": "multiple_choice",
                "choices": [("1", "one"), ("2", "two")],
            },
        ]

        power_driver_command._create_subparser(driver_settings, parser)

        args = parser.parse_args(
            ["--password", "pass", "--version", "1", "--multi-flag", "1"]
        )

        self.assertEqual(args.password, "pass")
        self.assertEqual(args.version, "1")
        self.assertEqual(args.multi_flag, ["1"])

    def test_parse_args_virsh(self):
        args = power_driver_command._parse_args(
            [
                "on",
                "virsh",
                "--power-address",
                "qemu+ssh://ubuntu@$KVM_HOST/system",
                "--power-id",
                "power_id",
            ]
        )

        self.assertEqual(args.command, "on")
        self.assertEqual(args.driver, "virsh")
        self.assertEqual(
            args.power_address, "qemu+ssh://ubuntu@$KVM_HOST/system"
        )
        self.assertEqual(args.power_id, "power_id")

    def test_parse_args_ipmi(self):
        """Test parsing args with ipmi, as it includes settings with defined choices"""

        args = power_driver_command._parse_args(
            [
                "on",
                "ipmi",
                "--power-address",
                "power_address",
                "--power-driver",
                "LAN_2_0",
                "--workaround-flags",
                "opensesspriv",
                "--workaround-flags",
                "authcap",
                "--power-off-mode",
                "hard",
            ]
        )

        self.assertEqual(args.command, "on")
        self.assertEqual(args.driver, "ipmi")
        self.assertEqual(args.power_address, "power_address")
        self.assertEqual(args.power_driver, "LAN_2_0")
        self.assertEqual(args.workaround_flags, ["opensesspriv", "authcap"])

    @inlineCallbacks
    def test_run(self):
        args = Namespace()
        args.command = "on"
        args.driver = "fake"

        driver = FakeDriver()
        registry = {"fake": driver}

        status = yield ensureDeferred(
            power_driver_command._run(reactor, args, registry)
        )
        self.assertEqual("on", status)
