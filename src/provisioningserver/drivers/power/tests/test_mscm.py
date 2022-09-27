# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.drivers.power.mscm`."""


from io import BytesIO
from random import randint
import re
from socket import error as SOCKETError
from textwrap import dedent
from unittest.mock import call, Mock

from hypothesis import given, settings
from hypothesis.strategies import sampled_from
from paramiko import SSHException
from testtools.matchers import Equals
from testtools.testcase import ExpectedException
from twisted.internet.defer import inlineCallbacks
from twisted.internet.threads import deferToThread

from maastesting import get_testing_timeout
from maastesting.factory import factory
from maastesting.matchers import MockCalledOnceWith, MockCallsMatch
from maastesting.testcase import MAASTestCase, MAASTwistedRunTest
from provisioningserver.drivers.power import (
    PowerActionError,
    PowerConnError,
    PowerFatalError,
)
from provisioningserver.drivers.power import mscm as mscm_module
from provisioningserver.drivers.power.mscm import (
    cartridge_mapping,
    MSCMPowerDriver,
    probe_and_enlist_mscm,
)
from provisioningserver.utils.twisted import asynchronous

TIMEOUT = get_testing_timeout()


def make_node_id():
    """Make a node_id."""
    return f"c{randint(1, 45)}n{randint(1, 8)}"


NODE_LIST = dedent(
    """\
Slot ID    Proc Manufacturer      Architecture         Memory Power Status
---- ----- ---------------------- -------------------- ------ ----- ------
  1  %s    Intel Corporation      x86 Architecture     32 GB  Off   OK
  ...
"""
)


NODE_INFO = dedent(
    """\
  c1: #Cartridge %s
    Type: Compute
    Manufacturer: HP
    Product Name: %s
    ...
"""
)


NODE_MACADDR = dedent(
    """\
Slot ID NIC 1 (Switch A)  NIC 2 (Switch B)  NIC 3 (Switch A)  NIC 4 (Switch B)
---- -- ----------------  ----------------  ----------------  ----------------
  1  %s %s                %s                N/A               N/A
  ...
"""
)


def make_context():
    """Make and return a power parameters context."""
    return {
        "node_id": factory.make_name("node_id"),
        "power_address": factory.make_name("power_address"),
        "power_user": factory.make_name("power_user"),
        "power_pass": factory.make_name("power_pass"),
    }


class TestMSCMPowerDriver(MAASTestCase):
    def test_missing_packages(self):
        # there's nothing to check for, just confirm it returns []
        driver = mscm_module.MSCMPowerDriver()
        missing = driver.detect_missing_packages()
        self.assertEqual([], missing)

    def test_run_mscm_command_returns_command_output(self):
        driver = MSCMPowerDriver()
        command = factory.make_name("command")
        context = make_context()
        SSHClient = self.patch(mscm_module, "SSHClient")
        AutoAddPolicy = self.patch(mscm_module, "AutoAddPolicy")
        ssh_client = SSHClient.return_value
        expected = factory.make_name("output").encode("utf-8")
        stdout = BytesIO(expected)
        streams = factory.make_streams(stdout=stdout)
        ssh_client.exec_command = Mock(return_value=streams)
        output = driver.run_mscm_command(command, **context)

        self.expectThat(expected.decode("utf-8"), Equals(output))
        self.expectThat(SSHClient, MockCalledOnceWith())
        self.expectThat(
            ssh_client.set_missing_host_key_policy,
            MockCalledOnceWith(AutoAddPolicy.return_value),
        )
        self.expectThat(
            ssh_client.connect,
            MockCalledOnceWith(
                context["power_address"],
                username=context["power_user"],
                password=context["power_pass"],
            ),
        )
        self.expectThat(ssh_client.exec_command, MockCalledOnceWith(command))

    @settings(deadline=None)
    @given(sampled_from([SSHException, EOFError, SOCKETError]))
    def test_run_mscm_command_crashes_for_ssh_connection_error(self, error):
        driver = MSCMPowerDriver()
        command = factory.make_name("command")
        context = make_context()
        self.patch(mscm_module, "AutoAddPolicy")
        SSHClient = self.patch(mscm_module, "SSHClient")
        ssh_client = SSHClient.return_value
        ssh_client.connect.side_effect = error
        self.assertRaises(
            PowerConnError, driver.run_mscm_command, command, **context
        )

    def test_power_on_calls_run_mscm_command(self):
        driver = MSCMPowerDriver()
        system_id = factory.make_name("system_id")
        context = make_context()
        power_query = self.patch(driver, "power_query")
        power_query.return_value = "on"
        self.patch(driver, "power_off")
        self.patch(driver, "configure_node_bootonce_pxe")
        run_mscm_command = self.patch(driver, "run_mscm_command")
        driver.power_on(system_id, context)

        self.assertThat(
            run_mscm_command,
            MockCallsMatch(
                call(
                    "set node bootonce pxe %s" % context["node_id"], **context
                ),
                call("set node power on %s" % context["node_id"], **context),
            ),
        )

    def test_power_on_crashes_for_connection_error(self):
        driver = MSCMPowerDriver()
        system_id = factory.make_name("system_id")
        context = make_context()
        power_query = self.patch(driver, "power_query")
        power_query.return_value = "off"
        self.patch(driver, "configure_node_bootonce_pxe")
        run_mscm_command = self.patch(driver, "run_mscm_command")
        run_mscm_command.side_effect = PowerConnError("Connection Error")
        self.assertRaises(
            PowerActionError, driver.power_on, system_id, context
        )

    def test_power_off_calls_run_mscm_command(self):
        driver = MSCMPowerDriver()
        system_id = factory.make_name("system_id")
        context = make_context()
        run_mscm_command = self.patch(driver, "run_mscm_command")
        driver.power_off(system_id, context)

        self.assertThat(
            run_mscm_command,
            MockCalledOnceWith(
                "set node power off force %s" % context["node_id"], **context
            ),
        )

    def test_power_off_crashes_for_connection_error(self):
        driver = MSCMPowerDriver()
        system_id = factory.make_name("system_id")
        context = make_context()
        run_mscm_command = self.patch(driver, "run_mscm_command")
        run_mscm_command.side_effect = PowerConnError("Connection Error")
        self.assertRaises(
            PowerActionError, driver.power_off, system_id, context
        )

    def test_power_query_returns_power_state_on(self):
        driver = MSCMPowerDriver()
        system_id = factory.make_name("system_id")
        context = make_context()
        run_mscm_command = self.patch(driver, "run_mscm_command")
        run_mscm_command.return_value = (
            "show node power c1n1\r\r\n\r\nCartridge #1\r\n  Node #1\r\n"
            "        Power State: On\r\n"
        )
        output = driver.power_query(system_id, context)
        self.assertEqual("on", output)

    @given(sampled_from(["Off", "Unavailable", "On"]))
    @settings(deadline=None)
    def test_power_query_returns_power_state(self, power_state):
        states = {"Off": "off", "Unavailable": "off", "On": "on"}
        driver = MSCMPowerDriver()
        system_id = factory.make_name("system_id")
        context = make_context()
        run_mscm_command = self.patch(driver, "run_mscm_command")
        run_mscm_command.return_value = (
            "show node power c1n1\r\r\n\r\nCartridge #1\r\n  Node #1\r\n"
            "        Power State: %s\r\n" % power_state
        )
        output = driver.power_query(system_id, context)
        self.assertEqual(states[power_state], output)

    def test_power_query_crashes_for_connection_error(self):
        driver = MSCMPowerDriver()
        system_id = factory.make_name("system_id")
        context = make_context()
        run_mscm_command = self.patch(driver, "run_mscm_command")
        run_mscm_command.side_effect = PowerConnError("Connection Error")
        self.assertRaises(
            PowerActionError, driver.power_query, system_id, context
        )

    def test_power_query_crashes_when_unable_to_find_match(self):
        driver = MSCMPowerDriver()
        system_id = factory.make_name("system_id")
        context = make_context()
        run_mscm_command = self.patch(driver, "run_mscm_command")
        run_mscm_command.return_value = "Rubbish"
        self.assertRaises(
            PowerFatalError, driver.power_query, system_id, context
        )


