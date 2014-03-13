# Copyright 2013 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type

import httplib
import json
import time
import logging
import urllib2
import urlparse

import provisioningserver.custom_hardware.utils as utils


logger = logging.getLogger(__name__)


class POWER_STATUS:
    ON = 'Power-On'
    OFF = 'Power-Off'
    RESET = 'Reset'


class SeaMicroAPIError(Exception):
    """Failure talking to a SeaMicro chassis controller. """

    def __init__(self, msg, response_code=None):
        super(SeaMicroAPIError, self).__init__(msg)
        self.response_code = response_code


class SeaMicroAPI(object):
    allowed_codes = [httplib.OK, httplib.ACCEPTED, httplib.NOT_MODIFIED]

    def __init__(self, url):
        """
        :param url: The URL of the seamicro chassis, e.g.: http://seamciro/v0.9
        :type url: string
        """
        self.url = url
        self.token = None

    def build_url(self, location, params=None):
        """Builds an order-dependent url, as the SeaMicro chassis
        requires order-dependent parameters.
        """
        if params is None:
            params = []
        params = filter(None, params)
        return urlparse.urljoin(self.url, location) + '?' + '&'.join(params)

    def parse_response(self, url, response):
        """Parses the HTTP response, checking for errors
        from the SeaMicro chassis.
        """
        if response.getcode() not in self.allowed_codes:
            raise SeaMicroAPIError(
                "got response code %s" % response.getcode(),
                response_code=response.getcode())
        text = response.read()

        # Decode the response, it should be json. If not
        # handle that case and set json_data to None, so
        # a SeaMicroAPIError can be raised.
        try:
            json_data = json.loads(text)
        except ValueError:
            json_data = None

        if not json_data:
            raise SeaMicroAPIError(
                'No JSON data found from %s: got %s' % (url, text))
        json_rpc_code = int(json_data['error']['code'])
        if json_rpc_code not in self.allowed_codes:
            raise SeaMicroAPIError(
                'Got JSON RPC error code %d: %s for %s' % (
                    json_rpc_code,
                    httplib.responses.get(json_rpc_code, 'Unknown!'),
                    url),
                response_code=json_rpc_code)
        return json_data

    def get(self, location, params=None):
        """Dispatch a GET request to a SeaMicro chassis.

        The seamicro box has order-dependent HTTP parameters, so we build
        our own get URL, and use a list vs. a dict for data, as the order is
        implicit.
        """
        url = self.build_url(location, params)
        response = urllib2.urlopen(url)
        json_data = self.parse_response(url, response)

        return json_data['result']

    def put(self, location, params=None):
        """Dispatch a PUT request to a SeaMicro chassis.

        The seamicro box has order-dependent HTTP parameters, so we build
        our own get URL, and use a list vs. a dict for data, as the order is
        implicit.
        """
        opener = urllib2.build_opener(urllib2.HTTPHandler)
        url = self.build_url(location, params)
        request = urllib2.Request(url)
        request.get_method = lambda: 'PUT'
        request.add_header('content-type', 'text/json')
        response = opener.open(request)
        json_data = self.parse_response(url, response)

        return json_data['result']

    def is_logged_in(self):
        return self.token is not None

    def login(self, username, password):
        if not self.is_logged_in():
            self.token = self.get("login", [username, password])

    def logout(self):
        if self.is_logged_in():
            self.get("logout")
            self.token = None

    def servers_all(self):
        return self.get("servers/all", [self.token])

    def servers(self):
        return self.get("servers", [self.token])

    def server_index(self, server_id):
        """API v0.9 uses arbitrary indexing, this function converts a server
        id to an index that can be used for detailed outputs & commands.
        """
        servers = self.servers()['serverId']
        for idx, name in servers.items():
            if name == server_id:
                return idx
        return None

    def power_server(self, server_id, new_status, do_pxe=False, force=False):
        idx = self.server_index(server_id)
        if idx is None:
            raise SeaMicroAPIError(
                'Failed to retrieve server index, '
                'invalid server_id: %s' % server_id)

        location = 'servers/%s' % idx
        params = ['action=%s' % new_status]
        if new_status in [POWER_STATUS.ON, POWER_STATUS.RESET]:
            if do_pxe:
                params.append("using-pxe=true")
            else:
                params.append("using-pxe=false")
        elif new_status in [POWER_STATUS.OFF]:
            if force:
                params.append("force=true")
            else:
                params.append("force=false")
        else:
            raise SeaMicroAPIError('Invalid power action: %s' % new_status)

        params.append(self.token)
        self.put(location, params=params)
        return True

    def power_on(self, server_id, do_pxe=False):
        return self.power_server(server_id, POWER_STATUS.ON, do_pxe=do_pxe)

    def power_off(self, server_id, force=False):
        return self.power_server(server_id, POWER_STATUS.OFF, force=force)

    def reset(self, server_id, do_pxe=False):
        return self.power_server(server_id, POWER_STATUS.RESET, do_pxe=do_pxe)


def probe_seamicro15k_and_enlist(ip, username, password, power_control=None):
    api = SeaMicroAPI('http://%s/v0.9/' % ip)
    api.login(username, password)

    servers = (
        server for server in
        api.servers_all().values()
        # There are 8 network cards attached to these boxes, we only use NIC 0
        # for PXE booting.
        if server['serverNIC'] == '0'
    )

    for server in servers:
        # serverId looks like 63/2, i.e. power id 63, CPU 2. We only want the
        # system id part of this.
        [system_id, _] = server['serverId'].split('/')
        mac = server['serverMacAddr']

        params = {
            'power_address': ip,
            'power_user': username,
            'power_pass': password,
            'power_control': power_control or 'ipmi',
            'system_id': system_id
        }

        utils.create_node(mac, 'amd64', 'sm15k', params)


def power_control_seamicro15k(ip, username, password, server_id, power_change,
                              retry_count=5, retry_wait=1):
    server_id = '%s/0' % server_id
    api = SeaMicroAPI('http://%s/v0.9/' % ip)

    while retry_count > 0:
        api.login(username, password)
        try:
            if power_change == "on":
                api.power_on(server_id, do_pxe=True)
            elif power_change == "off":
                api.power_off(server_id, force=True)
        except SeaMicroAPIError as e:
            # Chance that multiple login's are at once, the api
            # only supports one at a time. So lets try again after
            # a second, up to max retry count.
            if e.response_code == 401:
                retry_count -= 1
                time.sleep(retry_wait)
                continue
            else:
                raise
        break
