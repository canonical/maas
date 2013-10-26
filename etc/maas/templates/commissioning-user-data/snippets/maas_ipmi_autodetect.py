#!/usr/bin/python
#
# maas-ipmi-autodetect - autodetect and autoconfigure IPMI.
#
# Copyright (C) 2011-2013 Canonical
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

import os
import commands
import re
import string
import random
import time
import json


def is_ipmi_dhcp():
    status, output = commands.getstatusoutput(
        'bmc-config --checkout --key-pair="Lan_Conf:IP_Address_Source"')
    show_re = re.compile('IP_Address_Source\s+Use_DHCP')
    return show_re.search(output) is not None


def set_ipmi_network_source(source):
    status, output = commands.getstatusoutput(
        'bmc-config --commit --key-pair="Lan_Conf:IP_Address_Source=%s"'
        % source)


def get_ipmi_ip_address():
    status, output = commands.getstatusoutput(
        'bmc-config --checkout --key-pair="Lan_Conf:IP_Address"')
    show_re = re.compile('([0-9]{1,3}[.]?){4}')
    res = show_re.search(output)
    return res.group()


def get_ipmi_user_number(user):
    for i in range(1, 17):
        ipmi_user_number = "User%s" % i
        status, output = commands.getstatusoutput(
            'bmc-config --checkout --key-pair="%s:Username"'
            % ipmi_user_number)
        if user in output:
            return ipmi_user_number
    return None


def commit_ipmi_user_settings(user, password):
    ipmi_user_number = get_ipmi_user_number(user)
    if ipmi_user_number is None:
        status, output = commands.getstatusoutput(
            'bmc-config --commit --key-pair="User10:Username=%s"' % user)
        ipmi_user_number = get_ipmi_user_number(user)
    status, output = commands.getstatusoutput(
        'bmc-config --commit --key-pair="%s:Username=%s"'
        % (ipmi_user_number, user))
    status, output = commands.getstatusoutput(
        'bmc-config --commit --key-pair="%s:Password=%s"'
        % (ipmi_user_number, password))
    status, output = commands.getstatusoutput(
        'bmc-config --commit --key-pair="%s:Enable_User=Yes"'
        % ipmi_user_number)
    status, output = commands.getstatusoutput(
        'bmc-config --commit --key-pair="%s:Lan_Enable_IPMI_Msgs=Yes"'
        % ipmi_user_number)
    status, output = commands.getstatusoutput(
        'bmc-config --commit --key-pair="%s:Lan_Privilege_Limit=Administrator"'
        % ipmi_user_number)


def commit_ipmi_settings(config):
    status, output = commands.getstatusoutput(
        'bmc-config --commit --filename %s' % config)


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
    (status, output) = commands.getstatusoutput('ipmi-locate')
    show_re = re.compile('(IPMI\ Version:) (\d\.\d)')
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
