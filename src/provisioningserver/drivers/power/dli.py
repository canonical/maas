# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""DLI Power Driver."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from time import sleep

from provisioningserver.drivers.power import (
    PowerDriver,
    PowerError,
    PowerFatalError,
)
from provisioningserver.utils import shell
from provisioningserver.utils.shell import (
    call_and_check,
    ExternalProcessError,
)


class DLIPowerDriver(PowerDriver):
    name = 'dli'
    description = "DLI Power Driver."
    settings = []

    def detect_missing_packages(self):
        if not shell.has_command_available('wget'):
            return ['wget']
        return []

    def _set_outlet_state(
            self, power_change, outlet_id=None, power_user=None,
            power_pass=None, power_address=None, **extra):
        """Power DLI outlet ON/OFF."""
        try:
            url = 'http://%s:%s@%s/outlet?%s=%s' % (
                power_user, power_pass, power_address, outlet_id, power_change)
            # --auth-no-challenge: send Basic HTTP authentication
            # information without first waiting for the server's challenge.
            call_and_check([
                'wget', '--auth-no-challenge', '-O', '/dev/null', url])
        except ExternalProcessError as e:
            raise PowerFatalError(
                "Failed to power %s outlet %s: %s" % (
                    power_change, outlet_id, e.output_as_unicode))

    def _query_outlet_state(
            self, outlet_id=None, power_user=None,
            power_pass=None, power_address=None, **extra):
        """Query DLI outlet power state.

        Sample snippet of query output from DLI:
        ...
        <!--
        function reg() {
        window.open('http://www.digital-loggers.com/reg.html?SN=LPC751740');
        }
        //-->
        </script>
        </head>
        <!-- state=02 lock=00 -->

        <body alink="#0000FF" vlink="#0000FF">
        <FONT FACE="Arial, Helvetica, Sans-Serif">
        ...
        """
        try:
            url = 'http://%s:%s@%s/index.htm' % (
                power_user, power_pass, power_address)
            # --auth-no-challenge: send Basic HTTP authentication
            # information without first waiting for the server's challenge.
            query = call_and_check([
                'wget', '--auth-no-challenge', '-qO-', url])
            state = query.split('<!-- state=')[1].split()[0]
            # state is a bitmap of the DLI's oulet states, where bit 0
            # corresponds to oulet 1's power state, bit 1 corresponds to
            # outlet 2's power state, etc., encoded as hexadecimal.
            if (int(state, 16) & (1 << int(outlet_id) - 1)) > 0:
                return 'on'
            else:
                return 'off'
        except ExternalProcessError as e:
            raise PowerFatalError(
                "Failed to power query outlet %s: %s" % (
                    outlet_id, e.output_as_unicode))

    def power_on(self, system_id, context):
        """Power on DLI outlet."""
        if self._query_outlet_state(**context) == 'on':
            self._set_outlet_state('OFF', **context)
            sleep(1)
            if self._query_outlet_state(**context) != 'off':
                raise PowerError(
                    "Unable to power off outlet %s that is already on."
                    % context['outlet_id'])
        self._set_outlet_state('ON', **context)

    def power_off(self, system_id, context):
        """Power off DLI outlet."""
        self._set_outlet_state('OFF', **context)

    def power_query(self, system_id, context):
        """Power query DLI outlet."""
        return self._query_outlet_state(**context)
