# Copyright 2017-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.drivers.power.virsh`."""

import pexpect
from twisted.internet.defer import inlineCallbacks

from maastesting import get_testing_timeout
from maastesting.factory import factory
from maastesting.testcase import MAASTestCase, MAASTwistedRunTest
from provisioningserver.drivers.power import virsh
from provisioningserver.drivers.power.virsh import VirshPowerDriver
from provisioningserver.utils.shell import (
    get_env_with_locale,
    has_command_available,
)

TIMEOUT = get_testing_timeout()


class TestVirshSSH(MAASTestCase):
    """Tests for `VirshSSH`."""

    def configure_virshssh_pexpect(self, inputs=None, dom_prefix=None):
        """Configures the VirshSSH class to use 'cat' process
        for testing instead of the actual virsh."""
        conn = virsh.VirshSSH(timeout=0.1, dom_prefix=dom_prefix)
        self.addCleanup(conn.close)
        self.patch(conn, "_execute")
        conn._spawn("cat")
        if inputs is not None:
            for line in inputs:
                conn.sendline(line)
        return conn

    def configure_virshssh(self, results, dom_prefix=None):
        virshssh = virsh.VirshSSH(dom_prefix=dom_prefix)
        mock_run = self.patch(virshssh, "run")
        if isinstance(results, str):
            mock_run.return_value = results
        else:
            # either a single exception or a list of results/errors
            mock_run.side_effect = results

        return virshssh

    def test_login_prompt(self):
        virsh_outputs = ["virsh # "]
        conn = self.configure_virshssh_pexpect(virsh_outputs)
        self.assertTrue(conn.login(poweraddr=factory.make_name("poweraddr")))

    def test_login_with_sshkey(self):
        virsh_outputs = [
            "The authenticity of host '127.0.0.1' can't be established.",
            "ECDSA key fingerprint is "
            "00:11:22:33:44:55:66:77:88:99:aa:bb:cc:dd:ee:ff.",
            "Are you sure you want to continue connecting (yes/no)? ",
        ]
        conn = self.configure_virshssh_pexpect(virsh_outputs)
        mock_sendline = self.patch(conn, "sendline")
        conn.login(poweraddr=factory.make_name("poweraddr"))
        mock_sendline.assert_called_once_with("yes")

    def test_login_with_password(self):
        virsh_outputs = [
            "ubuntu@%s's password: " % factory.make_ipv4_address()
        ]
        conn = self.configure_virshssh_pexpect(virsh_outputs)
        fake_password = factory.make_name("password")
        mock_sendline = self.patch(conn, "sendline")
        conn.login(
            poweraddr=factory.make_name("poweraddr"), password=fake_password
        )
        mock_sendline.assert_called_once_with(fake_password)

    def test_login_missing_password(self):
        virsh_outputs = [
            "ubuntu@%s's password: " % factory.make_ipv4_address()
        ]
        conn = self.configure_virshssh_pexpect(virsh_outputs)
        mock_close = self.patch(conn, "close")
        self.assertFalse(conn.login(poweraddr=factory.make_name("poweraddr")))
        mock_close.assert_called_once_with()

    def test_pkttyagent_permission_denied(self):
        # Sometimes pkttyagent can't be executed in the snap. The connection
        # itself still works, though.
        # See https://bugs.launchpad.net/maas/+bug/2053033
        virsh_outputs = [
            "libvirt:  error : cannot execute binary /usr/bin/pkttyagent: Permission denied",
            "Welcome to virsh, the virtualization interactive terminal.",
            "",
            "Type:  'help' for help with commands",
            "       'quit' to quit",
            "",
            "virsh # ",
        ]
        conn = self.configure_virshssh_pexpect(virsh_outputs)
        self.assertTrue(conn.login(poweraddr=factory.make_name("poweraddr")))

    def test_login_invalid(self):
        virsh_outputs = ["Permission denied, please try again."]
        conn = self.configure_virshssh_pexpect(virsh_outputs)
        mock_close = self.patch(conn, "close")
        self.assertFalse(conn.login(poweraddr=factory.make_name("poweraddr")))
        mock_close.assert_called_once_with()

    def test_unknown(self):
        virsh_outputs = [factory.make_string()]
        conn = self.configure_virshssh_pexpect(virsh_outputs)
        mock_close = self.patch(conn, "close")
        self.assertFalse(conn.login(poweraddr=factory.make_name("poweraddr")))
        mock_close.assert_called_once_with()

    def test_login_errors_with_poweraddr_extra_parameters(self):
        conn = virsh.VirshSSH(timeout=0.1)
        self.addCleanup(conn.close)
        poweraddr = "qemu+ssh://ubuntu@10.0.0.2/system?no_verify=1"
        conn._spawn("cat")
        self.assertRaises(virsh.VirshError, conn.login, poweraddr)

    def test_login_with_poweraddr_adds_extra_parameters(self):
        conn = virsh.VirshSSH(timeout=0.1)
        self.addCleanup(conn.close)
        mock_execute = self.patch(conn, "_execute")
        mock_close = self.patch(conn, "close")
        poweraddr = "qemu+ssh://ubuntu@10.0.0.2/system"
        conn._spawn("cat")
        self.assertFalse(conn.login(poweraddr=poweraddr))
        new_poweraddr = poweraddr + "?command=/usr/lib/maas/unverified-ssh"
        mock_execute.assert_called_once_with(new_poweraddr)
        mock_close.assert_called_once_with()

    def test_login_with_poweraddr_no_extra_parameters(self):
        conn = virsh.VirshSSH(timeout=0.1)
        self.addCleanup(conn.close)
        mock_execute = self.patch(conn, "_execute")
        mock_close = self.patch(conn, "close")
        poweraddr = "qemu+ssh://ubuntu@10.0.0.2/system"
        conn._spawn("cat")
        self.assertFalse(conn.login(poweraddr=poweraddr))
        mock_execute.assert_called_once_with(
            poweraddr + "?command=/usr/lib/maas/unverified-ssh"
        )
        mock_close.assert_called_once_with()

    def test_logout(self):
        conn = self.configure_virshssh_pexpect()
        mock_sendline = self.patch(conn, "sendline")
        mock_close = self.patch(conn, "close")
        conn.logout()
        mock_sendline.assert_called_once_with("quit")
        mock_close.assert_called_once_with()

    def test_prompt(self):
        virsh_outputs = ["virsh # "]
        conn = self.configure_virshssh_pexpect(virsh_outputs)
        self.assertTrue(conn.prompt())

    def test_invalid_prompt(self):
        virsh_outputs = [factory.make_string()]
        conn = self.configure_virshssh_pexpect(virsh_outputs)
        self.assertFalse(conn.prompt())

    def test_run(self):
        cmd = ["list", "--all", "--name"]
        expected = " ".join(cmd)
        names = [factory.make_name("machine") for _ in range(3)]
        conn = self.configure_virshssh_pexpect()
        conn.before = ("\n".join([expected] + names)).encode("utf-8")
        mock_sendline = self.patch(conn, "sendline")
        mock_prompt = self.patch(conn, "prompt")
        output = conn.run(cmd)
        mock_sendline.assert_called_once_with(expected)
        mock_prompt.assert_called_once_with()
        self.assertEqual("\n".join(names), output)

    def test_run_error(self):
        cmd = ["list", "--all", "--name"]
        message = "something failed"
        conn = self.configure_virshssh_pexpect()
        conn.before = "\n".join([" ".join(cmd), f"error: {message}"]).encode(
            "utf-8"
        )
        self.patch(conn, "sendline")
        self.patch(conn, "prompt")
        mock_maaslog = self.patch(virsh, "maaslog")
        error = self.assertRaises(virsh.VirshError, conn.run, cmd)
        expected_message = "Virsh command ['list', '--all', '--name'] failed: something failed"
        self.assertEqual(str(error), expected_message)
        mock_maaslog.error.assert_called_once_with(expected_message)

    def test_get_machine_state(self):
        state = factory.make_name("state")
        conn = self.configure_virshssh(state)
        expected = conn.get_machine_state("")
        self.assertEqual(state, expected)

    def test_get_machine_state_error(self):
        conn = self.configure_virshssh(virsh.VirshError("some error"))
        expected = conn.get_machine_state("")
        self.assertIsNone(expected)

    def test_poweron(self):
        conn = self.configure_virshssh("")
        expected = conn.poweron(factory.make_name("machine"))
        self.assertTrue(expected)

    def test_poweron_error(self):
        conn = self.configure_virshssh(virsh.VirshError("some error"))
        expected = conn.poweron(factory.make_name("machine"))
        self.assertFalse(expected)

    def test_poweroff(self):
        conn = self.configure_virshssh("")
        expected = conn.poweroff(factory.make_name("machine"))
        self.assertTrue(expected)

    def test_poweroff_error(self):
        conn = self.configure_virshssh(virsh.VirshError("some error"))
        expected = conn.poweroff(factory.make_name("machine"))
        self.assertFalse(expected)

    def test_resets_locale(self):
        """
        VirshSSH resets the locale to ensure we only ever get English strings.
        """
        c_utf8_environment = get_env_with_locale()
        mock_spawn = self.patch(pexpect.spawn, "__init__")
        self.configure_virshssh("")
        mock_spawn.assert_called_once_with(
            None, timeout=30, maxread=2000, env=c_utf8_environment
        )


