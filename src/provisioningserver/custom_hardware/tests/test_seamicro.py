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
from maastesting.testcase import MAASTestCase
from maastesting.matchers import (
    MockCalledWith,
    MockCalledOnceWith,
    )
from mock import Mock
import provisioningserver.custom_hardware.utils
from provisioningserver.custom_hardware.seamicro import (
    POWER_STATUS,
    SeaMicroAPI,
    SeaMicroAPIError,
    probe_seamicro15k_and_enlist,
    power_control_seamicro15k,
    )


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


class TestSeaMicroAPI(MAASTestCase):
    """Tests for SeaMicroAPI."""

    def test_build_url(self):
        url = factory.getRandomString()
        api = SeaMicroAPI('http://%s/' % url)
        location = factory.getRandomString()
        params = [factory.getRandomString() for _ in range(3)]
        output = api.build_url(location, params)
        parsed = urlparse.urlparse(output)
        self.assertEqual(url, parsed.netloc)
        self.assertEqual(location, parsed.path.split('/')[1])
        self.assertEqual(params, parsed.query.split('&'))

    def test_invalid_reponse_code(self):
        url = 'http://%s/' % factory.getRandomString()
        api = SeaMicroAPI(url)
        response = FakeResponse(401, 'Unauthorized')
        self.assertRaises(
            SeaMicroAPIError, api.parse_response,
            url, response)

    def test_invalid_json_response(self):
        url = 'http://%s/' % factory.getRandomString()
        api = SeaMicroAPI(url)
        response = FakeResponse(200, factory.getRandomString())
        self.assertRaises(
            SeaMicroAPIError, api.parse_response,
            url, response)

    def test_json_error_response(self):
        url = 'http://%s/' % factory.getRandomString()
        api = SeaMicroAPI(url)
        data = {
            'error': {
                'code': 401
                }
            }
        response = FakeResponse(200, data, is_json=True)
        self.assertRaises(
            SeaMicroAPIError, api.parse_response,
            url, response)

    def test_json_valid_response(self):
        url = 'http://%s/' % factory.getRandomString()
        api = SeaMicroAPI(url)
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
        self.assertEqual(result['result']['data'], output)

    def configure_get_result(self, result=None):
        self.patch(
            provisioningserver.custom_hardware.seamicro.SeaMicroAPI, 'get',
            Mock(return_value=result))

    def test_login_and_logout(self):
        token = factory.getRandomString()
        self.configure_get_result(token)
        url = 'http://%s/' % factory.getRandomString()
        api = SeaMicroAPI(url)
        api.login('username', 'password')
        self.assertEqual(api.token, token)
        api.logout()
        self.assertEqual(api.token, None)

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
        api = SeaMicroAPI(url)
        self.assertEqual(api.server_index('0/0'), 0)
        self.assertEqual(api.server_index('1/0'), 1)
        self.assertEqual(api.server_index('2/0'), 2)
        self.assertEqual(api.server_index('3/0'), None)

    def configure_put_server_power(self, token=None):
        result = {
            'serverId': {
                0: '0/0',
                }
            }
        self.configure_get_result(result)
        mock = self.patch(
            provisioningserver.custom_hardware.seamicro.SeaMicroAPI,
            'put')
        url = 'http://%s/' % factory.getRandomString()
        api = SeaMicroAPI(url)
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

    def test_probe_seamicro15k_and_enlist(self):
        ip = factory.getRandomString()
        token = factory.getRandomString()
        username = factory.getRandomString()
        password = factory.getRandomString()
        mock = self.patch(
            provisioningserver.custom_hardware.seamicro.SeaMicroAPI,
            'login')
        mock.return_value = token
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
        self.configure_get_result(result)
        mock_create_node = self.patch(
            provisioningserver.custom_hardware.utils,
            'create_node')

        probe_seamicro15k_and_enlist(
            ip, username, password, power_control='ipmi')
        self.assertEqual(mock_create_node.call_count, 3)

        last = result[2]
        power_params = {
            'power_control': 'ipmi',
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

    def test_power_control_seamicro15k(self):
        ip = factory.getRandomString()
        token = factory.getRandomString()
        username = factory.getRandomString()
        password = factory.getRandomString()
        self.patch(
            provisioningserver.custom_hardware.seamicro.SeaMicroAPI,
            'login', Mock(return_value=token))
        mock = self.patch(
            provisioningserver.custom_hardware.seamicro.SeaMicroAPI,
            'power_server')

        power_control_seamicro15k(ip, username, password, '25', 'on')
        self.assertThat(
            mock,
            MockCalledOnceWith('25/0', POWER_STATUS.ON, do_pxe=True))

    def test_power_control_seamicro15k_retry_failure(self):
        ip = factory.getRandomString()
        token = factory.getRandomString()
        username = factory.getRandomString()
        password = factory.getRandomString()
        self.patch(
            provisioningserver.custom_hardware.seamicro.SeaMicroAPI,
            'login', Mock(return_value=token))
        mock = self.patch(
            provisioningserver.custom_hardware.seamicro.SeaMicroAPI,
            'power_server')
        mock.side_effect = SeaMicroAPIError("mock error", response_code=401)

        power_control_seamicro15k(
            ip, username, password, '25', 'on',
            retry_count=5, retry_wait=0)
        self.assertEqual(mock.call_count, 5)

    def test_power_control_seamicro15k_exception_failure(self):
        ip = factory.getRandomString()
        token = factory.getRandomString()
        username = factory.getRandomString()
        password = factory.getRandomString()
        self.patch(
            provisioningserver.custom_hardware.seamicro.SeaMicroAPI,
            'login', Mock(return_value=token))
        mock = self.patch(
            provisioningserver.custom_hardware.seamicro.SeaMicroAPI,
            'power_server')
        mock.side_effect = SeaMicroAPIError("mock error")

        self.assertRaises(
            SeaMicroAPIError, power_control_seamicro15k,
            ip, username, password, '25', 'on')
