# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'power_control_msftocs',
    'power_state_msftocs',
    'probe_and_enlist_msftocs',
    ]

import urllib2
import urlparse

from lxml.etree import fromstring
from provisioningserver.utils import (
    commission_node,
    create_node,
)
from provisioningserver.utils.twisted import synchronous


class MicrosoftOCSState(object):
    ON = "ON"
    OFF = "OFF"


class MicrosoftOCSException(Exception):
    """Failure talking to a MicrosoftOCS chassis controller. """


class MicrosoftOCSAPI(object):
    """API to communicate with the Microsoft OCS Chassis Manager."""

    def __init__(self, ip, port, username, password):
        """
        :param ip: The IP address of the MicrosoftOCS chassis,
          e.g.: "192.168.0.1"
        :type ip: string
        :param port: The http port to connect to the MicrosoftOCS chassis,
          e.g.: "8000"
        :type port: string
        :param username: The username for authentication to the MicrosoftOCS
          chassis, e.g.: "admin"
        :type username: string
        :param password: The password for authentication to the MicrosoftOCS
          chassis, e.g.: "password"
        :type password: string
        """
        self.ip = ip
        self.port = port
        self.username = username
        self.password = password

    def build_url(self, command, params=None):
        url = 'http://%s:%d/' % (self.ip, self.port)
        if params is None:
            params = []
        params = filter(None, params)
        return urlparse.urljoin(url, command) + '?' + '&'.join(params)

    def extract_from_response(self, response, element_tag):
        """Extract text from first element with element_tag in response."""
        root = fromstring(response)
        return root.findtext(
            './/ns:%s' % element_tag,
            namespaces={'ns': root.nsmap[None]})

    def get(self, command, params=None):
        """Dispatch a GET request to a Microsoft OCS chassis."""
        url = self.build_url(command, params)
        authinfo = urllib2.HTTPPasswordMgrWithDefaultRealm()
        authinfo.add_password(None, url, self.username, self.password)
        proxy_handler = urllib2.ProxyHandler({})
        auth_handler = urllib2.HTTPBasicAuthHandler(authinfo)
        opener = urllib2.build_opener(proxy_handler, auth_handler)
        urllib2.install_opener(opener)
        response = urllib2.urlopen(url)
        return response.read()

    def get_blade_power_state(self, bladeid):
        """Gets the ON/OFF State of Blade."""
        params = ["bladeid=%s" % bladeid]
        return self.extract_from_response(
            self.get('GetBladeState', params), 'bladeState')

    def _set_power(self, bladeid, element_tag):
        """Set AC Outlet Power for Blade."""
        params = ["bladeid=%s" % bladeid]
        return self.extract_from_response(
            self.get(element_tag, params), 'completionCode')

    def set_power_off_blade(self, bladeid):
        """Turns AC Outlet Power OFF for Blade."""
        return self._set_power(bladeid, 'SetBladeOff')

    def set_power_on_blade(self, bladeid):
        """Turns AC Outlet Power ON for Blade."""
        return self._set_power(bladeid, 'SetBladeOn')

    def set_next_boot_device(self, bladeid, pxe=False,
                             uefi=False, persistent=False):
        """Set Next Boot Device."""
        boot_pxe = '2' if pxe else '3'
        boot_uefi = 'true' if uefi else 'false'
        boot_persistent = 'true' if persistent else 'false'
        params = [
            "bladeid=%s" % bladeid, "bootType=%s" % boot_pxe,
            "uefi=%s" % boot_uefi, "persistent=%s" % boot_persistent
        ]
        return self.extract_from_response(
            self.get('SetNextBoot', params), 'nextBoot')

    def get_blades(self):
        """Gets available Blades.

        Returns dictionary of blade numbers and their corresponding
        MAC Addresses.
        """
        blades = {}
        root = fromstring(self.get('GetChassisInfo'))
        namespace = {'ns': root.nsmap[None]}
        blade_collections = root.find(
            './/ns:bladeCollections', namespaces=namespace)
        # Iterate over all BladeInfo Elements
        for blade_info in blade_collections:
            blade_mac_address = blade_info.find(
                './/ns:bladeMacAddress', namespaces=namespace)
            macs = []
            # Iterate over all NicInfo Elements and add MAC Addresses
            for nic_info in blade_mac_address:
                macs.append(
                    nic_info.findtext(
                        './/ns:macAddress', namespaces=namespace))
            macs = filter(None, macs)
            if macs:
                # Retrive Blade id number
                bladeid = blade_info.findtext(
                    './/ns:bladeNumber', namespaces=namespace)
                # Add MAC Addresses for Blade
                blades[bladeid] = macs

        return blades


def power_state_msftocs(ip, port, username, password, blade_id):
    """Return the power state for the given Blade."""

    port = int(port) or 8000  # Default Port for MicrosoftOCS Chassis is 8000
    api = MicrosoftOCSAPI(ip, port, username, password)

    try:
        power_state = api.get_blade_power_state(blade_id)
    except Exception as e:
        raise MicrosoftOCSException(
            "Failed to retrieve power state: %s" % e)

    if power_state == MicrosoftOCSState.OFF:
        return 'off'
    elif power_state == MicrosoftOCSState.ON:
        return 'on'
    raise MicrosoftOCSException('Unknown power state: %s' % power_state)


def power_control_msftocs(
        ip, port, username, password, blade_id, power_change):
    """Control the power state for the given Blade."""

    port = int(port) or 8000  # Default Port for MicrosoftOCS Chassis is 8000
    api = MicrosoftOCSAPI(ip, port, username, password)

    if power_change == 'on':
        power_state = api.get_blade_power_state(blade_id)
        if power_state == MicrosoftOCSState.ON:
            api.set_power_off_blade(blade_id)
        # Set default (persistent) boot to HDD
        api.set_next_boot_device(blade_id, persistent=True)
        # Set next boot to PXE
        api.set_next_boot_device(blade_id, pxe=True)
        api.set_power_on_blade(blade_id)
    elif power_change == 'off':
        api.set_power_off_blade(blade_id)
    else:
        raise MicrosoftOCSException(
            "Unexpected MAAS power mode: %s" % power_change)


@synchronous
def probe_and_enlist_msftocs(
        user, ip, port, username, password, accept_all=False):
    """ Extracts all of nodes from msftocs, sets all of them to boot via
    HDD by, default, sets them to bootonce via PXE, and then enlists them
    into MAAS.
    """
    port = int(port) or 8000  # Default Port for MicrosoftOCS Chassis is 8000
    api = MicrosoftOCSAPI(ip, port, username, password)

    try:
        # if get_blades works, we have access to the system
        blades = api.get_blades()
    except:
        raise MicrosoftOCSException(
            "Failed to probe nodes for Microsoft OCS with ip=%s "
            "port=%d, username=%s, password=%s"
            % (ip, port, username, password))

    for blade_id, macs in blades.iteritems():
        # Set default (persistent) boot to HDD
        api.set_next_boot_device(blade_id, persistent=True)
        # Set next boot to PXE
        api.set_next_boot_device(blade_id, pxe=True)
        params = {
            'power_address': ip,
            'power_port': port,
            'power_user': username,
            'power_pass': password,
            'blade_id': blade_id,
        }
        system_id = create_node(macs, 'amd64', 'msftocs', params).wait(30)

        if accept_all:
            commission_node(system_id, user).wait(30)
