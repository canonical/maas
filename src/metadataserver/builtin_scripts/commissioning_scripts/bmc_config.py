#!/usr/bin/env python3
#
# bmc-config - Detect and configure BMC's for MAAS use.
#
# Author: Andres Rodriguez <andres.rodriguez@canonical.com>
#         Lee Trager <lee.trager@canonical.com>
#
# Copyright (C) 2013-2021 Canonical
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# --- Start MAAS 1.0 script metadata ---
# name: 30-maas-01-bmc-config
# title: Detect and configure BMC's for MAAS use.
# description: Detect and configure BMC credentials for MAAS use.
# tags: bmc-config
# script_type: commissioning
# parameters:
#   maas_auto_ipmi_user:
#     type: string
#     max: 20
#     argument_format: --username={input}
#   maas_auto_ipmi_user_password:
#     type: password
#     max: 20
#     argument_format: --password={input}
#   maas_auto_ipmi_k_g_bmc_key:
#     type: password
#     max: 20
#     argument_format: --ipmi-k-g={input}
#   maas_auto_ipmi_user_privilege_level:
#     type: choice
#     choices:
#       - [USER, User]
#       - [OPERATOR, Operator]
#       - [ADMIN, Administrator]
#     argument_format: --ipmi-privilege-level={input}
#   maas_auto_ipmi_cipher_suite_id:
#     type: string
#     max: 2
#     argument_format: --ipmi-cipher-suite-id={input}
# packages:
#   apt:
#     - freeipmi-tools
#     - ipmitool
#     - python3-paramiko
# timeout: 00:05:00
# --- End MAAS 1.0 script metadata --

from abc import ABCMeta, abstractmethod, abstractproperty
import argparse
from collections import OrderedDict
from functools import lru_cache
import glob
import ipaddress
import json
import os
from os.path import basename
import platform
import random
import re
from shutil import which
import ssl
import string
from subprocess import (
    CalledProcessError,
    check_call,
    check_output,
    DEVNULL,
    PIPE,
    run,
    TimeoutExpired,
)
import sys
import time
import traceback
import urllib
import urllib.request

from paramiko.client import MissingHostKeyPolicy, SSHClient
import yaml

# Most commands execute very quickly. A timeout is used to catch commands which
# hang. Sometimes a hanging command can be handled, othertimes not. 3 minutes
# is used as the timeout as some BMCs respond slowly when a large amount of
# data is being returned. LP:1917652 was due to a slow responding BMC which
# timed out when IPMI._bmc_get_config() was called.
COMMAND_TIMEOUT = 60 * 3


def exit_skipped():
    """Write a result YAML indicating the test has been skipped."""
    result_path = os.environ.get("RESULT_PATH")
    if result_path is not None:
        with open(result_path, "w") as results_file:
            yaml.safe_dump({"status": "skipped"}, results_file)
    sys.exit()


class BMCConfig(metaclass=ABCMeta):
    """Base class for BMC detection."""

    username = None
    password = None

    def __init__(self, *args, **kwargs):
        pass

    @abstractmethod
    def __str__(self):
        """The pretty name of the BMC type."""

    @abstractproperty
    def power_type(self):
        """The power_type of the BMC."""

    @abstractmethod
    def detected(self):
        """Returns boolean value of whether the BMC was detected."""

    def add_bmc_user(self):
        """Add the specified BMC user and (re)set its password.

        Should set the username and password, even if it hasn't been
        changed.
        """
        # MAAS is the default user and will always be passed to the script.
        if self.username not in (None, "maas"):
            print(
                "WARNING: Unable to set a specific username or password on %s!"
                % self
            )

    def configure(self):
        """Configure the BMC for use."""
        pass

    @abstractmethod
    def get_bmc_ip(self):
        """Return the IP address of the BMC."""

    def get_credentials(self):
        """Return the BMC credentials for MAAS to use the BMC."""
        return {
            "power_address": self.get_bmc_ip(),
            "power_user": self.username if self.username else "",
            "power_pass": self.password if self.password else "",
        }


