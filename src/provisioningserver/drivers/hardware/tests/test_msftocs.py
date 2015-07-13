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
from StringIO import StringIO
from textwrap import dedent
import urllib2 as urllib2
import urlparse

from maastesting.factory import factory
from maastesting.matchers import (
    MockAnyCall,
    MockCalledOnceWith,
)
from maastesting.testcase import (
    MAASTestCase,
    MAASTwistedRunTest,
)
from mock import Mock
from provisioningserver.drivers.hardware import msftocs
from provisioningserver.drivers.hardware.msftocs import (
    MicrosoftOCSAPI,
    MicrosoftOCSError,
    MicrosoftOCSState,
    power_control_msftocs,
    power_state_msftocs,
    probe_and_enlist_msftocs,
)
from provisioningserver.utils.twisted import asynchronous
from testtools.matchers import Equals
from testtools.testcase import ExpectedException
from twisted.internet.defer import inlineCallbacks
from twisted.internet.threads import deferToThread


XMLNS = "http://schemas.datacontract.org/2004/07/Microsoft.GFS.WCS.Contracts"
XMLNS_I = "http://www.w3.org/2001/XMLSchema-instance"


def make_msftocs_api():
    """Make a MicrosoftOCSAPI object with randomized parameters."""
    ip = factory.make_ipv4_address()
    port = randint(2000, 4000)
    username = factory.make_name('user')
    password = factory.make_name('password')
    return MicrosoftOCSAPI(ip, port, username, password)


def make_msftocs_params():
    """Make and return the parameters used for power control/state."""
    ip = factory.make_ipv4_address()
    port = randint(2000, 4000)
    username = factory.make_name('username')
    password = factory.make_name('password')
    bladeid = randint(1, 24)
    return ip, port, username, password, bladeid


class Test_MicrosoftOCSAPI(MAASTestCase):
    """Tests for `MicrosoftOCSAPI`."""

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

    def test_get_gets_response(self):
        api = make_msftocs_api()
        params = [factory.make_string() for _ in range(3)]
        command = factory.make_string()
        expected = dedent("""
            <ChassisInfoResponse xmlns='%s' xmlns:i='%s'>
                <bladeCollections>
                    <BladeInfo>
                    </BladeInfo>
                </bladeCollections>
            </ChassisInfoResponse>
        """ % (XMLNS, XMLNS_I))
        response = StringIO(expected)
        mock_urlopen = self.patch(
            urllib2, 'urlopen', Mock(return_value=response))
        url = api.build_url(command, params)
        output = api.get(command, params)

        self.expectThat(output, Equals(expected))
        self.expectThat(
            mock_urlopen, MockCalledOnceWith(url))

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
            MicrosoftOCSAPI, 'get', Mock(return_value=response))
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
            MicrosoftOCSAPI, 'get', Mock(return_value=response))
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
            MicrosoftOCSAPI, 'get', Mock(return_value=response))
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
            "uefi=%s" % boot_uefi, "persistent=%s" % boot_persistent
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
            MicrosoftOCSAPI, 'get', Mock(return_value=response))
        expected = 'ForcePxe'
        output = api.set_next_boot_device(bladeid, pxe=True)

        self.expectThat(output, Equals(expected))
        self.expectThat(
            mock_response, MockCalledOnceWith('SetNextBoot', params))

    def test_get_blades_gets_blades(self):
        api = make_msftocs_api()
        response = dedent("""
            <ChassisInfoResponse xmlns='%s' xmlns:i='%s'>
                <bladeCollections>
                    <BladeInfo>
                        <completionCode>Success</completionCode>
                        <apiVersion>1</apiVersion>
                        <statusDescription/>
                        <bladeNumber>11</bladeNumber>
                        <bladeGuid></bladeGuid>
                        <bladeName>BLADE11</bladeName>
                        <powerState>ON</powerState>
                        <bladeMacAddress>
                            <NicInfo>
                                <completionCode>Success</completionCode>
                                <apiVersion>1</apiVersion>
                                <statusDescription/>
                                <deviceId>1</deviceId>
                                <macAddress>F4:52:14:D6:70:98</macAddress>
                            </NicInfo>
                            <NicInfo>
                                <completionCode>Success</completionCode>
                                <apiVersion>1</apiVersion>
                                <statusDescription></statusDescription>
                                <deviceId>2</deviceId>
                                <macAddress/>
                            </NicInfo>
                        </bladeMacAddress>
                    </BladeInfo>
                </bladeCollections>
            </ChassisInfoResponse>
        """ % (XMLNS, XMLNS_I))
        mock_response = self.patch(
            MicrosoftOCSAPI, 'get', Mock(return_value=response))
        expected = {'11': [u'F4:52:14:D6:70:98']}
        output = api.get_blades()

        self.expectThat(output, Equals(expected))
        self.expectThat(
            mock_response, MockCalledOnceWith('GetChassisInfo'))


