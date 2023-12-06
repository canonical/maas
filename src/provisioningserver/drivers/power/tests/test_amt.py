# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


from os.path import dirname, join
from pathlib import Path
from random import choice
from textwrap import dedent
from unittest.mock import call, sentinel

from lxml import etree

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from provisioningserver.drivers.power import (
    PowerActionError,
    PowerConnError,
    PowerFatalError,
)
from provisioningserver.drivers.power import amt as amt_module
from provisioningserver.drivers.power.amt import AMT_ERRORS, AMTPowerDriver
from provisioningserver.utils.shell import has_command_available, ProcessResult
from provisioningserver.utils.snap import SnapPaths

AMTTOOL_OUTPUT = dedent(
    """\
### AMT info on machine '192.168.0.10' ###
AMT version:  %s
Hostname:     maas.is.the.best
Powerstate:   %s
Remote Control Capabilities:
    IanaOemNumber                   0
    OemDefinedCapabilities          IDER SOL BiosSetup
    SpecialCommandsSupported        PXE-boot HD-boot cd-boot
    SystemCapabilitiesSupported     powercycle powerdown powerup reset
    SystemFirmwareCapabilities      0
"""
).encode("utf-8")


WSMAN_IDENTIFY_OUTPUT = dedent(
    """\
  <a:Header/>
  <a:Body>
    <b:IdentifyResponse>
      <b:ProtocolVersion>http://schemas.dmtf.org/wbem/wsman/1/wsman.xsd</b:ProtocolVersion>
      <b:ProductVendor>Intel(r)</b:ProductVendor>
      <b:ProductVersion>AMT %s</b:ProductVersion>
      <c:DASHVersion>1.0.0</c:DASHVersion>
      <b:SecurityProfiles>
        ...
"""
).encode("utf-8")


WSMAN_OUTPUT = dedent(
    """\
...
  <a:Body>
    <g:PullResponse>
      <g:Items>
        <h:CIM_AssociatedPowerManagementService>
          <h:AvailableRequestedPowerStates>2</h:AvailableRequestedPowerStates>
          <h:PowerState>%s</h:PowerState>
          <h:RequestedPowerState>2</h:RequestedPowerState>
          <h:ServiceProvided>
          ...
"""
).encode("utf-8")


def make_context():
    return {
        "system_id": factory.make_name("system_id"),
        "power_address": factory.make_name("power_address"),
        "ip_address": factory.make_ipv4_address(),
        "power_pass": factory.make_name("power_pass"),
        "boot_mode": factory.make_name("boot_mode"),
    }


