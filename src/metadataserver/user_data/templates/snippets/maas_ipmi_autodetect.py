#!/usr/bin/python3
#
# maas-ipmi-autodetect - autodetect and autoconfigure IPMI.
#
# Copyright (C) 2013-2016 Canonical
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

from collections import OrderedDict
import json
import os
import platform
import random
import re
import string
import subprocess
import time


class IPMIError(Exception):
    """An error related to IPMI."""


def run_command(command_args):
    """Run a command. Return output if successful or raise exception if not."""
    output = subprocess.check_output(command_args, stderr=subprocess.STDOUT)
    return output.decode("utf-8")


def bmc_get(key):
    """Fetch the output of a key via bmc-config checkout."""
    command = ("bmc-config", "--checkout", "--key-pair=%s" % key)
    output = run_command(command)
    return output


def bmc_set(key, value):
    """Set the value of a key via bmc-config commit."""
    command = ("bmc-config", "--commit", "--key-pair=%s=%s" % (key, value))
    run_command(command)


def format_user_key(user_number, parameter):
    """Format a user key string."""
    return "%s:%s" % (user_number, parameter)


def bmc_user_get(user_number, parameter):
    """Get a user parameter via bmc-config commit."""
    key = format_user_key(user_number, parameter)
    raw = bmc_get(key)
    pattern = r"^\s*%s(?:[ \t])+([^#\s]+[^\n]*)$" % (re.escape(parameter))
    match = re.search(pattern, raw, re.MULTILINE)
    if match is None:
        return None
    return match.group(1)


def bmc_user_set(user_number, parameter, value):
    """Set a user parameter via bmc-config commit."""
    key = format_user_key(user_number, parameter)
    bmc_set(key, value)


def bmc_list_sections():
    """Retrieve the names of config sections from the BMC."""
    command = ("bmc-config", "-L")
    output = run_command(command)
    return output


def list_user_numbers():
    """List the user numbers on the BMC."""
    output = bmc_list_sections()
    pattern = r"^(User\d+)$"
    users = re.findall(pattern, output, re.MULTILINE)

    return users


def pick_user_number_from_list(search_username, user_numbers):
    """Pick the best user number for a user from a list of user numbers.

    If any any existing user's username matches the search username, pick
    that user.

    Otherwise, pick the first user that has no username set.

    If no users match those criteria, raise an IPMIError.
    """
    first_unused = None

    for user_number in user_numbers:
        # The IPMI spec reserves User1 as anonymous.
        if user_number == "User1":
            continue

        username = bmc_user_get(user_number, "Username")

        if username == search_username:
            return user_number

        # Usually a BMC won't include a Username value if the user is unused.
        # Some HP BMCs use "(Empty User)" to indicate a user in unused.
        if username in [None, "(Empty User)"] and first_unused is None:
            first_unused = user_number

    return first_unused


def pick_user_number(search_username):
    """Pick the best user number for a username."""
    user_numbers = list_user_numbers()
    user_number = pick_user_number_from_list(search_username, user_numbers)

    if not user_number:
        raise IPMIError("No IPMI user slots available.")

    return user_number


def is_ipmi_dhcp():
    output = bmc_get("Lan_Conf:IP_Address_Source")
    show_re = re.compile(r"IP_Address_Source\s+Use_DHCP")
    return show_re.search(output) is not None


def set_ipmi_network_source(source):
    bmc_set("Lan_Conf:IP_Address_Source", source)


def _bmc_get_ipmi_addresses(address_type):
    try:
        return bmc_get(address_type)
    except subprocess.CalledProcessError:
        return ""


def get_ipmi_ip_address():
    show_re = re.compile(
        r"((?:[0-9]{1,3}\.){3}[0-9]{1,3}|[0-9a-fA-F]*:[0-9a-fA-F:.]+)"
    )
    for address_type in [
        "Lan_Conf:IP_Address",
        "Lan6_Conf:IPv6_Static_Addresses",
        "Lan6_Conf:IPv6_Dynamic_Addresses",
    ]:
        output = _bmc_get_ipmi_addresses(address_type)
        # Loop through the addreses by preference: IPv4, static IPv6, dynamic
        # IPv6.  Return the first valid, non-link-local address we find.
        # While we could conceivably allow link-local addresses, we would need
        # to devine which of our interfaces is the correct link, and then we
        # would need support for link-local addresses in freeipmi-tools.
        res = show_re.findall(output)
        for ip in res:
            if ip.lower().startswith("fe80::") or ip == "0.0.0.0":
                time.sleep(2)
                continue
            if address_type.startswith("Lan6_"):
                return "[%s]" % ip
            return ip
    # No valid IP address was found.
    return None


