# Copyright 2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test bmc_config functions."""

from collections import OrderedDict
import io
import os
import random
import re
from subprocess import CalledProcessError, DEVNULL
from unittest.mock import call, MagicMock

import yaml

from maasserver.testing.factory import factory
from maastesting.fixtures import TempDirectory
from maastesting.matchers import (
    MockCalledOnce,
    MockCalledOnceWith,
    MockCallsMatch,
    MockNotCalled,
)
from maastesting.testcase import MAASTestCase
from metadataserver.builtin_scripts.commissioning_scripts import bmc_config


class TestExitSkipped(MAASTestCase):
    def test_result_path_defined(self):
        result_path = factory.make_name("result_path")
        self.patch(bmc_config.os, "environ", {"RESULT_PATH": result_path})
        mock_open = self.patch(bmc_config, "open")
        mock_open.return_value = io.StringIO()
        mock_yaml_safe_dump = self.patch(bmc_config.yaml, "safe_dump")

        self.assertRaises(SystemExit, bmc_config.exit_skipped)
        self.assertThat(mock_open, MockCalledOnceWith(result_path, "w"))
        self.assertThat(
            mock_yaml_safe_dump,
            MockCalledOnceWith({"status": "skipped"}, mock_open.return_value),
        )

    def test_result_path_not_defined(self):
        mock_open = self.patch(bmc_config, "open")

        self.assertRaises(SystemExit, bmc_config.exit_skipped)
        self.assertThat(mock_open, MockNotCalled())