class TestAMTPowerDriver(MAASTestCase):
    def setUp(self):
        super().setUp()
        self.patch(amt_module, "sleep")

    def patch_run_command(
        self, stdout=b"", stderr=b"", returncode=0, decode=False
    ):
        mock_run_command = self.patch(amt_module.shell, "run_command")
        if decode:
            stdout = stdout.decode()
            stderr = stderr.decode()
        mock_run_command.return_value = ProcessResult(
            stdout=stdout, stderr=stderr, returncode=returncode
        )
        return mock_run_command

    def test_missing_packages(self):
        mock = self.patch(has_command_available)
        mock.return_value = False
        driver = amt_module.AMTPowerDriver()
        missing = driver.detect_missing_packages()
        self.assertEqual(["wsmancli"], missing)

    def test_no_missing_packages(self):
        mock = self.patch(has_command_available)
        mock.return_value = True
        driver = amt_module.AMTPowerDriver()
        missing = driver.detect_missing_packages()
        self.assertEqual([], missing)

    def test_render_wsman_state_xml_renders_xml(self):
        amt_power_driver = AMTPowerDriver()
        power_change = choice(["on", "off", "restart"])
        result = amt_power_driver._render_wsman_state_xml(power_change)

        with open(
            join(dirname(dirname(__file__)), "amt.wsman-state.xml"), "rb"
        ) as fd:
            tree = etree.fromstring(fd.read())
            power_states = {"on": "2", "off": "8", "restart": "10"}
            [state] = tree.xpath("//p:PowerState", namespaces=tree.nsmap)
            state.text = power_states[power_change]

            self.assertEqual(result, etree.tostring(tree))

    def test_get_power_state_gets_state(self):
        amt_power_driver = AMTPowerDriver()
        namespaces = {
            "h": (
                "http://schemas.dmtf.org/wbem/wscim/1/cim-schema"
                "/2/CIM_AssociatedPowerManagementService"
            )
        }
        xml = dedent(
            """\
            <?xml version="1.0" encoding="UTF-8"?>
            <root>text</root>
            <?xml version="1.0" encoding="UTF-8"?>
            <h:Envelope xmlns:h="%s">
                <h:Body>
                    <h:CIM_AssociatedPowerManagementService>
                        <h:PowerState>8</h:PowerState>
                    </h:CIM_AssociatedPowerManagementService>
                </h:Body>
            </h:Envelope>
        """
        ).encode("utf-8")

        result = amt_power_driver.get_power_state(
            xml % namespaces["h"].encode("utf-8")
        )

        self.assertEqual(result, "8")

    def test_run_runs_command(self):
        amt_power_driver = AMTPowerDriver()
        amt_power_driver.env = None
        command = (factory.make_name("command"),)
        power_pass = factory.make_name("power_pass")
        stdin = factory.make_name("stdin").encode("utf-8")
        run_command_mock = self.patch_run_command(stdout=b"stdout")

        result = amt_power_driver._run(command, power_pass, stdin)

        run_command_mock.assert_called_once_with(
            *command,
            stdin=stdin,
            extra_environ={"AMT_PASSWORD": power_pass},
            decode=False
        )
        self.assertEqual(result, b"stdout")

    def test_run_raises_power_action_error(self):
        amt_power_driver = AMTPowerDriver()
        self.patch_run_command(returncode=1)
        self.assertRaises(
            PowerActionError,
            amt_power_driver._run,
            (),
            factory.make_name("power-pass"),
            None,
        )

    def test_set_pxe_boot_sets_pxe(self):
        amt_power_driver = AMTPowerDriver()
        ip_address = factory.make_ipv4_address()
        power_pass = factory.make_name("power_pass")
        wsman_pxe_options = {
            "ChangeBootOrder": (
                join(dirname(dirname(__file__)), "amt.wsman-pxe.xml"),
                (
                    "http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/"
                    'CIM_BootConfigSetting?InstanceID="Intel(r) '
                    'AMT: Boot Configuration 0"'
                ),
            ),
            "SetBootConfigRole": (
                join(dirname(dirname(__file__)), "amt.wsman-boot-config.xml"),
                (
                    "http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/"
                    "CIM_BootService?SystemCreationClassName="
                    '"CIM_ComputerSystem"&SystemName="Intel(r) AMT"'
                    '&CreationClassName="CIM_BootService"&Name="Intel(r)'
                    ' AMT Boot Service"'
                ),
            ),
        }
        wsman_opts = (
            "-C",
            "/etc/openwsman/openwsman_client.conf",
            "--port",
            "16992",
            "--hostname",
            ip_address,
            "--username",
            "admin",
            "--password",
            power_pass,
            "--noverifypeer",
            "--noverifyhost",
            "--input",
            "-",
        )
        _run_mock = self.patch(amt_power_driver, "_run")
        amt_power_driver._set_pxe_boot(ip_address, power_pass)

        commands = []
        stdins = []
        for method, (schema_file, schema_uri) in wsman_pxe_options.items():
            with open(schema_file, "rb") as fd:
                action = ("invoke", "--method", method, schema_uri)
                command = ("wsman",) + wsman_opts + action
                commands.append(command)
                stdins.append(fd.read())
        _run_mock.assert_has_calls(
            [
                call(commands[0], power_pass, stdin=stdins[0]),
                call(commands[1], power_pass, stdin=stdins[1]),
            ]
        )

    def test_issue_amttool_command_calls__run(self):
        amt_power_driver = AMTPowerDriver()
        ip_address = factory.make_ipv4_address()
        power_pass = factory.make_name("power_pass")
        amttool_boot_mode = factory.make_name("amttool_boot_mode")
        stdin = factory.make_name("stdin").encode("utf-8")
        cmd = choice(["power-cycle", "powerup"])
        command = "amttool", ip_address, cmd, amttool_boot_mode
        _run_mock = self.patch(amt_power_driver, "_run")
        _run_mock.return_value = b"output"

        result = amt_power_driver._issue_amttool_command(
            cmd,
            ip_address,
            power_pass,
            amttool_boot_mode=amttool_boot_mode,
            stdin=stdin,
        )

        _run_mock.assert_called_once_with(command, power_pass, stdin=stdin)
        self.assertEqual(result, b"output")

    def test_issue_wsman_command_calls__run_for_power(self):
        amt_power_driver = AMTPowerDriver()
        power_change = choice(["on", "off", "restart"])
        ip_address = factory.make_ipv4_address()
        power_pass = factory.make_name("power_pass")
        wsman_power_schema_uri = (
            "http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/"
            "CIM_PowerManagementService?SystemCreationClassName="
            '"CIM_ComputerSystem"&SystemName="Intel(r) AMT"'
            '&CreationClassName="CIM_PowerManagementService"&Name='
            '"Intel(r) AMT Power Management Service"'
        )
        command = (
            "wsman",
            "-C",
            "/etc/openwsman/openwsman_client.conf",
            "--port",
            "16992",
            "--hostname",
            ip_address,
            "--username",
            "admin",
            "--password",
            power_pass,
            "--noverifypeer",
            "--noverifyhost",
            "--input",
            "-",
            "invoke",
            "--method",
            "RequestPowerStateChange",
            wsman_power_schema_uri,
        )
        _render_wsman_state_xml_mock = self.patch(
            amt_power_driver, "_render_wsman_state_xml"
        )
        _render_wsman_state_xml_mock.return_value = b"stdin"
        _run_mock = self.patch(amt_power_driver, "_run")
        _run_mock.return_value = b"output"

        result = amt_power_driver._issue_wsman_command(
            power_change, ip_address, power_pass
        )

        _run_mock.assert_called_once_with(command, power_pass, stdin=b"stdin")
        self.assertEqual(result, b"output")

    def test_issue_wsman_command_calls__run_for_query(self):
        amt_power_driver = AMTPowerDriver()
        ip_address = factory.make_ipv4_address()
        power_pass = factory.make_name("power_pass")
        wsman_query_schema_uri = (
            "http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/"
            "CIM_AssociatedPowerManagementService"
        )
        wsman_opts = (
            "-C",
            "/etc/openwsman/openwsman_client.conf",
            "--port",
            "16992",
            "--hostname",
            ip_address,
            "--username",
            "admin",
            "--password",
            power_pass,
            "--noverifypeer",
            "--noverifyhost",
        )
        wsman_query_opts = wsman_opts + ("--optimize", "--encoding", "utf-8")
        action = ("enumerate", wsman_query_schema_uri)
        command = ("wsman",) + wsman_query_opts + action
        _run_mock = self.patch(amt_power_driver, "_run")
        _run_mock.return_value = b"ignored"

        amt_power_driver._issue_wsman_command("query", ip_address, power_pass)

        _run_mock.assert_called_once_with(command, power_pass, stdin=None)

    def test_issue_wsman_has_config_file_from_snap(self):
        self.patch(
            amt_module.snap.SnapPaths, "from_environ"
        ).return_value = SnapPaths(snap=Path("/snap/maas/current"))
        ip_address = factory.make_ipv4_address()
        power_pass = factory.make_name("power_pass")
        amt_power_driver = AMTPowerDriver()
        _run_mock = self.patch(amt_power_driver, "_run")
        amt_power_driver._issue_wsman_command("query", ip_address, power_pass)
        [call] = _run_mock.mock_calls
        self.assertEqual(
            call.args[0][:3],
            (
                "wsman",
                "-C",
                "/snap/maas/current/etc/openwsman/openwsman_client.conf",
            ),
        )

    def test_amttool_query_state_queries_on(self):
        amt_power_driver = AMTPowerDriver()
        ip_address = factory.make_ipv4_address()
        power_pass = factory.make_name("power_pass")
        _issue_amttool_command_mock = self.patch(
            amt_power_driver, "_issue_amttool_command"
        )
        _issue_amttool_command_mock.return_value = AMTTOOL_OUTPUT % (
            b"",
            b"S0",
        )

        result = amt_power_driver.amttool_query_state(ip_address, power_pass)

        _issue_amttool_command_mock.assert_called_once_with(
            "info", ip_address, power_pass
        )
        self.assertEqual(result, "on")

    def test_amttool_query_state_queries_off(self):
        amt_power_driver = AMTPowerDriver()
        ip_address = factory.make_ipv4_address()
        power_pass = factory.make_name("power_pass")
        _issue_amttool_command_mock = self.patch(
            amt_power_driver, "_issue_amttool_command"
        )
        _issue_amttool_command_mock.return_value = AMTTOOL_OUTPUT % (
            b"",
            b"S5 (soft-off)",
        )

        result = amt_power_driver.amttool_query_state(ip_address, power_pass)

        _issue_amttool_command_mock.assert_called_once_with(
            "info", ip_address, power_pass
        )
        self.assertEqual(result, "off")

    def test_amttool_query_state_queries_unknown(self):
        amt_power_driver = AMTPowerDriver()
        ip_address = factory.make_ipv4_address()
        power_pass = factory.make_name("power_pass")
        amt_power_driver.ip_address = factory.make_name("ip_address")
        _issue_amttool_command_mock = self.patch(
            amt_power_driver, "_issue_amttool_command"
        )
        _issue_amttool_command_mock.return_value = AMTTOOL_OUTPUT % (
            b"",
            b"error",
        )

        self.assertRaises(
            PowerActionError,
            amt_power_driver.amttool_query_state,
            ip_address,
            power_pass,
        )
        _issue_amttool_command_mock.assert_called_once_with(
            "info", ip_address, power_pass
        )

    def test_amttool_query_state_runs_query_loop(self):
        amt_power_driver = AMTPowerDriver()
        ip_address = factory.make_ipv4_address()
        power_pass = factory.make_name("power_pass")
        self.patch(
            amt_power_driver, "_issue_amttool_command"
        ).return_value = b""
        self.assertRaises(
            PowerActionError,
            amt_power_driver.amttool_query_state,
            ip_address,
            power_pass,
        )

    def test_amttool_restart_power_cycles(self):
        amt_power_driver = AMTPowerDriver()
        ip_address = factory.make_ipv4_address()
        power_pass = factory.make_name("power_pass")
        amttool_boot_mode = factory.make_name("amttool_boot_mode")
        _issue_amttool_command_mock = self.patch(
            amt_power_driver, "_issue_amttool_command"
        )

        amt_power_driver.amttool_restart(
            ip_address, power_pass, amttool_boot_mode
        )

        _issue_amttool_command_mock.assert_called_once_with(
            "power_cycle",
            ip_address,
            power_pass,
            amttool_boot_mode=amttool_boot_mode,
            stdin=b"yes",
        )

    def test_amttool_power_on_powers_on(self):
        amt_power_driver = AMTPowerDriver()
        ip_address = factory.make_ipv4_address()
        power_pass = factory.make_name("power_pass")
        amttool_boot_mode = factory.make_name("amttool_boot_mode")
        _issue_amttool_command_mock = self.patch(
            amt_power_driver, "_issue_amttool_command"
        )
        amttool_query_state_mock = self.patch(
            amt_power_driver, "amttool_query_state"
        )
        amttool_query_state_mock.return_value = "on"

        amt_power_driver.amttool_power_on(
            ip_address, power_pass, amttool_boot_mode
        )

        _issue_amttool_command_mock.assert_called_once_with(
            "powerup",
            ip_address,
            power_pass,
            amttool_boot_mode=amttool_boot_mode,
            stdin=b"yes",
        )
        amttool_query_state_mock.assert_called_once_with(
            ip_address, power_pass
        )

    def test_amttool_power_on_raises_power_action_error(self):
        amt_power_driver = AMTPowerDriver()
        ip_address = factory.make_ipv4_address()
        power_pass = factory.make_name("power_pass")
        amttool_boot_mode = factory.make_name("amttool_boot_mode")
        self.patch(amt_power_driver, "_issue_amttool_command")
        amttool_query_state_mock = self.patch(
            amt_power_driver, "amttool_query_state"
        )
        amttool_query_state_mock.return_value = "error"

        self.assertRaises(
            PowerActionError,
            amt_power_driver.amttool_power_on,
            ip_address,
            power_pass,
            amttool_boot_mode,
        )

    def test_amttool_power_off_powers_off(self):
        amt_power_driver = AMTPowerDriver()
        ip_address = factory.make_ipv4_address()
        power_pass = factory.make_name("power_pass")
        amttool_query_state_mock = self.patch(
            amt_power_driver, "amttool_query_state"
        )
        amttool_query_state_mock.return_value = "off"

        amt_power_driver.amttool_power_off(ip_address, power_pass)

        amttool_query_state_mock.assert_called_once_with(
            ip_address, power_pass
        )

    def test_amttool_power_off_raises_power_action_error(self):
        amt_power_driver = AMTPowerDriver()
        ip_address = factory.make_ipv4_address()
        power_pass = factory.make_name("power_pass")
        amttool_query_state_mock = self.patch(
            amt_power_driver, "amttool_query_state"
        )
        amttool_query_state_mock.return_value = "error"
        self.patch(amt_power_driver, "_issue_amttool_command")

        self.assertRaises(
            PowerActionError,
            amt_power_driver.amttool_power_off,
            ip_address,
            power_pass,
        )

    def test_wsman_query_state_queries_on(self):
        amt_power_driver = AMTPowerDriver()
        ip_address = factory.make_ipv4_address()
        power_pass = factory.make_name("power_pass")
        get_power_state_mock = self.patch(amt_power_driver, "get_power_state")
        get_power_state_mock.return_value = "2"
        _issue_wsman_command_mock = self.patch(
            amt_power_driver, "_issue_wsman_command"
        )
        _issue_wsman_command_mock.return_value = WSMAN_OUTPUT % b"2"

        result = amt_power_driver.wsman_query_state(ip_address, power_pass)

        _issue_wsman_command_mock.assert_called_once_with(
            "query", ip_address, power_pass
        )
        self.assertEqual(result, "on")

    def test_wsman_query_state_queries_off(self):
        amt_power_driver = AMTPowerDriver()
        ip_address = factory.make_ipv4_address()
        power_pass = factory.make_name("power_pass")
        get_power_state_mock = self.patch(amt_power_driver, "get_power_state")
        get_power_state_mock.return_value = "6"
        _issue_wsman_command_mock = self.patch(
            amt_power_driver, "_issue_wsman_command"
        )
        _issue_wsman_command_mock.return_value = WSMAN_OUTPUT % b"6"

        result = amt_power_driver.wsman_query_state(ip_address, power_pass)

        _issue_wsman_command_mock.assert_called_once_with(
            "query", ip_address, power_pass
        )
        self.assertEqual(result, "off")

    def test_wsman_query_state_queries_unknown(self):
        amt_power_driver = AMTPowerDriver()
        ip_address = factory.make_ipv4_address()
        power_pass = factory.make_name("power_pass")
        get_power_state_mock = self.patch(amt_power_driver, "get_power_state")
        get_power_state_mock.return_value = "unknown"
        _issue_wsman_command_mock = self.patch(
            amt_power_driver, "_issue_wsman_command"
        )
        _issue_wsman_command_mock.return_value = WSMAN_OUTPUT % b"error"

        self.assertRaises(
            PowerActionError,
            amt_power_driver.wsman_query_state,
            ip_address,
            power_pass,
        )
        _issue_wsman_command_mock.assert_called_once_with(
            "query", ip_address, power_pass
        )

    def test_wsman_query_state_runs_query_loop(self):
        amt_power_driver = AMTPowerDriver()
        ip_address = factory.make_ipv4_address()
        power_pass = factory.make_name("power_pass")
        self.patch(amt_power_driver, "_issue_wsman_command").return_value = b""

        self.assertRaises(
            PowerActionError,
            amt_power_driver.wsman_query_state,
            ip_address,
            power_pass,
        )

    def test_wsman_power_on_powers_on(self):
        amt_power_driver = AMTPowerDriver()
        ip_address = factory.make_ipv4_address()
        power_pass = factory.make_name("power_pass")
        _set_pxe_boot_mock = self.patch(amt_power_driver, "_set_pxe_boot")
        _issue_wsman_command_mock = self.patch(
            amt_power_driver, "_issue_wsman_command"
        )
        wsman_query_state_mock = self.patch(
            amt_power_driver, "wsman_query_state"
        )
        wsman_query_state_mock.return_value = "on"

        amt_power_driver.wsman_power_on(ip_address, power_pass)

        _set_pxe_boot_mock.assert_called_once_with(ip_address, power_pass)
        _issue_wsman_command_mock.assert_called_once_with(
            "on", ip_address, power_pass
        )
        wsman_query_state_mock.assert_called_once_with(ip_address, power_pass)

    def test_wsman_power_on_powers_restart(self):
        amt_power_driver = AMTPowerDriver()
        ip_address = factory.make_ipv4_address()
        power_pass = factory.make_name("power_pass")
        _set_pxe_boot_mock = self.patch(amt_power_driver, "_set_pxe_boot")
        _issue_wsman_command_mock = self.patch(
            amt_power_driver, "_issue_wsman_command"
        )
        wsman_query_state_mock = self.patch(
            amt_power_driver, "wsman_query_state"
        )
        wsman_query_state_mock.return_value = "on"

        amt_power_driver.wsman_power_on(ip_address, power_pass, restart=True)

        _set_pxe_boot_mock.assert_called_once_with(ip_address, power_pass)
        _issue_wsman_command_mock.assert_called_once_with(
            "restart", ip_address, power_pass
        )
        wsman_query_state_mock.assert_called_once_with(ip_address, power_pass)

    def test_wsman_power_on_raises_power_action_error(self):
        amt_power_driver = AMTPowerDriver()
        ip_address = factory.make_ipv4_address()
        power_pass = factory.make_name("power_pass")
        self.patch(amt_power_driver, "_set_pxe_boot")
        self.patch(amt_power_driver, "_issue_wsman_command")
        wsman_query_state_mock = self.patch(
            amt_power_driver, "wsman_query_state"
        )
        wsman_query_state_mock.return_value = "error"

        self.assertRaises(
            PowerActionError,
            amt_power_driver.wsman_power_on,
            ip_address,
            power_pass,
        )

    def test_wsman_power_on_powers_off(self):
        amt_power_driver = AMTPowerDriver()
        ip_address = factory.make_ipv4_address()
        power_pass = factory.make_name("power_pass")
        _issue_wsman_command_mock = self.patch(
            amt_power_driver, "_issue_wsman_command"
        )
        wsman_query_state_mock = self.patch(
            amt_power_driver, "wsman_query_state"
        )
        wsman_query_state_mock.return_value = "off"

        amt_power_driver.wsman_power_off(ip_address, power_pass)

        _issue_wsman_command_mock.assert_called_once_with(
            "off", ip_address, power_pass
        )
        wsman_query_state_mock.assert_called_once_with(ip_address, power_pass)

    def test_wsman_power_off_raises_power_action_error(self):
        amt_power_driver = AMTPowerDriver()
        ip_address = factory.make_ipv4_address()
        power_pass = factory.make_name("power_pass")
        self.patch(amt_power_driver, "_issue_wsman_command")
        wsman_query_state_mock = self.patch(
            amt_power_driver, "wsman_query_state"
        )
        wsman_query_state_mock.return_value = "error"

        self.assertRaises(
            PowerActionError,
            amt_power_driver.wsman_power_off,
            ip_address,
            power_pass,
        )

    def test_get_amt_command_returns_amttool(self):
        amt_power_driver = AMTPowerDriver()
        ip_address = factory.make_ipv4_address()
        power_pass = factory.make_name("power_pass")
        mock_run_command = self.patch_run_command(
            stdout=WSMAN_IDENTIFY_OUTPUT % b"8.1.57",
            stderr=b"stderr",
            decode=True,
        )

        result = amt_power_driver._get_amt_command(ip_address, power_pass)
        mock_run_command.assert_called_once_with(
            "wsman",
            "-C",
            "/etc/openwsman/openwsman_client.conf",
            "identify",
            "--port",
            "16992",
            "--hostname",
            ip_address,
            "--username",
            "admin",
            "--password",
            power_pass,
        )
        self.assertEqual(result, "amttool")

    def test_get_amt_command_returns_wsman(self):
        amt_power_driver = AMTPowerDriver()
        ip_address = factory.make_ipv4_address()
        power_pass = factory.make_name("power_pass")
        mock_run_command = self.patch_run_command(
            stdout=WSMAN_IDENTIFY_OUTPUT % b"10.0.47",
            stderr=b"stderr",
            decode=True,
        )
        result = amt_power_driver._get_amt_command(ip_address, power_pass)

        mock_run_command.assert_called_once_with(
            "wsman",
            "-C",
            "/etc/openwsman/openwsman_client.conf",
            "identify",
            "--port",
            "16992",
            "--hostname",
            ip_address,
            "--username",
            "admin",
            "--password",
            power_pass,
        )
        self.assertEqual(result, "wsman")

    def test_get_amt_command_crashes_when_amttool_has_no_output(self):
        amt_power_driver = AMTPowerDriver()
        self.patch_run_command(decode=True)
        self.assertRaises(
            PowerConnError,
            amt_power_driver._get_amt_command,
            sentinel.ip_address,
            sentinel.power_pass,
        )

    def test_get_amt_command_crashes_when_no_version_found(self):
        amt_power_driver = AMTPowerDriver()
        self.patch_run_command(stdout=b"No match here", decode=True)
        self.assertRaises(
            PowerActionError,
            amt_power_driver._get_amt_command,
            sentinel.ip_address,
            sentinel.power_pass,
        )

    def test_get_amt_command_raises_power_error(self):
        amt_power_driver = AMTPowerDriver()
        for error, error_info in AMT_ERRORS.items():
            self.patch_run_command(stderr=error.encode("utf-8"), decode=True)
            self.assertRaises(
                error_info.get("exception"),
                amt_power_driver._get_amt_command,
                factory.make_ipv4_address(),
                factory.make_name("power_pass"),
            )

    def test_get_amttool_boot_mode_local_boot(self):
        amt_power_driver = AMTPowerDriver()
        result = amt_power_driver._get_amttool_boot_mode("local")
        self.assertEqual(result, "")

    def test_get_ammtool_boot_mode_pxe_booting(self):
        amt_power_driver = AMTPowerDriver()
        boot_mode = factory.make_name("boot_mode")
        result = amt_power_driver._get_amttool_boot_mode(boot_mode)
        self.assertEqual(result, boot_mode)

    def test_get_ip_address_returns_ip_address(self):
        amt_power_driver = AMTPowerDriver()
        power_address = factory.make_name("power_address")
        ip_address = factory.make_ipv4_address()
        result = amt_power_driver._get_ip_address(power_address, ip_address)
        self.assertEqual(result, ip_address)

    def test_get_ip_address_returns_power_address(self):
        amt_power_driver = AMTPowerDriver()
        power_address = factory.make_name("power_address")
        result = amt_power_driver._get_ip_address(power_address, None)
        self.assertEqual(result, power_address)

    def test_get_ip_address_raises_no_host_provided(self):
        amt_power_driver = AMTPowerDriver()
        self.assertRaises(
            PowerFatalError, amt_power_driver._get_ip_address, None, None
        )

    def test_power_on_powers_on_with_amttool_when_already_on(self):
        amt_power_driver = AMTPowerDriver()
        context = make_context()
        _get_amt_command_mock = self.patch(
            amt_power_driver, "_get_amt_command"
        )
        _get_amt_command_mock.return_value = "amttool"
        amttool_query_state_mock = self.patch(
            amt_power_driver, "amttool_query_state"
        )
        amttool_query_state_mock.return_value = "on"
        amttool_restart_mock = self.patch(amt_power_driver, "amttool_restart")

        amt_power_driver.power_on(context["system_id"], context)

        _get_amt_command_mock.assert_called_once_with(
            context["ip_address"], context["power_pass"]
        )
        amttool_query_state_mock.assert_called_once_with(
            context["ip_address"], context["power_pass"]
        )
        amttool_restart_mock.assert_called_once_with(
            context["ip_address"],
            context["power_pass"],
            context["boot_mode"],
        )

    def test_power_on_powers_on_with_amttool_when_already_off(self):
        amt_power_driver = AMTPowerDriver()
        context = make_context()
        _get_amt_command_mock = self.patch(
            amt_power_driver, "_get_amt_command"
        )
        _get_amt_command_mock.return_value = "amttool"
        amttool_query_state_mock = self.patch(
            amt_power_driver, "amttool_query_state"
        )
        amttool_query_state_mock.return_value = "off"
        amttool_power_on_mock = self.patch(
            amt_power_driver, "amttool_power_on"
        )

        amt_power_driver.power_on(context["system_id"], context)

        _get_amt_command_mock.assert_called_once_with(
            context["ip_address"], context["power_pass"]
        )
        amttool_query_state_mock.assert_called_once_with(
            context["ip_address"], context["power_pass"]
        )
        amttool_power_on_mock.assert_called_once_with(
            context["ip_address"],
            context["power_pass"],
            context["boot_mode"],
        )

    def test_power_on_powers_on_with_wsman_when_already_on(self):
        amt_power_driver = AMTPowerDriver()
        context = make_context()
        _get_amt_command_mock = self.patch(
            amt_power_driver, "_get_amt_command"
        )
        _get_amt_command_mock.return_value = "wsman"
        wsman_query_state_mock = self.patch(
            amt_power_driver, "wsman_query_state"
        )
        wsman_query_state_mock.return_value = "on"
        wsman_power_on_mock = self.patch(amt_power_driver, "wsman_power_on")

        amt_power_driver.power_on(context["system_id"], context)

        _get_amt_command_mock.assert_called_once_with(
            context["ip_address"], context["power_pass"]
        )
        wsman_query_state_mock.assert_called_once_with(
            context["ip_address"], context["power_pass"]
        )
        wsman_power_on_mock.assert_called_once_with(
            context["ip_address"], context["power_pass"], restart=True
        )

    def test_power_on_powers_on_with_wsman_when_already_off(self):
        amt_power_driver = AMTPowerDriver()
        context = make_context()
        _get_amt_command_mock = self.patch(
            amt_power_driver, "_get_amt_command"
        )
        _get_amt_command_mock.return_value = "wsman"
        wsman_query_state_mock = self.patch(
            amt_power_driver, "wsman_query_state"
        )
        wsman_query_state_mock.return_value = "off"
        wsman_power_on_mock = self.patch(amt_power_driver, "wsman_power_on")

        amt_power_driver.power_on(context["system_id"], context)

        _get_amt_command_mock.assert_called_once_with(
            context["ip_address"], context["power_pass"]
        )
        wsman_query_state_mock.assert_called_once_with(
            context["ip_address"], context["power_pass"]
        )
        wsman_power_on_mock.assert_called_once_with(
            context["ip_address"], context["power_pass"]
        )

    def test_power_off_powers_off_with_amttool(self):
        amt_power_driver = AMTPowerDriver()
        context = make_context()
        _get_amt_command_mock = self.patch(
            amt_power_driver, "_get_amt_command"
        )
        _get_amt_command_mock.return_value = "amttool"
        amttool_query_state_mock = self.patch(
            amt_power_driver, "amttool_query_state"
        )
        amttool_query_state_mock.return_value = "on"
        amttool_power_off_mock = self.patch(
            amt_power_driver, "amttool_power_off"
        )

        amt_power_driver.power_off(context["system_id"], context)
        _get_amt_command_mock.assert_called_once_with(
            context["ip_address"], context["power_pass"]
        )
        amttool_query_state_mock.assert_called_once_with(
            context["ip_address"], context["power_pass"]
        )
        amttool_power_off_mock.assert_called_once_with(
            context["ip_address"], context["power_pass"]
        )

    def test_power_off_powers_off_with_wsman(self):
        amt_power_driver = AMTPowerDriver()
        context = make_context()
        _get_amt_command_mock = self.patch(
            amt_power_driver, "_get_amt_command"
        )
        _get_amt_command_mock.return_value = "wsman"
        wsman_query_state_mock = self.patch(
            amt_power_driver, "wsman_query_state"
        )
        wsman_query_state_mock.return_value = "on"
        wsman_power_off_mock = self.patch(amt_power_driver, "wsman_power_off")

        amt_power_driver.power_off(context["system_id"], context)
        _get_amt_command_mock.assert_called_once_with(
            context["ip_address"], context["power_pass"]
        )
        wsman_query_state_mock.assert_called_once_with(
            context["ip_address"], context["power_pass"]
        )
        wsman_power_off_mock.assert_called_once_with(
            context["ip_address"], context["power_pass"]
        )

    def test_power_query_queries_with_amttool(self):
        amt_power_driver = AMTPowerDriver()
        context = make_context()
        _get_amt_command_mock = self.patch(
            amt_power_driver, "_get_amt_command"
        )
        _get_amt_command_mock.return_value = "amttool"
        amttool_query_state_mock = self.patch(
            amt_power_driver, "amttool_query_state"
        )
        amttool_query_state_mock.return_value = "off"

        state = amt_power_driver.power_query(context["system_id"], context)

        _get_amt_command_mock.assert_called_once_with(
            context["ip_address"], context["power_pass"]
        )
        amttool_query_state_mock.assert_called_once_with(
            context["ip_address"], context["power_pass"]
        )
        self.assertEqual(state, "off")

    def test_power_query_queries_with_wsman(self):
        amt_power_driver = AMTPowerDriver()
        context = make_context()
        _get_amt_command_mock = self.patch(
            amt_power_driver, "_get_amt_command"
        )
        _get_amt_command_mock.return_value = "wsman"
        wsman_query_state_mock = self.patch(
            amt_power_driver, "wsman_query_state"
        )
        wsman_query_state_mock.return_value = "on"

        state = amt_power_driver.power_query(context["system_id"], context)

        _get_amt_command_mock.assert_called_once_with(
            context["ip_address"], context["power_pass"]
        )
        wsman_query_state_mock.assert_called_once_with(
            context["ip_address"], context["power_pass"]
        )
        self.assertEqual(state, "on")
