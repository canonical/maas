# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for ``provisioningserver.drivers.hardware.apc``."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from random import randint

from maastesting.factory import factory
from maastesting.matchers import (
    MockCalledOnceWith,
    MockCallsMatch,
    )
from maastesting.testcase import MAASTestCase
from mock import call
from provisioningserver.drivers.hardware import apc as apc_module
from provisioningserver.drivers.hardware.apc import (
    APCException,
    APCState,
    APCTelnet,
    power_control_apc,
    power_state_apc,
    )
from testtools.matchers import Equals


POWER_STATE_OUTPUT = """
        ------- Outlet Control/Configuration -------

         1- Outlet 1                 ON
         2- Outlet 2                 ON
         3- Outlet 3                 ON
         4- Outlet 4                 ON
         5- Outlet 5                 ON
         6- Outlet 6                 ON
         7- Outlet 7                 ON
         8- Outlet 8                 ON
         9- Outlet 9                 ON
        10- Outlet 10                ON
        11- Outlet 11                ON
        12- Outlet 12                ON
        13- Outlet 13                OFF
        14- Outlet 14                ON
        15- Outlet 15                ON
        16- Outlet 16                ON
        17- Master Control/Configuration
"""


USERNAME_PROMPT = 'User Name : '
PASSWORD_PROMPT = 'Password  : '
CMD_PROMPT = '\r\n> '
CONFIRM_PROMPT = 'cancel : '
CONFIRM_CHANGE = 'YES\r'


def make_apc_telnet():
    """Return an APCTelnet object with randomized parameters."""
    ip = factory.make_ipv4_address()
    username = factory.make_name('username')
    password = factory.make_name('password')
    return APCTelnet(ip, username, password)


class TestAPCTelnet(MAASTestCase):
    """Tests for `APCTelnet`."""

    def test_read_reads(self):
        apc = make_apc_telnet()
        self.patch(apc, 'telnet')
        text = factory.make_name('text')
        apc._read(text)
        self.assertThat(apc.telnet.read_until, MockCalledOnceWith(text))

    def test_write_writes(self):
        apc = make_apc_telnet()
        text = factory.make_name('text')
        telnet = self.patch(apc_module, 'Telnet').return_value
        apc.telnet = telnet
        apc._write(text)
        self.assertThat(telnet.write, MockCalledOnceWith((text)))

    def test_write_read_transaction_writes_and_reads(self):
        apc = make_apc_telnet()
        wtext = factory.make_name('wtext')
        rtext = factory.make_name('rtext')
        telnet = self.patch(apc_module, 'Telnet').return_value
        apc.telnet = telnet
        apc._write_read_transaction(wtext, rtext)
        self.expectThat(telnet.write, MockCalledOnceWith((wtext)))
        self.expectThat(telnet.read_until, MockCalledOnceWith((rtext)))

    def test_enter_username_enters_username(self):
        apc = make_apc_telnet()
        _read = self.patch(apc, '_read')
        _write = self.patch(apc, '_write')
        apc._enter_username()
        self.expectThat(_read, MockCalledOnceWith(USERNAME_PROMPT))
        self.expectThat(_write, MockCalledOnceWith(apc.username + '\r'))

    def test_enter_password_enters_password(self):
        apc = make_apc_telnet()
        _read = self.patch(apc, '_read')
        _write = self.patch(apc, '_write')
        apc._enter_password()
        self.expectThat(
            _read, MockCallsMatch(
                call(PASSWORD_PROMPT),
                call(CMD_PROMPT)))
        self.expectThat(_write, MockCalledOnceWith(apc.password + '\r'))

    def test_select_option_selects_option(self):
        apc = make_apc_telnet()
        option = factory.make_name('option')
        _write_read_transaction = self.patch(
            apc, '_write_read_transaction')
        apc._select_option(option)
        self.assertThat(
            _write_read_transaction, MockCalledOnceWith(
                "%s\r" % option, CMD_PROMPT))

    def test_select_outlet_selects_outlet(self):
        apc = make_apc_telnet()
        outlet = randint(1, 16)
        _select_option = self.patch(
            apc, '_select_option')
        apc._select_outlet(outlet)
        self.assertThat(_select_option, MockCalledOnceWith(outlet))

    def test_drill_down_to_outlet_menu_drills_down(self):
        apc = make_apc_telnet()
        _select_option = self.patch(
            apc, '_select_option')
        apc._drill_down_to_outlet_menu()
        self.assertThat(
            _select_option, MockCallsMatch(
                call(1), call(2), call(1)))

    def test_confirm_option_confirms_option(self):
        apc = make_apc_telnet()
        option = factory.make_name('option')
        _write_read_transaction = self.patch(
            apc, '_write_read_transaction')
        apc._confirm_option(option)
        self.expectThat(
            _write_read_transaction, MockCallsMatch(
                call('%s\r' % option, CONFIRM_PROMPT),
                call(CONFIRM_CHANGE, '...'),
                call('\r', CMD_PROMPT)))

    def test_enter_opens_telnet_connection(self):
        apc = make_apc_telnet()
        telnet = self.patch(apc_module, 'Telnet')
        apc.__enter__()
        self.assertThat(telnet, MockCalledOnceWith(apc.ip, timeout=30))

    def test_exit_closes_telnet_connection(self):
        apc = make_apc_telnet()
        telnet = self.patch(apc_module, 'Telnet').return_value
        apc.telnet = telnet
        apc.__exit__()
        self.expectThat(telnet.close, MockCalledOnceWith())
        self.expectThat(apc.telnet, Equals(None))

    def test_power_off_outlet_powers_outlet_off(self):
        apc = make_apc_telnet()
        outlet = randint(1, 16)
        telnet = self.patch(apc_module, 'Telnet')
        _drill_down_to_outlet_menu = self.patch(
            apc, '_drill_down_to_outlet_menu')
        _select_outlet = self.patch(apc, '_select_outlet')
        _select_option = self.patch(apc, '_select_option')
        _confirm_option = self.patch(apc, '_confirm_option')
        apc.power_off_outlet(outlet)
        self.expectThat(telnet, MockCalledOnceWith(apc.ip, timeout=30))
        self.expectThat(
            _drill_down_to_outlet_menu, MockCalledOnceWith())
        self.expectThat(_select_outlet, MockCalledOnceWith(outlet))
        self.expectThat(_select_option, MockCalledOnceWith(1))
        self.expectThat(_confirm_option, MockCalledOnceWith(2))

    def test_power_on_outlet_powers_outlet_on(self):
        apc = make_apc_telnet()
        outlet = randint(1, 16)
        telnet = self.patch(apc_module, 'Telnet')
        _drill_down_to_outlet_menu = self.patch(
            apc, '_drill_down_to_outlet_menu')
        _select_outlet = self.patch(apc, '_select_outlet')
        _select_option = self.patch(apc, '_select_option')
        _confirm_option = self.patch(apc, '_confirm_option')
        apc.power_on_outlet(outlet)
        self.expectThat(telnet, MockCalledOnceWith(apc.ip, timeout=30))
        self.expectThat(
            _drill_down_to_outlet_menu, MockCalledOnceWith())
        self.expectThat(_select_outlet, MockCalledOnceWith(outlet))
        self.expectThat(_select_option, MockCalledOnceWith(1))
        self.expectThat(_confirm_option, MockCallsMatch(call(2), call(1)))

    def test_get_power_state_of_outlet_gets_power_state(self):
        apc = make_apc_telnet()
        outlet = randint(1, 16)
        telnet = self.patch(apc_module, 'Telnet')
        _drill_down_to_outlet_menu = self.patch(
            apc, '_drill_down_to_outlet_menu')
        _drill_down_to_outlet_menu.return_value = POWER_STATE_OUTPUT
        expected = POWER_STATE_OUTPUT.split(
            "Outlet %s" % outlet)[1].lstrip().split('\r')[0]
        power_state = apc.get_power_state_of_outlet(outlet)
        self.expectThat(telnet, MockCalledOnceWith(apc.ip, timeout=30))
        self.expectThat(
            _drill_down_to_outlet_menu, MockCalledOnceWith())
        self.expectThat(expected, Equals(power_state))


