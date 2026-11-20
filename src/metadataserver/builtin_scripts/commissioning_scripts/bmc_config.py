#!/usr/bin/env python3
#
# bmc-config - Detect and configure BMC's for MAAS use.
#
# Author: Andres Rodriguez <andres.rodriguez@canonical.com>
#         Lee Trager <lee.trager@canonical.com>
#
# Copyright (C) 2013-2026 Canonical
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
# --- End MAAS 1.0 script metadata ---

from abc import ABCMeta, abstractmethod, abstractproperty
import argparse
from base64 import b64encode
from collections import OrderedDict
from collections.abc import Callable
from functools import lru_cache
import glob
import ipaddress
import json
import os
from os.path import basename
import platform
import random
import re
import secrets
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


# This script is distributed to and run standalone on the machine being
# commissioned, which does not have the MAAS packages installed. It cannot
# import maascommon, so the password-generation logic below is copied from
# `maascommon.utils.password` (and the complexity policy it depends on,
# `maascommon.password_policy.validate_password_complexity`). Keep both
# copies in sync if either changes.
def _validate_password_complexity(password: str) -> bool:
    """Check password complexity requirements for hardening mode.

    Enforces: min 14 chars, uppercase, digit, special char.
    """
    return (
        len(password) >= 14
        and re.search(r"[A-Z]", password) is not None
        and re.search(r"\d", password) is not None
        and re.search(r"[^a-zA-Z0-9]", password) is not None
    )


def _generate_password_by_rule(length: int) -> str:
    """Generate a password guaranteed to satisfy the complexity policy.

    Unlike random sampling, this forces one uppercase letter, one digit, and
    one special character into fixed draws before filling the remaining
    positions and shuffling. This trades a small amount of distribution
    uniformity for a guaranteed-terminating construction, used as a fallback
    when random sampling fails to find a compliant result within a bounded
    number of attempts.
    """
    uppercase = string.ascii_uppercase
    lowercase = string.ascii_lowercase
    digits = string.digits
    # Matches the altchars used by the base64-based candidate generator.
    special = ".!"

    password_chars = [
        secrets.choice(uppercase),
        secrets.choice(digits),
        secrets.choice(special),
    ]

    all_chars = uppercase + lowercase + digits + special
    password_chars += [
        secrets.choice(all_chars) for _ in range(length - len(password_chars))
    ]

    rng = random.SystemRandom()
    rng.shuffle(password_chars)

    return "".join(password_chars)