class Test_MicrosoftOCSPowerState(MAASTestCase):
    """Tests for `power_state_msftocs`."""

    def test_power_state_msftocs_failed_to_get_state_server_error(self):
        ip, port, username, password, bladeid = make_msftocs_params()
        power_state_mock = self.patch(MicrosoftOCSAPI, 'get_blade_power_state')
        power_state_mock.side_effect = urllib2.URLError('error')

        self.assertRaises(
            MicrosoftOCSError, power_state_msftocs, ip, port,
            username, password, bladeid)
        self.expectThat(power_state_mock, MockCalledOnceWith(bladeid))

    def test_power_state_msftocs_failed_to_get_state_http_error(self):
        ip, port, username, password, bladeid = make_msftocs_params()
        power_state_mock = self.patch(MicrosoftOCSAPI, 'get_blade_power_state')
        power_state_mock.side_effect = urllib2.HTTPError(
            None, None, None, None, None)

        self.assertRaises(
            MicrosoftOCSError, power_state_msftocs, ip, port,
            username, password, bladeid)
        self.expectThat(power_state_mock, MockCalledOnceWith(bladeid))

    def test_power_state_msftocs_gets_off_state(self):
        ip, port, username, password, bladeid = make_msftocs_params()
        power_state_mock = self.patch(MicrosoftOCSAPI, 'get_blade_power_state')
        power_state_mock.return_value = MicrosoftOCSState.OFF

        self.expectThat(
            power_state_msftocs(ip, port, username, password, bladeid),
            Equals('off'))
        self.expectThat(power_state_mock, MockCalledOnceWith(bladeid))

    def test_power_state_msftocs_gets_on_state(self):
        ip, port, username, password, bladeid = make_msftocs_params()
        power_state_mock = self.patch(MicrosoftOCSAPI, 'get_blade_power_state')
        power_state_mock.return_value = MicrosoftOCSState.ON

        self.expectThat(
            power_state_msftocs(ip, port, username, password, bladeid),
            Equals('on'))
        self.expectThat(power_state_mock, MockCalledOnceWith(bladeid))

    def test_power_state_msftocs_errors_on_unknown_state(self):
        ip, port, username, password, bladeid = make_msftocs_params()
        power_state_mock = self.patch(MicrosoftOCSAPI, 'get_blade_power_state')
        power_state_mock.return_value = factory.make_name('error')

        self.assertRaises(
            MicrosoftOCSError, power_state_msftocs, ip, port,
            username, password, bladeid)
        self.expectThat(power_state_mock, MockCalledOnceWith(bladeid))


