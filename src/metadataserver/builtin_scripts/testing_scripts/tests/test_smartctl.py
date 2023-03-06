# Copyright 2017-2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test smartctl functions."""


import io
import random
from subprocess import CalledProcessError, DEVNULL, STDOUT, TimeoutExpired
from unittest.mock import call

from maasserver.testing.factory import factory
from maastesting.matchers import (
    MockCalledOnce,
    MockCalledOnceWith,
    MockCallsMatch,
    MockNotCalled,
)
from maastesting.testcase import MAASTestCase
from metadataserver.builtin_scripts.testing_scripts import smartctl


class TestRunSmartCTL(MAASTestCase):
    def setUp(self):
        super().setUp()
        self.output = factory.make_name("output")
        self.mock_check_output = self.patch(smartctl, "check_output")
        self.mock_check_output.return_value = self.output.encode()
        self.mock_print = self.patch(smartctl, "print")
        self.blockdevice = factory.make_name("blockdevice")
        self.args = [factory.make_name("arg") for _ in range(3)]

    def test_default(self):
        self.assertEqual(
            self.output, smartctl.run_smartctl(self.blockdevice, self.args)
        )
        self.assertThat(
            self.mock_check_output,
            MockCalledOnceWith(
                ["sudo", "-n", "smartctl"] + self.args + [self.blockdevice],
                timeout=smartctl.TIMEOUT,
            ),
        )
        self.assertThat(self.mock_print, MockNotCalled())

    def test_device(self):
        device = factory.make_name("device")
        self.assertEqual(
            self.output,
            smartctl.run_smartctl(self.blockdevice, self.args, device=device),
        )
        self.assertThat(
            self.mock_check_output,
            MockCalledOnceWith(
                ["sudo", "-n", "smartctl", "-d", device]
                + self.args
                + [self.blockdevice],
                timeout=smartctl.TIMEOUT,
            ),
        )
        self.assertThat(self.mock_print, MockNotCalled())

    def test_output(self):
        self.assertEqual(
            self.output,
            smartctl.run_smartctl(self.blockdevice, self.args, output=True),
        )
        self.assertThat(
            self.mock_check_output,
            MockCalledOnceWith(
                ["sudo", "-n", "smartctl"] + self.args + [self.blockdevice],
                timeout=smartctl.TIMEOUT,
            ),
        )
        self.assertThat(self.mock_print, MockCalledOnce())

    def test_output_invalid_utf8_replaced(self):
        # invalid UTF-8 input
        self.mock_check_output.return_value = b"foo\x99bar"
        self.assertEqual(
            "foo\ufffdbar",
            smartctl.run_smartctl(self.blockdevice, self.args, output=True),
        )


class TestRunStorCLI(MAASTestCase):
    def setUp(self):
        super().setUp()
        self.output = factory.make_name("output")
        self.mock_check_output = self.patch(smartctl, "check_output")
        self.mock_check_output.return_value = self.output.encode()
        self.mock_print = self.patch(smartctl, "print")
        self.args = [factory.make_name("arg") for _ in range(3)]

    def test_default(self):
        self.assertEqual(self.output, smartctl.run_storcli(self.args))
        self.assertThat(
            self.mock_check_output,
            MockCalledOnceWith(
                ["sudo", "-n", "storcli64"] + self.args,
                timeout=smartctl.TIMEOUT,
            ),
        )
        self.assertThat(self.mock_print, MockNotCalled())

    def test_using_alt_path(self):
        self.patch(smartctl.os.path, "exists").return_value = True
        self.assertEqual(self.output, smartctl.run_storcli(self.args))
        self.assertThat(
            self.mock_check_output,
            MockCalledOnceWith(
                ["sudo", "-n", "/opt/MegaRAID/storcli/storcli64"] + self.args,
                timeout=smartctl.TIMEOUT,
            ),
        )
        self.assertThat(self.mock_print, MockNotCalled())

    def test_output(self):
        self.assertEqual(self.output, smartctl.run_storcli(self.args, True))
        self.assertThat(
            self.mock_check_output,
            MockCalledOnceWith(
                ["sudo", "-n", "storcli64"] + self.args,
                timeout=smartctl.TIMEOUT,
            ),
        )
        self.assertThat(self.mock_print, MockCalledOnce())


