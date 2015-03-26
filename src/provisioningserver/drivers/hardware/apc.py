# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Support for managing American Power Conversion (APC) PDU outlets via Telnet.

APC Network Management Card AOS and Rack PDU APP firmware versions supported:

v3.7.3
v3.7.4
"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )
str = None

__metaclass__ = type
__all__ = [
    'power_control_apc',
    'power_state_apc',
]

from telnetlib import Telnet
from time import sleep


USERNAME_PROMPT = 'User Name : '
PASSWORD_PROMPT = 'Password  : '
CMD_PROMPT = '\r\n> '
CONFIRM_PROMPT = 'cancel : '
CONFIRM_CHANGE = 'YES\r'


class APCState(object):
    OFF = "OFF"
    ON = "ON"


class APCException(Exception):
    """Failure communicating to the APC PDU. """


class APCTelnet:

    def __init__(self, ip, username, password):
        """
        Example of telnet connection displaying output
        and prompt with possible user choices:

        Trying 192.168.2.1...
        Connected to 192.168.2.1.
        Escape character is '^]'.

        User Name : apc
        Password  : ***

        ...

        ------- Control Console -------------------------------

        1- Device Manager
        2- Network
        3- System
        4- Logout

        <ESC>- Main Menu, <ENTER>- Refresh, <CTRL-L>- Event Log
        >
        """
        super(APCTelnet, self).__init__()
        self.ip = ip
        self.username = username
        self.password = password

    def _read(self, text):
        return self.telnet.read_until(text)

    def _write(self, text):
        self.telnet.write((text).encode('ascii'))

    def _write_read_transaction(self, wtext, rtext):
        self._write(wtext)
        return self._read(rtext)

    def _enter_username(self):
        self._read(USERNAME_PROMPT)
        self._write(self.username + '\r')

    def _enter_password(self):
        self._read(PASSWORD_PROMPT)
        self._write(self.password + '\r')
        self._read(CMD_PROMPT)

    def _select_option(self, option):
        return self._write_read_transaction(
            "%s\r" % option, CMD_PROMPT)

    def _select_outlet(self, outlet):
        self._select_option(outlet)

    def _drill_down_to_outlet_menu(self):
        self._select_option(1)
        self._select_option(2)
        return self._select_option(1)

    def _confirm_option(self, option):
        self._write_read_transaction(
            "%s\r" % option, CONFIRM_PROMPT)
        self._write_read_transaction(CONFIRM_CHANGE, '...')
        self._write_read_transaction('\r', CMD_PROMPT)

    def _power_on_outlet(self, outlet):
        self._drill_down_to_outlet_menu()
        self._select_outlet(outlet)
        self._select_option(1)
        # Confirm power on
        self._confirm_option(1)

    def _power_off_outlet(self, outlet):
        self._drill_down_to_outlet_menu()
        self._select_outlet(outlet)
        self._select_option(1)
        # Confirm power off
        self._confirm_option(2)

    def __enter__(self):
        self.telnet = Telnet(self.ip, timeout=30)
        self._enter_username()
        self._enter_password()

    def __exit__(self, *exc_info):
        telnet, self.telnet = self.telnet, None
        telnet.close()

    def power_off_outlet(self, outlet):
        """Power off outlet."""
        with self:
            self._power_off_outlet(outlet)

    def power_on_outlet(self, outlet):
        """Power on outlet.

        This forces the outlet off first, before turning it on.
        """
        with self:
            self._power_off_outlet(outlet)
            sleep(2)  # Without this it's too fast.
            self._power_on_outlet(outlet)

    def get_power_state_of_outlet(self, outlet):
        """Get power state of outlet (ON/OFF)."""
        with self:
            output = self._drill_down_to_outlet_menu()
            power_state = output.split(
                "Outlet %s" % outlet)[1].lstrip().split('\r')[0]
        return power_state


def power_control_apc(ip, username, password, outlet, power_change):
    """Handle calls from the power template for outlets with a power type
    of 'apc'.
    """
    apc = APCTelnet(ip, username, password)

    if power_change == 'off':
        apc.power_off_outlet(outlet)
    elif power_change == 'on':
        apc.power_on_outlet(outlet)
    else:
        raise AssertionError(
            "Unrecognised power change: %r" % (power_change,))


def power_state_apc(ip, username, password, outlet):
    """Return the power state for the APC PDU outlet."""
    apc = APCTelnet(ip, username, password)

    try:
        power_state = apc.get_power_state_of_outlet(outlet)
    except Exception as e:
        raise APCException(
            "Failed to retrieve power state: %s" % e)

    if power_state == APCState.OFF:
        return 'off'
    elif power_state == APCState.ON:
        return 'on'
    raise APCException('Unknown power state: %r' % power_state)