class TestIPMI(MAASTestCase):
    def setUp(self):
        super().setUp()
        self.username = factory.make_name("username")
        self.password = factory.make_name("password")
        self.ipmi = bmc_config.IPMI(self.username, self.password)
        self.mock_check_output = self.patch(bmc_config, "check_output")
        self.mock_sleep = self.patch(bmc_config.time, "sleep")
        self.mock_print = self.patch(bmc_config, "print")

    def test_power_type(self):
        self.assertEqual("ipmi", self.ipmi.power_type)

    def test_str(self):
        self.assertEqual("IPMI", str(self.ipmi))

    def test_bmc_get(self):
        key = factory.make_name("key")
        value = factory.make_name("value")
        self.mock_check_output.return_value = value.encode()

        self.assertEqual(value, self.ipmi._bmc_get(key))
        self.assertThat(
            self.mock_check_output,
            MockCalledOnceWith(
                ["bmc-config", "--checkout", f"--key-pair={key}"],
                stderr=DEVNULL,
                timeout=60,
            ),
        )

    def test_bmc_get_returns_none_on_error(self):
        key = factory.make_name("key")
        self.mock_check_output.side_effect = factory.make_exception()

        self.assertIsNone(self.ipmi._bmc_get(key))
        self.assertThat(
            self.mock_check_output,
            MockCalledOnceWith(
                ["bmc-config", "--checkout", f"--key-pair={key}"],
                stderr=DEVNULL,
                timeout=60,
            ),
        )

    def test_get_ipmi_locate_output(self):
        # Make sure we start out with a cleared cache
        self.ipmi._get_ipmi_locate_output.cache_clear()
        ret = factory.make_string()
        self.mock_check_output.return_value = ret.encode()

        self.assertEqual(ret, self.ipmi._get_ipmi_locate_output())
        # Because the value is cached check_output should only be
        # called once.
        self.assertEqual(ret, self.ipmi._get_ipmi_locate_output())
        self.assertThat(
            self.mock_check_output,
            MockCalledOnceWith(["ipmi-locate"], timeout=60),
        )

    def test_detected_true(self):
        mock_get_ipmi_locate_output = self.patch(
            self.ipmi, "_get_ipmi_locate_output"
        )
        mock_get_ipmi_locate_output.return_value = random.choice(
            [
                "IPMI Version: 1.0\n",
                "IPMI Version: 1.5\n",
                "IPMI Version: 2.0\n",
            ]
        )
        self.assertTrue(self.ipmi.detected())

    def test_detected_true_dev_ipmi(self):
        self.mock_check_output.return_value = b""
        self.patch(bmc_config.glob, "glob").return_value = ["/dev/ipmi0"]
        self.assertTrue(self.ipmi.detected())

    def test_detected_false(self):
        mock_get_ipmi_locate_output = self.patch(
            self.ipmi, "_get_ipmi_locate_output"
        )
        mock_get_ipmi_locate_output.return_value = factory.make_string()
        self.assertFalse(self.ipmi.detected())

    def test_generate_random_password(self):
        for attempt in range(0, 100):
            password = self.ipmi._generate_random_password()
            self.assertTrue(10 <= len(password) <= 15)
            self.assertIsNotNone(
                re.match(r"^[\da-z]+$", password, re.IGNORECASE), password
            )

    def test_generate_random_password_with_special_chars(self):
        # Huawei uses a non-standard IPMI password policy
        special_chars = set("!\"#$%&'()*+-./:;<=>?@[\\]^_`{|}~")
        for attempt in range(0, 100):
            password = self.ipmi._generate_random_password(
                with_special_chars=True
            )
            self.assertTrue(10 <= len(password) <= 15)
            self.assertTrue(
                any((c in special_chars) for c in password), password
            )
            self.assertIsNotNone(re.match(r".*[a-z].*", password), password)
            self.assertIsNotNone(re.match(r".*[A-Z].*", password), password)
            self.assertIsNotNone(re.match(r".*[0-9].*", password), password)
            # Test password doesn't have two or more occurrences of the
            # the same consecutive character.
            self.assertFalse(re.search(r"(.)\1", password))

    def test_make_ipmi_user_settings(self):
        username = factory.make_name("username")
        password = factory.make_name("password")
        self.assertEqual(
            OrderedDict(
                (
                    ("Username", username),
                    ("Password", password),
                    ("Enable_User", "Yes"),
                    ("Lan_Privilege_Limit", "Administrator"),
                    ("Lan_Enable_IPMI_Msgs", "Yes"),
                )
            ),
            self.ipmi._make_ipmi_user_settings(username, password),
        )

    def test_pick_user_number_finds_empty(self):
        self.mock_check_output.return_value = (
            b"User1\n"
            b"User2\n"
            b"User3\n"
            b"User4\n"
            b"User5\n"
            b"User6\n"
            b"User7\n"
            b"User8\n"
            b"User9\n"
            b"User10\n"
            b"User11\n"
            b"User12\n"
            b"Lan_Channel\n"
            b"Lan_Conf\n"
        )
        self.patch(self.ipmi, "_bmc_get").side_effect = [
            "Section User1\n"
            "\t## Give Username\n"
            "\t##Username                NULL\n"
            "EndSection\n"
        ] + [
            f"Section User{i}\n"
            "\t## Give Username\n"
            "\tUsername                (Empty User)\n"
            "EndSection\n"
            for i in range(2, 12)
        ]
        self.assertEqual("User2", self.ipmi._pick_user_number("maas"))
        self.assertThat(
            self.mock_check_output,
            MockCalledOnceWith(["bmc-config", "-L"], timeout=60),
        )

    def test_pick_user_number_finds_existing(self):
        self.mock_check_output.return_value = (
            b"User1\n"
            b"User2\n"
            b"User3\n"
            b"User4\n"
            b"User5\n"
            b"User6\n"
            b"User7\n"
            b"User8\n"
            b"User9\n"
            b"User10\n"
            b"User11\n"
            b"User12\n"
            b"Lan_Channel\n"
            b"Lan_Conf\n"
        )
        self.patch(self.ipmi, "_bmc_get").side_effect = (
            [
                "Section User1\n"
                "\t## Give Username\n"
                "\t##Username                NULL\n"
                "EndSection\n"
            ]
            + [
                f"Section User{i}\n"
                "\t## Give Username\n"
                "\tUsername                (Empty User)\n"
                "EndSection\n"
                for i in range(2, 11)
            ]
            + [
                "Section User12\n"
                "\t## Give Username\n"
                "\tUsername                maas\n"
                "EndSection\n"
            ]
        )
        self.assertEqual("User12", self.ipmi._pick_user_number("maas"))
        self.assertThat(
            self.mock_check_output,
            MockCalledOnceWith(["bmc-config", "-L"], timeout=60),
        )

    def test_add_bmc_user(self):
        user_number = "User%s" % random.randint(2, 12)
        self.patch(self.ipmi, "_pick_user_number").return_value = user_number
        mock_bmc_set = self.patch(self.ipmi, "_bmc_set")

        self.ipmi.add_bmc_user()

        self.assertEqual(self.username, self.ipmi.username)
        self.assertEqual(self.password, self.ipmi.password)
        self.assertThat(
            mock_bmc_set,
            MockCallsMatch(
                call(f"{user_number}:Username", self.username),
                call(f"{user_number}:Password", self.password),
                call(f"{user_number}:Enable_User", "Yes"),
                call(f"{user_number}:Lan_Privilege_Limit", "Administrator"),
                call(f"{user_number}:Lan_Enable_IPMI_Msgs", "Yes"),
            ),
        )

    def test_add_bmc_user_rand_password(self):
        user_number = "User%s" % random.randint(2, 12)
        self.ipmi.username = None
        self.ipmi.password = None
        password = factory.make_name("password")
        password_w_spec_chars = factory.make_name("password_w_spec_chars")
        self.patch(self.ipmi, "_pick_user_number").return_value = user_number
        self.patch(self.ipmi, "_generate_random_password").side_effect = (
            password,
            password_w_spec_chars,
        )
        mock_bmc_set = self.patch(self.ipmi, "_bmc_set")

        self.ipmi.add_bmc_user()

        self.assertEqual("maas", self.ipmi.username)
        self.assertEqual(password, self.ipmi.password)
        self.assertThat(
            mock_bmc_set,
            MockCallsMatch(
                call(f"{user_number}:Username", "maas"),
                call(f"{user_number}:Password", password),
                call(f"{user_number}:Enable_User", "Yes"),
                call(f"{user_number}:Lan_Privilege_Limit", "Administrator"),
                call(f"{user_number}:Lan_Enable_IPMI_Msgs", "Yes"),
            ),
        )

    def test_add_bmc_user_rand_password_with_special_chars(self):
        self.ipmi.username = None
        self.ipmi.password = None
        user_number = "User%s" % random.randint(2, 12)
        password = factory.make_name("password")
        password_w_spec_chars = factory.make_name("password_w_spec_chars")
        self.patch(self.ipmi, "_pick_user_number").return_value = user_number
        self.patch(self.ipmi, "_generate_random_password").side_effect = (
            password,
            password_w_spec_chars,
        )
        mock_bmc_set = self.patch(self.ipmi, "_bmc_set")
        mock_bmc_set.side_effect = (
            None,
            factory.make_exception(),
            None,
            None,
            None,
            None,
            None,
        )

        self.ipmi.add_bmc_user()

        self.assertEqual("maas", self.ipmi.username)
        self.assertEqual(password_w_spec_chars, self.ipmi.password)
        self.assertThat(
            mock_bmc_set,
            MockCallsMatch(
                call(f"{user_number}:Username", "maas"),
                call(f"{user_number}:Password", password),
                call(f"{user_number}:Username", "maas"),
                call(f"{user_number}:Password", password_w_spec_chars),
                call(f"{user_number}:Enable_User", "Yes"),
                call(f"{user_number}:Lan_Privilege_Limit", "Administrator"),
                call(f"{user_number}:Lan_Enable_IPMI_Msgs", "Yes"),
            ),
        )

    def test_add_bmc_user_fails(self):
        user_number = "User%s" % random.randint(2, 12)
        password = factory.make_name("password")
        password_w_spec_chars = factory.make_name("password_w_spec_chars")
        self.patch(self.ipmi, "_pick_user_number").return_value = user_number
        self.patch(self.ipmi, "_generate_random_password").side_effect = (
            password,
            password_w_spec_chars,
        )
        mock_bmc_set = self.patch(self.ipmi, "_bmc_set")
        mock_bmc_set.side_effect = factory.make_exception()

        self.assertRaises(SystemExit, self.ipmi.add_bmc_user)

    def test_set_ipmi_lan_channel_setting_verifies(self):
        mock_bmc_set = self.patch(self.ipmi, "_bmc_set")
        mock_bmc_get = self.patch(self.ipmi, "_bmc_get")
        mock_bmc_get.side_effect = (
            (
                "Section Lan_Channel\n"
                "\t## Possible values: Disabled/Pre_Boot_Only/"
                "Always_Available/Shared\n"
                "\tVolatile_Access_Mode                  Always_Available\n"
                "EndSection\n"
            ),
            (
                "Section Lan_Channel\n"
                "\t## Possible values: Disabled/Pre_Boot_Only/"
                "Always_Available/Shared\n"
                "\tNon_Volatile_Access_Mode              Always_Available\n"
                "EndSection\n"
            ),
        )
        self.ipmi._set_ipmi_lan_channel_settings()
        self.assertThat(mock_bmc_set, MockNotCalled())

    def test_set_ipmi_lan_channel_setting_enables(self):
        mock_bmc_set = self.patch(self.ipmi, "_bmc_set")
        mock_bmc_get = self.patch(self.ipmi, "_bmc_get")
        mock_bmc_get.side_effect = (
            (
                "Section Lan_Channel\n"
                "\t## Possible values: Disabled/Pre_Boot_Only/"
                "Always_Available/Shared\n"
                "\tVolatile_Access_Mode                  Disabled\n"
                "EndSection\n"
            ),
            (
                "Section Lan_Channel\n"
                "\t## Possible values: Disabled/Pre_Boot_Only/"
                "Always_Available/Shared\n"
                "\tNon_Volatile_Access_Mode              Pre_Boot_only\n"
                "EndSection\n"
            ),
        )
        self.ipmi._set_ipmi_lan_channel_settings()
        self.assertThat(
            mock_bmc_set,
            MockCallsMatch(
                call("Lan_Channel:Volatile_Access_Mode", "Always_Available"),
                call(
                    "Lan_Channel:Non_Volatile_Access_Mode", "Always_Available"
                ),
            ),
        )

    def test_configure(self):
        mock_set_ipmi_lan_channel_settings = self.patch(
            self.ipmi, "_set_ipmi_lan_channel_settings"
        )
        self.ipmi.configure()
        self.assertThat(mock_set_ipmi_lan_channel_settings, MockCalledOnce())

    def test_get_bmc_ipv4(self):
        ip = factory.make_ipv4_address()
        mock_bmc_get = self.patch(self.ipmi, "_bmc_get")
        mock_bmc_get.return_value = (
            "Section Lan_Conf\n"
            "\t## Give valid IP address\n"
            "\tIP_Address              %s\n"
            "EndSection\n" % ip
        )
        self.assertEqual(ip, self.ipmi._get_bmc_ip())

    def test_get_bmc_ipv6_static(self):
        ip = factory.make_ipv6_address()
        mock_bmc_get = self.patch(self.ipmi, "_bmc_get")
        mock_bmc_get.side_effect = (
            (
                "Section Lan_Conf\n"
                "\t## Give valid IP address\n"
                "\tIP_Address              0.0.0.0\n"
                "EndSection\n"
            ),
            (
                "Section Lan6_Conf\n"
                "\t## Give valid IPv6 address\n"
                "\tIP_Address              %s\n"
                "EndSection\n" % ip
            ),
        )
        self.assertEqual(f"[{ip}]", self.ipmi._get_bmc_ip())

    def test_get_bmc_ipv6_dynamic(self):
        ip = factory.make_ipv6_address()
        mock_bmc_get = self.patch(self.ipmi, "_bmc_get")
        mock_bmc_get.side_effect = (
            (
                "Section Lan_Conf\n"
                "\t## Give valid IP address\n"
                "\tIPv6_Address              0.0.0.0\n"
                "EndSection\n"
            ),
            (
                "Section Lan6_Conf\n"
                "\t## Give valid IPv6 address\n"
                "\tIP_Address              fe80::216:ffe3:f9eb:1f58\n"
                "EndSection\n"
            ),
            (
                "Section Lan6_Conf\n"
                "\t## READ-ONLY: IPv6 dynamic address\n"
                "\t## IPv6_Dynamic_Addresses        %s\n"
                "EndSection\n" % ip
            ),
        )
        self.assertEqual(f"[{ip}]", self.ipmi._get_bmc_ip())

    def test_get_bmc_ip_finds_none(self):
        self.patch(self.ipmi, "_bmc_get").return_value = ""
        self.assertIsNone(self.ipmi._get_bmc_ip())

    def test_get_bmc_ip(self):
        ip = factory.make_ip_address()
        mock_bmc_set = self.patch(self.ipmi, "_bmc_set")
        self.patch(self.ipmi, "_get_bmc_ip").return_value = ip

        self.assertEqual(ip, self.ipmi.get_bmc_ip())
        self.assertThat(mock_bmc_set, MockNotCalled())

    def test_get_bmc_ip_enables_static(self):
        ip = factory.make_ip_address()
        mock_bmc_set = self.patch(self.ipmi, "_bmc_set")
        self.patch(self.ipmi, "_get_bmc_ip").side_effect = (None, None, ip)

        self.assertEqual(ip, self.ipmi.get_bmc_ip())
        self.assertThat(
            mock_bmc_set,
            MockCalledOnceWith("Lan_Conf:IP_Address_Source", "Static"),
        )

    def test_get_bmc_ip_enables_dynamic(self):
        ip = factory.make_ip_address()
        mock_bmc_set = self.patch(self.ipmi, "_bmc_set")
        self.patch(self.ipmi, "_get_bmc_ip").side_effect = (
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            ip,
        )

        self.assertEqual(ip, self.ipmi.get_bmc_ip())
        self.assertThat(
            mock_bmc_set,
            MockCallsMatch(
                call("Lan_Conf:IP_Address_Source", "Static"),
                call("Lan_Conf:IP_Address_Source", "Use_DHCP"),
            ),
        )

    def test_get_bmc_ip_fails(self):
        mock_bmc_set = self.patch(self.ipmi, "_bmc_set")
        self.patch(self.ipmi, "_get_bmc_ip").return_value = None

        self.assertRaises(SystemExit, self.ipmi.get_bmc_ip)
        self.assertThat(
            mock_bmc_set,
            MockCallsMatch(
                call("Lan_Conf:IP_Address_Source", "Static"),
                call("Lan_Conf:IP_Address_Source", "Use_DHCP"),
            ),
        )

    def test_get_credentials_lan_new(self):
        self.ipmi.username = factory.make_name("username")
        self.ipmi.password = factory.make_name("password")
        self.patch(
            self.ipmi, "_get_ipmi_locate_output"
        ).return_value = "IPMI Version: 2.0"
        self.patch(bmc_config.platform, "machine").return_value = "ppc64le"
        self.patch(bmc_config.os.path, "isdir").return_value = True
        ip = factory.make_ip_address()
        self.patch(self.ipmi, "get_bmc_ip").return_value = ip

        self.assertEqual(
            {
                "power_address": ip,
                "power_pass": self.ipmi.password,
                "power_user": self.ipmi.username,
                "power_driver": "LAN_2_0",
                "power_boot_type": "efi",
            },
            self.ipmi.get_credentials(),
        )

    def test_get_credentials_lan_old(self):
        self.ipmi.username = factory.make_name("username")
        self.ipmi.password = factory.make_name("password")
        self.patch(
            self.ipmi, "_get_ipmi_locate_output"
        ).return_value = "IPMI Version: 1.0"
        self.patch(bmc_config.platform, "machine").return_value = "x86_64"
        self.patch(bmc_config.os.path, "isdir").return_value = False
        ip = factory.make_ip_address()
        self.patch(self.ipmi, "get_bmc_ip").return_value = ip

        self.assertEqual(
            {
                "power_address": ip,
                "power_pass": self.ipmi.password,
                "power_user": self.ipmi.username,
                "power_driver": "LAN",
                "power_boot_type": "auto",
            },
            self.ipmi.get_credentials(),
        )


