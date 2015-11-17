# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""AMT Power Driver."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from itertools import chain
from os.path import (
    dirname,
    join,
)
import re
from subprocess import (
    PIPE,
    Popen,
)
from time import sleep

from lxml import etree
from provisioningserver.drivers.power import (
    get_c_environment,
    is_power_parameter_set,
    PowerActionError,
    PowerDriver,
    PowerFatalError,
)
from provisioningserver.utils import shell


REQUIRED_PACKAGES = [["amttool", "amtterm"], ["wsman", "wsmancli"]]


class AMTPowerDriver(PowerDriver):

    name = 'amt'
    description = "AMT Power Driver."
    settings = []

    def detect_missing_packages(self):
        missing_packages = []
        for binary, package in REQUIRED_PACKAGES:
            if not shell.has_command_available(binary):
                missing_packages.append(package)
        return missing_packages

    def _render_wsman_state_xml(self, power_change):
        """Render wsman state XML."""
        wsman_state_filename = join(dirname(__file__), "amt.wsman-state.xml")
        wsman_state_ns = {
            "p": (
                "http://schemas.dmtf.org/wbem/wscim/1/cim-schema"
                "/2/CIM_PowerManagementService"
            ),
        }
        tree = etree.parse(wsman_state_filename)
        [ps] = tree.xpath("//p:PowerState", namespaces=wsman_state_ns)
        power_states = {'on': '2', 'off': '8', 'restart': '10'}
        ps.text = power_states[power_change]
        return etree.tostring(tree)

    def _parse_multiple_xml_docs(self, xml):
        """Parse multiple XML documents.

        Each document must commence with an XML document declaration, i.e.
        <?xml ...

        Works around a weird decision in `wsman` where it returns multiple XML
        documents in a single stream.
        """
        xmldecl = re.compile(b'<[?]xml\\s')
        xmldecls = xmldecl.finditer(xml)
        starts = [match.start() for match in xmldecls]
        ends = starts[1:] + [len(xml)]
        frags = (xml[start:end] for start, end in zip(starts, ends))
        return (etree.fromstring(frag) for frag in frags)

    def get_power_state(self, xml):
        """Get PowerState text from XML."""
        namespaces = {
            "h": (
                "http://schemas.dmtf.org/wbem/wscim/1/cim-schema"
                "/2/CIM_AssociatedPowerManagementService"
            ),
        }
        state = next(chain.from_iterable(
            doc.xpath('//h:PowerState/text()', namespaces=namespaces)
            for doc in self._parse_multiple_xml_docs(xml)
        ))
        return state

    def _get_amt_environment(self, power_pass):
        """Set and return environment for AMT."""
        env = get_c_environment()
        env['AMT_PASSWORD'] = power_pass
        return env

    def _run(self, command, power_pass, stdin=None):
        """Run a subprocess with stdin."""
        env = self._get_amt_environment(power_pass)
        process = Popen(
            command, stdin=PIPE, stdout=PIPE, stderr=PIPE, env=env)
        stdout, stderr = process.communicate(stdin)
        if process.returncode != 0:
            raise PowerFatalError(
                "Failed to run command: %s with error: %s" % (command, stderr))
        return stdout

    def _issue_amttool_command(
            self, cmd, ip_address, power_pass,
            amttool_boot_mode=None, stdin=None):
        """Perform a command using amttool."""
        command = ('amttool', ip_address, cmd)
        if cmd in ('power-cycle', 'powerup'):
            command += (amttool_boot_mode,)
        return self._run(command, power_pass, stdin=stdin)

    def _issue_wsman_command(self, power_change, ip_address, power_pass):
        """Perform a command using wsman."""
        wsman_power_schema_uri = (
            'http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/'
            'CIM_PowerManagementService?SystemCreationClassName='
            '"CIM_ComputerSystem",SystemName="Intel(r) AMT"'
            ',CreationClassName="CIM_PowerManagementService",Name='
            '"Intel(r) AMT Power Management Service"'
        )
        wsman_query_schema_uri = (
            'http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/'
            'CIM_AssociatedPowerManagementService'
        )
        wsman_power_opts = (
            '--port', '16992', '--hostname', ip_address, '--username',
            'admin', '-p', power_pass, '-V', '-v'
        )
        if power_change in ('on', 'off', 'restart'):
            stdin = self._render_wsman_state_xml(power_change)
            command = (
                'wsman', 'invoke', '-a',
                'RequestPowerStateChange',
                wsman_power_schema_uri
            ) + wsman_power_opts + ('-J', '-')
        elif power_change == 'query':
            wsman_query_opts = wsman_power_opts + ('-o', '-j', 'utf-8')
            stdin = None  # No input for query
            command = (
                'wsman', 'enumerate', wsman_query_schema_uri
            ) + wsman_query_opts
        return self._run(command, power_pass, stdin=stdin)

    def amttool_query_state(self, ip_address, power_pass):
        """Ask for node's power state: 'on' or 'off', via amttool."""
        # Retry the state if it fails because it often fails the first time
        output = None
        for _ in xrange(10):
            output = self._issue_amttool_command(
                'info', ip_address, power_pass)
            if output is not None and output != '':
                break
            # Wait 1 second between retries.  AMT controllers are generally
            # very light and may not be comfortable with more frequent
            # queries.
            sleep(1)

        if output is None:
            raise PowerFatalError("amttool power querying FAILED.")
        # Wide awake (S0), or asleep (S1-S4), but not a clean slate that
        # will lead to a fresh boot.
        if 'S5' in output:
            return 'off'
        for state in ('S0', 'S1', 'S2', 'S3', 'S4'):
            if state in output:
                return 'on'
        raise PowerActionError(
            "Got unknown power state from node: %s" % state)

    def wsman_query_state(self, ip_address, power_pass):
        """Ask for node's power state: 'on' or 'off', via wsman."""
        # Retry the state if it fails because it often fails the first time.
        output = None
        for _ in xrange(10):
            output = self._issue_wsman_command('query', ip_address, power_pass)
            if output is not None and output != '':
                break
            # Wait 1 second between retries.  AMT controllers are generally
            # very light and may not be comfortable with more frequent
            # queries.
            sleep(1)

        if output is None:
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
            if state in (
                    '2', '3', '4', '5', '7', '9', '10', '14', '15', '16'):
                return 'on'
            elif state in ('6', '8', '12', '13'):
                return 'off'
            else:
                raise PowerFatalError(
                    "Got unknown power state from node: %s" % state)

    def amttool_restart(self, ip_address, power_pass, amttool_boot_mode):
        """Restart the node via amttool."""
        self._issue_amttool_command(
            'power_cycle', ip_address, power_pass,
            amttool_boot_mode=amttool_boot_mode, stdin='yes')

    def wsman_restart(self, ip_address, power_pass):
        """Restart the node via wsman."""
        self._issue_wsman_command('restart', ip_address, power_pass)

    def amttool_power_on(self, ip_address, power_pass, amttool_boot_mode):
        """Power on the node via amttool."""
        # Try several times.  Power commands often fail the first time.
        for _ in xrange(10):
            # Issue the AMT command; amttool will prompt for confirmation.
            self._issue_amttool_command(
                'powerup', ip_address, power_pass,
                amttool_boot_mode=amttool_boot_mode, stdin='yes')
            if self.amttool_query_state(ip_address, power_pass) == 'on':
                return
            sleep(1)
        raise PowerActionError("Machine is not powering on.  Giving up.")

    def wsman_power_on(self, ip_address, power_pass):
        """Power on the node via wsman."""
        # Issue the wsman command to change power state.
        self._issue_wsman_command('on', ip_address, power_pass)
        # Check power state several times.  It usually takes a second or
        # two to get the correct state.
        for _ in xrange(10):
            if self.wsman_query_state(ip_address, power_pass) == 'on':
                return  # Success.  Machine is on.
            sleep(1)
        raise PowerActionError("Machine is not powering on.  Giving up.")

    def amttool_power_off(self, ip_address, power_pass):
        """Power off the node via amttool."""
        # Try several times.  Power commands often fail the first time.
        for _ in xrange(10):
            if self.amttool_query_state(ip_address, power_pass) == 'off':
                # Success.  Machine is off.
                return
                # Issue the AMT command; amttool will prompt for confirmation.
            self._issue_amttool_command(
                'powerdown', ip_address, power_pass, stdin='yes')
            sleep(1)
        raise PowerActionError("Machine is not powering off.  Giving up.")

    def wsman_power_off(self, ip_address, power_pass):
        """Power off the node via wsman."""
        # Issue the wsman command to change power state.
        self._issue_wsman_command('off', ip_address, power_pass)
        # Check power state several times.  It usually takes a second or
        # two to get the correct state.
        for _ in xrange(10):
            if self.wsman_query_state(ip_address, power_pass) == 'off':
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
        env = self._get_amt_environment(power_pass)
        process = Popen(
            ('amttool', ip_address, 'info'), stdout=PIPE, stderr=PIPE, env=env)
        stdout, stderr = process.communicate()
        stderr = stderr.strip()
        # Need to check for both because querying normally gives
        # stdout and returncode !=0.  Only when both conditions are met
        # do we know that we should raise an exception.
        if process.returncode != 0 and not stdout:
            raise PowerFatalError(
                "Unable to retrieve AMT version: %s" % stderr)
        version = stdout.split(
            'AMT version:')[1].split()[0].split('.')[0]
        if version > '8':
            return 'wsman'
        else:
            return 'amttool'

    def _get_amttool_boot_mode(self, boot_mode):
        """Set amttool boot mode."""
        # boot_mode tells us whether we're pxe booting or local booting.
        # For local booting, the argument to amttool must be empty
        # (NOT 'hd', it doesn't work!).
        if boot_mode == 'local':
            return ''
        else:
            return boot_mode

    def _get_ip_address(self, power_address, ip_address):
        """Get the IP address of the AMT BMC."""
        # The user specified power_address overrides any automatically
        # determined ip_address.
        if (is_power_parameter_set(power_address) and not
                is_power_parameter_set(ip_address)):
            return power_address
        elif is_power_parameter_set(ip_address):
            return ip_address
        else:
            raise PowerFatalError('No host provided')

    def power_on(self, system_id, context):
        """Power on AMT node."""
        ip_address = self._get_ip_address(
            context.get('power_address'), context.get('ip_address'))
        power_pass = context.get('power_pass')
        amt_command = self._get_amt_command(ip_address, power_pass)
        if amt_command == 'amttool':
            amttool_boot_mode = self._get_amttool_boot_mode(
                context.get('boot_mode'))
            if self.amttool_query_state(ip_address, power_pass) == 'on':
                self.amttool_restart(ip_address, power_pass, amttool_boot_mode)
            else:
                self.amttool_power_on(
                    ip_address, power_pass, amttool_boot_mode)
        elif amt_command == 'wsman':
            if self.wsman_query_state(ip_address, power_pass) == 'on':
                self.wsman_restart(ip_address, power_pass)
            else:
                self.wsman_power_on(ip_address, power_pass)

    def power_off(self, system_id, context):
        """Power off AMT node."""
        ip_address = self._get_ip_address(
            context.get('power_address'), context.get('ip_address'))
        power_pass = context.get('power_pass')
        amt_command = self._get_amt_command(ip_address, power_pass)
        if amt_command == 'amttool':
            if self.amttool_query_state(ip_address, power_pass) != 'off':
                self.amttool_power_off(ip_address, power_pass)
        elif amt_command == 'wsman':
            if self.wsman_query_state(ip_address, power_pass) != 'off':
                self.wsman_power_off(ip_address, power_pass)

    def power_query(self, system_id, context):
        """Power query AMT node."""
        ip_address = self._get_ip_address(
            context.get('power_address'), context.get('ip_address'))
        power_pass = context.get('power_pass')
        amt_command = self._get_amt_command(ip_address, power_pass)
        if amt_command == 'amttool':
            return self.amttool_query_state(ip_address, power_pass)
        elif amt_command == 'wsman':
            return self.wsman_query_state(ip_address, power_pass)