def _generate_base64_password(length: int) -> str:
    """Generate a candidate password by base64-encoding random bytes.

    Uses `.` and `!` in place of the standard `+`/`/` altchars, so the
    output alphabet is limited to letters, digits, `.`, and `!`.

    Requests enough random bytes, rounded up to a multiple of 3, so the
    base64 encoding never produces padding (`=`) characters; every
    character considered is genuinely random rather than a fixed filler.
    """
    num_groups = -(-length // 4)  # ceil(length / 4)
    num_bytes = num_groups * 3
    encoded = b64encode(os.urandom(num_bytes), altchars=b".!").decode("ascii")
    return encoded[:length]


def generate_password(
    min_length: int = 14,
    max_length: int = 14,
    max_attempts: int = 1000,
    extra_constraint: Callable[[str], bool] | None = None,
) -> str:
    """Generate a FIPS-compliant password.

    Generates a password meeting FIPS 140-2/140-3 and STIG/CIS hardening
    requirements, as enforced by `_validate_password_complexity`:
    - Minimum 14 characters (satisfies FIPS lower bound on PBKDF2/HMAC key length)
    - At least one uppercase letter
    - At least one digit
    - At least one special character (non-alphanumeric)

    The password length is drawn once, uniformly at random, from
    `[min_length, max_length]`, then held fixed across every attempt made
    for this call. Generates candidates by base64-encoding random bytes and
    retries until one satisfies the complexity policy. If no compliant
    password is found within `max_attempts`, falls back to a single
    rule-based construction attempt, which is itself required to satisfy
    the policy (and any `extra_constraint`) before being returned.

    Args:
        min_length: Minimum password length (minimum 14). Defaults to 14.
        max_length: Maximum password length. Must be >= `min_length`.
            Defaults to 14.
        max_attempts: Maximum candidates to try before falling back to the
            rule-based construction. Defaults to 1000.
        extra_constraint: Optional additional predicate a candidate must
            satisfy. Checked alongside the complexity policy on every
            attempt, including the rule-based fallback, and is required
            before a password is returned.

    Raises:
        ValueError: If `min_length` is less than 14, if `max_length` is
            less than `min_length`, or if no password satisfying all
            constraints could be generated within `max_attempts` (plus the
            single fallback attempt).

    Returns:
        A FIPS-compliant password string.
    """
    if min_length < 14:
        raise ValueError(
            f"Password length must be at least 14 characters, got {min_length}"
        )
    if max_length < min_length:
        raise ValueError(
            f"max_length ({max_length}) must be >= min_length ({min_length})"
        )

    length = min_length + secrets.randbelow(max_length - min_length + 1)

    def satisfies_constraints(password: str) -> bool:
        return _validate_password_complexity(password) and (
            extra_constraint is None or extra_constraint(password)
        )

    for _ in range(max_attempts):
        password = _generate_base64_password(length)
        if satisfies_constraints(password):
            return password

    # Single semi-deterministic fallback attempt, in the sense that
    # it is guaranteed to be FIPS-compliant. However, it might fail the
    # extra constraints.
    password = _generate_password_by_rule(length)
    if satisfies_constraints(password):
        return password

    raise ValueError(
        "Unable to generate a password satisfying all constraints after "
        f"{max_attempts} attempts"
    )


# Characters accepted across observed BMC vendor password policies (e.g.
# Huawei, Lenovo, DGX): letters, digits, and this conservative punctuation
# set. Notably excludes whitespace and backslash, which some vendors reject
# outright. LP:2081842 - the exclusion of backslash in particular comes from
# a BMC that rejected it.
_BMC_PASSWORD_ALLOWED_CHARS = re.compile(
    r"^[A-Za-z0-9~`!\"@#$%^&*()\-+={}\[\]|:;'<>,?/._]+$"
)


def _build_bmc_password_constraint(
    username: str | None = None,
    old_password: str | None = None,
) -> Callable[[str], bool]:
    """Build an `extra_constraint` combining common BMC vendor password
    policies, for use with `generate_password`.

    `generate_password`'s own complexity policy already guarantees an
    uppercase letter, a digit, and a special character on every generated
    password, which alone satisfies every observed vendor's "at least N of
    {upper, lower, digit, special}" requirement (N <= 2). The "at least 2 of
    {lowercase, uppercase, digit}" variant is re-checked explicitly below
    anyway, so this constraint doesn't depend on that upstream guarantee.
    What remains, and is checked here, is vendor-specific:
    - Only letters, digits, and a conservative punctuation set are allowed;
      no whitespace or other characters. (LP:2081842)
    - At least 2 of {lowercase, uppercase, digit} character types present.
      (LP:1621175 - Huawei and Lenovo enforce a password policy stricter
      than the IPMI spec, requiring multiple character classes.)
    - No more than 2 consecutive occurrences of the same character.
      (LP:1758760)
    - Must not equal `username`, or `username` reversed, and if
      `old_password` is given, must differ from it in at least 2 character
      positions. (No specific MAAS bug; these come from generic vendor BMC
      password policy documentation, not an observed failure.)

    Length bounds (commonly 8-20 or 10-20 characters, depending on vendor)
    are enforced via `generate_password`'s `min_length`/`max_length`, not
    here.
    """

    def constraint(password: str) -> bool:
        # LP:2081842 - only accept characters known to be safe across
        # observed vendor BMC password policies.
        if not _BMC_PASSWORD_ALLOWED_CHARS.match(password):
            return False
        char_types_present = sum(
            (
                re.search(r"[a-z]", password) is not None,
                re.search(r"[A-Z]", password) is not None,
                re.search(r"\d", password) is not None,
            )
        )
        # LP:1621175 - Huawei and Lenovo enforce a password policy stricter
        # than the IPMI spec, requiring multiple character classes.
        if char_types_present < 2:
            return False
        # LP:1758760 - no more than 2 consecutive occurrences of the same
        # character.
        if re.search(r"(.)\1\1", password):
            return False
        # No specific MAAS bug; comes from generic vendor BMC password
        # policy documentation, not an observed failure.
        if username and password in (username, username[::-1]):
            return False
        if old_password is not None:
            longer, shorter = sorted(
                (password, old_password), key=len, reverse=True
            )
            differing_positions = sum(
                1 for a, b in zip(longer, shorter) if a != b
            ) + (len(longer) - len(shorter))
            # No specific MAAS bug; comes from generic vendor BMC password
            # policy documentation, not an observed failure.
            if differing_positions < 2:
                return False
        return True

    return constraint


class BMCConfig(metaclass=ABCMeta):
    """Base class for BMC detection."""

    username = None
    password = None

    def __init__(self, *args, **kwargs):  # noqa: B027
        pass

    @abstractmethod
    def __str__(self) -> str:
        """The pretty name of the BMC type."""

    @abstractproperty
    def power_type(self):
        """The power_type of the BMC."""

    @abstractmethod
    def detected(self) -> bool:
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

    def configure(self):  # noqa: B027
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
            # LP:1993916, LP:1621175, LP:2130621 - across vendors (Lenovo,
            # Huawei, NVIDIA DGX H200), there is an observed minimum length
            # requirement beyond of 16. IPMI 1.5 also
            # imposes a maximum length of 16, and is apparently the only
            # one to do so that we are aware of. Together, this boxes us
            # into min_length=16 and max_length=16.
            # `_build_bmc_password_constraint` enforces the remaining,
            # vendor-agnostic rules (allowed characters, no 3+ consecutive
            # repeats, not equal to the username or its reverse).
            password = generate_password(
                min_length=16,
                max_length=16,
                extra_constraint=_build_bmc_password_constraint(
                    username=self.username
                ),
            )
        else:
            password = self.password
        try:
            for key, value in self._make_ipmi_user_settings(
                self.username, password
            ).items():
                if self._bmc_config[user_number].get(key) != value:
                    self._bmc_set(user_number, key, value)
        except Exception:
            print("ERROR: Unable to add BMC user!", file=sys.stderr)
            sys.exit(1)
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
        except Exception as err:
            print(
                f"DEBUG: Exception occurred when trying to execute ipmi-locate command: {str(err)}"
            )
            return False
        else:
            m = re.search(r"(IPMI\ Version:) (\d\.\d)", output)
            # ipmi-locate always returns 0. If the IPMI version regex doesn't match,
            # check if /dev/ipmi[0-9] exists. This is needed on the PPC64
            # host in the MAAS CI.
            if m or len(glob.glob("/dev/ipmi[0-9]")):
                return True
            else:
                print(
                    "DEBUG: Could not find IPMI version or an IPMI device in /dev"
                )
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
        """Configure and retrieve IPMI BMC IP."""
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

    def __str__(self) -> str:
        return "HP Moonshot"

    def detected(self) -> bool:
        output = ""
        try:
            output = check_output(
                ["ipmitool", "raw", "06", "01"],
                timeout=COMMAND_TIMEOUT,
                stderr=DEVNULL,
            ).decode()
        except Exception as err:
            print(
                f"DEBUG: Exception occurred executing ipmitool command: {str(err)}"
            )
            return False
        # 14 is the code that identifies the BMC as HP Moonshot
        device_id = output.split()[0]
        if device_id == "14":
            return True
        else:
            print(
                f"DEBUG: Detected BMC is not HP Moonshot, has device ID {device_id}"
            )
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
                ",0-m",
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
        except (CalledProcessError, TimeoutExpired, FileNotFoundError) as err:
            print(
                f"DEBUG: Exception occurred when trying to detect switch: {str(err)}"
            )
            return False
        else:
            if switch_type is None:
                print("DEBUG: Unknown/no switch detected.")
                return False
        try:
            # Second, lets verify if this is a known endpoint
            # First try to hit the API. This would work on Wedge 100.
            local_addr = _get_wedge_local_addr()
            response = urllib.request.urlopen(
                f"http://[{local_addr}]:8080/api"
            )
            if b"Wedge RESTful API Entry" in response.read():
                return True
        except Exception:
            pass
        if self.get_bmc_ip():
            # If the above failed, try to hit the SSH. This would work on Wedge 40.
            return True
        print("DEBUG: Unable to connect to the Wedge device via SSH or API.")
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
    _node_id = None
    _redfish_ip = None
    _redfish_port = None
    _session_token = None

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

        vendor_id = get_smbios_value(data, "idVendor")
        if vendor_id is None:
            raise ConfigurationError(
                "'idVendor' key not present in SMBIOS data"
            )
        else:
            vendor_id = vendor_id[2:]

        product_id = get_smbios_value(data, "idProduct")
        if product_id is None:
            raise ConfigurationError(
                "'idProduct' key not present in SMBIOS data"
            )
        else:
            product_id = product_id[2:]

        if not all((vendor_id, product_id)):
            raise ConfigurationError(
                "Missing idVendor and idProduct information"
            )

        iface = None
        try:
            with open(os.environ["MAAS_RESOURCES_FILE"]) as fd:
                machine_resources_data = json.load(fd)
                iface = get_network_interface(
                    machine_resources_data, vendor_id, product_id
                )
                if iface is None:
                    raise ConfigurationError("Missing Redfish Host Interface")
        except ConfigurationError:
            # Pass on the known configuration error
            raise
        except Exception as e:
            # Catch any other exception and raise a wrapping ConfigurationError
            raise ConfigurationError(
                "Failed to get network interface for Redfish"
            ) from e

        self._configure_network(iface, data)

        self._bmc_get_config()
        self.add_bmc_user()

        self._redfish_ip = get_smbios_value(
            data, "IPv4 Redfish Service Address"
        )
        self._redfish_port = get_smbios_value(data, "Redfish Service Port")

        if not all((self._redfish_ip, self._redfish_port)):
            raise ConfigurationError("Missing Redfish Service information.")

    def detected(self) -> bool:
        try:
            self._detect()
            return self.get_bmc_ip() is not None
        # XXX: we should know which exceptions to expect, so we can handle them
        except ConfigurationError as err:
            print(
                f"DEBUG: Redfish detection and configuration failed. Reason: {str(err)}"
            )
            return False

    def _get_session_token(self):
        if self._session_token is not None:
            return self._session_token

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
            return None

        token = response.getheader("X-Auth-Token")
        if token is None:
            print(
                f"WARNING: Missing X-Auth-Token header. {response.getheaders()}"
            )
            return None

        self._session_token = token
        return token

    def _get_first_collection_member_id(self, collection_name):
        token = self._get_session_token()
        if token is None:
            return None

        url = f"https://{self._redfish_ip}:{self._redfish_port}/redfish/v1/{collection_name}"
        req = urllib.request.Request(url)
        req.add_header("X-Auth-Token", token)
        response = urllib.request.urlopen(
            req, context=ssl._create_unverified_context()
        )
        if response.status != 200:
            print(
                f"WARNING: Failed to read {collection_name} info. {response.status} {response.getheaders()} {response.read()}"
            )
            return None

        data = json.loads(response.read().decode())
        members = data.get("Members")
        if not members or len(members) == 0:
            print(
                f"WARNING: Missing Redfish {collection_name} Collection. {data}"
            )
            return None

        member = members[0].get("@odata.id")
        if not member:
            print(
                f"WARNING: Missing @odata.id in Redfish {collection_name} member. {members[0]}"
            )
            return None

        member = member.rstrip("/")
        return basename(member)

    def _get_manager_id(self):
        return self._get_first_collection_member_id("Managers")

    def get_manager_id(self):
        if self._manager_id is None:
            self._manager_id = self._get_manager_id()
        return self._manager_id

    def _get_node_id(self):
        return self._get_first_collection_member_id("Systems")

    def get_node_id(self):
        if self._node_id is None:
            self._node_id = self._get_node_id()
        return self._node_id

    def _get_bmc_ip(self):
        token = self._get_session_token()
        if token is None:
            return None

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
            return None

        data = json.loads(response.read().decode())
        interfaces = data.get("Members")
        if not interfaces or len(interfaces) == 0:
            print(f"WARNING: Missing Redfish Manager Interfaces. {data}")
            return None

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

            iface_data = json.loads(response.read().decode())
            addresses = iface_data.get("IPv4Addresses")
            if not addresses or len(addresses) == 0:
                print(f"WARNING: Missing Redfish IPv4 Address. {iface_data}")
                return

            for ip in addresses:
                if (
                    not ip["Address"]
                    or ip["Address"] in ["0.0.0.0", "16.1.15.1"]
                    or ip["Address"].startswith("169.254")
                ):
                    continue
                return ip["Address"]
        print("WARNING: No valid Redfish IPv4 address found.")

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
            "node_id": self.get_node_id(),
        }