class TestAPCPowerControl(MAASTestCase):
    """Tests for `power_control_apc`."""

    def test__errors_on_unknown_power_change(self):
        ip = factory.make_ipv4_address()
        username = factory.make_name('username')
        password = factory.make_name('password')
        outlet = randint(1, 16)
        power_change = factory.make_name('error')
        self.assertRaises(
            AssertionError, power_control_apc, ip,
            username, password, outlet, power_change)

    def test__powers_on_outlet(self):
        ip = factory.make_ipv4_address()
        username = factory.make_name('username')
        password = factory.make_name('password')
        outlet = randint(1, 16)
        power_on_outlet = self.patch(APCTelnet, 'power_on_outlet')

        power_control_apc(
            ip, username, password, outlet, power_change='on')
        self.assertThat(power_on_outlet, MockCalledOnceWith(outlet))

    def test__powers_off_outlet(self):
        ip = factory.make_ipv4_address()
        username = factory.make_name('username')
        password = factory.make_name('password')
        outlet = randint(1, 16)
        power_off_outlet = self.patch(APCTelnet, 'power_off_outlet')

        power_control_apc(
            ip, username, password, outlet, power_change='off')
        self.assertThat(power_off_outlet, MockCalledOnceWith(outlet))


class TestAPCPowerState(MAASTestCase):
    """Tests for `power_state_apc`."""

    def test__fails_to_get_state(self):
        ip = factory.make_ipv4_address()
        username = factory.make_name('username')
        password = factory.make_name('password')
        outlet = randint(1, 16)
        power_state = self.patch(APCTelnet, 'get_power_state_of_outlet')
        power_state.side_effect = APCException('error')
        self.assertRaises(
            APCException, power_state_apc, ip, username, password, outlet)

    def test__gets_power_state_off(self):
        ip = factory.make_ipv4_address()
        username = factory.make_name('username')
        password = factory.make_name('password')
        outlet = randint(1, 16)
        power_state = self.patch(APCTelnet, 'get_power_state_of_outlet')
        power_state.return_value = APCState.OFF
        self.assertThat(
            power_state_apc(ip, username, password, outlet),
            Equals('off'))

    def test__gets_power_state_on(self):
        ip = factory.make_ipv4_address()
        username = factory.make_name('username')
        password = factory.make_name('password')
        outlet = randint(1, 16)
        power_state = self.patch(APCTelnet, 'get_power_state_of_outlet')
        power_state.return_value = APCState.ON
        self.assertThat(
            power_state_apc(ip, username, password, outlet),
            Equals('on'))

    def test__errors_on_unknown_state(self):
        ip = factory.make_ipv4_address()
        username = factory.make_name('username')
        password = factory.make_name('password')
        outlet = randint(1, 16)
        power_state = self.patch(APCTelnet, 'get_power_state_of_outlet')
        power_state.return_value = factory.make_name('error')
        self.assertRaises(
            APCException, power_state_apc, ip, username, password, outlet)