def verify_ipmi_user_settings(user_number, user_settings):
    """Verify user settings were applied correctly."""

    bad_values = {}

    for key, expected_value in user_settings.items():
        # Password isn't included in checkout. Plus,
        # some older BMCs may not support Enable_User.
        if key not in ["Enable_User", "Password"]:
            value = bmc_user_get(user_number, key)
            if value != expected_value:
                bad_values[key] = value

    if len(bad_values) == 0:
        return

    errors_string = " ".join(
        [
            "for '%s', expected '%s', actual '%s';"
            % (key, user_settings[key], actual_value)
            for key, actual_value in bad_values.items()
        ]
    ).rstrip(";")
    message = "IPMI user setting verification failures: %s." % errors_string
    raise IPMIError(message)


def apply_ipmi_user_settings(user_settings):
    """Commit and verify IPMI user settings."""
    username = user_settings["Username"]
    ipmi_user_number = pick_user_number(username)

    for key, value in user_settings.items():
        bmc_user_set(ipmi_user_number, key, value)

    verify_ipmi_user_settings(ipmi_user_number, user_settings)


def make_ipmi_user_settings(username, password):
    """Factory for IPMI user settings."""
    # Some BMCs care about the order these settings are applied in.
    #
    # - Dell Poweredge R420 Systems require the username and password to
    # be set prior to the user being enabled.
    #
    # - Supermicro systems require the LAN Privilege Limit to be set
    # prior to enabling LAN IPMI msgs for the user.
    user_settings = OrderedDict(
        (
            ("Username", username),
            ("Password", password),
            ("Enable_User", "Yes"),
            ("Lan_Privilege_Limit", "Administrator"),
            ("Lan_Enable_IPMI_Msgs", "Yes"),
        )
    )
    return user_settings


def configure_ipmi_user(username):
    """Create or configure an IPMI user for remote use."""
    for password in [
        generate_random_password(),
        generate_random_password(with_special_chars=True),
    ]:
        user_settings = make_ipmi_user_settings(username, password)
        try:
            apply_ipmi_user_settings(user_settings)
            return password
        except subprocess.CalledProcessError:
            pass
    raise IPMIError("Unable to set BMC password.")


def set_ipmi_lan_channel_settings():
    """Enable IPMI-over-Lan (Lan_Channel) if it is disabled"""
    for mode in [
        "Lan_Channel:Volatile_Access_Mode",
        "Lan_Channel:Non_Volatile_Access_Mode",
    ]:
        output = bmc_get(mode)
        show_re = re.compile(r"%s\s+Always_Available" % mode.split(":")[1])
        if show_re.search(output) is None:
            # Some BMC's don't support setting Lan_Channel (see LP: #1287274).
            # If that happens, it would cause the script to fail preventing
            # the script from continuing. To address this, simply catch the
            # error, return and allow the script to continue.
            try:
                bmc_set(mode, "Always_Available")
            except subprocess.CalledProcessError:
                return


def commit_ipmi_settings(config):
    run_command(("bmc-config", "--commit", "--filename", config))


def get_maas_power_settings(user, password, ipaddress, version, boot_type):
    return "%s,%s,%s,%s,%s" % (user, password, ipaddress, version, boot_type)


def get_maas_power_settings_json(
    user, password, ipaddress, version, boot_type
):
    power_params = {
        "power_address": ipaddress,
        "power_pass": password,
        "power_user": user,
        "power_driver": version,
        "power_boot_type": boot_type,
    }
    return json.dumps(power_params)


