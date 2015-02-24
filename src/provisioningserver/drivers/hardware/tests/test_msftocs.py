# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for ``provisioningserver.drivers.hardware.msftocs``."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from random import randint
from textwrap import dedent
import urlparse

from maastesting.factory import factory
from maastesting.matchers import MockCalledOnceWith
from maastesting.testcase import MAASTestCase
from mock import Mock
from provisioningserver.drivers.hardware.msftocs import (
    MsftocsAPI,
    MsftocsException,
    MsftocsState,
    power_control_msftocs,
    power_state_msftocs,
    )
from testtools.matchers import Equals


XMLNS = "http://schemas.datacontract.org/2004/07/Microsoft.GFS.WCS.Contracts"
XMLNS_I = "http://www.w3.org/2001/XMLSchema-instance"


def make_msftocs_api():
    """Make a MsftocsAPI object with randomized parameters."""
    ip = factory.make_ipv4_address()
    port = randint(2000, 4000)
    username = factory.make_name('user')
    password = factory.make_name('password')
    return MsftocsAPI(ip, port, username, password)


def make_msftocs_params():
    """Make and return the parameters used for power control/state."""
    ip = factory.make_ipv4_address()
    port = randint(2000, 4000)
    username = factory.make_name('username')
    password = factory.make_name('password')
    bladeid = randint(1, 24)
    return ip, port, username, password, bladeid


class Test_MsftocsAPI(MAASTestCase):
    """Tests for `MsftocsAPI`."""

    def test_build_url_builds_url(self):
        api = make_msftocs_api()
        params = [factory.make_string() for _ in range(3)]
        command = factory.make_string()
        output = api.build_url(command, params)
        parsed = urlparse.urlparse(output)
        url = '%s:%d' % (api.ip, api.port)
        self.expectThat(url, Equals(parsed.netloc))
        self.expectThat(command, Equals(parsed.path.split('/')[1]))
        self.expectThat(params, Equals(parsed.query.split('&')))

    def test_extract_from_response_finds_element_content(self):
        api = make_msftocs_api()
        response = dedent("""
            <a xmlns='%s' xmlns:i='%s'>
                <b/>
                <c/>
                <d>Test</d>
            </a>
        """ % (XMLNS, XMLNS_I))
        element_tag = 'd'
        expected = 'Test'
        output = api.extract_from_response(response, element_tag)
        self.assertThat(output, Equals(expected))

    def test_get_blade_power_state_gets_power_state(self):
        api = make_msftocs_api()
        bladeid = randint(1, 24)
        params = ["bladeid=%s" % bladeid]
        response = dedent("""
            <BladeStateResponse xmlns='%s' xmlns:i='%s'>
                <completionCode>Success</completionCode>
                <apiVersion>1</apiVersion>
                <statusDescription/>
                <bladeNumber>%s</bladeNumber>
                <bladeState>ON</bladeState>
            </BladeStateResponse>
        """ % (XMLNS, XMLNS_I, bladeid))
        mock_response = self.patch(
            MsftocsAPI, 'get', Mock(return_value=response))
        expected = 'ON'
        output = api.get_blade_power_state(bladeid)

        self.expectThat(output, Equals(expected))
        self.expectThat(
            mock_response, MockCalledOnceWith('GetBladeState', params))

    def test_set_power_off_blade_powers_off_blade(self):
        api = make_msftocs_api()
        bladeid = randint(1, 24)
        params = ["bladeid=%s" % bladeid]
        response = dedent("""
            <BladeResponse xmlns='%s' xmlns:i='%s'>
                <completionCode>Success</completionCode>
                <apiVersion>1</apiVersion>
                <statusDescription/>
                <bladeNumber>%s</bladeNumber>
            </BladeResponse>
        """ % (XMLNS, XMLNS_I, bladeid))
        mock_response = self.patch(
            MsftocsAPI, 'get', Mock(return_value=response))
        expected = 'Success'
        output = api.set_power_off_blade(bladeid)

        self.expectThat(output, Equals(expected))
        self.expectThat(
            mock_response, MockCalledOnceWith('SetBladeOff', params))

    def test_set_power_on_blade_powers_on_blade(self):
        api = make_msftocs_api()
        bladeid = randint(1, 24)
        params = ["bladeid=%s" % bladeid]
        response = dedent("""
            <BladeResponse xmlns='%s' xmlns:i='%s'>
                <completionCode>Success</completionCode>
                <apiVersion>1</apiVersion>
                <statusDescription/>
                <bladeNumber>%s</bladeNumber>
            </BladeResponse>
        """ % (XMLNS, XMLNS_I, bladeid))
        mock_response = self.patch(
            MsftocsAPI, 'get', Mock(return_value=response))
        expected = 'Success'
        output = api.set_power_on_blade(bladeid)

        self.expectThat(output, Equals(expected))
        self.expectThat(
            mock_response, MockCalledOnceWith('SetBladeOn', params))

    def test_set_next_boot_device_sets_device(self):
        api = make_msftocs_api()
        bladeid = randint(1, 24)
        bootType = '2'
        boot_uefi = 'false'
        boot_persistent = 'false'
        params = [
            "bladeid=%s" % bladeid, "bootType=%s" % bootType,
            "uefi=%s" % boot_uefi, "persistent=%s" % boot_persistent,
        ]
        response = dedent("""
            <BootResponse xmlns='%s' xmlns:i='%s'>
                <completionCode>Success</completionCode>
                <apiVersion>1</apiVersion>
                <statusDescription>Success</statusDescription>
                <bladeNumber>%s</bladeNumber>
                <nextBoot>ForcePxe</nextBoot>
            </BootResponse>
        """ % (XMLNS, XMLNS_I, bladeid))
        mock_response = self.patch(
            MsftocsAPI, 'get', Mock(return_value=response))
        expected = 'ForcePxe'
        output = api.set_next_boot_device(bladeid, pxe=True)

        self.expectThat(output, Equals(expected))
        self.expectThat(
            mock_response, MockCalledOnceWith('SetNextBoot', params))


