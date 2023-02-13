# Copyright 2015-2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""AMT Power Driver."""


from itertools import chain
from os.path import dirname, join
import re
from time import sleep

from lxml import etree

from provisioningserver.drivers import make_ip_extractor, make_setting_field
from provisioningserver.drivers.power import (
    is_power_parameter_set,
    PowerActionError,
    PowerAuthError,
    PowerConnError,
    PowerDriver,
    PowerSettingError,
)
from provisioningserver.utils import shell, snap

AMT_ERRORS = {
    "401 Unauthorized": {
        "message": (
            "Incorrect password.  Check BMC configuration and try again."
        ),
        "exception": PowerAuthError,
    },
    "500 Can't connect": {
        "message": (
            "Could not connect to BMC.  "
            "Check BMC configuration and try again."
        ),
        "exception": PowerConnError,
    },
}


REQUIRED_PACKAGES = [["wsman", "wsmancli"]]


class AMTPowerDriver(PowerDriver):
    name = "amt"
    chassis = False
    can_probe = False
    can_set_boot_order = False
    description = "Intel AMT"
    settings = [
        make_setting_field(
            "power_pass", "Power password", field_type="password", secret=True
        ),
        make_setting_field("power_address", "Power address", required=True),
    ]
    ip_extractor = make_ip_extractor("power_address")

    def detect_missing_packages(self):
        missing_packages = []
        for binary, package in REQUIRED_PACKAGES:
            if not shell.has_command_available(binary):
                missing_packages.append(package)
        return missing_packages

    def _render_wsman_state_xml(self, power_change) -> bytes:
        """Render wsman state XML."""
        wsman_state_filename = join(dirname(__file__), "amt.wsman-state.xml")
        wsman_state_ns = {
            "p": (
                "http://schemas.dmtf.org/wbem/wscim/1/cim-schema"
                "/2/CIM_PowerManagementService"
            )
        }
        tree = etree.parse(wsman_state_filename)
        [ps] = tree.xpath("//p:PowerState", namespaces=wsman_state_ns)
        power_states = {"on": "2", "off": "8", "restart": "10"}
        ps.text = power_states[power_change]
        return etree.tostring(tree)

    def _parse_multiple_xml_docs(self, xml: bytes):
        """Parse multiple XML documents.

        Each document must commence with an XML document declaration, i.e.
        <?xml ...

        Works around a weird decision in `wsman` where it returns multiple XML
        documents in a single stream.
        """
        xmldecl = re.compile(b"<[?]xml\\s")
        xmldecls = xmldecl.finditer(xml)
        starts = [match.start() for match in xmldecls]
        ends = starts[1:] + [len(xml)]
        frags = (xml[start:end] for start, end in zip(starts, ends))
        return (etree.fromstring(frag) for frag in frags)

    def get_power_state(self, xml: bytes) -> str:
        """Get PowerState text from XML."""
        namespaces = {
            "h": (
                "http://schemas.dmtf.org/wbem/wscim/1/cim-schema"
                "/2/CIM_AssociatedPowerManagementService"
            )
        }
        state = next(
            chain.from_iterable(
                doc.xpath("//h:PowerState/text()", namespaces=namespaces)
                for doc in self._parse_multiple_xml_docs(xml)
            )
        )
        return state

    def _set_pxe_boot(self, ip_address, power_pass):
        """Set to PXE for next boot."""
        wsman_pxe_options = {
            "ChangeBootOrder": (
                join(dirname(__file__), "amt.wsman-pxe.xml"),
                (
                    "http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/"
                    'CIM_BootConfigSetting?InstanceID="Intel(r) '
                    'AMT: Boot Configuration 0"'
                ),
            ),
            "SetBootConfigRole": (
                join(dirname(__file__), "amt.wsman-boot-config.xml"),
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
        )
        # Change boot order to PXE and enable boot config request
        for method, (schema_file, schema_uri) in wsman_pxe_options.items():
            with open(schema_file, "rb") as fd:
                command = self._get_wsman_command(
                    *wsman_opts, method, schema_uri
                )
                self._run(command, power_pass, stdin=fd.read())

    def _run(
        self, command: tuple, power_pass: str, stdin: bytes = None
    ) -> bytes:
        """Run a subprocess with stdin."""
        result = shell.run_command(
            *command,
            stdin=stdin,
            extra_environ={"AMT_PASSWORD": power_pass},
            decode=False,
        )
        if result.returncode != 0:
            raise PowerActionError(
                "Failed to run command: %s with error: %s"
                % (command, result.stderr.decode("utf-8", "replace"))
            )
        return result.stdout

    def _issue_amttool_command(
        self,
        cmd: str,
        ip_address: str,
        power_pass: str,
        amttool_boot_mode=None,
        stdin=None,
    ) -> bytes:
        """Perform a command using amttool."""
        command = ("amttool", ip_address, cmd)
        if cmd in ("power-cycle", "powerup"):
            command += (amttool_boot_mode,)
        return self._run(command, power_pass, stdin=stdin)

    def _issue_wsman_command(
        self, power_change: str, ip_address: str, power_pass: str
    ) -> bytes:
        """Perform a command using wsman."""
        wsman_power_schema_uri = (
            "http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/"
            "CIM_PowerManagementService?SystemCreationClassName="
            '"CIM_ComputerSystem"&SystemName="Intel(r) AMT"'
            '&CreationClassName="CIM_PowerManagementService"&Name='
            '"Intel(r) AMT Power Management Service"'
        )
        wsman_query_schema_uri = (
            "http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/"
            "CIM_AssociatedPowerManagementService"
        )
        command_args = (
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
        if power_change in ("on", "off", "restart"):
            stdin = self._render_wsman_state_xml(power_change)
            command_args += (
                "--input",
                "-",
                "invoke",
                "--method",
                "RequestPowerStateChange",
                wsman_power_schema_uri,
            )
        elif power_change == "query":
            stdin = None  # No input for query
            command_args += (
                "--optimize",
                "--encoding",
                "utf-8",
                "enumerate",
                wsman_query_schema_uri,
            )
        command = self._get_wsman_command(*command_args)
        return self._run(command, power_pass, stdin=stdin)

    def amttool_query_state(self, ip_address, power_pass):
        """Ask for node's power state: 'on' or 'off', via amttool."""
        # Retry the state if it fails because it often fails the first time
        for _ in range(10):
            output = self._issue_amttool_command(
                "info", ip_address, power_pass
            )
            if output:
                break
            # Wait 1 second between retries.  AMT controllers are generally
            # very light and may not be comfortable with more frequent
            # queries.
            sleep(1)

        if not output:
            raise PowerActionError("amttool power querying failed.")

        # Ensure that from this point forward that output is a str.
        output = output.decode("utf-8")

        # Wide awake (S0), or asleep (S1-S4), but not a clean slate that
        # will lead to a fresh boot.
        if "S5" in output:
            return "off"
        for state in ("S0", "S1", "S2", "S3", "S4"):
            if state in output:
                return "on"
        raise PowerActionError("Got unknown power state from node: %s" % state)

    def wsman_query_state(self, ip_address, power_pass):
        """Ask for node's power state: 'on' or 'off', via wsman."""
        # Retry the state if it fails because it often fails the first time.
        for _ in range(10):
            output = self._issue_wsman_command("query", ip_address, power_pass)
            if output:
                break
            # Wait 1 second between retries.  AMT controllers are generally
            # very light and may not be comfortable with more frequent
            # queries.
            sleep(1)

        if not output:
            raise PowerActionError("wsman power querying failed.")
        else:
            state = self.get_power_state(output)
            # There are a LOT of possible power states
            # 1: Other                    9: Power Cycle (Off-Hard)
            # 2: On                       10: Master Bus Reset
            # 3: Sleep - Light            11: Diagnostic Interrupt (NMI)
            # 4: Sleep - Deep             12: Off - Soft Graceful
            # 5: Power Cycle (Off - Soft) 13: Off - Hard Graceful
            # 6: Off - Hard               14: Master Bus Reset Graceful
            # 7: Hibernate (Off - Soft)   15: Power Cycle (Off-Soft Graceful)
            # 8: Off - Soft               16: Power Cycle (Off-Hard Graceful)
            #                             17: Diagnostic Interrupt (INIT)

            # These are all power states that indicate that the system is
            # either ON or will resume function in an ON or Powered Up
            # state (e.g. being power cycled currently)
            if state in ("2", "3", "4", "5", "7", "9", "10", "14", "15", "16"):
                return "on"
            elif state in ("6", "8", "12", "13"):
                return "off"
            else:
                raise PowerActionError(
                    "Got unknown power state from node: %s" % state
                )

    def amttool_restart(self, ip_address, power_pass, amttool_boot_mode):
        """Restart the node via amttool."""
        self._issue_amttool_command(
            "power_cycle",
            ip_address,
            power_pass,
            amttool_boot_mode=amttool_boot_mode,
            stdin=b"yes",
        )

    def amttool_power_on(self, ip_address, power_pass, amttool_boot_mode):
        """Power on the node via amttool."""
        # Try several times.  Power commands often fail the first time.
        for _ in range(10):
            # Issue the AMT command; amttool will prompt for confirmation.
            self._issue_amttool_command(
                "powerup",
                ip_address,
                power_pass,
                amttool_boot_mode=amttool_boot_mode,
                stdin=b"yes",
            )
            if self.amttool_query_state(ip_address, power_pass) == "on":
                return
            sleep(1)
        raise PowerActionError("Machine is not powering on.  Giving up.")

    def wsman_power_on(self, ip_address, power_pass, restart=False):
        """Power on the node via wsman."""
        power_command = "restart" if restart else "on"
        self._set_pxe_boot(ip_address, power_pass)
        self._issue_wsman_command(power_command, ip_address, power_pass)
        # Check power state several times.  It usually takes a second or
        # two to get the correct state.
        for _ in range(10):
            if self.wsman_query_state(ip_address, power_pass) == "on":
                return  # Success.  Machine is on.
            sleep(1)
        raise PowerActionError("Machine is not powering on.  Giving up.")

    def amttool_power_off(self, ip_address, power_pass):
        """Power off the node via amttool."""
        # Try several times.  Power commands often fail the first time.
        for _ in range(10):
            if self.amttool_query_state(ip_address, power_pass) == "off":
                # Success.  Machine is off.
                return
                # Issue the AMT command; amttool will prompt for confirmation.
            self._issue_amttool_command(
                "powerdown", ip_address, power_pass, stdin=b"yes"
            )
            sleep(1)
        raise PowerActionError("Machine is not powering off.  Giving up.")

    def wsman_power_off(self, ip_address, power_pass):
        """Power off the node via wsman."""
        # Issue the wsman command to change power state.
        self._issue_wsman_command("off", ip_address, power_pass)
        # Check power state several times.  It usually takes a second or
        # two to get the correct state.
        for _ in range(10):
            if self.wsman_query_state(ip_address, power_pass) == "off":
                return  # Success.  Machine is off.
            else:
                sleep(1)
        raise PowerActionError("Machine is not powering off.  Giving up.")

    def _get_amt_command(self, ip_address, power_pass):
        """Retrieve AMT command to use, either amttool or wsman
        (if AMT version > 8), for the given system.
        """
        # XXX bug=1331214
        # Check if the AMT ver > 8
        # If so, we need wsman, not amttool
        command = self._get_wsman_command(
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
        result = shell.run_command(*command)
        if not result.stdout:
            for error, error_info in AMT_ERRORS.items():
                if error in result.stderr:
                    raise error_info.get("exception")(
                        error_info.get("message")
                    )
            raise PowerConnError(
                f"Unable to retrieve AMT version: {result.stderr}"
            )
        else:
            match = re.search(r"ProductVersion>AMT\s*([0-9]+)", result.stdout)
            if match is None:
                raise PowerActionError(
                    "Unable to extract AMT version from "
                    f"amttool output: {result.stdout}"
                )
            else:
                version = match.group(1)
                if int(version) > 8:
                    return "wsman"
                else:
                    return "amttool"

    def _get_amttool_boot_mode(self, boot_mode):
        """Set amttool boot mode."""
        # boot_mode tells us whether we're pxe booting or local booting.
        # For local booting, the argument to amttool must be empty
        # (NOT 'hd', it doesn't work!).
        if boot_mode == "local":
            return ""
        else:
            return boot_mode

    def _get_wsman_command(self, *args):
        base_path = snap.SnapPaths.from_environ().snap or "/"
        return (
            "wsman",
            "-C",
            join(base_path, "etc/openwsman/openwsman_client.conf"),
        ) + args

    def _get_ip_address(self, power_address, ip_address):
        """Get the IP address of the AMT BMC."""
        # The user specified power_address overrides any automatically
        # determined ip_address.
        if is_power_parameter_set(
            power_address
        ) and not is_power_parameter_set(ip_address):
            return power_address
        elif is_power_parameter_set(ip_address):
            return ip_address
        else:
            raise PowerSettingError(
                "No IP address provided.  "
                "Please update BMC configuration and try again."
            )

    def power_on(self, system_id, context):
        """Power on AMT node."""
        ip_address = self._get_ip_address(
            context.get("power_address"), context.get("ip_address")
        )
        power_pass = context.get("power_pass")
        amt_command = self._get_amt_command(ip_address, power_pass)
        if amt_command == "amttool":
            amttool_boot_mode = self._get_amttool_boot_mode(
                context.get("boot_mode")
            )
            if self.amttool_query_state(ip_address, power_pass) == "on":
                self.amttool_restart(ip_address, power_pass, amttool_boot_mode)
            else:
                self.amttool_power_on(
                    ip_address, power_pass, amttool_boot_mode
                )
        elif amt_command == "wsman":
            if self.wsman_query_state(ip_address, power_pass) == "on":
                self.wsman_power_on(ip_address, power_pass, restart=True)
            else:
                self.wsman_power_on(ip_address, power_pass)

    def power_off(self, system_id, context):
        """Power off AMT node."""
        ip_address = self._get_ip_address(
            context.get("power_address"), context.get("ip_address")
        )
        power_pass = context.get("power_pass")
        amt_command = self._get_amt_command(ip_address, power_pass)
        if amt_command == "amttool":
            if self.amttool_query_state(ip_address, power_pass) != "off":
                self.amttool_power_off(ip_address, power_pass)
        elif amt_command == "wsman":
            if self.wsman_query_state(ip_address, power_pass) != "off":
                self.wsman_power_off(ip_address, power_pass)

    def power_query(self, system_id, context):
        """Power query AMT node."""
        ip_address = self._get_ip_address(
            context.get("power_address"), context.get("ip_address")
        )
        power_pass = context.get("power_pass")
        amt_command = self._get_amt_command(ip_address, power_pass)
        if amt_command == "amttool":
            return self.amttool_query_state(ip_address, power_pass)
        elif amt_command == "wsman":
            return self.wsman_query_state(ip_address, power_pass)
