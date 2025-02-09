# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Utility to parse 'ip route' output.

Example dictionary returned by get_ip_route():

{'default': {
    'gateway': '192.168.1.1',
    'dev': 'eno1',
    'protocol': 'static',
    'metric': 100,
    'flags': []},
 '172.16.254.0/24': {
    'gateway': u'192.168.1.1',
    'dev': 'eno1',
    'protocol': 'static',
    'metric': 50,
    'flags': []},
}

"""

import json

from provisioningserver.utils.shell import call_and_check


def get_ip_route():
    """Returns this system's local IP route information as a dictionary.

    :raises:ExternalProcessError: if IP route information could not be
        gathered.
    """
    output = call_and_check(
        ["ip", "-json", "route", "list", "scope", "global"]
    )
    routes = {}
    for entry in json.loads(output):
        routes[entry.pop("dst")] = entry
    return routes