class TestHPMoonshot(MAASTestCase):
    def setUp(self):
        super().setUp()
        self.hp_moonshot = bmc_config.HPMoonshot()
        self.mock_check_output = self.patch(bmc_config, "check_output")
        self.mock_print = self.patch(bmc_config, "print")

    def make_hex_array(self, size=11):
        return [
            str(hex(random.randint(0, 256))).split("x")[1]
            for _ in range(1, size)
        ]

    def test_power_type(self):
        self.assertEqual("moonshot", self.hp_moonshot.power_type)

    def test_str(self):
        self.assertEqual("HP Moonshot", str(self.hp_moonshot))

    def test_detect(self):
        self.mock_check_output.return_value = " ".join(
            ["14"] + self.make_hex_array(10)
        ).encode()
        self.assertTrue(self.hp_moonshot.detected())
        self.assertThat(
            self.mock_check_output,
            MockCalledOnceWith(
                ["ipmitool", "raw", "06", "01"], timeout=60, stderr=DEVNULL
            ),
        )

    def test_add_bmc_user(self):
        self.hp_moonshot.add_bmc_user()
        self.assertEqual("Administrator", self.hp_moonshot.username)
        self.assertEqual("password", self.hp_moonshot.password)

    def test_get_local_address(self):
        hex_array = self.make_hex_array()
        self.mock_check_output.return_value = " ".join(hex_array).encode()
        self.assertEqual(
            f"0x{hex_array[2]}", self.hp_moonshot._get_local_address()
        )
        self.assertThat(
            self.mock_check_output,
            MockCalledOnceWith(
                ["ipmitool", "raw", "0x2c", "1", "0"], timeout=60
            ),
        )

    def test_get_bmc_ip(self):
        ip = factory.make_ip_address()
        self.mock_check_output.return_value = f"IP Address : {ip}".encode()
        local_address = factory.make_name("local_address")

        self.assertEqual(ip, self.hp_moonshot.get_bmc_ip(local_address))
        self.assertThat(
            self.mock_check_output,
            MockCalledOnceWith(
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
                timeout=60,
            ),
        )

    def test_get_bmc_ip_none(self):
        self.mock_check_output.return_value = "IP Address : ".encode()
        local_address = factory.make_name("local_address")

        self.assertIsNone(self.hp_moonshot.get_bmc_ip(local_address))
        self.assertThat(
            self.mock_check_output,
            MockCalledOnceWith(
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
                timeout=60,
            ),
        )

    def test_get_credentials(self):
        self.hp_moonshot.username = "Administrator"
        self.hp_moonshot.password = "password"

        mock_get_local_address = self.patch(
            self.hp_moonshot, "_get_local_address"
        )
        local_address = factory.make_name("local_address")
        mock_get_local_address.return_value = local_address

        output = factory.make_string()
        self.mock_check_output.return_value = output.encode()

        mock_get_cartridge_address = self.patch(
            self.hp_moonshot, "_get_cartridge_address"
        )
        node_address = factory.make_name("node_address")
        mock_get_cartridge_address.return_value = node_address

        mock_get_channel_number = self.patch(
            self.hp_moonshot, "_get_channel_number"
        )
        local_chan = factory.make_name("local_chan")
        cartridge_chan = factory.make_name("cartridge_chan")
        mock_get_channel_number.side_effect = (local_chan, cartridge_chan)

        mock_get_bmc_ip = self.patch(self.hp_moonshot, "get_bmc_ip")
        ip = factory.make_ip_address()
        mock_get_bmc_ip.return_value = ip

        self.assertEqual(
            {
                "power_address": ip,
                "power_pass": "password",
                "power_user": "Administrator",
                "power_hwaddress": "-B %s -T %s -b %s -t %s -m 0x20"
                % (
                    cartridge_chan,
                    node_address,
                    local_chan,
                    local_address,
                ),
            },
            self.hp_moonshot.get_credentials(),
        )
        self.assertThat(mock_get_local_address, MockCalledOnce())
        self.assertThat(
            mock_get_cartridge_address, MockCalledOnceWith(local_address)
        )
        self.assertThat(
            self.mock_check_output,
            MockCalledOnceWith(
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
                timeout=60,
            ),
        )
        self.assertThat(
            mock_get_channel_number,
            MockCallsMatch(
                call(local_address, output), call(node_address, output)
            ),
        )