class Test_MsftocsPowerState(MAASTestCase):
    """Tests for `power_state_msftocs`."""

    def test_power_state_msftocs_failed_to_get_state(self):
        ip, port, username, password, bladeid = make_msftocs_params()
        power_state_mock = self.patch(MsftocsAPI, 'get_blade_power_state')
        power_state_mock.side_effect = MsftocsException('error')
        self.assertRaises(
            MsftocsException, power_state_msftocs, ip, port,
            username, password, bladeid)

    def test_power_state_msftocs_gets_off_state(self):
        ip, port, username, password, bladeid = make_msftocs_params()
        power_state_mock = self.patch(MsftocsAPI, 'get_blade_power_state')
        power_state_mock.return_value = MsftocsState.OFF
        self.assertThat(
            power_state_msftocs(ip, port, username, password, bladeid),
            Equals('off'))

    def test_power_state_msftocs_gets_on_state(self):
        ip, port, username, password, bladeid = make_msftocs_params()
        power_state_mock = self.patch(MsftocsAPI, 'get_blade_power_state')
        power_state_mock.return_value = MsftocsState.ON
        self.assertThat(
            power_state_msftocs(ip, port, username, password, bladeid),
            Equals('on'))

    def test_power_state_msftocs_errors_on_unknown_state(self):
        ip, port, username, password, bladeid = make_msftocs_params()
        power_state_mock = self.patch(MsftocsAPI, 'get_blade_power_state')
        power_state_mock.return_value = factory.make_name('error')
        self.assertRaises(
            MsftocsException, power_state_msftocs, ip, port,
            username, password, bladeid)


class Test_MsftocsPowerControl(MAASTestCase):
    """Tests for `power_control_msftocs`."""

    def test_power_control_msftocs_errors_on_unknown_power_change(self):
        ip, port, username, password, bladeid = make_msftocs_params()
        power_change = factory.make_name('error')
        self.assertRaises(
            MsftocsException, power_control_msftocs, ip,
            port, username, password, bladeid, power_change)

    def test_power_control_msftocs_power_change_on_power_state_on(self):
        # power_change and current power_state are both 'on'
        ip, port, username, password, bladeid = make_msftocs_params()
        power_state_mock = self.patch(MsftocsAPI, 'get_blade_power_state')
        power_state_mock.return_value = MsftocsState.ON

        power_node_off_mock = self.patch(MsftocsAPI, 'set_power_off_blade')
        next_boot_mock = self.patch(MsftocsAPI, 'set_next_boot_device')
        power_node_on_mock = self.patch(MsftocsAPI, 'set_power_on_blade')

        power_control_msftocs(
            ip, port, username, password, bladeid, power_change='on')
        self.expectThat(power_state_mock, MockCalledOnceWith(bladeid))
        self.expectThat(power_node_off_mock, MockCalledOnceWith(bladeid))
        self.expectThat(next_boot_mock.call_count, Equals(2))
        self.expectThat(power_node_on_mock, MockCalledOnceWith(bladeid))

    def test_power_control_msftocs_power_change_on_power_state_off(self):
        # power_change is 'on' and current power_state is 'off'
        ip, port, username, password, bladeid = make_msftocs_params()
        power_state_mock = self.patch(MsftocsAPI, 'get_blade_power_state')
        power_state_mock.return_value = MsftocsState.OFF
        next_boot_mock = self.patch(MsftocsAPI, 'set_next_boot_device')
        power_node_on_mock = self.patch(MsftocsAPI, 'set_power_on_blade')

        power_control_msftocs(
            ip, port, username, password, bladeid, power_change='on')
        self.expectThat(power_state_mock, MockCalledOnceWith(bladeid))
        self.expectThat(next_boot_mock.call_count, Equals(2))
        self.expectThat(power_node_on_mock, MockCalledOnceWith(bladeid))

    def test_power_control_msftocs_power_change_off_power_state_on(self):
        # power_change is 'off' and current power_state is 'on'
        ip, port, username, password, bladeid = make_msftocs_params()
        power_node_off_mock = self.patch(MsftocsAPI, 'set_power_off_blade')

        power_control_msftocs(
            ip, port, username, password, bladeid, power_change='off')
        self.expectThat(power_node_off_mock, MockCalledOnceWith(bladeid))
