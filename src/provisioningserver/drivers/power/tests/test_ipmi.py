# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.drivers.power.ipmi`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import random
from subprocess import PIPE

from maastesting.factory import factory
from maastesting.matchers import (
    MockCalledOnceWith,
    MockNotCalled,
)
from maastesting.testcase import MAASTestCase
from mock import (
    ANY,
    sentinel,
)
from provisioningserver.drivers.power import (
    get_c_environment,
    ipmi as ipmi_module,
    PowerAuthError,
    PowerFatalError,
)
from provisioningserver.drivers.power.ipmi import (
    IPMI_CONFIG,
    IPMIPowerDriver,
)
from provisioningserver.utils.shell import (
    ExternalProcessError,
    has_command_available,
)
from testtools.matchers import (
    Contains,
    Equals,
)


def make_parameters():
    power_address = factory.make_name('power_address')
    power_user = factory.make_name('power_user')
    power_pass = factory.make_name('power_pass')
    power_driver = factory.make_name('power_driver')
    power_off_mode = factory.make_name('power_off_mode')
    ipmipower = factory.make_name('ipmipower')
    ipmi_chassis_config = factory.make_name('ipmi_chassis_config')
    context = {
        'power_address': power_address,
        'power_user': power_user,
        'power_pass': power_pass,
        'power_driver': power_driver,
        'power_off_mode': power_off_mode,
        'ipmipower': ipmipower,
        'ipmi_chassis_config': ipmi_chassis_config,
    }

    return (
        power_address, power_user, power_pass, power_driver,
        power_off_mode, ipmipower, ipmi_chassis_config, context
    )


def make_ipmi_chassis_config_command(
        ipmi_chassis_config, power_address, power_pass,
        power_driver, power_user, tmp_config_name):
    print(tmp_config_name)
    return (
        ipmi_chassis_config, '-W', 'opensesspriv', "--driver-type",
        power_driver, '-h', power_address, '-u', power_user, '-p', power_pass,
        '--commit', '--filename', tmp_config_name
    )


def make_ipmipower_command(
        ipmipower, power_address, power_pass,
        power_driver, power_user):
    return (
        ipmipower, '-W', 'opensesspriv', "--driver-type", power_driver, '-h',
        power_address, '-u', power_user, '-p', power_pass
    )


