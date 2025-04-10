# Copyright 2020-2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for register command code."""

from argparse import ArgumentParser, Namespace
from collections import defaultdict

from testtools import ExpectedException
from twisted.internet import reactor
from twisted.internet.defer import ensureDeferred, inlineCallbacks

from maastesting import get_testing_timeout
from maastesting.testcase import MAASTestCase, MAASTwistedRunTest
from provisioningserver import power_driver_command
from provisioningserver.drivers.power import PowerDriver


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

    calls = defaultdict(list)

    def __init__(self, clock=reactor):
        super().__init__(clock)
        self.calls = defaultdict(list)

    def power_on(self, *args, **kwargs):
        self._state = "on"
        self.calls["power_on"].append(True)

    def power_off(self, *args, **kwargs):
        self._state = "off"
        self.calls["power_off"].append(True)

    def power_query(self, *args, **kwargs):
        self.calls["power_query"].append(True)
        return self._state

    def power_cycle(self, *args, **kwargs):
        self._state = "on"
        self.calls["power_cycle"].append(True)

    def power_reset(self, *args, **kwargs):
        self._state = "on"
        self.calls["power_reset"].append(True)


class TestPowerDriverCommand(MAASTestCase):
    run_tests_with = MAASTwistedRunTest.make_factory(
        timeout=get_testing_timeout()
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

    def test_parse_args_dpu(self):
        """
        Ensure the `--is-dpu` flag is set correctly when given.
        """

        args = power_driver_command._parse_args(
            [
                "reset",
                "--is-dpu",
                "redfish",
                "--power-address",
                "addr",
                "--power-user",
                "maas",
                "--power-pass",
                "maas",
            ]
        )

        self.assertEqual(args.command, "reset")
        self.assertEqual(args.is_dpu, True)
        self.assertEqual(args.driver, "redfish")
        self.assertEqual(args.power_address, "addr")
        self.assertEqual(args.power_user, "maas")
        self.assertEqual(args.power_pass, "maas")

    @inlineCallbacks
    def test_dpu_calls_reset_on_power_reset(self):
        args = Namespace()
        args.command = "reset"
        args.driver = "fake"
        args.is_dpu = True

        driver = FakeDriver()
        registry = {"fake": driver}

        status = yield ensureDeferred(
            power_driver_command._run(reactor, args, registry)
        )

        self.assertEqual(status, "on")
        self.assertEqual(len(driver.calls["power_reset"]), 1)

    @inlineCallbacks
    def test_dpu_calls_reset_on_power_on(self):
        args = Namespace()
        args.command = "on"
        args.driver = "fake"
        args.is_dpu = True

        driver = FakeDriver()
        registry = {"fake": driver}

        status = yield ensureDeferred(
            power_driver_command._run(reactor, args, registry)
        )

        self.assertEqual(status, "on")
        self.assertEqual(len(driver.calls["power_on"]), 0)
        self.assertEqual(len(driver.calls["power_reset"]), 1)

    @inlineCallbacks
    def test_dpu_calls_reset_on_power_cycle(self):
        args = Namespace()
        args.command = "cycle"
        args.driver = "fake"
        args.is_dpu = True

        driver = FakeDriver()
        registry = {"fake": driver}

        status = yield ensureDeferred(
            power_driver_command._run(reactor, args, registry)
        )

        self.assertEqual(status, "on")
        self.assertEqual(len(driver.calls["power_cycle"]), 0)
        self.assertEqual(len(driver.calls["power_reset"]), 1)

    @inlineCallbacks
    def test_dpu_invalid_command_raises_error(self):
        args = Namespace()
        args.command = "off"
        args.driver = "fake"
        args.is_dpu = True

        driver = FakeDriver()
        registry = {"fake": driver}

        with ExpectedException(
            power_driver_command.InvalidDPUCommandError,
            f"Invalid power command to send to DPU: {args.command}",
        ):
            _ = yield ensureDeferred(
                power_driver_command._run(reactor, args, registry)
            )

    @inlineCallbacks
    def test_run(self):
        args = Namespace()
        args.command = "on"
        args.driver = "fake"
        args.is_dpu = False

        driver = FakeDriver()
        registry = {"fake": driver}

        status = yield ensureDeferred(
            power_driver_command._run(reactor, args, registry)
        )
        self.assertEqual("on", status)