class TestMakeDeviceName(MAASTestCase):
    def test_blockdevice(self):
        blockdevice = factory.make_name("blockdevice")
        self.assertEqual(blockdevice, smartctl.make_device_name(blockdevice))

    def test_device(self):
        blockdevice = factory.make_name("blockdevice")
        device = factory.make_name("device")
        self.assertEqual(
            "%s %s" % (blockdevice, device),
            smartctl.make_device_name(blockdevice, device),
        )


class TestExitSkipped(MAASTestCase):
    def test_default(self):
        result_path = factory.make_name("result_path")
        self.patch(smartctl.os, "environ", {"RESULT_PATH": result_path})
        mock_open = self.patch(smartctl, "open")
        mock_open.return_value = io.StringIO()
        mock_yaml_safe_dump = self.patch(smartctl.yaml, "safe_dump")

        self.assertRaises(SystemExit, smartctl.exit_skipped)
        self.assertThat(mock_open, MockCalledOnceWith(result_path, "w"))
        self.assertThat(
            mock_yaml_safe_dump,
            MockCalledOnceWith({"status": "skipped"}, mock_open.return_value),
        )


class TestFindMatchingMegaRAIDController(MAASTestCase):
    def setUp(self):
        super().setUp()
        self.patch(smartctl, "print")

    def test_no_controllers(self):
        mock_run_storcli = self.patch(smartctl, "run_storcli")
        mock_run_storcli.return_value = ""
        mock_exit_skipped = self.patch(smartctl, "exit_skipped")

        smartctl.find_matching_megaraid_controller(
            factory.make_name("blockdevice")
        )

        self.assertThat(mock_exit_skipped, MockCalledOnce())

    def test_found(self):
        scsi_id = factory.make_name()
        mock_run_storcli = self.patch(smartctl, "run_storcli")
        mock_run_storcli.side_effect = (
            "Number of Controllers = 2",
            "Virtual Drives = 1",
            "SCSI NAA Id = %s" % factory.make_name("scsi_id"),
            "Virtual Drives = 1",
            "SCSI NAA Id = %s" % scsi_id,
        )
        self.patch(smartctl.glob, "glob").return_value = [
            factory.make_name("path")
        ]
        self.patch(smartctl.os.path, "realpath").side_effect = (
            scsi_id,
            scsi_id,
        )
        self.assertEqual(
            1,
            smartctl.find_matching_megaraid_controller(
                factory.make_name("blockdevice")
            ),
        )

    def test_no_matching_scsi_id(self):
        mock_run_storcli = self.patch(smartctl, "run_storcli")
        mock_run_storcli.side_effect = (
            "Number of Controllers = 1",
            "Virtual Drives = 1",
            "SCSI NAA Id = %s" % factory.make_name("scsi_id"),
        )
        mock_exit_skipped = self.patch(smartctl, "exit_skipped")
        smartctl.find_matching_megaraid_controller(
            factory.make_name("blockdevice")
        )
        self.assertThat(mock_exit_skipped, MockCalledOnce())


class TestDetectMegaRAIDConfig(MAASTestCase):
    def setUp(self):
        super().setUp()
        self.patch(smartctl, "print")

    def test_no_storcli(self):
        mock_exit_skipped = self.patch(smartctl, "exit_skipped")
        smartctl.detect_megaraid_config(factory.make_name("blockdevice"))
        self.assertThat(mock_exit_skipped, MockCalledOnce())

    def test_returns_scsi_bus_nums(self):
        controller = random.randint(0, 3)
        scsi_bus_nums = [random.randint(0, 127) for _ in range(3)]
        self.patch(smartctl.os.path, "exists").return_value = True
        self.patch(
            smartctl, "find_matching_megaraid_controller"
        ).return_value = controller
        mock_run_storcli = self.patch(smartctl, "run_storcli")
        mock_run_storcli.return_value = "".join(
            [
                "%d:%d %d\n"
                % (
                    random.randint(0, 255),
                    random.randint(0, 255),
                    scsi_bus_num,
                )
                for scsi_bus_num in scsi_bus_nums
            ]
        )

        self.assertCountEqual(
            scsi_bus_nums,
            smartctl.detect_megaraid_config(factory.make_name("blockdevice")),
        )
        self.assertThat(
            mock_run_storcli,
            MockCalledOnceWith(
                ["/c%d" % controller, "/eall", "/sall", "show"]
            ),
        )


