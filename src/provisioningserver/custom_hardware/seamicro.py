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
import logging
import urllib2
import urlparse

from StringIO import StringIO

from provisioningserver.custom_hardware.utils import (
    create_node
    )
from provisioningserver.enum import (
    POWER_TYPE
    )

logger = logging.getLogger(__name__)


class SeaMicroAPIError(Exception):
    """Failure talking to a SeaMicro chassis controller. """


class SeaMicroAPI(object):
    def __init__(self, url, username=None, password=None):
        """
        :param url: The URL of the seamicro chassis, e.g.: http://seamciro/v0.9
        :type url: string
        """
        self.url = url
        self.token = self._get("login", [username, password])

    def _get(self, location, params=None):
        """Dispatch a GET request to a SeaMicro chassis.

        The seamicro box has order-dependent HTTP parameters, so we build
        our own get URL, and use a list vs. a dict for data, as the order is
        implicit.
        """
        if params is None:
            params = []
        params = filter(None, params)

        allowed_codes = [httplib.OK, httplib.ACCEPTED, httplib.NOT_MODIFIED]

        url = urlparse.urljoin(self.url, location) + '?' + '&'.join(params)
        response = urllib2.urlopen(url)
        if response.getcode() not in allowed_codes:
            raise SeaMicroAPIError("got response code %d" % response.getcode())
        text = response.read()
        json_data = json.load(StringIO(text))

        if not json_data:
            raise SeaMicroAPIError(
                'No JSON data found from %s: got %s' % (url, text))
        json_rpc_code = int(json_data['error']['code'])
        if json_rpc_code not in allowed_codes:
            raise SeaMicroAPIError(
                'Got JSON RPC error code %d: %s for %s' % (
                    json_rpc_code,
                    httplib.responses.get(json_rpc_code, 'Unknown!'),
                    url))

        return json_data['result']

    def servers_all(self):
        return self._get("servers/all", [self.token])


def probe_seamicro15k_and_enlist(ip, username, password):
    api = SeaMicroAPI('http://%s/v0.9/' % ip, username, password)

    servers = (
        server for _, server in
        api.servers_all().iteritems()
        # There are 8 network cards attached to these boxes, we only use NIC 0
        # for PXE booting.
        if server['serverNIC'] != '0'
    )

    for server in servers:
        # serverId looks like 63/2, i.e. power id 63, CPU 2. We only want the
        # system id part of this.
        [_, system_id] = server['serverId'].split('/')
        mac = server['serverMacAddr']

        params = {
            'power_address': ip,
            'power_user': username,
            'power_pass': password,
            'system_id': system_id
        }

        create_node(mac, 'amd64', POWER_TYPE.SEAMICRO15K, params)