class TestVirshPowerDriver(MAASTestCase):
    run_tests_with = MAASTwistedRunTest.make_factory(timeout=TIMEOUT)

    def test_missing_packages(self):
        mock = self.patch(has_command_available)
        mock.return_value = False
        driver = virsh.VirshPowerDriver()
        missing = driver.detect_missing_packages()
        self.assertEqual(["libvirt-clients"], missing)

    def test_no_missing_packages(self):
        mock = self.patch(has_command_available)
        mock.return_value = True
        driver = virsh.VirshPowerDriver()
        missing = driver.detect_missing_packages()
        self.assertEqual([], missing)

    def test_chassis_for_bmc_deduplication(self):
        # VMs on the same host share a single BMC (the hypervisor), so the
        # driver must be a chassis for BMC deduplication to work.
        driver = virsh.VirshPowerDriver()
        self.assertTrue(driver.chassis)
        self.assertTrue(driver.can_probe)

    def make_context(self):
        return {
            "system_id": factory.make_name("system_id"),
            "power_address": factory.make_name("power_address"),
            "power_id": factory.make_name("power_id"),
            "power_pass": factory.make_name("power_pass"),
        }

    def test_power_on_calls_power_control_virsh(self):
        power_change = "on"
        context = self.make_context()
        driver = VirshPowerDriver()
        power_control_virsh = self.patch(driver, "power_control_virsh")
        driver.power_on(context.get("system_id"), context)

        power_control_virsh.assert_called_once_with(
            power_change=power_change, **context
        )

    def test_power_off_calls_power_control_virsh(self):
        power_change = "off"
        context = self.make_context()
        driver = VirshPowerDriver()
        power_control_virsh = self.patch(driver, "power_control_virsh")
        driver.power_off(context.get("system_id"), context)

        power_control_virsh.assert_called_once_with(
            power_change=power_change, **context
        )

    def test_power_query_calls_power_state_virsh(self):
        power_state = "off"
        context = self.make_context()
        driver = VirshPowerDriver()
        power_state_virsh = self.patch(driver, "power_state_virsh")
        power_state_virsh.return_value = power_state
        expected_result = driver.power_query(context.get("system_id"), context)

        power_state_virsh.assert_called_once_with(**context)
        self.assertEqual(expected_result, power_state)

    @inlineCallbacks
    def test_power_control_login_failure(self):
        driver = VirshPowerDriver()
        mock_login = self.patch(virsh.VirshSSH, "login")
        mock_login.return_value = False
        with self.assertRaisesRegex(
            virsh.VirshError, r"^Failed to login to virsh console\.$"
        ):
            yield driver.power_control_virsh(
                factory.make_name("power_address"),
                factory.make_name("power_id"),
                factory.make_name("power_change"),
                power_pass=factory.make_string(),
            )

    @inlineCallbacks
    def test_power_control_on(self):
        driver = VirshPowerDriver()
        mock_login = self.patch(virsh.VirshSSH, "login")
        mock_login.return_value = True
        mock_state = self.patch(virsh.VirshSSH, "get_machine_state")
        mock_state.return_value = virsh.VirshVMState.OFF
        mock_poweron = self.patch(virsh.VirshSSH, "poweron")

        power_address = factory.make_name("power_address")
        power_id = factory.make_name("power_id")
        yield driver.power_control_virsh(power_address, power_id, "on")

        mock_login.assert_called_once_with(power_address, None)
        mock_state.assert_called_once_with(power_id)
        mock_poweron.assert_called_once_with(power_id)

    @inlineCallbacks
    def test_power_control_off(self):
        driver = VirshPowerDriver()
        mock_login = self.patch(virsh.VirshSSH, "login")
        mock_login.return_value = True
        mock_state = self.patch(virsh.VirshSSH, "get_machine_state")
        mock_state.return_value = virsh.VirshVMState.ON
        mock_poweroff = self.patch(virsh.VirshSSH, "poweroff")

        power_address = factory.make_name("power_address")
        power_id = factory.make_name("power_id")
        yield driver.power_control_virsh(power_address, power_id, "off")

        mock_login.assert_called_once_with(power_address, None)
        mock_state.assert_called_once_with(power_id)
        mock_poweroff.assert_called_once_with(power_id)

    @inlineCallbacks
    def test_power_control_bad_domain(self):
        driver = VirshPowerDriver()
        mock_login = self.patch(virsh.VirshSSH, "login")
        mock_login.return_value = True
        mock_state = self.patch(virsh.VirshSSH, "get_machine_state")
        mock_state.return_value = None

        power_address = factory.make_name("power_address")
        power_id = factory.make_name("power_id")
        with self.assertRaisesRegex(
            virsh.VirshError, f"^{power_id}: Failed to get power state$"
        ):
            yield driver.power_control_virsh(power_address, power_id, "on")

    @inlineCallbacks
    def test_power_control_power_failure(self):
        driver = VirshPowerDriver()
        mock_login = self.patch(virsh.VirshSSH, "login")
        mock_login.return_value = True
        mock_state = self.patch(virsh.VirshSSH, "get_machine_state")
        mock_state.return_value = virsh.VirshVMState.ON
        mock_poweroff = self.patch(virsh.VirshSSH, "poweroff")
        mock_poweroff.return_value = False

        power_address = factory.make_name("power_address")
        power_id = factory.make_name("power_id")
        with self.assertRaisesRegex(
            virsh.VirshError, f"^{power_id}: Failed to power off VM$"
        ):
            yield driver.power_control_virsh(power_address, power_id, "off")

    @inlineCallbacks
    def test_power_state_login_failure(self):
        driver = VirshPowerDriver()
        mock_login = self.patch(virsh.VirshSSH, "login")
        mock_login.return_value = False
        with self.assertRaisesRegex(
            virsh.VirshError, r"^Failed to login to virsh console\.$"
        ):
            yield driver.power_state_virsh(
                factory.make_name("power_address"),
                factory.make_name("power_id"),
                power_pass=factory.make_string(),
            )

    @inlineCallbacks
    def test_power_state_get_on(self):
        driver = VirshPowerDriver()
        mock_login = self.patch(virsh.VirshSSH, "login")
        mock_login.return_value = True
        mock_state = self.patch(virsh.VirshSSH, "get_machine_state")
        mock_state.return_value = virsh.VirshVMState.ON

        power_address = factory.make_name("power_address")
        power_id = factory.make_name("power_id")
        state = yield driver.power_state_virsh(power_address, power_id)
        self.assertEqual("on", state)

    @inlineCallbacks
    def test_power_state_get_off(self):
        driver = VirshPowerDriver()
        mock_login = self.patch(virsh.VirshSSH, "login")
        mock_login.return_value = True
        mock_state = self.patch(virsh.VirshSSH, "get_machine_state")
        mock_state.return_value = virsh.VirshVMState.OFF

        power_address = factory.make_name("power_address")
        power_id = factory.make_name("power_id")
        state = yield driver.power_state_virsh(power_address, power_id)
        self.assertEqual("off", state)

    @inlineCallbacks
    def test_power_state_bad_domain(self):
        driver = VirshPowerDriver()
        mock_login = self.patch(virsh.VirshSSH, "login")
        mock_login.return_value = True
        mock_state = self.patch(virsh.VirshSSH, "get_machine_state")
        mock_state.return_value = None

        power_address = factory.make_name("power_address")
        power_id = factory.make_name("power_id")
        with self.assertRaisesRegex(
            virsh.VirshError, f"^Failed to get domain: {power_id}$"
        ):
            yield driver.power_state_virsh(power_address, power_id)

    @inlineCallbacks
    def test_power_state_error_on_unknown_state(self):
        driver = VirshPowerDriver()
        mock_login = self.patch(virsh.VirshSSH, "login")
        mock_login.return_value = True
        mock_state = self.patch(virsh.VirshSSH, "get_machine_state")
        mock_state.return_value = "unknown"

        power_address = factory.make_name("power_address")
        power_id = factory.make_name("power_id")
        with self.assertRaisesRegex(
            virsh.VirshError, "^Unknown state: unknown$"
        ):
            yield driver.power_state_virsh(power_address, power_id)