class TestIPMIPowerDriver(MAASTestCase):

    def test_missing_packages(self):
        mock = self.patch(has_command_available)
        mock.return_value = False
        driver = ipmi_module.IPMIPowerDriver()
        missing = driver.detect_missing_packages()
        self.assertItemsEqual(['freeipmi-tools'], missing)

    def test_no_missing_packages(self):
        mock = self.patch(has_command_available)
        mock.return_value = True
        driver = ipmi_module.IPMIPowerDriver()
        missing = driver.detect_missing_packages()
        self.assertItemsEqual([], missing)

    def test__finds_power_address_from_mac_address(self):
        (power_address, power_user, power_pass, power_driver, power_off_mode,
         ipmipower, ipmi_chassis_config, context) = make_parameters()
        driver = IPMIPowerDriver()
        ip_address = factory.make_ipv4_address()
        find_ip_via_arp = self.patch(ipmi_module, 'find_ip_via_arp')
        find_ip_via_arp.return_value = ip_address
        power_change = random.choice(("on", "off"))
        env = get_c_environment()

        context['mac_address'] = factory.make_mac_address()
        context['power_address'] = random.choice((None, "", "   "))

        self.patch_autospec(driver, "_issue_ipmi_chassis_config_command")
        self.patch_autospec(driver, "_issue_ipmi_power_command")
        driver._issue_ipmi_command(power_change, **context)

        # The IP address is passed to _issue_ipmi_chassis_config_command.
        self.assertThat(
            driver._issue_ipmi_chassis_config_command,
            MockCalledOnceWith(ANY, power_change, ip_address, env))
        # The IP address is also within the command passed to
        # _issue_ipmi_chassis_config_command.
        self.assertThat(
            driver._issue_ipmi_chassis_config_command.call_args[0],
            Contains(ip_address))
        # The IP address is passed to _issue_ipmi_power_command.
        self.assertThat(
            driver._issue_ipmi_power_command,
            MockCalledOnceWith(ANY, power_change, ip_address, env))
        # The IP address is also within the command passed to
        # _issue_ipmi_power_command.
        self.assertThat(
            driver._issue_ipmi_power_command.call_args[0],
            Contains(ip_address))

    def test__chassis_config_written_to_temporary_file(self):
        NamedTemporaryFile = self.patch(ipmi_module, "NamedTemporaryFile")
        tmpfile = NamedTemporaryFile.return_value
        tmpfile.__enter__.return_value = tmpfile
        tmpfile.name = factory.make_name("filename")

        IPMIPowerDriver._issue_ipmi_chassis_config_command(
            ["true"], sentinel.change, sentinel.addr, None)

        self.assertThat(NamedTemporaryFile, MockCalledOnceWith())
        self.assertThat(tmpfile.__enter__, MockCalledOnceWith())
        self.assertThat(tmpfile.write, MockCalledOnceWith(IPMI_CONFIG))
        self.assertThat(tmpfile.flush, MockCalledOnceWith())
        self.assertThat(tmpfile.__exit__, MockCalledOnceWith(None, None, None))

    def test__issue_ipmi_command_issues_power_on(self):
        (power_address, power_user, power_pass, power_driver, power_off_mode,
         ipmipower, ipmi_chassis_config, context) = make_parameters()
        ipmi_chassis_config_command = make_ipmi_chassis_config_command(
            ipmi_chassis_config, power_address, power_pass, power_driver,
            power_user, ANY)
        ipmipower_command = make_ipmipower_command(
            ipmipower, power_address, power_pass, power_driver, power_user)
        ipmipower_command += ('--cycle', '--on-if-off')
        ipmi_power_driver = IPMIPowerDriver()
        env = get_c_environment()
        popen_mock = self.patch(ipmi_module, 'Popen')
        process = popen_mock.return_value
        process.communicate.return_value = (None, '')
        process.returncode = 0
        call_and_check_mock = self.patch(ipmi_module, 'call_and_check')
        call_and_check_mock.return_value = 'on'

        result = ipmi_power_driver._issue_ipmi_command('on', **context)

        self.expectThat(
            popen_mock, MockCalledOnceWith(
                ipmi_chassis_config_command, stdout=PIPE,
                stderr=PIPE, env=env))
        self.expectThat(
            call_and_check_mock, MockCalledOnceWith(
                ipmipower_command, env=env))
        self.expectThat(result, Equals('on'))

    def test__issue_ipmi_command_issues_power_off(self):
        (power_address, power_user, power_pass, power_driver, power_off_mode,
         ipmipower, ipmi_chassis_config, context) = make_parameters()
        ipmi_chassis_config_command = make_ipmi_chassis_config_command(
            ipmi_chassis_config, power_address, power_pass, power_driver,
            power_user, ANY)
        ipmipower_command = make_ipmipower_command(
            ipmipower, power_address, power_pass, power_driver, power_user)
        ipmipower_command += ('--off', )
        ipmi_power_driver = IPMIPowerDriver()
        env = get_c_environment()
        popen_mock = self.patch(ipmi_module, 'Popen')
        process = popen_mock.return_value
        process.communicate.return_value = (None, '')
        process.returncode = 0
        call_and_check_mock = self.patch(ipmi_module, 'call_and_check')
        call_and_check_mock.return_value = 'off'

        result = ipmi_power_driver._issue_ipmi_command('off', **context)

        self.expectThat(
            popen_mock, MockCalledOnceWith(
                ipmi_chassis_config_command, stdout=PIPE,
                stderr=PIPE, env=env))
        self.expectThat(
            call_and_check_mock, MockCalledOnceWith(
                ipmipower_command, env=env))
        self.expectThat(result, Equals('off'))

    def test__issue_ipmi_command_issues_power_off_soft_mode(self):
        (power_address, power_user, power_pass, power_driver, power_off_mode,
         ipmipower, ipmi_chassis_config, context) = make_parameters()
        context['power_off_mode'] = 'soft'
        ipmi_chassis_config_command = make_ipmi_chassis_config_command(
            ipmi_chassis_config, power_address, power_pass, power_driver,
            power_user, ANY)
        ipmipower_command = make_ipmipower_command(
            ipmipower, power_address, power_pass, power_driver, power_user)
        ipmipower_command += ('--soft', )
        ipmi_power_driver = IPMIPowerDriver()
        env = get_c_environment()
        popen_mock = self.patch(ipmi_module, 'Popen')
        process = popen_mock.return_value
        process.communicate.return_value = (None, '')
        process.returncode = 0
        call_and_check_mock = self.patch(ipmi_module, 'call_and_check')
        call_and_check_mock.return_value = 'off'

        result = ipmi_power_driver._issue_ipmi_command('off', **context)

        self.expectThat(
            popen_mock, MockCalledOnceWith(
                ipmi_chassis_config_command, stdout=PIPE,
                stderr=PIPE, env=env))
        self.expectThat(
            call_and_check_mock, MockCalledOnceWith(
                ipmipower_command, env=env))
        self.expectThat(result, Equals('off'))

    def test__issue_ipmi_command_issues_power_query(self):
        (power_address, power_user, power_pass, power_driver, power_off_mode,
         ipmipower, ipmi_chassis_config, context) = make_parameters()
        ipmipower_command = make_ipmipower_command(
            ipmipower, power_address, power_pass, power_driver, power_user)
        ipmipower_command += ('--stat', )
        ipmi_power_driver = IPMIPowerDriver()
        env = get_c_environment()
        popen_mock = self.patch(ipmi_module, 'Popen')
        process = popen_mock.return_value
        process.communicate.return_value = (None, '')
        process.returncode = 0
        call_and_check_mock = self.patch(ipmi_module, 'call_and_check')
        call_and_check_mock.return_value = 'other'

        result = ipmi_power_driver._issue_ipmi_command('query', **context)

        self.expectThat(popen_mock, MockNotCalled())
        self.expectThat(
            call_and_check_mock, MockCalledOnceWith(
                ipmipower_command, env=env))
        self.expectThat(result, Equals('other'))

    def test__issue_ipmi_command_issues_raises_power_auth_error(self):
        _, _, _, _, _, _, _, context = make_parameters()
        ipmi_power_driver = IPMIPowerDriver()
        popen_mock = self.patch(ipmi_module, 'Popen')
        process = popen_mock.return_value
        process.communicate.return_value = (None, 'password invalid')
        process.returncode = 0

        self.assertRaises(
            PowerAuthError, ipmi_power_driver._issue_ipmi_command,
            'on', **context)

    def test__issue_ipmi_command_logs_maaslog_warning(self):
        _, _, _, _, _, _, _, context = make_parameters()
        ipmi_power_driver = IPMIPowerDriver()
        popen_mock = self.patch(ipmi_module, 'Popen')
        process = popen_mock.return_value
        process.communicate.return_value = (None, 'maaslog error')
        process.returncode = -1
        maaslog = self.patch(ipmi_module, 'maaslog')
        self.patch(ipmi_power_driver, '_issue_ipmi_power_command')

        ipmi_power_driver._issue_ipmi_command('on', **context)

        self.assertThat(
            maaslog.warning, MockCalledOnceWith(
                'Failed to change the boot order to PXE %s: %s' % (
                    context['power_address'], 'maaslog error')))

    def test__issue_ipmi_command_issues_catches_external_process_error(self):
        _, _, _, _, _, _, _, context = make_parameters()
        ipmi_power_driver = IPMIPowerDriver()
        popen_mock = self.patch(ipmi_module, 'Popen')
        process = popen_mock.return_value
        process.communicate.return_value = (None, '')
        process.returncode = 0
        call_and_check_mock = self.patch(ipmi_module, 'call_and_check')
        call_and_check_mock.side_effect = (
            ExternalProcessError(1, "ipmipower something"))

        self.assertRaises(
            PowerFatalError, ipmi_power_driver._issue_ipmi_command,
            'on', **context)

    def test_power_on_calls__issue_ipmi_command(self):
        _, _, _, _, _, _, _, context = make_parameters()
        ipmi_power_driver = IPMIPowerDriver()
        _issue_ipmi_command_mock = self.patch(
            ipmi_power_driver, '_issue_ipmi_command')
        system_id = factory.make_name('system_id')
        ipmi_power_driver.power_on(system_id, context)

        self.assertThat(
            _issue_ipmi_command_mock, MockCalledOnceWith('on', **context))

    def test_power_off_calls__issue_ipmi_command(self):
        _, _, _, _, _, _, _, context = make_parameters()
        ipmi_power_driver = IPMIPowerDriver()
        _issue_ipmi_command_mock = self.patch(
            ipmi_power_driver, '_issue_ipmi_command')
        system_id = factory.make_name('system_id')
        ipmi_power_driver.power_off(system_id, context)

        self.assertThat(
            _issue_ipmi_command_mock, MockCalledOnceWith('off', **context))

    def test_power_query_calls__issue_ipmi_command(self):
        _, _, _, _, _, _, _, context = make_parameters()
        ipmi_power_driver = IPMIPowerDriver()
        _issue_ipmi_command_mock = self.patch(
            ipmi_power_driver, '_issue_ipmi_command')
        system_id = factory.make_name('system_id')
        ipmi_power_driver.power_query(system_id, context)

        self.assertThat(
            _issue_ipmi_command_mock, MockCalledOnceWith('query', **context))