class TestWedge(MAASTestCase):
    def setUp(self):
        super().setUp()
        self.wedge = bmc_config.Wedge()
        self.mock_check_output = self.patch(bmc_config, "check_output")

    def test_power_type(self):
        self.assertEqual("wedge", self.wedge.power_type)

    def test_str(self):
        self.assertEqual("Facebook Wedge", str(self.wedge))

    def test_detect_known_switch(self):
        self.mock_check_output.side_effect = random.choice(
            [
                (b"Intel", b"EPGSVR", b""),
                (b"Joytech", b"Wedge-AC-F 20-001329", b""),
                (
                    b"To be filled by O.E.M.",
                    b"",
                    b"PCOM-B632VG-ECC-FB-ACCTON-D",
                ),
            ]
        )
        self.assertEqual("accton", self.wedge._detect_known_switch())

    def test_detect_known_switch_false(self):
        self.mock_check_output.side_effect = (
            factory.make_name("system-manufacturer").encode(),
            factory.make_name("system-product-name").encode(),
            factory.make_name("baseboard-product-name").encode(),
        )
        self.assertIsNone(self.wedge._detect_known_switch())

    def test_wedge_local_addr(self):
        self.mock_check_output.return_value = (
            b"8: eth0    inet fe80::ff:fe00:2/64 brd 10.0.0.255 scope global "
            b"eth0\\       valid_lft forever preferred_lft forever"
        )
        self.assertEquals("fe80::1%eth0", self.wedge._wedge_local_addr)
        # Call multiple times to verify caching
        self.assertEquals(
            self.wedge._wedge_local_addr, self.wedge._wedge_local_addr
        )
        self.assertThat(self.mock_check_output, MockCalledOnce())

    def test_detected_unknown_switch(self):
        self.patch(self.wedge, "_detect_known_switch").return_value = None
        self.assertFalse(self.wedge.detected())

    def test_detected_rest_api(self):
        self.patch(self.wedge, "_detect_known_switch").return_value = "accton"
        mock_urlopen = self.patch(bmc_config.urllib.request, "urlopen")
        mock_urlopen.return_value.read.return_value = (
            b"Wedge RESTful API Entry"
        )
        self.assertTrue(self.wedge.detected())

    def test_detected_ip(self):
        self.patch(self.wedge, "_detect_known_switch").return_value = "accton"
        self.patch(
            self.wedge, "get_bmc_ip"
        ).return_value = factory.make_ip_address()
        self.assertTrue(self.wedge.detected())

    def test_detected_false(self):
        self.patch(self.wedge, "_detect_known_switch").return_value = "accton"
        self.patch(self.wedge, "get_bmc_ip").return_value = None
        self.assertFalse(self.wedge.detected())

    def test_get_bmc_ip(self):
        self.mock_check_output.return_value = (
            b"8: eth0    inet fe80::ff:fe00:2/64 brd 10.0.0.255 scope global "
            b"eth0\\       valid_lft forever preferred_lft forever"
        )
        mock_ssh_client = self.patch(bmc_config, "SSHClient")
        mock_client = mock_ssh_client.return_value
        mock_client.set_missing_host_key_policy = MagicMock()
        mock_client.connect = MagicMock()
        mock_stdout = MagicMock()
        mock_stdout.read.return_value = (
            b"1: lo    inet 127.0.0.1/8 scope host lo\\       "
            b"valid_lft forever preferred_lft forever"
            b"\n"
            b"8: eth0    inet 10.0.0.10/24 brd 10.0.0.255 scope global "
            b"eth0\\       valid_lft forever preferred_lft forever"
            b"\n"
            b"10: eth1    inet 192.168.122.78/24 brd 192.168.122.255 scope "
            b"global dynamic eth1\\       valid_lft 3348sec preferred_lft "
            b"3348sec"
        )
        mock_client.exec_command.return_value = None, mock_stdout, None

        self.assertEquals("10.0.0.10", self.wedge.get_bmc_ip())
        # Call multiple times to verify caching
        self.assertEquals(self.wedge.get_bmc_ip(), self.wedge.get_bmc_ip())
        self.assertThat(mock_ssh_client, MockCalledOnce())
        self.assertThat(
            mock_client.set_missing_host_key_policy,
            MockCalledOnceWith(bmc_config.IgnoreHostKeyPolicy),
        )
        self.assertThat(
            mock_client.connect,
            MockCalledOnceWith(
                "fe80::1%eth0", username="root", password="0penBmc"
            ),
        )

    def test_get_bmc_ip_none(self):
        self.assertIsNone(self.wedge.get_bmc_ip())

    def test_get_credentials(self):
        ip = factory.make_ip_address()
        self.patch(self.wedge, "get_bmc_ip").return_value = ip
        self.assertEqual(
            {
                "power_address": ip,
                "power_user": "root",
                "power_pass": "0penBmc",
            },
            self.wedge.get_credentials(),
        )