class TestCheckSMARTSupport(MAASTestCase):
    def setUp(self):
        super().setUp()
        self.patch(smartctl, "print")

    def test_raises_timeoutexpired(self):
        mock_run_smartctl = self.patch(smartctl, "run_smartctl")
        mock_run_smartctl.side_effect = TimeoutExpired("smartctl", 60)
        self.assertRaises(
            TimeoutExpired,
            smartctl.check_SMART_support,
            factory.make_name("blockdevice"),
        )

    def test_raises_calledprocesserrror(self):
        mock_run_smartctl = self.patch(smartctl, "run_smartctl")
        mock_run_smartctl.side_effect = CalledProcessError(1, "smartctl")
        self.assertRaises(
            CalledProcessError,
            smartctl.check_SMART_support,
            factory.make_name("blockdevice"),
        )

    def test_available(self):
        mock_run_smartctl = self.patch(smartctl, "run_smartctl")
        mock_run_smartctl.return_value = (
            "Product: %s\n"
            "SMART support is: Available\n" % factory.make_name("product")
        )
        self.assertEqual(
            (None, []),
            smartctl.check_SMART_support(factory.make_name("blockdevice")),
        )

    def test_available2(self):
        mock_run_smartctl = self.patch(smartctl, "run_smartctl")
        mock_run_smartctl.return_value = (
            "SMART overall-health self-assessment test result: "
        )
        self.assertEqual(
            (None, []),
            smartctl.check_SMART_support(factory.make_name("blockdevice")),
        )

    def test_available_megaraid(self):
        mock_run_smartctl = self.patch(smartctl, "run_smartctl")
        mock_run_smartctl.return_value = (
            "Product: MegaRAID\n" "SMART support is: Unavailable\n"
        )
        scsi_ids = [random.randint(0, 127) for _ in range(3)]
        self.patch(smartctl, "detect_megaraid_config").return_value = scsi_ids
        self.assertEqual(
            ("megaraid", scsi_ids),
            smartctl.check_SMART_support(factory.make_name("blockdevice")),
        )

    def test_unavailable(self):
        mock_run_smartctl = self.patch(smartctl, "run_smartctl")
        mock_run_smartctl.return_value = (
            "Product: %s\n"
            "SMART support is: Unavailable\n" % factory.make_name("product")
        )
        mock_exit_skipped = self.patch(smartctl, "exit_skipped")
        smartctl.check_SMART_support(factory.make_name("blockdevice"))
        self.assertThat(mock_exit_skipped, MockCalledOnce())


class TestRunSmartCTLSelfTest(MAASTestCase):
    def test_default(self):
        mock_run_smartctl = self.patch(smartctl, "run_smartctl")
        blockdevice = factory.make_name("blockdevice")
        test = factory.make_name("test")
        device = factory.make_name("device")
        smartctl.run_smartctl_selftest(blockdevice, test, device)
        self.assertThat(
            mock_run_smartctl,
            MockCalledOnceWith(
                blockdevice, ["-t", test], device, output=True, stderr=DEVNULL
            ),
        )

    def test_raises_timeoutexpired(self):
        mock_run_smartctl = self.patch(smartctl, "run_smartctl")
        mock_run_smartctl.side_effect = TimeoutExpired("smartctl", 60)
        mock_print = self.patch(smartctl, "print")
        blockdevice = factory.make_name("blockdevice")
        test = factory.make_name("test")
        self.assertRaises(
            TimeoutExpired, smartctl.run_smartctl_selftest, blockdevice, test
        )
        self.assertThat(mock_print, MockCalledOnce())

    def test_raises_calledprocesserror(self):
        mock_run_smartctl = self.patch(smartctl, "run_smartctl")
        mock_run_smartctl.side_effect = CalledProcessError(1, "smartctl")
        mock_print = self.patch(smartctl, "print")
        blockdevice = factory.make_name("blockdevice")
        test = factory.make_name("test")
        self.assertRaises(
            CalledProcessError,
            smartctl.run_smartctl_selftest,
            blockdevice,
            test,
        )
        self.assertThat(mock_print, MockCalledOnce())