class IPMIBase(BMCConfig):
    def _pick_user_number(self, search_username):
        """Pick the best user number for a user from a list of user numbers.

        If any any existing user's username matches the search username, pick
        that user.

        Otherwise, pick the first user that has no username set.
        """
        first_unused = None
        for section_name, section in self._bmc_config.items():
            if not section_name.startswith("User"):
                continue
            # The IPMI spec reserves User1 as anonymous.
            if section_name == "User1":
                continue

            if search_username and search_username == section.get("Username"):
                print('INFO: Found existing IPMI user "%s"!' % search_username)
                return section_name
            elif (
                not section.get("Username")
                or section.get("Username") == "(Empty User)"
            ) and first_unused is None:
                # Usually a BMC won't include a Username value if the user is
                # unused. Some HP BMCs use "(Empty User)" to indicate a user in
                # unused.
                first_unused = section_name
        return first_unused

    def add_bmc_user(self):
        if not self.username:
            self.username = "maas"
        user_number = self._pick_user_number(self.username)
        print('INFO: Configuring IPMI BMC user "%s"...' % self.username)
        print("INFO: IPMI user number - %s" % user_number)
        print("INFO: IPMI user privilege level - %s" % self._get_ipmi_priv())
        if not self.password:
            passwords = [
                self._generate_random_password(),
                # Some BMC require a longer password https://bugs.launchpad.net/maas/+bug/1993916/
                self._generate_random_password(min_length=16, max_length=20),
                self._generate_random_password(with_special_chars=True),
            ]
        else:
            passwords = [self.password]
        for password in passwords:
            try:
                for key, value in self._make_ipmi_user_settings(
                    self.username, password
                ).items():
                    if self._bmc_config[user_number].get(key) != value:
                        self._bmc_set(user_number, key, value)
            except Exception:
                pass
            else:
                self.password = password
                # Not all user settings are available on all BMC keys, its
                # okay if these fail to be set.
                self._bmc_set_keys(
                    user_number,
                    [
                        "Lan_Enable_Link_Auth",
                        "SOL_Payload_Access",
                        "Serial_Enable_Link_Auth",
                    ],
                    "Yes",
                )
                return
        print("ERROR: Unable to add BMC user!", file=sys.stderr)
        sys.exit(1)

    def _bmc_get_config(self, section=None):
        """Fetch and cache all BMC settings."""
        print("INFO: Reading current IPMI BMC values...")
        cmd = ["bmc-config", "--checkout", "--verbose"]
        if section:
            cmd += ["-S", section]
        try:
            proc = run(
                cmd,
                stdout=PIPE,
                timeout=COMMAND_TIMEOUT,
            )
        except Exception:
            print(
                "ERROR: Unable to get all current IPMI settings!",
                file=sys.stderr,
            )
            raise
        section = None
        for line in proc.stdout.decode(errors="surrogateescape").splitlines():
            line = line.split("#")[0].strip()
            if not line:
                continue
            key_value = line.split(maxsplit=1)
            if section is None and key_value[0] == "Section":
                section = {}
                self._bmc_config[key_value[1]] = section
            elif key_value[0] == "EndSection":
                section = None
            elif section is not None:
                if len(key_value) == 2:
                    section[key_value[0]] = key_value[1]
                else:
                    section[key_value[0]] = ""
            else:
                if len(key_value) == 2:
                    self._bmc_config[key_value[0]] = key_value[1]
                else:
                    self._bmc_config[key_value[0]] = ""

    def _bmc_set(self, section, key, value):
        """Set the value of a key via bmc-config commit.

        Exceptions are not caught so a commit failure causes a script failure.
        """
        check_call(
            [
                "bmc-config",
                "--commit",
                f"--key-pair={section}:{key}={value}",
            ],
            timeout=COMMAND_TIMEOUT,
        )
        # If the value was set update the cache.
        if section not in self._bmc_config:
            self._bmc_config[section] = {}
        self._bmc_config[section][key] = value

    def _bmc_set_keys(self, section, keys, value):
        """Set a section of keys to one value."""
        if section not in self._bmc_config:
            # Some sections aren't available to all BMCs
            print("INFO: %s settings unavailable!" % section)
            return
        for key in keys:
            # Some keys aren't available on all BMCs, only set ones which
            # are available.
            if (
                key in self._bmc_config[section]
                and self._bmc_config[section][key] != value
            ):
                try:
                    self._bmc_set(section, key, value)
                except (CalledProcessError, TimeoutExpired):
                    print(
                        "WARNING: Unable to set %s:%s to %s!"
                        % (section, key, value)
                    )

    def _generate_random_password(
        self, min_length=10, max_length=15, with_special_chars=False
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
            letters += "".join(
                [random.choice(string.digits) for _ in range(2)]
            )
            # Randomly select a special character
            letters += random.choice(special_chars)
            # Create the extra characters to fullfill max_length
            letters += "".join(
                [
                    random.choice(string.ascii_letters)
                    for _ in range(length - 7)
                ]
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

    def _get_ipmi_priv(self):
        """Map ipmitool name to IPMI spec name

        freeipmi-tools and the IPMI protocol use different names for privilege
        levels. MAAS stores the IPMI privilege level using the freeipmi-tools
        form as it interacts with ipmipower frequently.
        """
        return {
            "USER": "User",
            "OPERATOR": "Operator",
            "ADMIN": "Administrator",
        }.get(self._privilege_level, "Administrator")

    def _make_ipmi_user_settings(self, username, password):
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
                ("Lan_Privilege_Limit", self._get_ipmi_priv()),
                ("Lan_Enable_IPMI_Msgs", "Yes"),
            )
        )
        return user_settings

    def _check_ciphers_enabled(self):
        rmcpp_section = "Rmcpplus_Conf_Privilege"

        if (
            rmcpp_section not in self._bmc_config
            or len(self._bmc_config[rmcpp_section]) == 0
        ):
            # RMCP+ not supported, IPMI < 2.0
            return True

        return "Administrator" in self._bmc_config[rmcpp_section].values()

    def _config_ipmi_lan_channel_settings(self):
        """Enable IPMI-over-Lan (Lan_Channel) if it is disabled"""
        print("INFO: Configuring IPMI Lan_Channel...")

        for channel in [
            "Lan_Channel",
            "Lan_Channel_Channel_1",
            "Lan_Channel_Channel_2",
            "Lan_Channel_Channel_3",
        ]:
            lan_channel = self._bmc_config.get(channel, {})

            if not lan_channel:
                continue

            for key in [
                "Volatile_Access_Mode",
                "Non_Volatile_Access_Mode",
            ]:
                if lan_channel.get(key) != "Always_Available":
                    print(
                        "INFO: Enabling BMC network access - %s:%s"
                        % (channel, key)
                    )
                    # Some BMC's don't support setting Lan_Channel (see LP: #1287274).
                    # If that happens, it would cause the script to fail preventing
                    # the script from continuing. To address this, simply catch the
                    # error, return and allow the script to continue.
                    try:
                        self._bmc_set(channel, key, "Always_Available")
                    except Exception:
                        print(
                            "WARNING: Unable to set %s:%s. "
                            "BMC may be unavailable over the network!"
                            % (channel, key)
                        )

            self._bmc_set_keys(
                channel,
                [
                    f"{auth_type}_{volatility}"
                    for auth_type in [
                        "Enable_User_Level_Auth",
                        "Enable_Per_Message_Auth",
                        "Enable_Pef_Alerting",
                    ]
                    for volatility in ["Volatile", "Non_Volatile"]
                ],
                "Yes",
            )

    def _config_lan_conf_auth(self):
        """Configure Lan_Conf_Auth."""
        print("INFO: Configuring IPMI Lan_Channel_Auth...")
        if "Lan_Channel_Auth" not in self._bmc_config:
            print("INFO: Lan_Channel_Auth settings unavailable!")
            return

        self._bmc_set_keys(
            "Lan_Channel_Auth",
            [
                f"{user}_Enable_Auth_Type_{enc_type}"
                for user in [
                    "Callback",
                    "User",
                    "Admin",
                    "OEM",
                ]
                for enc_type in [
                    "None",
                    "MD2",
                    "OEM_Proprietary",
                ]
            ],
            "No",
        )
        self._bmc_set_keys("Lan_Channel_Auth", ["SOL_Payload_Access"], "Yes")

    def _config_kg(self):
        if self._kg:
            if self._kg != self._bmc_config.get(
                "Lan_Conf_Security_Keys", {}
            ).get("K_G"):
                print("INFO: Setting user given IPMI K_g BMC key...")
                try:
                    self._bmc_set("Lan_Conf_Security_Keys", "K_G", self._kg)
                except (CalledProcessError, TimeoutExpired):
                    print(
                        "ERROR: Unable to set usergiven BMC key on device!",
                        file=sys.stderr,
                    )
                    # If the kg failed to be set don't return a kg to MAAS.
                    self._kg = ""
                    # If the user passes a BMC key and its unable to be set fail
                    # the script as the system can't be secured as requested. Raise
                    # the exception to help with debug but this is most likely a
                    # BMC firmware issue.
                    raise
        elif "Lan_Conf_Security_Keys" in self._bmc_config:
            # Check if the IPMI K_g BMC key was already set and capture it.
            kg = self._bmc_config["Lan_Conf_Security_Keys"].get("K_G")
            if kg and not re.search("^0x0+$", kg):
                print("INFO: Found existing K_g BMC key!")
                self._kg = kg
        if not self._kg:
            print(
                "WARNING: No K_g BMC key found or configured, "
                "communication with BMC will not use a session key!"
            )