class TestDetectAndConfigure(MAASTestCase):
    def setUp(self):
        super().setUp()
        self.patch(bmc_config, "print")

    def test_finds_first(self):
        bmc_config_path = os.path.join(
            self.useFixture(TempDirectory()).path, "bmc-config.yaml"
        )
        creds = {
            factory.make_name("key"): factory.make_name("value")
            for _ in range(6)
        }
        args = MagicMock()
        args.user = factory.make_name("user")
        args.password = factory.make_name("password")
        self.patch(bmc_config.HPMoonshot, "detected").return_value = True
        self.patch(
            bmc_config.HPMoonshot, "get_credentials"
        ).return_value = creds

        bmc_config.detect_and_configure(args, bmc_config_path)

        with open(bmc_config_path, "r") as f:
            self.assertEqual(
                {"power_type": "moonshot", **creds}, yaml.safe_load(f)
            )

    def test_finds_second(self):
        bmc_config_path = os.path.join(
            self.useFixture(TempDirectory()).path, "bmc-config.yaml"
        )
        creds = {
            factory.make_name("key"): factory.make_name("value")
            for _ in range(6)
        }
        args = MagicMock()
        args.user = factory.make_name("user")
        args.password = factory.make_name("password")
        self.patch(bmc_config.HPMoonshot, "detected").return_value = False
        self.patch(bmc_config.IPMI, "detected").return_value = True
        self.patch(bmc_config.IPMI, "configure")
        self.patch(bmc_config.IPMI, "add_bmc_user")
        self.patch(bmc_config.IPMI, "get_credentials").return_value = creds

        bmc_config.detect_and_configure(args, bmc_config_path)

        with open(bmc_config_path, "r") as f:
            self.assertEqual(
                {"power_type": "ipmi", **creds}, yaml.safe_load(f)
            )

    def test_finds_nothing(self):
        bmc_config_path = os.path.join(
            self.useFixture(TempDirectory()).path, "bmc-config.yaml"
        )
        args = MagicMock()
        args.user = factory.make_name("user")
        args.password = factory.make_name("password")
        self.patch(bmc_config.HPMoonshot, "detected").return_value = False
        self.patch(bmc_config.IPMI, "detected").return_value = False
        self.patch(bmc_config.Wedge, "detected").return_value = False

        bmc_config.detect_and_configure(args, bmc_config_path)

        self.assertFalse(os.path.exists(bmc_config_path))
        self.assertThat(bmc_config.HPMoonshot.detected, MockCalledOnce())
        self.assertThat(bmc_config.IPMI.detected, MockCalledOnce())
        self.assertThat(bmc_config.Wedge.detected, MockCalledOnce())