class TestWaitSmartCTLSelfTest(MAASTestCase):
    def setUp(self):
        super().setUp()
        self.patch(smartctl, "print")

    def test_waits(self):
        blockdevice = factory.make_name("blockdevice")
        test = factory.make_name("test")
        device = factory.make_name("device")
        mock_sleep = self.patch(smartctl, "sleep")
        mock_run_smartctl = self.patch(smartctl, "run_smartctl")
        mock_run_smartctl.side_effect = (
            "Self-test execution status: (42) Self-test routine in progress",
            "",
            "",
        )

        smartctl.wait_smartctl_selftest(blockdevice, test, device)

        self.assertThat(
            mock_run_smartctl,
            MockCallsMatch(
                call(blockdevice, ["-c"], device),
                call(blockdevice, ["-c"], device),
                call(blockdevice, ["--all"], device),
            ),
        )
        self.assertThat(mock_sleep, MockCalledOnceWith(30))

    def test_waits_alt(self):
        blockdevice = factory.make_name("blockdevice")
        test = factory.make_name("test")
        device = factory.make_name("device")
        mock_sleep = self.patch(smartctl, "sleep")
        mock_run_smartctl = self.patch(smartctl, "run_smartctl")
        mock_run_smartctl.side_effect = (
            "Background %s Self test in progress" % test,
            "Background %s Self test in progress" % test,
            "",
        )

        smartctl.wait_smartctl_selftest(blockdevice, test, device)

        self.assertThat(
            mock_run_smartctl,
            MockCallsMatch(
                call(blockdevice, ["-c"], device),
                call(blockdevice, ["--all"], device),
                call(blockdevice, ["--all"], device),
            ),
        )
        self.assertThat(mock_sleep, MockCalledOnceWith(30))

    def test_raises_timeoutexpired(self):
        blockdevice = factory.make_name("blockdevice")
        test = factory.make_name("test")
        device = factory.make_name("device")
        mock_run_smartctl = self.patch(smartctl, "run_smartctl")
        mock_run_smartctl.side_effect = TimeoutExpired("smartctl", 60)
        mock_sleep = self.patch(smartctl, "sleep")
        self.assertRaises(
            TimeoutExpired,
            smartctl.wait_smartctl_selftest,
            blockdevice,
            test,
            device,
        )
        self.assertThat(mock_sleep, MockNotCalled())

    def test_raises_calledprocesserror(self):
        blockdevice = factory.make_name("blockdevice")
        test = factory.make_name("test")
        device = factory.make_name("device")
        mock_run_smartctl = self.patch(smartctl, "run_smartctl")
        mock_run_smartctl.side_effect = CalledProcessError(1, "smartctl")
        mock_sleep = self.patch(smartctl, "sleep")
        self.assertRaises(
            CalledProcessError,
            smartctl.wait_smartctl_selftest,
            blockdevice,
            test,
            device,
        )
        self.assertThat(mock_sleep, MockNotCalled())


class TestCheckSmartCTL(MAASTestCase):
    def setUp(self):
        super().setUp()
        self.patch(smartctl, "print")

    def test_default(self):
        mock_run_smartctl = self.patch(smartctl, "run_smartctl")
        blockdevice = factory.make_name("blockdevice")
        device = factory.make_name("device")
        smartctl.check_smartctl(blockdevice, device)
        self.assertThat(
            mock_run_smartctl,
            MockCalledOnceWith(
                blockdevice, ["--xall"], device, output=True, stderr=STDOUT
            ),
        )

    def test_raises_timeoutexpired(self):
        mock_run_smartctl = self.patch(smartctl, "run_smartctl")
        mock_run_smartctl.side_effect = TimeoutExpired("smartctl", 60)
        blockdevice = factory.make_name("blockdevice")
        self.assertRaises(TimeoutExpired, smartctl.check_smartctl, blockdevice)

    def test_ignores_returncode_four(self):
        mock_run_smartctl = self.patch(smartctl, "run_smartctl")
        mock_run_smartctl.side_effect = CalledProcessError(
            4, "smartctl", factory.make_name("output").encode()
        )
        blockdevice = factory.make_name("blockdevice")
        device = factory.make_name("device")
        smartctl.check_smartctl(blockdevice, device)
        self.assertThat(
            mock_run_smartctl,
            MockCalledOnceWith(
                blockdevice, ["--xall"], device, output=True, stderr=STDOUT
            ),
        )

    def test_raises_calledprocesserror(self):
        mock_run_smartctl = self.patch(smartctl, "run_smartctl")
        mock_run_smartctl.side_effect = CalledProcessError(42, "smartctl")
        blockdevice = factory.make_name("blockdevice")
        self.assertRaises(
            CalledProcessError, smartctl.check_smartctl, blockdevice
        )


