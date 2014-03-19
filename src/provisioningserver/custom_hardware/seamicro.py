# Copyright 2013 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'power_control_seamicro15k_v09',
    'power_control_seamicro15k_v2',
    'probe_seamicro15k_and_enlist',
    ]

import httplib
import json
import logging
import time
import urllib2
import urlparse

from seamicroclient import client as seamicro_client
from seamicroclient import exceptions as seamicro_exceptions
import provisioningserver.custom_hardware.utils as utils


logger = logging.getLogger(__name__)


class POWER_STATUS:
    ON = 'Power-On'
    OFF = 'Power-Off'
    RESET = 'Reset'


class SeaMicroError(Exception):
    """Failure talking to a SeaMicro chassis controller. """
    pass


class SeaMicroAPIV09Error(SeaMicroError):
    """Failure talking to a SeaMicro API v0.9. """

    def __init__(self, msg, response_code=None):
        super(SeaMicroAPIV09Error, self).__init__(msg)
        self.response_code = response_code


class SeaMicroAPIV09(object):
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
            raise SeaMicroAPIV09Error(
                "got response code %s" % response.getcode(),
                response_code=response.getcode())
        text = response.read()

        # Decode the response, it should be json. If not
        # handle that case and set json_data to None, so
        # a SeaMicroAPIV09Error can be raised.
        try:
            json_data = json.loads(text)
        except ValueError:
            json_data = None

        if not json_data:
            raise SeaMicroAPIV09Error(
                'No JSON data found from %s: got %s' % (url, text))
        json_rpc_code = int(json_data['error']['code'])
        if json_rpc_code not in self.allowed_codes:
            raise SeaMicroAPIV09Error(
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
            raise SeaMicroAPIV09Error(
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
            raise SeaMicroAPIV09Error('Invalid power action: %s' % new_status)

        params.append(self.token)
        self.put(location, params=params)
        return True

    def power_on(self, server_id, do_pxe=False):
        return self.power_server(server_id, POWER_STATUS.ON, do_pxe=do_pxe)

    def power_off(self, server_id, force=False):
        return self.power_server(server_id, POWER_STATUS.OFF, force=force)

    def reset(self, server_id, do_pxe=False):
        return self.power_server(server_id, POWER_STATUS.RESET, do_pxe=do_pxe)


def get_seamicro15k_api(version, ip, username, password):
    """Gets the api client depending on the version.
    Supports v0.9 and v2.0.

    :returns: api for version, None if version not supported
    """
    if version == 'v0.9':
        api = SeaMicroAPIV09('http://%s/v0.9/' % ip)
        try:
            api.login(username, password)
        except urllib2.URLError:
            # Cannot reach using v0.9, might not be supported
            return None
        return api
    elif version == 'v2.0':
        url = 'http://%s' % ip
        try:
            api = seamicro_client.Client(
                '2', auth_url=url, username=username, password=password)
        except seamicro_exceptions.ConnectionRefused:
            # Cannot reach using v2.0, might no be supported
            return None
        return api


def get_seamicro15k_servers(version, ip, username, password):
    """Gets a list of tuples containing (server_id, mac_address) from the
    sm15k api version. Supports v0.9 and v2.0.

    :returns: list of (server_id, mac_address), None if version not supported
    """
    api = get_seamicro15k_api(version, ip, username, password)
    if api:
        if version == 'v0.9':
            return (
                (server['serverId'].split('/')[0], server['serverMacAddr'])
                for server in
                api.servers_all().values()
                # There are 8 network cards attached to these boxes, we only
                # use NIC 0 for PXE booting.
                if server['serverNIC'] == '0'
            )
        elif version == 'v2.0':
            return (
                (server.id, server.serverMacAddr)
                for server in
                api.servers.list()
                # There are 8 network cards attached to these boxes, we only
                # use NIC 0 for PXE booting.
                if server.serverNIC == '0'
            )
    return None


def select_seamicro15k_api_version(power_control):
    """Returns the lastest api version to use."""
    if power_control == 'ipmi':
        return ['v2.0', 'v0.9']
    if power_control == 'restapi':
        return ['v0.9']
    if power_control == 'restapi2':
        return ['v2.0']
    raise SeaMicroError(
        'Unsupported power control method: %s.' % power_control)


def find_seamicro15k_servers(ip, username, password, power_control):
    """Returns the list of servers, using the latest supported api version."""
    api_versions = select_seamicro15k_api_version(power_control)
    for version in api_versions:
        servers = get_seamicro15k_servers(version, ip, username, password)
        if servers is not None:
            return servers
    raise SeaMicroError('Failure to retrieve servers.')


def probe_seamicro15k_and_enlist(ip, username, password, power_control=None):
    power_control = power_control or 'ipmi'

    servers = find_seamicro15k_servers(ip, username, password, power_control)
    for system_id, mac in servers:
        params = {
            'power_address': ip,
            'power_user': username,
            'power_pass': password,
            'power_control': power_control,
            'system_id': system_id
        }

        utils.create_node(mac, 'amd64', 'sm15k', params)


def power_control_seamicro15k_v09(ip, username, password, server_id,
                                  power_change, retry_count=5, retry_wait=1):
    server_id = '%s/0' % server_id
    api = SeaMicroAPIV09('http://%s/v0.9/' % ip)

    while retry_count > 0:
        api.login(username, password)
        try:
            if power_change == "on":
                api.power_on(server_id, do_pxe=True)
            elif power_change == "off":
                api.power_off(server_id, force=True)
        except SeaMicroAPIV09Error as e:
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


def power_control_seamicro15k_v2(ip, username, password, server_id,
                                 power_change):
    api = get_seamicro15k_api('v2.0', ip, username, password)
    if api:
        server = api.servers.get(server_id)
        if power_change == "on":
            server.power_on()
        elif power_change == "off":
            server.power_off()