class TestMain(MAASTestCase):
    def setUp(self):
        super().setUp()
        self.mock_check_call = self.patch(bmc_config, "check_call")
        self.patch(bmc_config.argparse.ArgumentParser, "parse_args")
        self.patch(bmc_config, "print")

    def test_checks_bmc_config_path_env_var_set(self):
        self.assertRaises(SystemExit, bmc_config.main)

    def test_skips_if_bmc_config_exists(self):
        self.patch(bmc_config.os.environ, "get")
        self.patch(bmc_config.os.path, "exists").return_value = True
        mock_exit_skipped = self.patch(bmc_config, "exit_skipped")

        bmc_config.main()

        self.assertThat(mock_exit_skipped, MockCalledOnce())

    def test_runs_if_not_on_vm(self):
        self.patch(bmc_config.os.environ, "get")
        self.patch(bmc_config.os.path, "exists").return_value = False
        self.mock_check_call.side_effect = CalledProcessError(
            1, ["systemd-detect-virt", "-q"]
        )
        mock_run = self.patch(bmc_config, "run")
        mock_detect_and_configure = self.patch(
            bmc_config, "detect_and_configure"
        )

        bmc_config.main()

        self.assertThat(
            self.mock_check_call,
            MockCalledOnceWith(["systemd-detect-virt", "-q"], timeout=60),
        )
        self.assertThat(
            mock_run,
            MockCallsMatch(
                call(
                    ["sudo", "-E", "modprobe", "ipmi_msghandler"], timeout=60
                ),
                call(["sudo", "-E", "modprobe", "ipmi_devintf"], timeout=60),
                call(["sudo", "-E", "modprobe", "ipmi_si"], timeout=60),
                call(["sudo", "-E", "modprobe", "ipmi_ssif"], timeout=60),
                call(["sudo", "-E", "udevadm", "settle"], timeout=60),
            ),
        )
        self.assertThat(mock_detect_and_configure, MockCalledOnce())

    def test_does_nothing_if_on_vm(self):
        self.patch(bmc_config.os.environ, "get")
        self.patch(bmc_config.os.path, "exists").return_value = False
        mock_detect_and_configure = self.patch(
            bmc_config, "detect_and_configure"
        )
        mock_exit_skipped = self.patch(bmc_config, "exit_skipped")

        bmc_config.main()

        self.assertThat(mock_detect_and_configure, MockNotCalled())
        self.assertThat(mock_exit_skipped, MockCalledOnce())
