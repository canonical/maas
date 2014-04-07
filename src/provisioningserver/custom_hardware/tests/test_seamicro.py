# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.custom_hardware.seamicro`.
"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import json
import urlparse

from maastesting.factory import factory
from maastesting.matchers import (
    MockCalledOnceWith,
    MockCalledWith,
    MockCallsMatch,
    )
from maastesting.testcase import MAASTestCase
from mock import (
    call,
    Mock,
    )
from provisioningserver.custom_hardware.seamicro import (
    find_seamicro15k_servers,
    power_control_seamicro15k_v09,
    power_control_seamicro15k_v2,
    POWER_STATUS,
    probe_seamicro15k_and_enlist,
    SeaMicroAPIV09,
    SeaMicroAPIV09Error,
    SeaMicroError,
    select_seamicro15k_api_version,
    )
import provisioningserver.custom_hardware.utils


class FakeResponse(object):

    def __init__(self, response_code, response, is_json=False):
        self.response_code = response_code
        self.response = response
        if is_json:
            self.response = json.dumps(response)

    def getcode(self):
        return self.response_code

    def read(self):
        return self.response


class FakeServer(object):

    def __init__(self, id, serverNIC='0'):
        self.id = id
        self.serverNIC = serverNIC
        self.serverMacAddr = factory.getRandomMACAddress()


class FakeSeaMicroServerManager(object):

    def __init__(self):
        self.servers = []

    def get(self, server_id):
        for server in self.servers:
            if server_id == server.id:
                return server
        return None

    def list(self):
        return self.servers


class FakeSeaMicroClient(object):
    pass


class TestSeaMicroAPIV09(MAASTestCase):
    """Tests for SeaMicroAPIV09."""

    def test_build_url(self):
        url = factory.getRandomString()
        api = SeaMicroAPIV09('http://%s/' % url)
        location = factory.getRandomString()
        params = [factory.getRandomString() for _ in range(3)]
        output = api.build_url(location, params)
        parsed = urlparse.urlparse(output)
        self.assertEqual(url, parsed.netloc)
        self.assertEqual(location, parsed.path.split('/')[1])
        self.assertEqual(params, parsed.query.split('&'))

    def test_invalid_reponse_code(self):
        url = 'http://%s/' % factory.getRandomString()
        api = SeaMicroAPIV09(url)
        response = FakeResponse(401, 'Unauthorized')
        self.assertRaises(
            SeaMicroAPIV09Error, api.parse_response,
            url, response)

    def test_invalid_json_response(self):
        url = 'http://%s/' % factory.getRandomString()
        api = SeaMicroAPIV09(url)
        response = FakeResponse(200, factory.getRandomString())
        self.assertRaises(
            SeaMicroAPIV09Error, api.parse_response,
            url, response)

    def test_json_error_response(self):
        url = 'http://%s/' % factory.getRandomString()
        api = SeaMicroAPIV09(url)
        data = {
            'error': {
                'code': 401
                }
            }
        response = FakeResponse(200, data, is_json=True)
        self.assertRaises(
            SeaMicroAPIV09Error, api.parse_response,
            url, response)

    def test_json_valid_response(self):
        url = 'http://%s/' % factory.getRandomString()
        api = SeaMicroAPIV09(url)
        output = factory.getRandomString()
        data = {
            'error': {
                'code': 200
                },
            'result': {
                'data': output
                },
            }
        response = FakeResponse(200, data, is_json=True)
        result = api.parse_response(url, response)
        self.assertEqual(output, result['result']['data'])

    def configure_get_result(self, result=None):
        self.patch(
            provisioningserver.custom_hardware.seamicro.SeaMicroAPIV09, 'get',
            Mock(return_value=result))

    def test_login_and_logout(self):
        token = factory.getRandomString()
        self.configure_get_result(token)
        url = 'http://%s/' % factory.getRandomString()
        api = SeaMicroAPIV09(url)
        api.login('username', 'password')
        self.assertEqual(token, api.token)
        api.logout()
        self.assertIsNone(api.token)

    def test_get_server_index(self):
        result = {
            'serverId': {
                0: '0/0',
                1: '1/0',
                2: '2/0',
                }
            }
        self.configure_get_result(result)
        url = 'http://%s/' % factory.getRandomString()
        api = SeaMicroAPIV09(url)
        self.assertEqual(0, api.server_index('0/0'))
        self.assertEqual(1, api.server_index('1/0'))
        self.assertEqual(2, api.server_index('2/0'))
        self.assertIsNone(api.server_index('3/0'))

    def configure_put_server_power(self, token=None):
        result = {
            'serverId': {
                0: '0/0',
                }
            }
        self.configure_get_result(result)
        mock = self.patch(
            provisioningserver.custom_hardware.seamicro.SeaMicroAPIV09,
            'put')
        url = 'http://%s/' % factory.getRandomString()
        api = SeaMicroAPIV09(url)
        api.token = token
        return mock, api

    def assert_put_power_called(self, mock, idx, new_status, *params):
        location = 'servers/%d' % idx
        params = ['action=%s' % new_status] + list(params)
        self.assertThat(mock, MockCalledOnceWith(location, params=params))

    def test_put_server_power_on_using_pxe(self):
        token = factory.getRandomString()
        mock, api = self.configure_put_server_power(token)
        api.power_on('0/0', do_pxe=True)
        self.assert_put_power_called(
            mock, 0, POWER_STATUS.ON, 'using-pxe=true', token)

    def test_put_server_power_on_not_using_pxe(self):
        token = factory.getRandomString()
        mock, api = self.configure_put_server_power(token)
        api.power_on('0/0', do_pxe=False)
        self.assert_put_power_called(
            mock, 0, POWER_STATUS.ON, 'using-pxe=false', token)

    def test_put_server_power_reset_using_pxe(self):
        token = factory.getRandomString()
        mock, api = self.configure_put_server_power(token)
        api.reset('0/0', do_pxe=True)
        self.assert_put_power_called(
            mock, 0, POWER_STATUS.RESET, 'using-pxe=true', token)

    def test_put_server_power_reset_not_using_pxe(self):
        token = factory.getRandomString()
        mock, api = self.configure_put_server_power(token)
        api.reset('0/0', do_pxe=False)
        self.assert_put_power_called(
            mock, 0, POWER_STATUS.RESET, 'using-pxe=false', token)

    def test_put_server_power_off(self):
        token = factory.getRandomString()
        mock, api = self.configure_put_server_power(token)
        api.power_off('0/0', force=False)
        self.assert_put_power_called(
            mock, 0, POWER_STATUS.OFF, 'force=false', token)

    def test_put_server_power_off_force(self):
        token = factory.getRandomString()
        mock, api = self.configure_put_server_power(token)
        api.power_off('0/0', force=True)
        self.assert_put_power_called(
            mock, 0, POWER_STATUS.OFF, 'force=true', token)