class IPMI(IPMIBase):
    """Handle detection and configuration of IPMI BMCs."""

    power_type = "ipmi"

    def __init__(
        self,
        username=None,
        password=None,
        ipmi_k_g="",
        ipmi_privilege_level="",
        ipmi_cipher_suite_id="3",
        **kwargs,
    ):
        self.username = username
        self.password = password
        self._kg = ipmi_k_g
        self._cipher_suite_id = ipmi_cipher_suite_id
        self._privilege_level = ipmi_privilege_level
        self._bmc_config = {}

    def __str__(self):
        return "IPMI"

    def detected(self):
        # Verify the BMC uses IPMI.
        try:
            output = _get_ipmi_locate_output()
        except Exception:
            return False
        else:
            m = re.search(r"(IPMI\ Version:) (\d\.\d)", output)
            # ipmi-locate always returns 0. If The regex doesn't match
            # check if /dev/ipmi[0-9] exists. This is needed on the PPC64
            # host in the MAAS CI.
            if m or len(glob.glob("/dev/ipmi[0-9]")):
                return True
            else:
                return False

    def configure(self):
        self._bmc_get_config()
        # Configure IPMI settings as suggested in http://fish2.com/ipmi/bp.pdf
        # None of these settings should effect current environments. Settings
        # can be overriden with a custom commissioning script which runs after
        # this one.

        if not self._check_ciphers_enabled():
            # We can't detect any suitable cipher. We still continue,
            # since we don't trust that the BMC reports all the
            # ciphers that actually are usable.
            print("WARNING: No cipher enabled!", file=sys.stderr)

        self._config_ipmi_lan_channel_settings()
        self._config_lan_conf_auth()
        self._config_kg()

        print("INFO: Configuring IPMI Serial_Channel...")
        self._bmc_set_keys(
            "Serial_Channel",
            [
                f"{auth_type}_{volatility}"
                for auth_type in [
                    "Enable_User_Level_Auth",
                    "Enable_Per_Message_Auth",
                    "Enable_Pef_Alerting",
                ]
                for volatility in ["Volatile", "Non_Volatile"]
            ],
            "Yes",
        )
        print("INFO: Configuring IPMI SOL_Conf...")
        self._bmc_set_keys(
            "SOL_Conf",
            [
                "Force_SOL_Payload_Authentication",
                "Force_SOL_Payload_Encryption",
            ],
            "Yes",
        )

    def _get_bmc_ip(self, invalidate_cache=False):
        """Return the current IP of the BMC, returns none if unavailable."""
        show_re = re.compile(
            r"((?:[0-9]{1,3}\.){3}[0-9]{1,3}|[0-9a-fA-F]*:[0-9a-fA-F:.]+)"
        )
        # The MAC Address may only appear in Lan_Conf(IPv4) even when IPv6
        # is in use.
        mac_address = None
        for section_name, key in [
            ("Lan_Conf", "IP_Address"),
            ("Lan_Conf_Channel_1", "IP_Address"),
            ("Lan_Conf_Channel_2", "IP_Address"),
            ("Lan_Conf_Channel_3", "IP_Address"),
            ("Lan6_Conf", "IPv6_Static_Addresses"),
            ("Lan6_Conf", "IPv6_Dynamic_Addresses"),
        ]:
            if invalidate_cache:
                self._bmc_get_config(section_name)
            try:
                section = self._bmc_config[section_name]
                mac_address = section.get("MAC_Address", mac_address)
                value = section[key]
            except KeyError:
                continue
            # Loop through the addreses by preference: IPv4, static IPv6, dynamic
            # IPv6.  Return the first valid, non-link-local address we find.
            # While we could conceivably allow link-local addresses, we would need
            # to devine which of our interfaces is the correct link, and then we
            # would need support for link-local addresses in freeipmi-tools.
            res = show_re.findall(value)
            for ip in res:
                if ip.lower().startswith("fe80::") or ip == "0.0.0.0":
                    time.sleep(2)
                    continue
                if section_name.startswith("Lan6_"):
                    return section_name, "[%s]" % ip, mac_address
                return section_name, ip, mac_address
            # No valid IP address was found.
        return None, None, mac_address

    def get_bmc_ip(self):
        """Configure and retreive IPMI BMC IP."""
        section_name, ip_address, mac_address = self._get_bmc_ip()
        if ip_address:
            return ip_address, mac_address
        print("INFO: Attempting to enable preconfigured static IP on BMC...")
        self._bmc_set(section_name, "IP_Address_Source", "Static")
        for _ in range(6):
            time.sleep(10)
            _, ip_address, mac_address = self._get_bmc_ip(True)
            if ip_address:
                return ip_address, mac_address
        print("INFO: Attempting to enable DHCP on BMC...")
        self._bmc_set(section_name, "IP_Address_Source", "Use_DHCP")
        for _ in range(6):
            time.sleep(10)
            _, ip_address, mac_address = self._get_bmc_ip(True)
            if ip_address:
                print("WARNING: BMC is configured to use DHCP!")
                return ip_address, mac_address
        print("ERROR: Unable to determine BMC IP address!", file=sys.stderr)
        sys.exit(1)

    def get_credentials(self):
        """Return the BMC credentials to use the BMC."""
        if (
            "IPMI Version: 2.0" in _get_ipmi_locate_output()
            or platform.machine() == "ppc64le"
        ):
            ipmi_version = "LAN_2_0"
        else:
            ipmi_version = "LAN"
        print("INFO: IPMI Version - %s" % ipmi_version)
        if os.path.isdir("/sys/firmware/efi"):
            boot_type = "efi"
        else:
            boot_type = "auto"
        print("INFO: IPMI boot type - %s" % boot_type)
        ip_address, mac_address = self.get_bmc_ip()
        return {
            "power_address": ip_address,
            "power_user": self.username,
            "power_pass": self.password,
            "power_driver": ipmi_version,
            "power_boot_type": boot_type,
            "k_g": self._kg,
            "cipher_suite_id": self._cipher_suite_id,
            "privilege_level": self._privilege_level,
            "mac_address": mac_address,
        }