class TestExecuteSmartCTL(MAASTestCase):
    def setUp(self):
        super().setUp()
        self.patch(smartctl, "print")
        self.blockdevice = factory.make_name("blockdevice")
        self.test = factory.make_name("test")
        self.mock_check_smart_support = self.patch(
            smartctl, "check_SMART_support"
        )
        self.mock_run_smartctl_selftest = self.patch(
            smartctl, "run_smartctl_selftest"
        )
        self.mock_wait_smartctl_selftest = self.patch(
            smartctl, "wait_smartctl_selftest"
        )
        self.mock_check_smartctl = self.patch(smartctl, "check_smartctl")

    def test_returns_false_with_check_smart_support_error(self):
        self.mock_check_smart_support.side_effect = random.choice(
            [
                TimeoutExpired("smartctl", 60),
                CalledProcessError(42, "smartctl"),
            ]
        )
        self.assertFalse(
            smartctl.execute_smartctl(self.blockdevice, self.test)
        )
        self.assertThat(self.mock_run_smartctl_selftest, MockNotCalled())
        self.assertThat(self.mock_wait_smartctl_selftest, MockNotCalled())
        self.assertThat(self.mock_check_smartctl, MockNotCalled())

    def test_returns_false_when_unable_to_check_device_support(self):
        device = factory.make_name("device")
        self.mock_check_smart_support.side_effect = (
            (device, [42]),
            random.choice(
                [
                    TimeoutExpired("smartctl", 60),
                    CalledProcessError(42, "smartctl"),
                ]
            ),
        )
        device = "%s,42" % device
        self.assertFalse(
            smartctl.execute_smartctl(self.blockdevice, self.test)
        )
        self.assertThat(
            self.mock_check_smart_support,
            MockCallsMatch(
                call(self.blockdevice), call(self.blockdevice, device)
            ),
        )
        self.assertThat(self.mock_run_smartctl_selftest, MockNotCalled())
        self.assertThat(
            self.mock_wait_smartctl_selftest,
            MockCalledOnceWith(self.blockdevice, self.test, device),
        )
        self.assertThat(
            self.mock_check_smartctl,
            MockCalledOnceWith(self.blockdevice, device),
        )

    def test_returns_false_when_unable_to_start_device_test(self):
        device = factory.make_name("device")
        self.mock_check_smart_support.return_value = (device, [42])
        self.mock_run_smartctl_selftest.side_effect = (
            random.choice(
                [
                    TimeoutExpired("smartctl", 60),
                    CalledProcessError(42, "smartctl"),
                ]
            ),
        )
        device = "%s,42" % device
        self.assertFalse(
            smartctl.execute_smartctl(self.blockdevice, self.test)
        )
        self.assertThat(
            self.mock_check_smart_support,
            MockCallsMatch(
                call(self.blockdevice), call(self.blockdevice, device)
            ),
        )
        self.assertThat(
            self.mock_run_smartctl_selftest,
            MockCalledOnceWith(self.blockdevice, self.test, device),
        )
        self.assertThat(
            self.mock_wait_smartctl_selftest,
            MockCalledOnceWith(self.blockdevice, self.test, device),
        )
        self.assertThat(
            self.mock_check_smartctl,
            MockCalledOnceWith(self.blockdevice, device),
        )

    def test_returns_false_when_unable_to_wait_start_device_test(self):
        device = factory.make_name("device")
        self.mock_check_smart_support.return_value = (device, [42])
        self.mock_wait_smartctl_selftest.side_effect = (
            random.choice(
                [
                    TimeoutExpired("smartctl", 60),
                    CalledProcessError(42, "smartctl"),
                ]
            ),
        )
        device = "%s,42" % device
        self.assertFalse(
            smartctl.execute_smartctl(self.blockdevice, self.test)
        )
        self.assertThat(
            self.mock_check_smart_support,
            MockCallsMatch(
                call(self.blockdevice), call(self.blockdevice, device)
            ),
        )
        self.assertThat(
            self.mock_run_smartctl_selftest,
            MockCalledOnceWith(self.blockdevice, self.test, device),
        )
        self.assertThat(
            self.mock_wait_smartctl_selftest,
            MockCalledOnceWith(self.blockdevice, self.test, device),
        )
        self.assertThat(
            self.mock_check_smartctl,
            MockCalledOnceWith(self.blockdevice, device),
        )

    def test_returns_false_when_unable_to_check_device(self):
        device = factory.make_name("device")
        self.mock_check_smart_support.return_value = (device, [42])
        self.mock_check_smartctl.side_effect = (
            random.choice(
                [
                    TimeoutExpired("smartctl", 60),
                    CalledProcessError(42, "smartctl"),
                ]
            ),
        )
        device = "%s,42" % device
        self.assertFalse(
            smartctl.execute_smartctl(self.blockdevice, self.test)
        )
        self.assertThat(
            self.mock_check_smart_support,
            MockCallsMatch(
                call(self.blockdevice), call(self.blockdevice, device)
            ),
        )
        self.assertThat(
            self.mock_run_smartctl_selftest,
            MockCalledOnceWith(self.blockdevice, self.test, device),
        )
        self.assertThat(
            self.mock_wait_smartctl_selftest,
            MockCalledOnceWith(self.blockdevice, self.test, device),
        )
        self.assertThat(
            self.mock_check_smartctl,
            MockCalledOnceWith(self.blockdevice, device),
        )

    def test_returns_true_with_device(self):
        device = factory.make_name("device")
        self.mock_check_smart_support.return_value = (device, [42])
        device = "%s,42" % device
        self.assertTrue(smartctl.execute_smartctl(self.blockdevice, self.test))
        self.assertThat(
            self.mock_check_smart_support,
            MockCallsMatch(
                call(self.blockdevice), call(self.blockdevice, device)
            ),
        )
        self.assertThat(
            self.mock_run_smartctl_selftest,
            MockCalledOnceWith(self.blockdevice, self.test, device),
        )
        self.assertThat(
            self.mock_wait_smartctl_selftest,
            MockCalledOnceWith(self.blockdevice, self.test, device),
        )
        self.assertThat(
            self.mock_check_smartctl,
            MockCalledOnceWith(self.blockdevice, device),
        )

    def test_tests_all_scsi_bus_nums(self):
        device = factory.make_name("device")
        self.mock_check_smart_support.return_value = (device, [1, 2, 3])
        self.assertTrue(smartctl.execute_smartctl(self.blockdevice, self.test))
        self.assertThat(
            self.mock_check_smart_support,
            MockCallsMatch(
                call(self.blockdevice),
                call(self.blockdevice, "%s,1" % device),
                call(self.blockdevice, "%s,2" % device),
                call(self.blockdevice, "%s,3" % device),
            ),
        )
        self.assertThat(
            self.mock_run_smartctl_selftest,
            MockCallsMatch(
                call(self.blockdevice, self.test, "%s,1" % device),
                call(self.blockdevice, self.test, "%s,2" % device),
                call(self.blockdevice, self.test, "%s,3" % device),
            ),
        )
        self.assertThat(
            self.mock_wait_smartctl_selftest,
            MockCallsMatch(
                call(self.blockdevice, self.test, "%s,1" % device),
                call(self.blockdevice, self.test, "%s,2" % device),
                call(self.blockdevice, self.test, "%s,3" % device),
            ),
        )
        self.assertThat(
            self.mock_check_smartctl,
            MockCallsMatch(
                call(self.blockdevice, "%s,1" % device),
                call(self.blockdevice, "%s,2" % device),
                call(self.blockdevice, "%s,3" % device),
            ),
        )

    def test_doesnt_run_testing_when_validating_device(self):
        device = factory.make_name("device")
        self.mock_check_smart_support.return_value = (device, [42])
        device = "%s,42" % device
        self.assertTrue(
            smartctl.execute_smartctl(self.blockdevice, "validate")
        )
        self.assertThat(
            self.mock_check_smart_support,
            MockCallsMatch(
                call(self.blockdevice), call(self.blockdevice, device)
            ),
        )
        self.assertThat(self.mock_run_smartctl_selftest, MockNotCalled())
        self.assertThat(self.mock_wait_smartctl_selftest, MockNotCalled())
        self.assertThat(
            self.mock_check_smartctl,
            MockCalledOnceWith(self.blockdevice, device),
        )

    def test_returns_false_when_starting_test_fails(self):
        self.mock_check_smart_support.return_value = (None, [])
        self.mock_run_smartctl_selftest.side_effect = random.choice(
            [
                TimeoutExpired("smartctl", 60),
                CalledProcessError(42, "smartctl"),
            ]
        )
        self.assertFalse(
            smartctl.execute_smartctl(self.blockdevice, self.test)
        )
        self.assertThat(
            self.mock_run_smartctl_selftest,
            MockCalledOnceWith(self.blockdevice, self.test),
        )
        self.assertThat(self.mock_wait_smartctl_selftest, MockNotCalled())
        self.assertThat(
            self.mock_check_smartctl, MockCalledOnceWith(self.blockdevice)
        )

    def test_returns_false_when_waiting_test_fails(self):
        self.mock_check_smart_support.return_value = (None, [])
        self.mock_wait_smartctl_selftest.side_effect = random.choice(
            [
                TimeoutExpired("smartctl", 60),
                CalledProcessError(42, "smartctl"),
            ]
        )
        self.assertFalse(
            smartctl.execute_smartctl(self.blockdevice, self.test)
        )
        self.assertThat(
            self.mock_run_smartctl_selftest,
            MockCalledOnceWith(self.blockdevice, self.test),
        )
        self.assertThat(
            self.mock_wait_smartctl_selftest,
            MockCalledOnceWith(self.blockdevice, self.test),
        )
        self.assertThat(
            self.mock_check_smartctl, MockCalledOnceWith(self.blockdevice)
        )

    def test_returns_false_when_check_fails(self):
        self.mock_check_smart_support.return_value = (None, [])
        self.mock_check_smartctl.side_effect = random.choice(
            [
                TimeoutExpired("smartctl", 60),
                CalledProcessError(42, "smartctl"),
            ]
        )
        self.assertFalse(
            smartctl.execute_smartctl(self.blockdevice, self.test)
        )
        self.assertThat(
            self.mock_run_smartctl_selftest,
            MockCalledOnceWith(self.blockdevice, self.test),
        )
        self.assertThat(
            self.mock_wait_smartctl_selftest,
            MockCalledOnceWith(self.blockdevice, self.test),
        )
        self.assertThat(
            self.mock_check_smartctl, MockCalledOnceWith(self.blockdevice)
        )

    def test_returns_true(self):
        self.mock_check_smart_support.return_value = (None, [])
        self.assertTrue(smartctl.execute_smartctl(self.blockdevice, self.test))
        self.assertThat(
            self.mock_run_smartctl_selftest,
            MockCalledOnceWith(self.blockdevice, self.test),
        )
        self.assertThat(
            self.mock_wait_smartctl_selftest,
            MockCalledOnceWith(self.blockdevice, self.test),
        )
        self.assertThat(
            self.mock_check_smartctl, MockCalledOnceWith(self.blockdevice)
        )

    def test_doesnt_run_testing_when_validating(self):
        self.mock_check_smart_support.return_value = (None, [])
        self.assertTrue(
            smartctl.execute_smartctl(self.blockdevice, "validate")
        )
        self.assertThat(self.mock_run_smartctl_selftest, MockNotCalled())
        self.assertThat(self.mock_wait_smartctl_selftest, MockNotCalled())
        self.assertThat(
            self.mock_check_smartctl, MockCalledOnceWith(self.blockdevice)
        )