class TestSeaMicro(MAASTestCase):
    """Tests for SeaMicro custom hardware."""

    def test_select_seamicro15k_api_version_ipmi(self):
        versions = select_seamicro15k_api_version('ipmi')
        self.assertEqual(['v2.0', 'v0.9'], versions)

    def test_select_seamicro15k_api_version_restapi(self):
        versions = select_seamicro15k_api_version('restapi')
        self.assertEqual(['v0.9'], versions)

    def test_select_seamicro15k_api_version_restapi2(self):
        versions = select_seamicro15k_api_version('restapi2')
        self.assertEqual(['v2.0'], versions)

    def configure_get_seamicro15k_api(self, return_value=None):
        ip = factory.getRandomIPAddress()
        username = factory.getRandomString()
        password = factory.getRandomString()
        mock = self.patch(
            provisioningserver.custom_hardware.seamicro,
            'get_seamicro15k_api')
        mock.return_value = return_value
        return mock, ip, username, password

    def test_find_seamicro15k_servers_impi(self):
        mock, ip, username, password = self.configure_get_seamicro15k_api()
        self.assertRaises(
            SeaMicroError, find_seamicro15k_servers, ip, username,
            password, 'ipmi')
        self.assertThat(
            mock,
            MockCallsMatch(
                call('v2.0', ip, username, password),
                call('v0.9', ip, username, password)))

    def test_find_seamicro15k_servers_restapi(self):
        mock, ip, username, password = self.configure_get_seamicro15k_api()
        self.assertRaises(
            SeaMicroError, find_seamicro15k_servers, ip, username,
            password, 'restapi')
        self.assertThat(
            mock, MockCalledOnceWith('v0.9', ip, username, password))

    def test_find_seamicro15k_servers_restapi2(self):
        mock, ip, username, password = self.configure_get_seamicro15k_api()
        self.assertRaises(
            SeaMicroError, find_seamicro15k_servers, ip, username,
            password, 'restapi2')
        self.assertThat(
            mock, MockCalledOnceWith('v2.0', ip, username, password))

    def configure_api_v09_login(self, token=None):
        token = token or factory.getRandomString()
        mock = self.patch(
            provisioningserver.custom_hardware.seamicro.SeaMicroAPIV09,
            'login')
        mock.return_value = token
        return mock

    def test_probe_seamicro15k_and_enlist_v09(self):
        self.configure_api_v09_login()
        ip = factory.getRandomIPAddress()
        username = factory.getRandomString()
        password = factory.getRandomString()
        result = {
            0: {
                'serverId': '0/0',
                'serverNIC': '0',
                'serverMacAddr': factory.getRandomMACAddress(),
                },
            1: {
                'serverId': '1/0',
                'serverNIC': '0',
                'serverMacAddr': factory.getRandomMACAddress(),
                },
            2: {
                'serverId': '2/0',
                'serverNIC': '0',
                'serverMacAddr': factory.getRandomMACAddress(),
                },
            3: {
                'serverId': '3/1',
                'serverNIC': '1',
                'serverMacAddr': factory.getRandomMACAddress(),
                },
            }
        self.patch(
            provisioningserver.custom_hardware.seamicro.SeaMicroAPIV09, 'get',
            Mock(return_value=result))
        mock_create_node = self.patch(
            provisioningserver.custom_hardware.utils,
            'create_node')

        probe_seamicro15k_and_enlist(
            ip, username, password, power_control='restapi')
        self.assertEqual(3, mock_create_node.call_count)

        last = result[2]
        power_params = {
            'power_control': 'restapi',
            'system_id': last['serverId'].split('/')[0],
            'power_address': ip,
            'power_pass': password,
            'power_user': username
            }
        self.assertThat(
            mock_create_node,
            MockCalledWith(
                last['serverMacAddr'], 'amd64',
                'sm15k', power_params))

    def test_power_control_seamicro15k_v09(self):
        self.configure_api_v09_login()
        ip = factory.getRandomIPAddress()
        username = factory.getRandomString()
        password = factory.getRandomString()
        mock = self.patch(
            provisioningserver.custom_hardware.seamicro.SeaMicroAPIV09,
            'power_server')

        power_control_seamicro15k_v09(ip, username, password, '25', 'on')
        self.assertThat(
            mock,
            MockCalledOnceWith('25/0', POWER_STATUS.ON, do_pxe=True))

    def test_power_control_seamicro15k_v09_retry_failure(self):
        self.configure_api_v09_login()
        ip = factory.getRandomIPAddress()
        username = factory.getRandomString()
        password = factory.getRandomString()
        mock = self.patch(
            provisioningserver.custom_hardware.seamicro.SeaMicroAPIV09,
            'power_server')
        mock.side_effect = SeaMicroAPIV09Error("mock error", response_code=401)

        power_control_seamicro15k_v09(
            ip, username, password, '25', 'on',
            retry_count=5, retry_wait=0)
        self.assertEqual(5, mock.call_count)

    def test_power_control_seamicro15k_v09_exception_failure(self):
        self.configure_api_v09_login()
        ip = factory.getRandomIPAddress()
        username = factory.getRandomString()
        password = factory.getRandomString()
        mock = self.patch(
            provisioningserver.custom_hardware.seamicro.SeaMicroAPIV09,
            'power_server')
        mock.side_effect = SeaMicroAPIV09Error("mock error")

        self.assertRaises(
            SeaMicroAPIV09Error, power_control_seamicro15k_v09,
            ip, username, password, '25', 'on')

    def test_probe_seamicro15k_and_enlist_v2(self):
        ip = factory.getRandomIPAddress()
        username = factory.getRandomString()
        password = factory.getRandomString()

        fake_server_0 = FakeServer('0')
        fake_server_1 = FakeServer('1')
        fake_server_invalid_nic = FakeServer('2', serverNIC='1')
        fake_client = FakeSeaMicroClient()
        fake_client.servers = FakeSeaMicroServerManager()
        fake_client.servers.servers.append(fake_server_0)
        fake_client.servers.servers.append(fake_server_1)
        fake_client.servers.servers.append(fake_server_invalid_nic)
        mock_get_api = self.patch(
            provisioningserver.custom_hardware.seamicro,
            'get_seamicro15k_api')
        mock_get_api.return_value = fake_client
        mock_create_node = self.patch(
            provisioningserver.custom_hardware.utils,
            'create_node')

        probe_seamicro15k_and_enlist(
            ip, username, password, power_control='restapi2')
        self.assertEqual(2, mock_create_node.call_count)

        self.assertThat(
            mock_create_node,
            MockCallsMatch(
                call(
                    fake_server_0.serverMacAddr, 'amd64', 'sm15k',
                    {
                        'power_control': 'restapi2',
                        'system_id': fake_server_0.id,
                        'power_address': ip,
                        'power_pass': password,
                        'power_user': username
                    }),
                call(
                    fake_server_1.serverMacAddr, 'amd64', 'sm15k',
                    {
                        'power_control': 'restapi2',
                        'system_id': fake_server_1.id,
                        'power_address': ip,
                        'power_pass': password,
                        'power_user': username
                    })))

    def test_power_control_seamicro15k_v2(self):
        ip = factory.getRandomIPAddress()
        username = factory.getRandomString()
        password = factory.getRandomString()

        fake_server = FakeServer('0')
        fake_client = FakeSeaMicroClient()
        fake_client.servers = FakeSeaMicroServerManager()
        fake_client.servers.servers.append(fake_server)
        mock_power_on = self.patch(fake_server, 'power_on')

        mock_get_api = self.patch(
            provisioningserver.custom_hardware.seamicro,
            'get_seamicro15k_api')
        mock_get_api.return_value = fake_client

        power_control_seamicro15k_v2(ip, username, password, '0', 'on')
        mock_power_on.assert_called()
