#!/usr/bin/python

from __future__ import (
    absolute_import,
    print_function,
    # unicode_literals,
    )

str = None

__metaclass__ = type

import argparse
import commands
import json
import re


IPMI_MAAS_USER = 'Administrator'
IPMI_MAAS_PASSWORD = 'password'


def get_local_address():
    output = commands.getoutput('ipmitool raw 0x2c 1 0')
    return "0x%s" % output.split()[2]


def get_cartridge_address(local_address):
    # obtain address of Cartridge Controller (parent of the system node):
    output = commands.getoutput(
        'ipmitool -t 0x20 -b 0 -m %s raw 0x2c 1 0' % local_address)
    return "0x%s" % output.split()[2]


def get_channel_number(address, output):
    # channel number (routing to this system node)
    show = re.compile(
        r'Device Slave Address\s+:\s+%sh(.*?)Channel Number\s+:\s+\d+'
        % address.replace('0x', '').upper(),
        re.DOTALL)
    res = show.search(output)
    return res.group(0).split()[-1]


def get_ipmi_ip_address(local_address):
    output = commands.getoutput(
        'ipmitool -B 0 -T 0x20 -b 0 -t 0x20 -m %s lan print 2' % local_address)
    show_re = re.compile('IP Address\s+:\s+([0-9]{1,3}[.]?){4}')
    res = show_re.search(output)
    return res.group().split()[-1]


def get_maas_power_settings(user, password, ipaddress, hwaddress):
    return "%s,%s,%s,%s" % (user, password, ipaddress, hwaddress)


def get_maas_power_settings_json(user, password, ipaddress, hwaddress):
    power_params = {
        "power_address": ipaddress,
        "power_pass": password,
        "power_user": user,
        "power_hwaddress": hwaddress,
    }
    return json.dumps(power_params)


def main():
    parser = argparse.ArgumentParser(
        description='send config file to modify IPMI settings with')
    parser.add_argument(
        "--commission-creds", action="store_true", dest="commission_creds",
        help="Create IPMI temporary credentials", default=False)

    args = parser.parse_args()

    local_address = get_local_address()
    node_address = get_cartridge_address(local_address)

    # Obtaining channel numbers:
    output = commands.getoutput(
        'ipmitool -b 0 -t 0x20 -m %s sdr list mcloc -v' % local_address)

    local_chan = get_channel_number(local_address, output)
    cartridge_chan = get_channel_number(node_address, output)

    # ipmitool -I lanplus -H 10.16.1.11 -U Administrator -P password -B 0
    #     -T 0x88 -b 7 -t 0x72 -m 0x20 power status
    IPMI_HW_ADDRESS = "-B %s -T %s -b %s -t %s -m 0x20" % (
        cartridge_chan,
        node_address,
        local_chan,
        local_address,
        )

    IPMI_IP_ADDRESS = get_ipmi_ip_address(local_address)

    if args.commission_creds:
        print(get_maas_power_settings_json(
            IPMI_MAAS_USER, IPMI_MAAS_PASSWORD, IPMI_IP_ADDRESS,
            IPMI_HW_ADDRESS))
    else:
        print(get_maas_power_settings(
            IPMI_MAAS_USER, IPMI_MAAS_PASSWORD, IPMI_IP_ADDRESS,
            IPMI_HW_ADDRESS))


if __name__ == '__main__':
    main()