class Test_MicrosoftOCSPowerControl(MAASTestCase):
    """Tests for `power_control_msftocs`."""

    def test_power_control_msftocs_errors_on_unknown_power_change(self):
        ip, port, username, password, bladeid = make_msftocs_params()
        power_change = factory.make_name('error')

        self.assertRaises(
            MicrosoftOCSError, power_control_msftocs, ip,
            port, username, password, bladeid, power_change)

    def test_power_control_msftocs_power_change_on_power_state_on(self):
        # power_change and current power_state are both 'on'
        ip, port, username, password, bladeid = make_msftocs_params()
        power_state_mock = self.patch(MicrosoftOCSAPI, 'get_blade_power_state')
        power_state_mock.return_value = MicrosoftOCSState.ON
        power_node_off_mock = self.patch(
            MicrosoftOCSAPI, 'set_power_off_blade')
        next_boot_mock = self.patch(MicrosoftOCSAPI, 'set_next_boot_device')
        power_node_on_mock = self.patch(MicrosoftOCSAPI, 'set_power_on_blade')
        power_control_msftocs(
            ip, port, username, password, bladeid, power_change='on')

        self.expectThat(power_state_mock, MockCalledOnceWith(bladeid))
        self.expectThat(power_node_off_mock, MockCalledOnceWith(bladeid))
        self.expectThat(next_boot_mock.call_count, Equals(2))
        self.expectThat(power_node_on_mock, MockCalledOnceWith(bladeid))

    def test_power_control_msftocs_power_change_on_power_state_off(self):
        # power_change is 'on' and current power_state is 'off'
        ip, port, username, password, bladeid = make_msftocs_params()
        power_state_mock = self.patch(MicrosoftOCSAPI, 'get_blade_power_state')
        power_state_mock.return_value = MicrosoftOCSState.OFF
        next_boot_mock = self.patch(MicrosoftOCSAPI, 'set_next_boot_device')
        power_node_on_mock = self.patch(MicrosoftOCSAPI, 'set_power_on_blade')
        power_control_msftocs(
            ip, port, username, password, bladeid, power_change='on')

        self.expectThat(power_state_mock, MockCalledOnceWith(bladeid))
        self.expectThat(next_boot_mock.call_count, Equals(2))
        self.expectThat(power_node_on_mock, MockCalledOnceWith(bladeid))

    def test_power_control_msftocs_power_change_off_power_state_on(self):
        # power_change is 'off' and current power_state is 'on'
        ip, port, username, password, bladeid = make_msftocs_params()
        power_node_off_mock = self.patch(
            MicrosoftOCSAPI, 'set_power_off_blade')
        power_control_msftocs(
            ip, port, username, password, bladeid, power_change='off')

        self.assertThat(power_node_off_mock, MockCalledOnceWith(bladeid))


class TestMicrosoftOCSProbeAndEnlist(MAASTestCase):
    """Tests for `probe_and_enlist_msftocs`."""

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

    @inlineCallbacks
    def test_probe_and_enlist_msftocs_probes_and_enlists(self):
        user = factory.make_name('user')
        ip = factory.make_ipv4_address()
        port = randint(2000, 4000)
        username = factory.make_name('username')
        password = factory.make_name('password')
        system_id = factory.make_name('system_id')
        blade_id = randint(1, 24)
        macs = [u'F4:52:14:D6:70:98', u'F4:52:14:D6:70:99']
        blades_mock = self.patch(MicrosoftOCSAPI, 'get_blades')
        blades_mock.return_value = {'%s' % blade_id: macs}
        next_boot_device_mock = self.patch(
            MicrosoftOCSAPI, 'set_next_boot_device')
        create_node_mock = self.patch(msftocs, 'create_node')
        create_node_mock.side_effect = asynchronous(lambda *args: system_id)
        commission_node_mock = self.patch(msftocs, 'commission_node')
        params = {
            'power_address': ip,
            'power_port': port,
            'power_user': username,
            'power_pass': password,
            'blade_id': blade_id,
        }
        yield deferToThread(
            probe_and_enlist_msftocs, user, ip, port, username,
            password, accept_all=True)

        self.expectThat(blades_mock, MockAnyCall())
        self.expectThat(next_boot_device_mock.call_count, Equals(2))
        self.expectThat(
            create_node_mock,
            MockCalledOnceWith(macs, 'amd64', 'msftocs', params))
        self.expectThat(
            commission_node_mock,
            MockCalledOnceWith(system_id, user))

    @inlineCallbacks
    def test_probe_and_enlist_msftocs_get_blades_failure_server_error(self):
        user = factory.make_name('user')
        ip = factory.make_ipv4_address()
        port = randint(2000, 4000)
        username = factory.make_name('username')
        password = factory.make_name('password')
        blades_mock = self.patch(MicrosoftOCSAPI, 'get_blades')
        blades_mock.side_effect = urllib2.URLError('error')

        with ExpectedException(MicrosoftOCSError):
            yield deferToThread(
                probe_and_enlist_msftocs, user, ip, port, username, password)
        self.expectThat(blades_mock, MockCalledOnceWith())

    @inlineCallbacks
    def test_probe_and_enlist_msftocs_get_blades_failure_http_error(self):
        user = factory.make_name('user')
        ip = factory.make_ipv4_address()
        port = randint(2000, 4000)
        username = factory.make_name('username')
        password = factory.make_name('password')
        blades_mock = self.patch(MicrosoftOCSAPI, 'get_blades')
        blades_mock.side_effect = urllib2.HTTPError(
            None, None, None, None, None)

        with ExpectedException(MicrosoftOCSError):
            yield deferToThread(
                probe_and_enlist_msftocs, user, ip, port, username, password)
        self.expectThat(blades_mock, MockCalledOnceWith())