# Moonshot may be able to use more of IPMI functionality however these
# features aren't enabled due to a lack of a test host.
class HPMoonshot(BMCConfig):
    """Handle detection and configuration of HP Moonshot BMCs."""

    power_type = "moonshot"
    username = "Administrator"
    password = "password"

    def __str__(self):
        return "HP Moonshot"

    def detected(self):
        try:
            output = check_output(
                ["ipmitool", "raw", "06", "01"],
                timeout=COMMAND_TIMEOUT,
                stderr=DEVNULL,
            ).decode()
        except Exception:
            return False
        # 14 is the code that identifies the BMC as HP Moonshot
        if output.split()[0] == "14":
            return True
        else:
            return False

    def _get_local_address(self):
        output = check_output(
            ["ipmitool", "raw", "0x2c", "1", "0"], timeout=COMMAND_TIMEOUT
        ).decode()
        return "0x%s" % output.split()[2]

    def _get_cartridge_address(self, local_address):
        # obtain address of Cartridge Controller (parent of the system node):
        output = check_output(
            [
                "ipmitool",
                "-t",
                "0x20",
                "-b",
                ",0" "-m",
                local_address,
                "raw",
                "0x2c",
                "1",
                "0",
            ],
            timeout=COMMAND_TIMEOUT,
        ).decode()
        return "0x%s" % output.split()[2]

    def _get_channel_number(self, address, output):
        m = re.search(
            r"Device Slave Address\s+:\s+%sh(.*?)Channel Number\s+:\s+\d+"
            % address.replace("0x", "").upper(),
            output,
            re.DOTALL,
        )
        return m.group(0).split()[-1]

    def get_bmc_ip(self, local_address=None):
        if not local_address:
            local_address = self._get_local_address()
        output = check_output(
            [
                "ipmitool",
                "-B",
                "0",
                "-T",
                "0x20",
                "-b",
                "0",
                "-t",
                "0x20",
                "-m",
                local_address,
                "lan",
                "print",
                "2",
            ],
            timeout=COMMAND_TIMEOUT,
        ).decode()
        m = re.search(
            r"IP Address\s+:\s+"
            r"(?P<addr>(?:[0-9]{1,3}\.){3}[0-9]{1,3}|[0-9a-fA-F]*:[0-9a-fA-F:.]+)",
            output,
        )
        if not m:
            return None
        return m.groupdict().get("addr", None)

    def get_credentials(self):
        local_address = self._get_local_address()
        node_address = self._get_cartridge_address(local_address)

        # Obtain channel numbers for routing to this system
        output = check_output(
            [
                "ipmitool",
                "-b",
                "0",
                "-t",
                "0x20",
                "-m",
                local_address,
                "sdr",
                "list",
                "mcloc",
                "-v",
            ],
            timeout=COMMAND_TIMEOUT,
        ).decode()
        local_chan = self._get_channel_number(local_address, output)
        cartridge_chan = self._get_channel_number(node_address, output)

        return {
            "power_address": self.get_bmc_ip(local_address),
            "power_user": self.username,
            "power_pass": self.password,
            "power_hwaddress": (
                "-B %s -T %s -b %s -t %s -m 0x20"
                % (
                    cartridge_chan,
                    node_address,
                    local_chan,
                    local_address,
                )
            ),
        }