def detect_and_configure(args, bmc_config_path: str) -> None:
    # Order matters here. HPMoonshot is a specical IPMI device, so try to
    # detect it first.
    bmc_list = [HPMoonshot, Redfish, IPMI, Wedge]
    for bmc_class in bmc_list:
        try:
            bmc = bmc_class(**vars(args))
            print(f"INFO: Checking for {bmc}...")
            if bmc.detected():
                print(f"INFO: {bmc} detected!")
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
            else:
                msg = f"INFO: No {bmc} detected."
                if bmc_class is not bmc_list[-1]:
                    msg += " Trying next BMC type..."
                print(msg)
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
    if args.ipmi_k_g:
        # k_g can either be provided as:
        # - Regular string, limited to 20 characters
        # - Hex-encoded string, limited to 42 characters ("0x" plus 20 hex pairs)
        valid_k_g_match = re.search(
            r"^(0x[a-zA-Z0-9]{40}|[\w\W]{20})$", str(args.ipmi_k_g)
        )
        if not valid_k_g_match:
            print(
                (
                    "ERROR: IPMI K_g key must be 20 characters long, or 40 characters "
                    "long and prefixed with '0x' if in hex-encoded format."
                ),
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
            # XXX: Used to be "sudo -E", dropped the "-E" since sudo-rs doesn't
            # support it, but didn't explicitly add any env var.
            run(["sudo", "modprobe", module], timeout=COMMAND_TIMEOUT)
        except TimeoutExpired:
            pass
    try:
        # XXX: Used to be "sudo -E", dropped the "-E" since sudo-rs doesn't
        # support it, but didn't explicitly add any env var.
        run(["sudo", "udevadm", "settle"], timeout=COMMAND_TIMEOUT)
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
                address_value = f"{':'.join(f'{device[address]}' for address in addresses)}"
                if card.get(address_type, "") == address_value:
                    return card["ports"][0]["id"]


if __name__ == "__main__":
    main()