def generate_random_password(
    min_length=10, max_length=15, with_special_chars=False
):
    length = random.randint(min_length, max_length)
    special_chars = "!\"#$%&'()*+-./:;<=>?@[\\]^_`{|}~"
    letters = ""
    if with_special_chars:
        # LP: #1621175 - Password generation for non-compliant IPMI password
        # policy. Huawei has implemented a different password policy that
        # does not confirm with the IPMI spec, hence we generate a password
        # that would be compliant to their use case.
        # Randomly select 2 Upper Case
        letters += "".join(
            [random.choice(string.ascii_uppercase) for _ in range(2)]
        )
        # Randomly select 2 Lower Case
        letters += "".join(
            [random.choice(string.ascii_lowercase) for _ in range(2)]
        )
        # Randomly select 2 numbers
        letters += "".join([random.choice(string.digits) for _ in range(2)])
        # Randomly select a special character
        letters += random.choice(special_chars)
        # Create the extra characters to fullfill max_length
        letters += "".join(
            [random.choice(string.ascii_letters) for _ in range(length - 7)]
        )
        # LP: #1758760 - Randomly mix the password until we ensure there's
        # not consecutive occurrences of the same character.
        password = "".join(random.sample(letters, len(letters)))
        while bool(re.search(r"(.)\1", password)):
            password = "".join(random.sample(letters, len(letters)))
        return password
    else:
        letters = string.ascii_letters + string.digits
        return "".join([random.choice(letters) for _ in range(length)])


def bmc_supports_lan2_0():
    """Detect if BMC supports LAN 2.0."""
    output = run_command("ipmi-locate")
    if "IPMI Version: 2.0" in output or platform.machine() == "ppc64le":
        return True
    return False


def get_system_boot_type():
    """Detect if the system has boot EFI."""
    if os.path.isdir("/sys/firmware/efi"):
        return "efi"
    return "auto"


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="send config file to modify IPMI settings with"
    )
    parser.add_argument(
        "--configdir",
        metavar="folder",
        help="specify config file directory",
        default=None,
    )
    parser.add_argument(
        "--dhcp-if-static",
        action="store_true",
        dest="dhcp",
        help="set network source to DHCP if Static",
        default=False,
    )
    parser.add_argument(
        "--commission-creds",
        action="store_true",
        dest="commission_creds",
        help="Create IPMI temporary credentials",
        default=False,
    )

    args = parser.parse_args()

    # Check whether IPMI is being set to DHCP. If it is not, and
    # '--dhcp-if-static' has been passed,  Set it to IPMI to DHCP.
    if not is_ipmi_dhcp() and args.dhcp:
        set_ipmi_network_source("Use_DHCP")
        # allow IPMI 120 seconds to obtain an IP address
        time.sleep(120)

    # create user/pass
    IPMI_MAAS_USER = "maas"
    IPMI_MAAS_PASSWORD = None

    IPMI_MAAS_PASSWORD = configure_ipmi_user(IPMI_MAAS_USER)

    # Attempt to enable IPMI Over Lan. If it is disabled, MAAS won't
    # be able to remotely communicate to the BMC.
    set_ipmi_lan_channel_settings()

    # Commit other IPMI settings
    if args.configdir:
        for file in os.listdir(args.configdir):
            commit_ipmi_settings(os.path.join(args.configdir, file))

    # get the IP address
    IPMI_IP_ADDRESS = get_ipmi_ip_address()
    if IPMI_IP_ADDRESS is None:
        # if IPMI_IP_ADDRESS not set (or reserved), wait 60 seconds and retry.
        set_ipmi_network_source("Static")
        time.sleep(2)
        set_ipmi_network_source("Use_DHCP")
        time.sleep(60)
        IPMI_IP_ADDRESS = get_ipmi_ip_address()

    if IPMI_IP_ADDRESS is None:
        # Exit (to not set power params in MAAS) if no IPMI_IP_ADDRESS
        # has been detected
        exit(1)

    if bmc_supports_lan2_0():
        IPMI_VERSION = "LAN_2_0"
    else:
        IPMI_VERSION = "LAN"

    IPMI_BOOT_TYPE = get_system_boot_type()

    if args.commission_creds:
        print(
            get_maas_power_settings_json(
                IPMI_MAAS_USER,
                IPMI_MAAS_PASSWORD,
                IPMI_IP_ADDRESS,
                IPMI_VERSION,
                IPMI_BOOT_TYPE,
            )
        )
    else:
        print(
            get_maas_power_settings(
                IPMI_MAAS_USER,
                IPMI_MAAS_PASSWORD,
                IPMI_IP_ADDRESS,
                IPMI_VERSION,
                IPMI_BOOT_TYPE,
            )
        )


if __name__ == "__main__":
    main()