class IgnoreHostKeyPolicy(MissingHostKeyPolicy):
    def missing_host_key(self, *args, **kwargs):
        return


# Facebook Wedge devices are really OpenBMC. More devices may work with this
# method but none are available to test with.
class Wedge(BMCConfig):
    """Handle detection and configure of Facebook Wedge device."""

    power_type = "wedge"
    username = "root"
    password = "0penBmc"

    _bmc_ip = None

    def __str__(self):
        return "Facebook Wedge"

    def _detect_known_switch(self):
        if which("dmidecode") is None:
            raise ConfigurationError("Missing 'dmidecode' binary")

        # This is based of https://github.com/lool/sonic-snap/blob/master/common/id-switch
        # try System Information > Manufacturer first
        # XXX ltrager 2020-09-16 - It would be better to get these values from
        # /sys but no test system is available.
        sys_manufacturer = check_output(
            ["dmidecode", "-s", "system-manufacturer"], timeout=COMMAND_TIMEOUT
        ).decode()
        prod_name = check_output(
            ["dmidecode", "-s", "system-product-name"], timeout=COMMAND_TIMEOUT
        ).decode()
        baseboard_prod_name = check_output(
            ["dmidecode", "-s", "baseboard-product-name"],
            timeout=COMMAND_TIMEOUT,
        ).decode()
        if (
            (sys_manufacturer == "Intel" and prod_name == "EPGSVR")
            or (
                sys_manufacturer == "Joytech"
                and prod_name == "Wedge-AC-F 20-001329"
            )
            or (
                sys_manufacturer == "To be filled by O.E.M."
                and baseboard_prod_name == "PCOM-B632VG-ECC-FB-ACCTON-D"
            )
        ):
            return "accton"
        return None

    def detected(self):
        # First detect this is a known switch
        try:
            switch_type = self._detect_known_switch()
        except (CalledProcessError, TimeoutExpired, FileNotFoundError):
            return False
        else:
            if switch_type is None:
                return False
        try:
            # Second, lets verify if this is a known endpoint
            # First try to hit the API. This would work on Wedge 100.
            response = urllib.request.urlopen(
                "http://[%s]:8080/api" % _get_wedge_local_addr()
            )
            if b"Wedge RESTful API Entry" in response.read():
                return True
        except Exception:
            pass
        if self.get_bmc_ip():
            # If the above failed, try to hit the SSH. This would work on Wedge 40.
            return True
        return False

    def get_bmc_ip(self):
        # cache the result of the IP discovery
        if self._bmc_ip is None:
            self._bmc_ip = self._get_bmc_ip()
        return self._bmc_ip

    def _get_bmc_ip(self):
        try:
            client = SSHClient()
            client.set_missing_host_key_policy(IgnoreHostKeyPolicy)
            client.connect(
                _get_wedge_local_addr(),
                username=self.username,
                password=self.password,
            )
            _, stdout, _ = client.exec_command(
                "ip -o -4 addr show", timeout=COMMAND_TIMEOUT
            )
            return (
                stdout.read().decode().splitlines()[1].split()[3].split("/")[0]
            )
        except Exception:
            return None


class ConfigurationError(Exception):
    """Thrown when there is a known configuration error"""


