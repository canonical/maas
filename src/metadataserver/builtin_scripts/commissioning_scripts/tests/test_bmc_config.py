# Copyright 2020-2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from collections import OrderedDict
import io
from json.decoder import JSONDecodeError
import os
import random
import re
from subprocess import CalledProcessError, DEVNULL, TimeoutExpired
import tempfile
import textwrap
from unittest.mock import call, MagicMock, patch
import urllib
import urllib.request

import yaml

from maasserver.testing.commissioning import DeviceType, FakeCommissioningData
from maasserver.testing.factory import factory
from maastesting.fixtures import TempDirectory
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
        mock_open.assert_called_once_with(result_path, "w")
        mock_yaml_safe_dump.assert_called_once_with(
            {"status": "skipped"}, mock_open.return_value
        )

    def test_result_path_not_defined(self):
        mock_open = self.patch(bmc_config, "open")

        self.assertRaises(SystemExit, bmc_config.exit_skipped)
        mock_open.assert_not_called()


class TestIPMI(MAASTestCase):
    def setUp(self):
        super().setUp()
        self.username = factory.make_name("username")
        self.password = factory.make_name("password")
        self.ipmi = bmc_config.IPMI(self.username, self.password)
        self.mock_check_output = self.patch(bmc_config, "check_output")
        self.mock_check_call = self.patch(bmc_config, "check_call")
        self.mock_run = self.patch(bmc_config, "run")
        self.mock_sleep = self.patch(bmc_config.time, "sleep")
        self.mock_print = self.patch(bmc_config, "print")

    def test_power_type(self):
        self.assertEqual("ipmi", self.ipmi.power_type)

    def test_str(self):
        self.assertEqual("IPMI", str(self.ipmi))

    def test_bmc_get_config(self):
        self.mock_run.return_value.stdout = b"""
# Section1 comment
Section Section1
        ## Comment 1
        Key1                        value1
        ## Comment 2
        Key2                        value2
        ## Comment 3
        Key3
EndSection
# Section2 comment
Section Section2
        ## Comment 1
        Key1                        value1
        ## Comment 2
        Key2                        value2
        ## Comment 3
        Key3
EndSection
# Key value comment
key1         value1
key2
"""
        self.ipmi._bmc_get_config()
        self.assertEqual(
            {
                "Section1": {
                    "Key1": "value1",
                    "Key2": "value2",
                    "Key3": "",
                },
                "Section2": {
                    "Key1": "value1",
                    "Key2": "value2",
                    "Key3": "",
                },
                "key1": "value1",
                "key2": "",
            },
            self.ipmi._bmc_config,
        )

    def test_bmc_get_config_section(self):
        self.mock_run.return_value.stdout = b"""
# Section1 comment
Section Section1
        ## Comment 1
        Key1                        value5
        ## Comment 2
        Key2                        value6
        ## Comment 3
        Key3                        value7
EndSection
"""
        self.ipmi._bmc_config = {
            "Section1": {
                "Key1": "value1",
                "Key2": "value2",
                "Key3": "",
            },
            "Section2": {
                "Key1": "value1",
                "Key2": "value2",
                "Key3": "",
            },
            "key1": "value1",
            "key2": "",
        }
        self.ipmi._bmc_get_config("Section1")
        self.assertEqual(
            {
                "Section1": {
                    "Key1": "value5",
                    "Key2": "value6",
                    "Key3": "value7",
                },
                "Section2": {
                    "Key1": "value1",
                    "Key2": "value2",
                    "Key3": "",
                },
                "key1": "value1",
                "key2": "",
            },
            self.ipmi._bmc_config,
        )

    def test_bmc_set(self):
        section = factory.make_name("section")
        key = factory.make_name("key")
        value = factory.make_name("value")
        self.ipmi._bmc_set(section, key, value)

        self.mock_check_call.assert_called_once_with(
            [
                "bmc-config",
                "--commit",
                f"--key-pair={section}:{key}={value}",
            ],
            timeout=bmc_config.COMMAND_TIMEOUT,
        )
        self.assertEqual({section: {key: value}}, self.ipmi._bmc_config)

    def test_bmc_set_keys(self):
        password = factory.make_string()
        self.ipmi._bmc_config = {
            "User2": {
                "Username": "maas",
                "Password": password,
                "Lan_Enable_Link_Auth": "Yes",
                "SOL_Payload_Access": "No",
            },
        }
        self.ipmi._bmc_set_keys(
            "User2",
            [
                "Lan_Enable_Link_Auth",
                "SOL_Payload_Access",
                "Serial_Enable_Link_Auth",
            ],
            "Yes",
        )
        # Only called once because there is only one value that exists
        # that needs to be updated.
        self.mock_check_call.assert_called_once_with(
            [
                "bmc-config",
                "--commit",
                "--key-pair=User2:SOL_Payload_Access=Yes",
            ],
            timeout=bmc_config.COMMAND_TIMEOUT,
        )
        # Verify cache has been updated
        self.assertEqual(
            {
                "User2": {
                    "Username": "maas",
                    "Password": password,
                    "Lan_Enable_Link_Auth": "Yes",
                    "SOL_Payload_Access": "Yes",
                },
            },
            self.ipmi._bmc_config,
        )

    def test_bmc_set_keys_warns_on_no_section(self):
        self.ipmi._bmc_config = {}
        self.ipmi._bmc_set_keys(
            factory.make_name("section"),
            [factory.make_name("key") for _ in range(3)],
            factory.make_name("value"),
        )
        self.mock_print.assert_called_once()

    def test_bmc_set_keys_warns_on_setting_failure(self):
        self.mock_check_call.side_effect = None
        self.ipmi._bmc_config = {}
        self.ipmi._bmc_set_keys(
            factory.make_name("section"),
            [factory.make_name("key") for _ in range(3)],
            factory.make_name("value"),
        )
        self.mock_print.assert_called_once()

    def test_detected_true(self):
        mock_get_ipmi_locate_output = self.patch(
            bmc_config, "_get_ipmi_locate_output"
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
            bmc_config, "_get_ipmi_locate_output"
        )
        mock_get_ipmi_locate_output.return_value = factory.make_string()
        self.assertFalse(self.ipmi.detected())
        self.mock_print.assert_called_once_with(
            "DEBUG: Could not find IPMI version or an IPMI device in /dev"
        )

    def test_detected_command_exception(self):
        mock_get_ipmi_locate_output = self.patch(
            bmc_config, "_get_ipmi_locate_output"
        )
        mock_get_ipmi_locate_output.side_effect = CalledProcessError(
            cmd=["ipmi-locate"], returncode=1
        )

        self.assertFalse(self.ipmi.detected())
        self.mock_print.assert_called_once_with(
            "DEBUG: Exception occurred when trying to execute ipmi-locate command: "
            "Command '['ipmi-locate']' returned non-zero exit status 1."
        )

    def test_generate_random_password(self):
        for attempt in range(0, 100):  # noqa: B007
            password = self.ipmi._generate_random_password()
            self.assertTrue(10 <= len(password) <= 15)
            self.assertIsNotNone(
                re.match(r"^[\da-z]+$", password, re.IGNORECASE), password
            )

    def test_generate_random_password_with_length(self):
        for attempt in range(0, 10):  # noqa: B007
            password = self.ipmi._generate_random_password(
                min_length=16, max_length=20
            )
            assert 16 <= len(password) <= 20
            assert (
                re.match(r"^[\da-z]+$", password, re.IGNORECASE) is not None
            ), password

    def test_generate_random_password_with_special_chars(self):
        # Huawei and Lenovo use a non-standard IPMI password policy
        special_chars = set("!\"#$%&'()*+-,./:;<=>?@[]^_`{|}~")
        for attempt in range(0, 100):  # noqa: B007
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
        self.ipmi._privilege_level, privilege_level = random.choice(
            [
                ("USER", "User"),
                ("OPERATOR", "Operator"),
                ("ADMIN", "Administrator"),
            ]
        )
        self.assertEqual(
            OrderedDict(
                (
                    ("Username", username),
                    ("Password", password),
                    ("Enable_User", "Yes"),
                    ("Lan_Privilege_Limit", privilege_level),
                    ("Lan_Enable_IPMI_Msgs", "Yes"),
                )
            ),
            self.ipmi._make_ipmi_user_settings(username, password),
        )

    def test_pick_user_number_finds_empty(self):
        self.ipmi._bmc_config = {
            "User1": {},
            "User2": {"Username": factory.make_name("username")},
            "User3": random.choice([{}, {"Username": "(Empty User)"}]),
            "User4": {"Username": factory.make_name("username")},
            "User5": random.choice([{}, {"Username": "(Empty User)"}]),
        }
        self.assertEqual("User3", self.ipmi._pick_user_number("maas"))

    def test_pick_user_number_finds_existing(self):
        search_username = factory.make_name("search_username")
        self.ipmi._bmc_config = {
            "User1": {},
            "User2": {"Username": factory.make_name("username")},
            "User3": random.choice([{}, {"Username": "(Empty User)"}]),
            "User4": {"Username": search_username},
            "User5": random.choice([{}, {"Username": "(Empty User)"}]),
        }
        self.assertEqual("User4", self.ipmi._pick_user_number(search_username))

    def test_add_bmc_user(self):
        mock_bmc_set = self.patch(self.ipmi, "_bmc_set")
        mock_bmc_set_keys = self.patch(self.ipmi, "_bmc_set_keys")
        self.ipmi._bmc_config = {
            "User1": {},
            "User2": {
                "Username": "",
                "Password": factory.make_name("password"),
                "Enable_User": "Yes",
                "Lan_Privilege_Limit": "Administrator",
                "Lan_Enable_IPMI_Msgs": "Yes",
            },
        }
        self.ipmi._privilege_level = "OPERATOR"

        self.ipmi.add_bmc_user()

        self.assertEqual(self.username, self.ipmi.username)
        self.assertEqual(self.password, self.ipmi.password)
        # Verify bmc_set is only called for values that have changed

        mock_bmc_set.assert_has_calls(
            [
                call("User2", "Username", self.username),
                call("User2", "Password", self.password),
                call("User2", "Lan_Privilege_Limit", "Operator"),
            ],
        )

        mock_bmc_set_keys.assert_called_once_with(
            "User2",
            [
                "Lan_Enable_Link_Auth",
                "SOL_Payload_Access",
                "Serial_Enable_Link_Auth",
            ],
            "Yes",
        )

    def test_add_bmc_user_rand_password(self):
        self.ipmi.username = None
        self.ipmi.password = None
        password = factory.make_name("password")
        stronger_password = factory.make_name("strongpassword")
        password_w_spec_chars = factory.make_name("password_w_spec_chars")
        self.patch(self.ipmi, "_generate_random_password").side_effect = (
            password,
            stronger_password,
            password_w_spec_chars,
        )
        mock_bmc_set = self.patch(self.ipmi, "_bmc_set")
        mock_bmc_set_keys = self.patch(self.ipmi, "_bmc_set_keys")
        self.ipmi._bmc_config = {
            "User1": {},
            "User2": {
                "Username": "",
                "Password": factory.make_name("password"),
                "Enable_User": "Yes",
                "Lan_Privilege_Limit": "Administrator",
                "Lan_Enable_IPMI_Msgs": "Yes",
            },
        }
        self.ipmi._privilege_level = "OPERATOR"

        self.ipmi.add_bmc_user()

        self.assertEqual("maas", self.ipmi.username)
        self.assertEqual(password, self.ipmi.password)
        # Verify bmc_set is only called for values that have changed
        mock_bmc_set.assert_has_calls(
            [
                call("User2", "Username", "maas"),
                call("User2", "Password", password),
                call("User2", "Lan_Privilege_Limit", "Operator"),
            ]
        )
        mock_bmc_set_keys.assert_called_once_with(
            "User2",
            [
                "Lan_Enable_Link_Auth",
                "SOL_Payload_Access",
                "Serial_Enable_Link_Auth",
            ],
            "Yes",
        )

    def test_add_bmc_user_rand_password_with_special_chars(self):
        self.ipmi.username = None
        self.ipmi.password = None
        password = factory.make_name("password")
        stronger_password = factory.make_name("strongpassword")
        password_w_spec_chars = factory.make_name("password_w_spec_chars")
        self.patch(self.ipmi, "_generate_random_password").side_effect = (
            password,
            stronger_password,
            password_w_spec_chars,
        )
        mock_bmc_set = self.patch(self.ipmi, "_bmc_set")
        mock_bmc_set.side_effect = (
            None,
            factory.make_exception(),
            None,
            factory.make_exception(),
            None,
            None,
            None,
        )
        mock_bmc_set_keys = self.patch(self.ipmi, "_bmc_set_keys")
        self.ipmi._bmc_config = {
            "User1": {},
            "User2": {
                "Username": "",
                "Password": factory.make_name("password"),
                "Enable_User": "Yes",
                "Lan_Privilege_Limit": "Administrator",
                "Lan_Enable_IPMI_Msgs": "Yes",
            },
        }
        self.ipmi._privilege_level = "OPERATOR"

        self.ipmi.add_bmc_user()

        self.assertEqual("maas", self.ipmi.username)
        self.assertEqual(password_w_spec_chars, self.ipmi.password)
        # Verify bmc_set is only called for values that have changed
        mock_bmc_set.assert_has_calls(
            [
                call("User2", "Username", "maas"),
                call("User2", "Password", password),
                call("User2", "Username", "maas"),
                call("User2", "Password", stronger_password),
                call("User2", "Username", "maas"),
                call("User2", "Password", password_w_spec_chars),
                call("User2", "Lan_Privilege_Limit", "Operator"),
            ]
        )
        mock_bmc_set_keys.assert_called_once_with(
            "User2",
            [
                "Lan_Enable_Link_Auth",
                "SOL_Payload_Access",
                "Serial_Enable_Link_Auth",
            ],
            "Yes",
        )

    def test_add_bmc_user_fails(self):
        mock_bmc_set = self.patch(self.ipmi, "_bmc_set")
        mock_bmc_set.side_effect = factory.make_exception()

        self.assertRaises(SystemExit, self.ipmi.add_bmc_user)

    def test_set_ipmi_lan_channel_setting_verifies(self):
        for channel in [
            "Lan_Channel",
            "Lan_Channel_Channel_1",
            "Lan_Channel_Channel_2",
            "Lan_Channel_Channel_3",
        ]:
            self.ipmi._bmc_config = {
                channel: {
                    "Volatile_Access_Mode": "Always_Available",
                    "Non_Volatile_Access_Mode": "Always_Available",
                },
            }
            mock_bmc_set = self.patch(self.ipmi, "_bmc_set")
            mock_bmc_set_keys = self.patch(self.ipmi, "_bmc_set_keys")
            self.ipmi._config_ipmi_lan_channel_settings()
            self.assertFalse(mock_bmc_set.called)
            mock_bmc_set_keys.assert_called_once_with(
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

    def test_set_ipmi_lan_channel_setting_enables(self):
        for channel in [
            "Lan_Channel",
            "Lan_Channel_Channel_1",
            "Lan_Channel_Channel_2",
            "Lan_Channel_Channel_3",
        ]:
            self.ipmi._bmc_config = {
                channel: {
                    "Volatile_Access_Mode": "Disabled",
                    "Non_Volatile_Access_Mode": "Pre_Boot_only",
                },
            }
            mock_bmc_set = self.patch(self.ipmi, "_bmc_set")
            mock_bmc_set_keys = self.patch(self.ipmi, "_bmc_set_keys")
            self.ipmi._config_ipmi_lan_channel_settings()
            mock_bmc_set.assert_has_calls(
                (
                    call(channel, "Volatile_Access_Mode", "Always_Available"),
                    call(
                        channel,
                        "Non_Volatile_Access_Mode",
                        "Always_Available",
                    ),
                )
            )
            mock_bmc_set_keys.assert_called_once_with(
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

    def test_config_lan_conf_auth(self):
        self.ipmi._bmc_config = {"Lan_Channel_Auth": {}}
        mock_bmc_set_keys = self.patch(self.ipmi, "_bmc_set_keys")

        self.ipmi._config_lan_conf_auth()

        mock_bmc_set_keys.assert_has_calls(
            [
                call(
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
                ),
                call("Lan_Channel_Auth", ["SOL_Payload_Access"], "Yes"),
            ]
        )

    def test_config_lan_conf_auth_does_nothing_if_missing(self):
        mock_bmc_set_keys = self.patch(self.ipmi, "_bmc_set_keys")

        self.ipmi._config_lan_conf_auth()

        mock_bmc_set_keys.assert_not_called()

    def test_config_kg_set(self):
        mock_bmc_set = self.patch(self.ipmi, "_bmc_set")
        kg = factory.make_name("kg")
        self.ipmi._kg = kg

        self.ipmi._config_kg()

        mock_bmc_set.assert_called_once_with(
            "Lan_Conf_Security_Keys", "K_G", kg
        )
        self.assertEqual(kg, self.ipmi._kg)

    def test_config_kg_set_does_nothing_if_already_set(self):
        kg = factory.make_name("kg")
        self.ipmi._bmc_config = {"Lan_Conf_Security_Keys": {"K_G": kg}}
        mock_bmc_set = self.patch(self.ipmi, "_bmc_set")
        self.ipmi._kg = kg

        self.ipmi._config_kg()

        mock_bmc_set.assert_not_called()
        self.assertEqual(kg, self.ipmi._kg)

    def test_config_kg_set_errors(self):
        mock_bmc_set = self.patch(self.ipmi, "_bmc_set")
        cmd = [factory.make_name("cmd")]
        exception = random.choice(
            [
                CalledProcessError(cmd=cmd, returncode=random.randint(1, 255)),
                TimeoutExpired(cmd=cmd, timeout=random.randint(1, 100)),
            ]
        )
        mock_bmc_set.side_effect = exception
        kg = factory.make_name("kg")
        self.ipmi._kg = kg

        self.assertRaises(type(exception), self.ipmi._config_kg)

        mock_bmc_set.assert_called_once_with(
            "Lan_Conf_Security_Keys", "K_G", kg
        )
        self.assertEqual("", self.ipmi._kg)

    def test_config_kg_detect(self):
        kg = factory.make_name("kg")
        self.ipmi._bmc_config = {"Lan_Conf_Security_Keys": {"K_G": kg}}

        self.ipmi._config_kg()

        self.assertEqual(kg, self.ipmi._kg)

    def test_config_kg_detects_nothing(self):
        self.ipmi._bmc_config = {
            "Lan_Conf_Security_Keys": {
                "K_G": "0x0000000000000000000000000000000000000000"
            }
        }

        self.ipmi._config_kg()

        self.assertEqual("", self.ipmi._kg)

    def test_configure(self):
        mock_bmc_get_config = self.patch(self.ipmi, "_bmc_get_config")
        mock_config_ipmi_lan_channel_settings = self.patch(
            self.ipmi, "_config_ipmi_lan_channel_settings"
        )
        mock_config_lang_conf_auth = self.patch(
            self.ipmi, "_config_lan_conf_auth"
        )
        mock_config_kg = self.patch(self.ipmi, "_config_kg")
        mock_bmc_set_keys = self.patch(self.ipmi, "_bmc_set_keys")
        mock_check_ciphers_enabled = self.patch(
            self.ipmi, "_check_ciphers_enabled"
        )

        self.ipmi.configure()

        mock_bmc_get_config.assert_called_once()
        mock_check_ciphers_enabled.assert_called_once()

        mock_config_ipmi_lan_channel_settings.assert_called_once()
        mock_config_lang_conf_auth.assert_called_once()
        mock_config_kg.assert_called_once()
        mock_bmc_set_keys.assert_has_calls(
            [
                call(
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
                ),
                call(
                    "SOL_Conf",
                    [
                        "Force_SOL_Payload_Authentication",
                        "Force_SOL_Payload_Encryption",
                    ],
                    "Yes",
                ),
            ]
        )

    def test_get_bmc_ipv4(self):
        ip = factory.make_ipv4_address()
        mac_address = factory.make_mac_address()
        self.ipmi._bmc_config = {
            "Lan_Conf": {
                "IP_Address": ip,
                "MAC_Address": mac_address,
            }
        }
        self.assertEqual(
            ("Lan_Conf", ip, mac_address), self.ipmi._get_bmc_ip()
        )

    def test_get_bmc_ipv6_static(self):
        ip = factory.make_ipv6_address()
        mac_address = factory.make_mac_address()
        self.ipmi._bmc_config = {
            "Lan6_Conf": {
                "IPv6_Static_Addresses": ip,
                "MAC_Address": mac_address,
            }
        }
        self.assertEqual(
            ("Lan6_Conf", f"[{ip}]", mac_address), self.ipmi._get_bmc_ip()
        )

    def test_get_bmc_ipv6_dynamic(self):
        ip = factory.make_ipv6_address()
        mac_address = factory.make_mac_address()
        self.ipmi._bmc_config = {
            "Lan6_Conf": {
                "IPv6_Dynamic_Addresses": ip,
                "MAC_Address": mac_address,
            }
        }
        self.assertEqual(
            ("Lan6_Conf", f"[{ip}]", mac_address), self.ipmi._get_bmc_ip()
        )

    def test_get_bmc_ipv6_gets_mac_From_ipv4(self):
        ip = factory.make_ipv6_address()
        mac_address = factory.make_mac_address()
        self.ipmi._bmc_config = {
            "Lan_Conf": {"MAC_Address": mac_address},
            "Lan6_Conf": {"IPv6_Dynamic_Addresses": ip},
        }
        self.assertEqual(
            ("Lan6_Conf", f"[{ip}]", mac_address), self.ipmi._get_bmc_ip()
        )

    def test_get_bmc_ip_finds_none(self):
        self.patch(self.ipmi, "_bmc_get").return_value = ""
        self.assertEqual((None, None, None), self.ipmi._get_bmc_ip())

    def test_get_bmc_ip(self):
        ip = factory.make_ip_address()
        mac_address = factory.make_mac_address()
        mock_bmc_set = self.patch(self.ipmi, "_bmc_set")
        mock_get_bmc_ip = self.patch(self.ipmi, "_get_bmc_ip")
        mock_get_bmc_ip.return_value = None, ip, mac_address

        self.assertEqual((ip, mac_address), self.ipmi.get_bmc_ip())
        mock_bmc_set.assert_not_called()
        mock_get_bmc_ip.assert_called_once_with()

    def test_get_bmc_ip_enables_static(self):
        ip = factory.make_ip_address()
        mac_address = factory.make_mac_address()
        mock_bmc_set = self.patch(self.ipmi, "_bmc_set")
        mock_get_bmc_ip = self.patch(self.ipmi, "_get_bmc_ip")
        mock_get_bmc_ip.side_effect = (
            ("Lan_Conf", None, mac_address),
            ("Lan_Conf", None, mac_address),
            ("Lan_Conf", ip, mac_address),
        )

        self.assertEqual((ip, mac_address), self.ipmi.get_bmc_ip())
        mock_bmc_set.assert_called_once_with(
            "Lan_Conf", "IP_Address_Source", "Static"
        )
        mock_get_bmc_ip.assert_has_calls([call(), call(True), call(True)])

    def test_get_bmc_ip_enables_dynamic(self):
        ip = factory.make_ip_address()
        mac_address = factory.make_mac_address()
        mock_bmc_set = self.patch(self.ipmi, "_bmc_set")
        mock_get_bmc_ip = self.patch(self.ipmi, "_get_bmc_ip")
        mock_get_bmc_ip.side_effect = (
            *[("Lan_Conf", None, mac_address) for _ in range(8)],
            ("Lan_Conf", ip, mac_address),
        )

        self.assertEqual((ip, mac_address), self.ipmi.get_bmc_ip())
        mock_bmc_set.assert_has_calls(
            [
                call("Lan_Conf", "IP_Address_Source", "Static"),
                call("Lan_Conf", "IP_Address_Source", "Use_DHCP"),
            ]
        )

        mock_get_bmc_ip.assert_has_calls(
            [call(), *[call(True) for _ in range(8)]]
        )

    def test_get_bmc_ip_fails(self):
        mock_bmc_set = self.patch(self.ipmi, "_bmc_set")
        mock_get_bmc_ip = self.patch(self.ipmi, "_get_bmc_ip")
        mock_get_bmc_ip.return_value = ("Lan_Conf", None, None)

        self.assertRaises(SystemExit, self.ipmi.get_bmc_ip)
        mock_bmc_set.assert_has_calls(
            [
                call("Lan_Conf", "IP_Address_Source", "Static"),
                call("Lan_Conf", "IP_Address_Source", "Use_DHCP"),
            ]
        )
        mock_get_bmc_ip.assert_has_calls(
            [call(), *[call(True) for _ in range(12)]],
        )

    def test_get_credentials_lan_new(self):
        self.ipmi.username = factory.make_name("username")
        self.ipmi.password = factory.make_name("password")
        self.patch(
            bmc_config, "_get_ipmi_locate_output"
        ).return_value = "IPMI Version: 2.0"
        self.patch(bmc_config.platform, "machine").return_value = "ppc64le"
        self.patch(bmc_config.os.path, "isdir").return_value = True
        ip = factory.make_ip_address()
        mac_address = factory.make_mac_address()
        self.patch(self.ipmi, "get_bmc_ip").return_value = (ip, mac_address)

        self.assertEqual(
            {
                "power_address": ip,
                "power_pass": self.ipmi.password,
                "power_user": self.ipmi.username,
                "power_driver": "LAN_2_0",
                "power_boot_type": "efi",
                "k_g": "",
                "cipher_suite_id": "3",
                "privilege_level": "",
                "mac_address": mac_address,
            },
            self.ipmi.get_credentials(),
        )

    def test_get_credentials_lan_old(self):
        self.ipmi.username = factory.make_name("username")
        self.ipmi.password = factory.make_name("password")
        self.patch(
            bmc_config, "_get_ipmi_locate_output"
        ).return_value = "IPMI Version: 1.0"
        self.patch(bmc_config.platform, "machine").return_value = "x86_64"
        self.patch(bmc_config.os.path, "isdir").return_value = False
        ip = factory.make_ip_address()
        mac_address = factory.make_mac_address()
        self.patch(self.ipmi, "get_bmc_ip").return_value = (ip, mac_address)

        self.assertEqual(
            {
                "power_address": ip,
                "power_pass": self.ipmi.password,
                "power_user": self.ipmi.username,
                "power_driver": "LAN",
                "power_boot_type": "auto",
                "k_g": "",
                "cipher_suite_id": "3",
                "privilege_level": "",
                "mac_address": mac_address,
            },
            self.ipmi.get_credentials(),
        )

    def test_get_crendentials_cipher_id_set(self):
        self.ipmi.username = factory.make_name("username")
        self.ipmi.password = factory.make_name("password")
        self.ipmi._cipher_suite_id = "17"
        self.patch(
            bmc_config, "_get_ipmi_locate_output"
        ).return_value = "IPMI Version: 1.0"
        self.patch(bmc_config.platform, "machine").return_value = "x86_64"
        self.patch(bmc_config.os.path, "isdir").return_value = False
        ip = factory.make_ip_address()
        mac_address = factory.make_mac_address()
        self.patch(self.ipmi, "get_bmc_ip").return_value = (ip, mac_address)

        self.assertEqual(
            {
                "power_address": ip,
                "power_pass": self.ipmi.password,
                "power_user": self.ipmi.username,
                "power_driver": "LAN",
                "power_boot_type": "auto",
                "k_g": "",
                "cipher_suite_id": "17",
                "privilege_level": "",
                "mac_address": mac_address,
            },
            self.ipmi.get_credentials(),
        )

    def test_ciphers_detects_enabled(self):
        self.ipmi._bmc_config = {
            "Rmcpplus_Conf_Privilege": {
                "Maximum_Privilege_Cipher_Suite_Id_0": "Unused",
                "Maximum_Privilege_Cipher_Suite_Id_1": "Unused",
                "Maximum_Privilege_Cipher_Suite_Id_2": "Unused",
                "Maximum_Privilege_Cipher_Suite_Id_3": "Administrator",
                "Maximum_Privilege_Cipher_Suite_Id_4": "Unused",
            },
        }
        self.assertTrue(self.ipmi._check_ciphers_enabled())

    def test_ciphers_empty(self):
        self.ipmi._bmc_config = {
            "Rmcpplus_Conf_Privilege": {},
        }
        self.assertTrue(self.ipmi._check_ciphers_enabled())

    def test_ciphers_list_nonexistent(self):
        self.ipmi._bmc_config = {}
        self.assertTrue(self.ipmi._check_ciphers_enabled())

    def test_ciphers_not_enable(self):
        self.ipmi._bmc_config = {
            "Rmcpplus_Conf_Privilege": {
                "Maximum_Privilege_Cipher_Suite_Id_0": "Unused",
                "Maximum_Privilege_Cipher_Suite_Id_3": "Operator",
                "Maximum_Privilege_Cipher_Suite_Id_4": "User",
                "Maximum_Privilege_Cipher_Suite_Id_5": "Unused",
            },
        }
        self.assertFalse(self.ipmi._check_ciphers_enabled())


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
        self.mock_check_output.assert_called_once_with(
            ["ipmitool", "raw", "06", "01"],
            timeout=bmc_config.COMMAND_TIMEOUT,
            stderr=DEVNULL,
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
        self.mock_check_output.assert_called_once_with(
            ["ipmitool", "raw", "0x2c", "1", "0"],
            timeout=bmc_config.COMMAND_TIMEOUT,
        )

    def test_get_bmc_ip(self):
        ip = factory.make_ip_address()
        self.mock_check_output.return_value = f"IP Address : {ip}".encode()
        local_address = factory.make_name("local_address")

        self.assertEqual(ip, self.hp_moonshot.get_bmc_ip(local_address))
        self.mock_check_output.assert_called_once_with(
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
            timeout=bmc_config.COMMAND_TIMEOUT,
        )

    def test_get_bmc_ip_none(self):
        self.mock_check_output.return_value = b"IP Address : "
        local_address = factory.make_name("local_address")

        self.assertIsNone(self.hp_moonshot.get_bmc_ip(local_address))
        self.mock_check_output.assert_called_once_with(
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
            timeout=bmc_config.COMMAND_TIMEOUT,
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
        mock_get_local_address.assert_called_once()
        mock_get_cartridge_address.assert_called_once_with(local_address)
        self.mock_check_output.assert_called_once_with(
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
            timeout=bmc_config.COMMAND_TIMEOUT,
        )
        mock_get_channel_number.assert_has_calls(
            [call(local_address, output), call(node_address, output)]
        )

    def test_detected_false_when_ipmitool_call_error(self):
        self.mock_check_output.side_effect = factory.make_exception(
            CalledProcessError(
                cmd=["ipmitool", "raw", "06", "01"], returncode=1
            )
        )

        self.assertFalse(self.hp_moonshot.detected())

        self.mock_print.assert_called_once_with(
            "DEBUG: Exception occurred executing ipmitool command: "
            "Command '['ipmitool', 'raw', '06', '01']' "
            "returned non-zero exit status 1."
        )
        self.mock_check_output.assert_called_once_with(
            ["ipmitool", "raw", "06", "01"],
            timeout=bmc_config.COMMAND_TIMEOUT,
            stderr=DEVNULL,
        )

    def test_detected_false_when_bmc_not_moonshot(self):
        self.mock_check_output.return_value = " ".join(
            ["15"] + self.make_hex_array(10)
        ).encode()

        self.assertFalse(self.hp_moonshot.detected())

        self.mock_print.assert_called_once_with(
            "DEBUG: Detected BMC is not HP Moonshot, has device ID 15"
        )
        self.mock_check_output.assert_called_once_with(
            ["ipmitool", "raw", "06", "01"],
            timeout=bmc_config.COMMAND_TIMEOUT,
            stderr=DEVNULL,
        )


class TestRedfish(MAASTestCase):
    class FakeSocket:
        def __init__(self, response_bytes):
            self._file = io.BytesIO(response_bytes)

        def makefile(self, *args, **kwargs):
            return self._file

    def setUp(self):
        super().setUp()
        self.redfish = bmc_config.Redfish()
        self.mock_check_output = self.patch(bmc_config, "check_output")
        self.mock_print = self.patch(bmc_config, "print")

    def test_str(self):
        self.assertEqual("Redfish", str(self.redfish))

    def test_get_smbios_data_no_redfish_detected(self):
        data = textwrap.dedent(
            """\
            # dmidecode 3.3
            Reading SMBIOS/DMI data from file skolar/skolar.dmi.
            SMBIOS 3.4.0 present.
            # SMBIOS implementations newer than version 3.3.0 are not
            # fully supported by this version of dmidecode.

            Handle 0x0039, DMI type 42, 16 bytes
            Management Controller Host Interface
            Host Interface Type: OEM"""
        ).encode()

        self.patch(bmc_config, "which").return_value = True
        self.mock_check_output.return_value = data
        self.assertIsNone(self.redfish._get_smbios_data())

    def test_get_smbios_data_redfish_detected(self):
        data = textwrap.dedent(
            """\
            # dmidecode 3.3
            Reading SMBIOS/DMI data from file skolar/skolar.dmi.
            SMBIOS 3.4.0 present.
            # SMBIOS implementations newer than version 3.3.0 are not
            # fully supported by this version of dmidecode.

            Handle 0x0039, DMI type 42, 16 bytes
            Management Controller Host Interface
            Host Interface Type: OEM

            Handle 0x004E, DMI type 42, 129 bytes
            Management Controller Host Interface
            Host Interface Type: Network
            Device Type: USB
            idVendor: 0x046b
            idProduct: 0xffb0
            Protocol ID: 04 (Redfish over IP)
            Service UUID: a0635470-debf-0010-9c04-d85ed302b24a
            Host IP Assignment Type: Static
            Host IP Address Format: IPv4
            IPv4 Address: 169.254.95.120
            IPv4 Mask: 255.255.0.0
            Redfish Service IP Discovery Type: Static
            Redfish Service IP Address Format: IPv4
            IPv4 Redfish Service Address: 169.254.95.118
            IPv4 Redfish Service Mask: 255.255.0.0
            Redfish Service Port: 443
            Redfish Service Vlan: 0
            Redfish Service Hostname:"""
        ).encode()

        expected = textwrap.dedent(
            """\
            Device Type: USB
            idVendor: 0x046b
            idProduct: 0xffb0
            Protocol ID: 04 (Redfish over IP)
            Service UUID: a0635470-debf-0010-9c04-d85ed302b24a
            Host IP Assignment Type: Static
            Host IP Address Format: IPv4
            IPv4 Address: 169.254.95.120
            IPv4 Mask: 255.255.0.0
            Redfish Service IP Discovery Type: Static
            Redfish Service IP Address Format: IPv4
            IPv4 Redfish Service Address: 169.254.95.118
            IPv4 Redfish Service Mask: 255.255.0.0
            Redfish Service Port: 443
            Redfish Service Vlan: 0
            Redfish Service Hostname:"""
        )

        self.patch(bmc_config, "which").return_value = True
        self.mock_check_output.return_value = data
        self.assertEqual(expected, self.redfish._get_smbios_data())

    def test_get_smbios_data_redfish_detected_with_two_interfaces(self):
        data = textwrap.dedent(
            """\
            # dmidecode 3.3
            Getting SMBIOS data from sysfs.
            SMBIOS 3.3.0 present.

            Handle 0x00D0, DMI type 42, 169 bytes
            Management Controller Host Interface
            Host Interface Type: Network
            Device Type: USB
            idVendor: 0x04b3
            idProduct: 0x4010
            Protocol ID: 04 (Redfish over IP)
            Service UUID: a4b13f22-d0f3-11ea-aca9-e5b8d327f39f
            Host IP Assignment Type: Static
            Host IP Address Format: IPv4
            IPv4 Address: 169.254.95.120
            IPv4 Mask: 255.255.0.0
            Redfish Service IP Discovery Type: Static
            Redfish Service IP Address Format: IPv4
            IPv4 Redfish Service Address: 169.254.95.118
            IPv4 Redfish Service Mask: 255.255.0.0
            Redfish Service Port: 443
            Redfish Service Vlan: 0
            Redfish Service Hostname: garamond

            Handle 0x00D1, DMI type 42, 169 bytes
            Management Controller Host Interface
            Host Interface Type: Network
            Device Type: USB
            idVendor: 0x04b3
            idProduct: 0x4010
            Protocol ID: 04 (Redfish over IP)
            Service UUID: a4b13f22-d0f3-11ea-aca9-e5b8d327f39f
            Host IP Assignment Type: Static
            Host IP Address Format: IPv4
            IPv4 Address: 169.254.95.120
            IPv4 Mask: 255.255.0.0
            Redfish Service IP Discovery Type: Static
            Redfish Service IP Address Format: IPv6
            IPv6 Redfish Service Address: fe80::7ed3:aff:fe54:60e6
            IPv6 Redfish Service Mask: ffff::
            Redfish Service Port: 443
            Redfish Service Vlan: 0
            Redfish Service Hostname: garamond"""
        ).encode()

        expected = textwrap.dedent(
            """\
            Device Type: USB
            idVendor: 0x04b3
            idProduct: 0x4010
            Protocol ID: 04 (Redfish over IP)
            Service UUID: a4b13f22-d0f3-11ea-aca9-e5b8d327f39f
            Host IP Assignment Type: Static
            Host IP Address Format: IPv4
            IPv4 Address: 169.254.95.120
            IPv4 Mask: 255.255.0.0
            Redfish Service IP Discovery Type: Static
            Redfish Service IP Address Format: IPv4
            IPv4 Redfish Service Address: 169.254.95.118
            IPv4 Redfish Service Mask: 255.255.0.0
            Redfish Service Port: 443
            Redfish Service Vlan: 0
            Redfish Service Hostname: garamond"""
        )

        self.patch(bmc_config, "which").return_value = True
        self.mock_check_output.return_value = data
        self.assertEqual(expected, self.redfish._get_smbios_data())

    def test_generate_netplan_config_dhcp_on(self):
        expected_config = textwrap.dedent(
            """
            network:
              version: 2
              ethernets:
                enx7ed30a5460e7:
                    addresses: []
                    dhcp4: true
            """
        )

        self.assertEqual(
            yaml.safe_dump((yaml.safe_load(expected_config))),
            self.redfish._generate_netplan_config(
                "enx7ed30a5460e7", True, None
            ),
        )

    def test_generate_netplan_config_dhcp_off(self):
        expected_config = textwrap.dedent(
            """
            network:
              version: 2
              ethernets:
                enx7ed30a5460e7:
                    addresses: [192.168.1.10/24]
                    dhcp4: false
            """
        )

        self.assertEqual(
            yaml.safe_dump((yaml.safe_load(expected_config))),
            self.redfish._generate_netplan_config(
                "enx7ed30a5460e7", False, "192.168.1.10/24"
            ),
        )

    def test_get_manager_id_missing_token(self):
        self.redfish.username = "maas"
        self.redfish.password = "password"
        self.redfish_ip = "127.0.0.1"
        self.redfish_port = "443"
        self.patch(self.redfish, "_detect").return_value = True

        mock_urlopen = self.patch(bmc_config.urllib.request, "urlopen")
        response = textwrap.dedent(
            """\
            HTTP/1.1 201 OK
            Date: Thu, May  27 15:27:54 2022
            Content-Type: application/json; charset="utf-8"
            Connection: close"""
        ).encode()

        sock = self.FakeSocket(response)
        response = urllib.request.http.client.HTTPResponse(sock)
        response.begin()

        mock_urlopen.return_value = response

        self.assertIsNone(self.redfish.get_manager_id())

    def test_get_manager_id_not_200(self):
        self.redfish.username = "maas"
        self.redfish.password = "password"
        self.redfish_ip = "127.0.0.1"
        self.redfish_port = "443"
        self.patch(self.redfish, "_detect").return_value = True

        mock_urlopen = self.patch(bmc_config.urllib.request, "urlopen")
        response = textwrap.dedent(
            """\
            HTTP/1.1 401 OK
            Date: Thu, May  27 15:27:54 2022
            Content-Type: application/json; charset="utf-8"
            Connection: close"""
        ).encode()

        sock = self.FakeSocket(response)
        response = urllib.request.http.client.HTTPResponse(sock)
        response.begin()

        mock_urlopen.return_value = response

        self.assertIsNone(self.redfish.get_manager_id())

    def test_get_manager_id(self):
        self.redfish.username = "maas"
        self.redfish.password = "password"
        self.redfish_ip = "127.0.0.1"
        self.redfish_port = "443"
        self.patch(self.redfish, "_detect").return_value = True

        mock_urlopen = self.patch(bmc_config.urllib.request, "urlopen")
        token_data = textwrap.dedent(
            """\
            HTTP/1.1 200 OK
            Date: Thu, May  27 15:27:54 2022
            Content-Type: application/json; charset="utf-8"
            X-Auth-Token: token
            Connection: close"""
        ).encode()

        managers_data = textwrap.dedent(
            """\
            HTTP/1.1 200 OK
            Date: Thu, May  27 15:27:54 2022
            Content-Type: application/json; charset="utf-8"
            Connection: close

            {"Members":[{"@odata.id":"/redfish/v1/Managers/1"}]}"""
        ).encode()

        sock_response_token = self.FakeSocket(token_data)
        response_token = urllib.request.http.client.HTTPResponse(
            sock_response_token
        )
        response_token.begin()

        sock_response_managers = self.FakeSocket(managers_data)
        response_managers = urllib.request.http.client.HTTPResponse(
            sock_response_managers
        )
        response_managers.begin()

        mock_urlopen.side_effect = (
            response_token,
            response_managers,
        )

        self.assertEqual("1", self.redfish.get_manager_id())

    def test_get_bmc_ip_missing_token(self):
        self.redfish.username = "maas"
        self.redfish.password = "password"
        self.redfish_ip = "127.0.0.1"
        self.redfish_port = "443"
        self.patch(self.redfish, "_detect").return_value = True

        mock_urlopen = self.patch(bmc_config.urllib.request, "urlopen")
        response = textwrap.dedent(
            """\
            HTTP/1.1 200 OK
            Date: Thu, May  27 15:27:54 2022
            Content-Type: application/json; charset="utf-8"
            Connection: close"""
        ).encode()

        sock = self.FakeSocket(response)
        response = urllib.request.http.client.HTTPResponse(sock)
        response.begin()

        mock_urlopen.return_value = response

        self.assertIsNone(self.redfish.get_bmc_ip())

    def test_get_bmc_ip_not_200(self):
        self.redfish.username = "maas"
        self.redfish.password = "password"
        self.redfish_ip = "127.0.0.1"
        self.redfish_port = "443"
        self.patch(self.redfish, "_detect").return_value = True

        mock_urlopen = self.patch(bmc_config.urllib.request, "urlopen")
        response = textwrap.dedent(
            """\
            HTTP/1.1 401 OK
            Date: Thu, May  27 15:27:54 2022
            Content-Type: application/json; charset="utf-8"
            Connection: close"""
        ).encode()

        sock = self.FakeSocket(response)
        response = urllib.request.http.client.HTTPResponse(sock)
        response.begin()

        mock_urlopen.return_value = response

        self.assertIsNone(self.redfish.get_bmc_ip())

    def test_get_bmc_ip(self):
        self.redfish.username = "maas"
        self.redfish.password = "password"
        self.redfish_ip = "127.0.0.1"
        self.redfish_port = "443"
        self.patch(self.redfish, "_detect").return_value = True
        self.patch(self.redfish, "get_manager_id").return_value = "1"

        mock_urlopen = self.patch(bmc_config.urllib.request, "urlopen")
        token_data = textwrap.dedent(
            """\
            HTTP/1.1 200 OK
            Date: Thu, May  27 15:27:54 2022
            Content-Type: application/json; charset="utf-8"
            X-Auth-Token: token
            Connection: close"""
        ).encode()

        interfaces_data = textwrap.dedent(
            """\
            HTTP/1.1 200 OK
            Date: Thu, May  27 15:27:54 2022
            Content-Type: application/json; charset="utf-8"
            Connection: close

            {"Members":[{"@odata.id":"/redfish/v1/Managers/1/EthernetInterfaces/1"}]}"""
        ).encode()

        address_data = textwrap.dedent(
            """\
            HTTP/1.1 200 OK
            Date: Thu, May  27 15:27:54 2022
            Content-Type: application/json; charset="utf-8"
            Connection: close

            {"IPv4Addresses":[{"Address":"127.0.0.1"}]}"""
        ).encode()

        sock_response_token = self.FakeSocket(token_data)
        response_token = urllib.request.http.client.HTTPResponse(
            sock_response_token
        )
        response_token.begin()

        sock_response_interfaces = self.FakeSocket(interfaces_data)
        response_interfaces = urllib.request.http.client.HTTPResponse(
            sock_response_interfaces
        )
        response_interfaces.begin()

        sock_response_address = self.FakeSocket(address_data)
        response_address = urllib.request.http.client.HTTPResponse(
            sock_response_address
        )
        response_address.begin()

        mock_urlopen.side_effect = (
            response_token,
            response_interfaces,
            response_address,
        )

        self.assertEqual("127.0.0.1", self.redfish.get_bmc_ip())

    def test_configure_network(self):
        data = textwrap.dedent(
            """\
            Device Type: USB
            idVendor: 0x046b
            idProduct: 0xffb0
            Protocol ID: 04 (Redfish over IP)
            Service UUID: a0635470-debf-0010-9c04-d85ed302b24a
            Host IP Assignment Type: Static
            Host IP Address Format: IPv4
            IPv4 Address: 169.254.95.120
            IPv4 Mask: 255.255.0.0
            Redfish Service IP Discovery Type: Static
            Redfish Service IP Address Format: IPv4
            IPv4 Redfish Service Address: 169.254.95.118
            IPv4 Redfish Service Mask: 255.255.0.0
            Redfish Service Port: 443
            Redfish Service Vlan: 0
            Redfish Service Hostname:"""
        )

        expected_config = textwrap.dedent(
            """
            network:
              version: 2
              ethernets:
                eth0:
                    addresses: [169.254.95.120/16]
                    dhcp4: false
            """
        )

        with tempfile.NamedTemporaryFile(
            prefix="redfish-netplan", mode="w+"
        ) as netconfig:
            mock_check_output = self.patch(bmc_config, "check_output")
            self.redfish._configure_network("eth0", data, netconfig.name)
            self.assertEqual(
                yaml.safe_dump((yaml.safe_load(expected_config))),
                netconfig.read(),
            )

            mock_check_output.assert_called_once_with(
                ["netplan", "apply"], timeout=bmc_config.COMMAND_TIMEOUT
            )

    def test_add_bmc_user(self):
        username = factory.make_name("username")
        password = factory.make_name("password")
        self.redfish = bmc_config.Redfish(username, password)
        mock_bmc_set = self.patch(self.redfish, "_bmc_set")
        mock_bmc_set_keys = self.patch(self.redfish, "_bmc_set_keys")
        self.redfish._bmc_config = {
            "User1": {},
            "User2": {
                "Username": "",
                "Password": factory.make_name("password"),
                "Enable_User": "Yes",
                "Lan_Privilege_Limit": "Administrator",
                "Lan_Enable_IPMI_Msgs": "Yes",
            },
        }
        self.redfish._privilege_level = "OPERATOR"

        self.redfish.add_bmc_user()

        self.assertEqual(username, self.redfish.username)
        self.assertEqual(password, self.redfish.password)
        # Verify bmc_set is only called for values that have changed
        mock_bmc_set.assert_has_calls(
            (
                call("User2", "Username", username),
                call("User2", "Password", password),
                call("User2", "Lan_Privilege_Limit", "Operator"),
            )
        )

        mock_bmc_set_keys.assert_called_once_with(
            "User2",
            [
                "Lan_Enable_Link_Auth",
                "SOL_Payload_Access",
                "Serial_Enable_Link_Auth",
            ],
            "Yes",
        )

    def test_detected_unknown_exception(self):
        self.patch(
            self.redfish, "_detect"
        ).side_effect = factory.make_exception_type((ValueError,))
        self.assertRaises(ValueError, self.redfish.detected)

    def test_detected_known_exception(self):
        self.patch(
            self.redfish, "_detect"
        ).side_effect = factory.make_exception_type(
            (bmc_config.ConfigurationError,)
        )
        self.assertFalse(self.redfish.detected())

    @patch.dict(os.environ, {}, clear=True)
    def test_detected_no_resources_file_env_key_set(self):
        """Catch IO related issue with potentially unset environment key."""
        self.patch(self.redfish, "_get_smbios_data").return_value = ""
        self.patch(bmc_config, "get_smbios_value").return_value = "aaa"

        self.assertFalse(self.redfish.detected())

        self.mock_print.assert_called_once_with(
            "DEBUG: Redfish detection and configuration failed. Reason: "
            "Failed to get network interface for Redfish"
        )

    @patch.dict(
        os.environ, {"MAAS_RESOURCES_FILE": "/tmp/res_file"}, clear=True
    )
    def test_detected_no_resources_file(self):
        """Catch IO related issue with potentially missing resources file."""

        self.patch(self.redfish, "_get_smbios_data").return_value = ""
        self.patch(bmc_config, "get_smbios_value").return_value = "aaa"

        json_load_mock = self.patch(bmc_config, "json.load")
        json_load_mock.side_effect = factory.make_exception_type(
            (JSONDecodeError,)
        )

        self.assertFalse(self.redfish.detected())

        self.mock_print.assert_called_once_with(
            "DEBUG: Redfish detection and configuration failed. Reason: "
            "Failed to get network interface for Redfish"
        )

    def test_get_credentials(self):
        ip = factory.make_ip_address()
        self.patch(self.redfish, "get_bmc_ip").return_value = ip
        self.redfish.username = factory.make_name("username")
        self.redfish.password = factory.make_name("password")
        self.patch(self.redfish, "get_manager_id").return_value = "1"
        self.assertEqual(
            {
                "power_address": ip,
                "power_user": self.redfish.username,
                "power_pass": self.redfish.password,
                "node_id": "1",
            },
            self.redfish.get_credentials(),
        )

    def test_missing_dmidecode_exception(self):
        self.patch(bmc_config, "which").return_value = None
        self.assertRaises(
            bmc_config.ConfigurationError, self.redfish._get_smbios_data
        )


class TestGetIPMILocateOutput(MAASTestCase):
    def test_get_ipmi_locate_output(self):
        mock_check_output = self.patch(bmc_config, "check_output")
        ret = factory.make_string()
        mock_check_output.return_value = ret.encode()
        # Make sure we start out with a cleared cache
        bmc_config._get_ipmi_locate_output.cache_clear()

        self.assertEqual(ret, bmc_config._get_ipmi_locate_output())
        # Because the value is cached check_output should only be
        # called once.
        self.assertEqual(ret, bmc_config._get_ipmi_locate_output())
        mock_check_output.assert_called_once_with(
            ["ipmi-locate"], timeout=bmc_config.COMMAND_TIMEOUT
        )


class TestGetWedgeLocalAddr(MAASTestCase):
    def test_wedge_local_addr(self):
        mock_check_output = self.patch(bmc_config, "check_output")
        mock_check_output.return_value = (
            b"8: eth0    inet fe80::ff:fe00:2/64 brd 10.0.0.255 scope global "
            b"eth0\\       valid_lft forever preferred_lft forever"
        )
        bmc_config._get_wedge_local_addr.cache_clear()
        self.assertEqual("fe80::1%eth0", bmc_config._get_wedge_local_addr())
        # Call multiple times to verify caching
        self.assertEqual(
            bmc_config._get_wedge_local_addr(),
            bmc_config._get_wedge_local_addr(),
        )
        mock_check_output.assert_called_once()


class TestWedge(MAASTestCase):
    def setUp(self):
        super().setUp()
        self.wedge = bmc_config.Wedge()
        self.mock_check_output = self.patch(bmc_config, "check_output")
        self.mock_print = self.patch(bmc_config, "print")
        bmc_config._get_wedge_local_addr.cache_clear()

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
        self.patch(bmc_config, "which").return_value = True
        self.assertEqual("accton", self.wedge._detect_known_switch())

    def test_detect_known_switch_false(self):
        self.mock_check_output.side_effect = (
            factory.make_name("system-manufacturer").encode(),
            factory.make_name("system-product-name").encode(),
            factory.make_name("baseboard-product-name").encode(),
        )
        self.patch(bmc_config, "which").return_value = True
        self.assertIsNone(self.wedge._detect_known_switch())

    def test_detected_unknown_switch(self):
        self.patch(self.wedge, "_detect_known_switch").return_value = None
        self.assertFalse(self.wedge.detected())
        self.mock_print.assert_called_once_with(
            "DEBUG: Unknown/no switch detected."
        )

    def test_detected_error_detecting_switch(self):
        """
        Simulate throwing an error calling any dmidecode command.

        Check printed error message is what we'd expect.
        """
        mock_detect_known_switch = self.patch(
            self.wedge, "_detect_known_switch"
        )
        mock_detect_known_switch.side_effect = CalledProcessError(
            cmd=["dmidecode", "-s", "system-manufacturer"], returncode=1
        )

        self.assertFalse(self.wedge.detected())
        self.mock_print.assert_called_once_with(
            "DEBUG: Exception occurred when trying to detect switch: "
            "Command '['dmidecode', '-s', 'system-manufacturer']' "
            "returned non-zero exit status 1."
        )

    def test_detected_dmidecode_error(self):
        self.patch(
            self.wedge, "_detect_known_switch"
        ).side_effect = random.choice(
            [
                CalledProcessError(
                    cmd="cmd", returncode=random.randint(1, 255)
                ),
                TimeoutExpired(cmd="cmd", timeout=random.randint(1, 100)),
                FileNotFoundError(),
            ]
        )
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

        self.assertEqual("10.0.0.10", self.wedge.get_bmc_ip())
        # Call multiple times to verify caching
        self.assertEqual(self.wedge.get_bmc_ip(), self.wedge.get_bmc_ip())
        mock_ssh_client.assert_called_once()
        mock_client.set_missing_host_key_policy.assert_called_once_with(
            bmc_config.IgnoreHostKeyPolicy
        )
        mock_client.connect.assert_called_once_with(
            "fe80::1%eth0", username="root", password="0penBmc"
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

    def test_missing_dmidecode_exception(self):
        self.patch(bmc_config, "which").return_value = None
        self.assertRaises(
            bmc_config.ConfigurationError, self.wedge._detect_known_switch
        )


class TestDetectAndConfigure(MAASTestCase):
    def setUp(self):
        super().setUp()
        self.mock_print = self.patch(bmc_config, "print")

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

        with open(bmc_config_path) as f:
            self.assertEqual(
                {"power_type": "moonshot", **creds}, yaml.safe_load(f)
            )

    def test_finds_third(self):
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
        self.patch(bmc_config.Redfish, "detected").return_value = False
        self.patch(bmc_config.IPMI, "detected").return_value = True
        self.patch(bmc_config.IPMI, "configure")
        self.patch(bmc_config.IPMI, "add_bmc_user")
        self.patch(bmc_config.IPMI, "get_credentials").return_value = creds

        bmc_config.detect_and_configure(args, bmc_config_path)

        with open(bmc_config_path) as f:
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
        self.patch(bmc_config.Redfish, "detected").return_value = False
        self.patch(bmc_config.IPMI, "detected").return_value = False
        self.patch(bmc_config.Wedge, "detected").return_value = False

        bmc_config.detect_and_configure(args, bmc_config_path)

        self.assertFalse(os.path.exists(bmc_config_path))
        bmc_config.HPMoonshot.detected.assert_called_once()
        bmc_config.Redfish.detected.assert_called_once()
        bmc_config.IPMI.detected.assert_called_once()
        bmc_config.Wedge.detected.assert_called_once()

        self.mock_print.assert_has_calls(
            [
                call("INFO: Checking for HP Moonshot..."),
                call("INFO: No HP Moonshot detected. Trying next BMC type..."),
                call("INFO: Checking for Redfish..."),
                call("INFO: No Redfish detected. Trying next BMC type..."),
                call("INFO: Checking for IPMI..."),
                call("INFO: No IPMI detected. Trying next BMC type..."),
                call("INFO: Checking for Facebook Wedge..."),
                call("INFO: No Facebook Wedge detected."),
                call("INFO: No BMC automatically detected!"),
            ]
        )


class TestMain(MAASTestCase):
    def setUp(self):
        super().setUp()
        self.mock_check_call = self.patch(bmc_config, "check_call")
        self.mock_parse_args = self.patch(
            bmc_config.argparse.ArgumentParser, "parse_args"
        )
        self.mock_parse_args.return_value.ipmi_k_g = None
        self.patch(bmc_config, "print")

    def test_validates_username_isnt_too_long(self):
        self.mock_parse_args.return_value.username = factory.make_string(21)
        self.assertRaises(SystemExit, bmc_config.main)

    def test_validates_password_isnt_too_long(self):
        self.mock_parse_args.return_value.password = factory.make_string(21)
        self.assertRaises(SystemExit, bmc_config.main)

    def test_validates_ipmi_k_g_isnt_too_long(self):
        self.mock_parse_args.return_value.ipmi_k_g = factory.make_string(21)
        self.assertRaises(SystemExit, bmc_config.main)

    def test_validates_ipmi_k_g_hex_isnt_too_long(self):
        self.mock_parse_args.return_value.ipmi_k_g = (
            "0x" + factory.make_string(41)
        )
        self.assertRaises(SystemExit, bmc_config.main)

    def test_checks_bmc_config_path_env_var_set(self):
        self.assertRaises(SystemExit, bmc_config.main)

    def test_skips_if_bmc_config_exists(self):
        self.patch(bmc_config.os.environ, "get")
        self.patch(bmc_config.os.path, "exists").return_value = True
        mock_exit_skipped = self.patch(bmc_config, "exit_skipped")

        bmc_config.main()

        mock_exit_skipped.assert_called_once()

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

        self.mock_check_call.assert_called_once_with(
            ["systemd-detect-virt", "-q"],
            timeout=bmc_config.COMMAND_TIMEOUT,
        )
        mock_run.assert_has_calls(
            [
                call(
                    ["sudo", "-E", "modprobe", "ipmi_msghandler"],
                    timeout=bmc_config.COMMAND_TIMEOUT,
                ),
                call(
                    ["sudo", "-E", "modprobe", "ipmi_devintf"],
                    timeout=bmc_config.COMMAND_TIMEOUT,
                ),
                call(
                    ["sudo", "-E", "modprobe", "ipmi_si"],
                    timeout=bmc_config.COMMAND_TIMEOUT,
                ),
                call(
                    ["sudo", "-E", "modprobe", "ipmi_ssif"],
                    timeout=bmc_config.COMMAND_TIMEOUT,
                ),
                call(
                    ["sudo", "-E", "udevadm", "settle"],
                    timeout=bmc_config.COMMAND_TIMEOUT,
                ),
            ]
        )
        mock_detect_and_configure.assert_called_once()

    def test_does_nothing_if_on_vm(self):
        self.patch(bmc_config.os.environ, "get")
        self.patch(bmc_config.os.path, "exists").return_value = False
        mock_detect_and_configure = self.patch(
            bmc_config, "detect_and_configure"
        )
        mock_exit_skipped = self.patch(bmc_config, "exit_skipped")

        bmc_config.main()

        mock_detect_and_configure.assert_not_called()
        mock_exit_skipped.assert_called_once()

    def test_get_network_interface_usb(self):
        data = FakeCommissioningData()
        card = data.create_network_card(DeviceType.USB)
        network = data.create_physical_network(card=card)

        self.assertEqual(
            network.name,
            bmc_config.get_network_interface(
                data.render(), card.vendor_id, card.product_id
            ),
        )

    def test_get_network_interface_pci(self):
        data = FakeCommissioningData()
        card = data.create_network_card(DeviceType.PCI)
        network = data.create_physical_network(card=card)

        self.assertEqual(
            network.name,
            bmc_config.get_network_interface(
                data.render(), card.vendor_id, card.product_id
            ),
        )

    def test_get_smbios_value(self):
        data = (
            "Device Type: USB\n"
            "idVendor: 0x046b\n"
            "idProduct: 0xffb0\n"
            "Protocol ID: 04 (Redfish over IP)\n"
            "Service UUID: a0635470-debf-0010-9c04-d85ed302b24a\n"
            "Host IP Assignment Type: Static\n"
            "Host IP Address Format: IPv4\n"
            "IPv4 Address: 169.254.95.120\n"
            "IPv4 Mask: 255.255.0.0\n"
            "Redfish Service IP Discovery Type: Static\n"
            "Redfish Service IP Address Format: IPv4\n"
            "IPv4 Redfish Service Address: 169.254.95.118\n"
            "IPv4 Redfish Service Mask: 255.255.0.0\n"
            "Redfish Service Port: 443\n"
            "Redfish Service Vlan: 0\n"
            "Redfish Service Hostname:"
        )

        self.assertEqual(
            "Static",
            bmc_config.get_smbios_value(data, "Host IP Assignment Type"),
        )
        self.assertEqual(
            "169.254.95.120", bmc_config.get_smbios_value(data, "IPv4 Address")
        )
