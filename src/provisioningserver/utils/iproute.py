# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Utility to parse 'ip route list scope global'.

Example dictionary returned by parse_ip_route():

{u'default': {u'via': u'192.168.1.1',
              u'dev': 'eno1',
              u'proto': 'static',
              u'metric': 100},
 u'172.16.254.0/24': {u'via': u'192.168.1.1',
                      u'dev': 'eno1'}}

The dictionary above is generated given the following input:

        default via 192.168.1.1 dev eno1  proto static  metric 100
        172.16.254.0/24 via 192.168.1.1 dev eno1
"""


from provisioningserver.utils.ipaddr import get_settings_dict
from provisioningserver.utils.shell import call_and_check


def _parse_route_definition(line):
    """Given a string of the format:
        <subnet> via <ip_address> dev <interface> metric <metric>
    Returns a dictionary containing the component parts.
    :param line: unicode
    :return: dict
    :raises: ValueError if a malformed interface route line is presented.
    """
    subnet, line = line.split(" ", 1)
    settings = get_settings_dict(line.strip())
    if "metric" in settings:
        settings["metric"] = int(settings["metric"])
    return subnet.strip(), settings


def parse_ip_route(output):
    """Parses the output from 'ip route list scope global' into a dictionary.

    Given the full output from 'ip route list scope global', parses it and
    returns a dictionary mapping each subnet to a route.

    :param output: string or unicode
    :return: dict
    """
    # It's possible, though unlikely, that unicode characters will appear
    # in interface names.
    if not isinstance(output, str):
        output = str(output, "utf-8")

    routes = {}
    for line in output.splitlines():
        subnet, route = _parse_route_definition(line)
        routes[subnet] = route
    return routes


def get_ip_route():
    """Returns this system's local IP route information as a dictionary.

    :raises:ExternalProcessError: if IP route information could not be
        gathered.
    """
    ip_route_output = call_and_check(
        ["ip", "route", "list", "scope", "global"]
    )
    return parse_ip_route(ip_route_output)