class Redfish(IPMIBase):
    """Handle detection and configuration of Redfish device."""

    power_type = "redfish"

    def __init__(
        self,
        username=None,
        password=None,
        ipmi_privilege_level="",
        **kwargs,
    ):
        self.username = username
        self.password = password
        self._privilege_level = ipmi_privilege_level
        self._bmc_config = {}

    _bmc_ip = None
    _manager_id = None
    _redfish_ip = None
    _redfish_port = None

    def __str__(self):
        return "Redfish"

    def _get_smbios_data(self):
        # SMBIOS Type 42 is a Redfish Host Interface
        # https://www.dmtf.org/sites/default/files/standards/documents/DSP0270_1.0.0.pdf

        # Handle 0x00D0, DMI type 42, 169 bytes
        # Management Controller Host Interface
        # 	Host Interface Type: Network
        # 	Device Type: USB
        # 	idVendor: 0x04b3
        # 	idProduct: 0x4010
        # 	Protocol ID: 04 (Redfish over IP)
        # 		Service UUID: a4b13f22-d0f3-11ea-aca9-e5b8d327f39f
        # 		Host IP Assignment Type: Static
        # 		Host IP Address Format: IPv4
        # 		IPv4 Address: 169.254.95.120
        # 		IPv4 Mask: 255.255.0.0
        # 		Redfish Service IP Discovery Type: Static
        # 		Redfish Service IP Address Format: IPv4
        # 		IPv4 Redfish Service Address: 169.254.95.118
        # 		IPv4 Redfish Service Mask: 255.255.0.0
        # 		Redfish Service Port: 443
        # 		Redfish Service Vlan: 0
        # 		Redfish Service Hostname: garamond

        if which("dmidecode") is None:
            raise ConfigurationError("Missing 'dmidecode' binary")

        smbios_data = check_output(
            ["dmidecode", "-t", "42"], timeout=COMMAND_TIMEOUT
        ).decode()

        splitted = smbios_data.split("\n\n")
        # skip first item, because it is a SMBIOS header text
        for entry in splitted[1:]:
            for key in (
                "Management Controller Host Interface\n",
                "Host Interface Type: Network\n",
            ):
                _, _, entry = entry.partition(key)

            if "Protocol ID: 04 (Redfish over IP)\n" in entry:
                return entry

    def _generate_netplan_config(self, iface, dhcp_enabled, addr=None):
        return yaml.safe_dump(
            {
                "network": {
                    "version": 2,
                    "ethernets": {
                        iface: {
                            "dhcp4": dhcp_enabled,
                            "addresses": [addr] if not dhcp_enabled else [],
                        }
                    },
                }
            }
        )

    def _configure_network(
        self, iface, data, config_path="/etc/netplan/99-redfish.yaml"
    ):
        # Host IP Assignment Type:
        #   Possible values: Unknown, Static, DHCP, AutoConfigure, HostSelected
        netplan_config = None
        assignment_type = get_smbios_value(data, "Host IP Assignment Type")
        if assignment_type in ("Unknown", "AutoConfigure", "HostSelected"):
            raise ConfigurationError("Unsupported Host IP Assignment Type")

        if assignment_type == "Static":
            ipv4_addr = get_smbios_value(data, "IPv4 Address")
            ipv4_mask = get_smbios_value(data, "IPv4 Mask")
            if not all((ipv4_addr, ipv4_mask)):
                raise ConfigurationError("Missing Host IPv4 information")

            prefix_length = ipaddress.IPv4Network((0, ipv4_mask)).prefixlen
            ipv4 = f"{ipv4_addr}/{prefix_length}"
            netplan_config = self._generate_netplan_config(iface, False, ipv4)

        if assignment_type == "DHCP":
            netplan_config = self._generate_netplan_config(iface, True)

        with open(config_path, "w") as netplan:
            netplan.write(netplan_config)

        # TODO: How to determine if netplan was applied?
        check_output(["netplan", "apply"], timeout=COMMAND_TIMEOUT).decode()

    def _detect(self):
        data = self._get_smbios_data()
        if data is None:
            raise ConfigurationError("Missing SMBIOS data")

        vendor_id = get_smbios_value(data, "idVendor")[2:]
        product_id = get_smbios_value(data, "idProduct")[2:]

        if not all((vendor_id, product_id)):
            raise ConfigurationError(
                "Missing idVendor and idProduct information"
            )

        iface = None
        with open(os.environ["MAAS_RESOURCES_FILE"]) as fd:
            machine_resources_data = json.load(fd)
            iface = get_network_interface(
                machine_resources_data, vendor_id, product_id
            )
            if iface is None:
                raise ConfigurationError("Missing Redfish Host Interface")

        self._configure_network(iface, data)

        self._bmc_get_config()
        self.add_bmc_user()

        self._redfish_ip = get_smbios_value(
            data, "IPv4 Redfish Service Address"
        )
        self._redfish_port = get_smbios_value(data, "Redfish Service Port")

        if not all((self._redfish_ip, self._redfish_port)):
            raise ConfigurationError("Missing Redfish Service information.")

    def detected(self):
        try:
            self._detect()
            return self.get_bmc_ip() is not None
        # XXX: we should know which exceptions to expect, so we can handle them
        except ConfigurationError as err:
            print(f"ERROR: Redfish configuration failed. {err}")
            return False

    def _get_manager_id(self):
        credentials = {
            "UserName": self.username,
            "Password": self.password,
        }

        url = f"https://{self._redfish_ip}:{self._redfish_port}/redfish/v1/SessionService/Sessions"
        req = urllib.request.Request(
            url,
            json.dumps(credentials).encode(),
            headers={"Content-Type": "application/json"},
        )
        response = urllib.request.urlopen(
            req, context=ssl._create_unverified_context()
        )
        if response.status not in [200, 201]:
            print(
                f"WARNING: Failed to get token. {response.status} {response.getheaders()} {response.read()}"
            )
            return

        token = response.getheader("X-Auth-Token")
        if token is None:
            print(
                f"WARNING: Missing X-Auth-Token header. {response.getheaders()}"
            )
            return

        url = f"https://{self._redfish_ip}:{self._redfish_port}/redfish/v1/Managers"
        req = urllib.request.Request(url)
        req.add_header("X-Auth-Token", token)
        response = urllib.request.urlopen(
            req, context=ssl._create_unverified_context()
        )
        if response.status != 200:
            print(
                f"WARNING: Failed to read Managers info. {response.status} {response.getheaders()} {response.read()}"
            )
            return

        response = json.loads(response.read().decode())
        managers = response.get("Members")
        if not managers or len(managers) == 0:
            print(
                f"WARNING: Missing Redfish Managers Collection. {response.read()}"
            )
            return
        manager = managers[0].get("@odata.id").rstrip("/")
        return basename(manager)

    def get_manager_id(self):
        if self._manager_id is None:
            self._manager_id = self._get_manager_id()
        return self._manager_id

    def _get_bmc_ip(self):
        credentials = {
            "UserName": self.username,
            "Password": self.password,
        }

        url = f"https://{self._redfish_ip}:{self._redfish_port}/redfish/v1/SessionService/Sessions"
        req = urllib.request.Request(
            url,
            json.dumps(credentials).encode(),
            headers={"Content-Type": "application/json"},
        )
        response = urllib.request.urlopen(
            req, context=ssl._create_unverified_context()
        )
        if response.status not in [200, 201]:
            print(
                f"WARNING: Failed to get token. {response.status} {response.getheaders()} {response.read()}"
            )
            return

        token = response.getheader("X-Auth-Token")
        if token is None:
            print(
                f"WARNING: Missing X-Auth-Token header. {response.getheaders()}"
            )
            return

        url = f"https://{self._redfish_ip}:{self._redfish_port}/redfish/v1/Managers/{self._manager_id}/EthernetInterfaces"
        req = urllib.request.Request(url)
        req.add_header("X-Auth-Token", token)
        response = urllib.request.urlopen(
            req, context=ssl._create_unverified_context()
        )
        if response.status != 200:
            print(
                f"WARNING: Failed to read Interfaces info. {response.status} {response.getheaders()} {response.read()}"
            )
            return

        response = json.loads(response.read().decode())
        interfaces = response.get("Members")
        if not interfaces or len(interfaces) == 0:
            print(
                f"WARNING: Missing Redfish Manager Interfaces. {response.read()}"
            )
            return

        for interface in interfaces:
            url = f"https://{self._redfish_ip}:{self._redfish_port}{interface['@odata.id']}"
            req = urllib.request.Request(url)
            req.add_header("X-Auth-Token", token)
            response = urllib.request.urlopen(
                req, context=ssl._create_unverified_context()
            )
            if response.status != 200:
                print(
                    f"WARNING: Failed to read {interface['@odata.id']} info. {response.status} {response.getheaders()} {response.read()}"
                )
                return

            response = json.loads(response.read().decode())
            addresses = response.get("IPv4Addresses")
            if not addresses or len(addresses) == 0:
                print(
                    f"WARNING: Missing Redfish IPv4 Address. {response.read()}"
                )
                return

            for ip in addresses:
                if (
                    not ip["Address"]
                    or ip["Address"] in ["0.0.0.0", "16.1.15.1"]
                    or ip["Address"].startswith("169.254")
                ):
                    continue
        return addresses[0].get("Address")

    def get_bmc_ip(self):
        if self._bmc_ip is None:
            self._manager_id = self.get_manager_id()
            self._bmc_ip = self._get_bmc_ip()
        return self._bmc_ip

    def get_credentials(self):
        """Return the BMC credentials for MAAS to use the BMC."""
        return {
            "power_address": self.get_bmc_ip(),
            "power_user": self.username if self.username else "",
            "power_pass": self.password if self.password else "",
            "node_id": self.get_manager_id(),
        }


