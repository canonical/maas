#!/usr/bin/python
#
# maas-ipmi-autodetect - autodetect and autoconfigure IPMI.
#
# Copyright (C) 2011-2014 Canonical
#
# Authors:
#    Andres Rodriguez <andres.rodriguez@canonical.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import (
    absolute_import,
    print_function,
    #unicode_literals,
    )

str = None

__metaclass__ = type

import json
import os
import random
import re
import string
import subprocess
import time


class IPMIUserError(Exception):
    """An error related to an IPMI user."""


def run_command(command_args):
    """Run a command. Return output if successful or raise exception if not."""
    output = subprocess.check_output(command_args, stderr=subprocess.STDOUT)
    return output


def bmc_get(key):
    """Fetch the output of a key via bmc-config checkout."""
    command = ('bmc-config', '--checkout', '--key-pair=%s' % key)
    output = run_command(command)
    return output


def bmc_set(key, value):
    """Set the value of a key via bmc-config commit."""
    command = ('bmc-config', '--commit', '--key-pair=%s=%s' % (key, value))
    run_command(command)


def format_user_key(user_number, parameter):
    """Format a user key string."""
    return '%s:%s' % (user_number, parameter)


def bmc_user_set(user_number, parameter, value):
    """Set a user parameter via bmc-config commit."""
    key = format_user_key(user_number, parameter)
    bmc_set(key, value)


def parse_section(section):
    """Parse the text of a section.

    Returns a tuple of ('SectionName', section_attributes_dict)
    """
    # match lines with a word followed by space and then a non commment string
    pattern = r'^\s*(\w+)\s+([^# \t\r\n\v\f]+).*$'
    kv_tuples = re.findall(pattern, section, re.MULTILINE)
    kv_dict = dict(kv_tuples)
    section_name = kv_dict.pop('Section')
    section_record = (section_name, kv_dict)

    return section_record


def bmc_get_section(section_name):
    """Retrieve the text of a section from the BMC."""
    command = ('bmc-config', '--checkout', '--section', section_name)
    output = run_command(command)
    return output


def get_user_record(user_number):
    """Return a dictionary of the user settings for a user number."""
    section = bmc_get_section(user_number)
    _, record = parse_section(section)
    return record


def bmc_list_sections():
    """Retrieve the names of config sections from the BMC."""
    command = ('bmc-config', '-L')
    output = run_command(command)
    return output


def list_user_numbers():
    """List the user numbers on the BMC."""
    output = bmc_list_sections()
    pattern = r'^(User\d+)$'
    users = re.findall(pattern, output, re.MULTILINE)

    return users


def pick_user_number_from_list(search_username, user_numbers):
    """Pick the best user number for a user from a list of user numbers.

    If any any existing user's username matches the search username, pick
    that user.

    Otherwise, pick the first user that has no username set.

    If no users match those criteria, raise an IPMIUserError.
    """
    first_unused = None

    for user_number in user_numbers:
        # The IPMI spec reserves User1 as anonymous.
        if user_number == 'User1':
            continue

        user_record = get_user_record(user_number)

        username = user_record.get('Username')

        if username == search_username:
            return user_number

        if username is None and first_unused is None:
                first_unused = user_number

    return first_unused


def pick_user_number(search_username):
    """Pick the best user number for a username."""
    user_numbers = list_user_numbers()
    user_number = pick_user_number_from_list(search_username, user_numbers)

    if not user_number:
        raise IPMIUserError('No IPMI user slots available.')

    return user_number


def is_ipmi_dhcp():
    output = bmc_get('Lan_Conf:IP_Address_Source')
    show_re = re.compile('IP_Address_Source\s+Use_DHCP')
    return show_re.search(output) is not None


def set_ipmi_network_source(source):
    bmc_set('Lan_Conf:IP_Address_Source', source)


def get_ipmi_ip_address():
    output = bmc_get('Lan_Conf:IP_Address')
    show_re = re.compile('([0-9]{1,3}[.]?){4}')
    res = show_re.search(output)
    return res.group()