class TestMSCMProbeAndEnlist(MAASTestCase):

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=TIMEOUT)

    scenarios = [
        (key, dict(product_name=key, arch=value))
        for key, value in cartridge_mapping.items()
    ]
    scenarios += [("default", dict(product_name="fake", arch="amd64/generic"))]

    @inlineCallbacks
    def test_probe_and_enlist(self):
        node_id = make_node_id()
        node_list = NODE_LIST % node_id
        node_info = NODE_INFO % (node_id, self.product_name)
        node_macaddr = NODE_MACADDR % (
            node_id,
            factory.make_mac_address(),
            factory.make_mac_address(),
        )
        macs = re.findall(r":".join(["[0-9a-f]{2}"] * 6), node_macaddr)

        user = factory.make_name("user")
        host = factory.make_hostname("mscm")
        username = factory.make_name("user")
        password = factory.make_name("password")
        domain = factory.make_name("domain")
        system_id = factory.make_name("system_id")
        mscm_driver = self.patch(mscm_module, "MSCMPowerDriver").return_value
        mscm_driver.run_mscm_command.side_effect = (
            node_list,
            None,
            node_info,
            node_macaddr,
        )
        create_node = self.patch(mscm_module, "create_node")
        create_node.side_effect = asynchronous(lambda *args: system_id)
        commission_node = self.patch(mscm_module, "commission_node")
        params = {
            "power_address": host,
            "power_user": username,
            "power_pass": password,
            "node_id": node_id,
        }

        yield deferToThread(
            probe_and_enlist_mscm, user, host, username, password, True, domain
        )

        self.expectThat(
            create_node,
            MockCalledOnceWith(macs, self.arch, "mscm", params, domain),
        )
        self.expectThat(commission_node, MockCalledOnceWith(system_id, user))


class TestMSCMProbeAndEnlistCrashesNoMatch(MAASTestCase):

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=TIMEOUT)

    @inlineCallbacks
    def test_probe_and_enlist_mscm_crashes_for_no_match(self):
        node_id = make_node_id()
        node_list = NODE_LIST % node_id
        user = factory.make_name("user")
        host = factory.make_hostname("mscm")
        username = factory.make_name("user")
        password = factory.make_name("password")
        Driver = self.patch(mscm_module, "MSCMPowerDriver")
        mscm_driver = Driver.return_value
        mscm_driver.run_mscm_command.side_effect = (node_list, None, "Error")

        with ExpectedException(PowerFatalError):
            yield deferToThread(
                probe_and_enlist_mscm, user, host, username, password
            )