def detect_and_configure(args, bmc_config_path):
    # Order matters here. HPMoonshot is a specical IPMI device, so try to
    # detect it first.
    for bmc_class in [HPMoonshot, Redfish, IPMI, Wedge]:
        try:
            bmc = bmc_class(**vars(args))
            print("INFO: Checking for %s..." % bmc)
            if bmc.detected():
                print("INFO: %s detected!" % bmc)
                bmc.configure()
                bmc.add_bmc_user()
                with open(bmc_config_path, "w") as f:
                    yaml.safe_dump(
                        {
                            "power_type": bmc.power_type,
                            **bmc.get_credentials(),
                        },
                        f,
                        default_flow_style=False,
                    )
                return
        except Exception as e:
            print(f"ERROR: {bmc_class.__name__} {e}\n{traceback.format_exc()}")
    print("INFO: No BMC automatically detected!")


def main():
    parser = argparse.ArgumentParser(
        description="BMC detection and configuration tool for MAAS"
    )
    parser.add_argument(
        "-u",
        "--username",
        type=str,
        default="maas",
        help="Specify the BMC username to create.",
    )
    parser.add_argument(
        "-p",
        "--password",
        type=str,
        help="Specify the BMC password to use with newly created user.",
    )
    parser.add_argument(
        "--ipmi-k-g",
        type=str,
        default="",
        help="The IPMI K_G BMC Key to set if IPMI is detected",
    )
    parser.add_argument(
        "--ipmi-privilege-level",
        choices=("USER", "OPERATOR", "ADMIN"),
        default="ADMIN",
        help="The IPMI priviledge level to create the MAAS user as.",
    )
    parser.add_argument(
        "--ipmi-cipher-suite-id",
        choices=("3", "8", "12", "17"),
        default="3",
        help="The IPMI cipher suite ID to use when connecting via ipmitool",
    )
    args = parser.parse_args()

    # 20 character limit is from IPMI 2.0
    if args.username and len(args.username) > 20:
        print(
            "ERROR: Username must be 20 characters or less!",
            file=sys.stderr,
        )
        sys.exit(os.EX_USAGE)
    if args.password and len(args.password) > 20:
        print(
            "ERROR: Password must be 20 characters or less!",
            file=sys.stderr,
        )
        sys.exit(os.EX_USAGE)
    if args.ipmi_k_g and len(args.ipmi_k_g) > 20:
        print(
            "ERROR: IPMI K_g key must be 20 characters or less!",
            file=sys.stderr,
        )
        sys.exit(os.EX_USAGE)

    bmc_config_path = os.environ.get("BMC_CONFIG_PATH")
    if not bmc_config_path:
        print(
            'ERROR: Environment variable "BMC_CONFIG_PATH" not defined!',
            file=sys.stderr,
        )
        sys.exit(os.EX_CONFIG)
    elif os.path.exists(bmc_config_path):
        print(
            "INFO: BMC configuration has occured in a previously run "
            "commissioning script, skipping"
        )
        return exit_skipped()

    # XXX: andreserl 2013-04-09 bug=1064527: Try to detect if node
    # is a Virtual Machine. If it is, do not try to detect IPMI.
    try:
        check_call(["systemd-detect-virt", "-q"], timeout=COMMAND_TIMEOUT)
    except CalledProcessError:
        pass
    else:
        print("INFO: Running on virtual machine, skipping")
        return exit_skipped()

    print("INFO: Loading IPMI kernel modules...")
    for module in [
        "ipmi_msghandler",
        "ipmi_devintf",
        "ipmi_si",
        "ipmi_ssif",
    ]:
        # The IPMI modules will fail to load if loaded on unsupported
        # hardware.
        try:
            run(["sudo", "-E", "modprobe", module], timeout=COMMAND_TIMEOUT)
        except TimeoutExpired:
            pass
    try:
        run(["sudo", "-E", "udevadm", "settle"], timeout=COMMAND_TIMEOUT)
    except TimeoutExpired:
        pass
    detect_and_configure(args, bmc_config_path)