def commit_ipmi_user_settings(user, password):
    ipmi_user_number = pick_user_number(user)
    bmc_user_set(ipmi_user_number, 'Username', user)
    bmc_user_set(ipmi_user_number, 'Password', password)
    bmc_user_set(ipmi_user_number, 'Enable_User', 'Yes')
    bmc_user_set(ipmi_user_number, 'Lan_Enable_IPMI_Msgs', 'Yes')
    bmc_user_set(ipmi_user_number, 'Lan_Privilege_Limit', 'Administrator')


def commit_ipmi_settings(config):
    run_command(('bmc-config', '--commit', '--filename %s') % config)


def get_maas_power_settings(user, password, ipaddress, version):
    return "%s,%s,%s,%s" % (user, password, ipaddress, version)


def get_maas_power_settings_json(user, password, ipaddress, version):
    power_params = {
        "power_address": ipaddress,
        "power_pass": password,
        "power_user": user,
        "power_driver": version,
    }
    return json.dumps(power_params)


def generate_random_password(min_length=8, max_length=15):
    length = random.randint(min_length, max_length)
    letters = string.ascii_letters + string.digits
    return ''.join([random.choice(letters) for _ in range(length)])


def get_ipmi_version():
    output = run_command(('ipmi-locate'))
    #IPMI Version: 2.0
    #IPMI locate driver: SMBIOS
    #IPMI interface: KCS
    #BMC driver device:
    #BMC I/O base address: 0xCA2
    #Register spacing: 1
    #show_re = re.compile('(IPMI\ Version:) (\d\.\d)')
    show_re = re.compile(
        '(IPMI\ Version:) (\d\.\d)(\n)(.*)(\n)(.*)(\n)(.*)(\n)'
        '(BMC\ I\/O\ base\ address:) (0xCA2)')
    res = show_re.search(output)
    if res is None:
        return
    return res.group(2)


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='send config file to modify IPMI settings with')
    parser.add_argument(
        "--configdir", metavar="folder", help="specify config file directory",
        default=None)
    parser.add_argument(
        "--dhcp-if-static", action="store_true", dest="dhcp",
        help="set network source to DHCP if Static", default=False)
    parser.add_argument(
        "--commission-creds", action="store_true", dest="commission_creds",
        help="Create IPMI temporary credentials", default=False)

    args = parser.parse_args()

    # Check whether IPMI is being set to DHCP. If it is not, and
    # '--dhcp-if-static' has been passed,  Set it to IPMI to DHCP.
    if not is_ipmi_dhcp() and args.dhcp:
        set_ipmi_network_source("Use_DHCP")
        # allow IPMI 120 seconds to obtain an IP address
        time.sleep(120)
    # create user/pass
    IPMI_MAAS_USER = "maas"
    IPMI_MAAS_PASSWORD = generate_random_password()

    # Configure IPMI user/password
    commit_ipmi_user_settings(IPMI_MAAS_USER, IPMI_MAAS_PASSWORD)

    # Commit other IPMI settings
    if args.configdir:
        for file in os.listdir(args.configdir):
            commit_ipmi_settings(os.path.join(args.configdir, file))

    # get the IP address
    IPMI_IP_ADDRESS = get_ipmi_ip_address()
    if IPMI_IP_ADDRESS == "0.0.0.0":
        # if IPMI_IP_ADDRESS is 0.0.0.0, wait 60 seconds and retry.
        set_ipmi_network_source("Static")
        time.sleep(2)
        set_ipmi_network_source("Use_DHCP")
        time.sleep(60)
        IPMI_IP_ADDRESS = get_ipmi_ip_address()

    if IPMI_IP_ADDRESS is None or IPMI_IP_ADDRESS == "0.0.0.0":
        # Exit (to not set power params in MAAS) if no IPMI_IP_ADDRESS
        # has been detected
        exit(1)

    IPMI_VERSION = "LAN"
    if get_ipmi_version() == "2.0":
        IPMI_VERSION = "LAN_2_0"
    if args.commission_creds:
        print(get_maas_power_settings_json(
            IPMI_MAAS_USER, IPMI_MAAS_PASSWORD, IPMI_IP_ADDRESS, IPMI_VERSION))
    else:
        print(get_maas_power_settings(
            IPMI_MAAS_USER, IPMI_MAAS_PASSWORD, IPMI_IP_ADDRESS, IPMI_VERSION))

if __name__ == '__main__':
    main()