@lru_cache(maxsize=1)
def _get_ipmi_locate_output():
    return check_output(["ipmi-locate"], timeout=COMMAND_TIMEOUT).decode()


@lru_cache(maxsize=1)
def _get_wedge_local_addr():
    try:
        # "fe80::ff:fe00:2" is the address for the device to the internal
        # BMC network.
        output = check_output(
            ["ip", "-o", "a", "show", "to", "fe80::ff:fe00:2"],
            timeout=COMMAND_TIMEOUT,
        ).decode()
        # fe80::1 is the BMC's LLA.
        return "fe80::1%%%s" % output.split()[1]
    except Exception:
        return None


def get_smbios_value(data, key):
    for item in data.split("\n"):
        if key in item:
            return item.split(":")[1].strip()


def get_network_interface(machine_resources, vendor_id, product_id):
    """Searches machine-resources data and returns network interface name
    that maches idVendor and idProduct fetched from SMBIOS
    """
    # XXX: this can be simplified once this is resolved
    # https://chat.canonical.com/canonical/pl/9fkoiwr837rr8yb99bx1qwzmkh
    device_type_addresses = (
        ("usb", ("bus_address", "device_address")),
        ("pci", ("pci_address",)),
    )

    for device_type, addresses in device_type_addresses:
        if device_type not in machine_resources["resources"]:
            continue
        for device in machine_resources["resources"][device_type]["devices"]:
            if (
                device["vendor_id"] != vendor_id
                or device["product_id"] != product_id
            ):
                continue

            for card in machine_resources["resources"]["network"]["cards"]:
                address_type = f"{device_type}_address"
                # pci_address holds address as 0000:0001:00.0
                # but usb_address is a combination of bus_address:device_address
                address_value = f'{":".join(f"{device[address]}" for address in addresses)}'
                if card.get(address_type, "") == address_value:
                    return card["ports"][0]["id"]


if __name__ == "__main__":
    main()
