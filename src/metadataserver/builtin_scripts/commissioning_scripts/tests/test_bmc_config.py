# Copyright 2020-2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test bmc_config functions."""

from collections import OrderedDict
import io
import os
import random
import re
from subprocess import CalledProcessError, DEVNULL, TimeoutExpired
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

        self.assertThat(
            self.mock_check_call,
            MockCalledOnceWith(
                [
                    "bmc-config",
                    "--commit",
                    f"--key-pair={section}:{key}={value}",
                ],
                timeout=60,
            ),
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
        self.assertThat(
            self.mock_check_call,
            MockCalledOnceWith(
                [
                    "bmc-config",
                    "--commit",
                    "--key-pair=User2:SOL_Payload_Access=Yes",
                ],
                timeout=60,
            ),
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
        self.assertThat(self.mock_print, MockCalledOnce())

    def test_bmc_set_keys_warns_on_setting_failure(self):
        self.mock_check_call.side_effect = None
        self.ipmi._bmc_config = {}
        self.ipmi._bmc_set_keys(
            factory.make_name("section"),
            [factory.make_name("key") for _ in range(3)],
            factory.make_name("value"),
        )
        self.assertThat(self.mock_print, MockCalledOnce())

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

    def test_get_ipmitool_lan_print(self):
        fake_output = factory.make_name("output")
        self.mock_check_output.side_effect = (
            CalledProcessError(cmd="cmd", returncode=random.randint(1, 255)),
            TimeoutExpired(cmd="cmd", timeout=random.randint(1, 100)),
            fake_output.encode(),
        )

        # Call twice to test caching
        self.ipmi._get_ipmitool_lan_print()
        channel, output = self.ipmi._get_ipmitool_lan_print()

        self.assertEqual("2", channel)
        self.assertEqual(fake_output, output)
        self.assertThat(
            self.mock_check_output,
            MockCallsMatch(
                call(
                    ["ipmitool", "lan", "print", "0"],
                    stderr=DEVNULL,
                    timeout=60,
                ),
                call(
                    ["ipmitool", "lan", "print", "1"],
                    stderr=DEVNULL,
                    timeout=60,
                ),
                call(
                    ["ipmitool", "lan", "print", "2"],
                    stderr=DEVNULL,
                    timeout=60,
                ),
            ),
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
        self.assertThat(
            mock_bmc_set,
            MockCallsMatch(
                call("User2", "Username", self.username),
                call("User2", "Password", self.password),
                call("User2", "Lan_Privilege_Limit", "Operator"),
            ),
        )
        self.assertThat(
            mock_bmc_set_keys,
            MockCalledOnceWith(
                "User2",
                [
                    "Lan_Enable_Link_Auth",
                    "SOL_Payload_Access",
                    "Serial_Enable_Link_Auth",
                ],
                "Yes",
            ),
        )

    def test_add_bmc_user_rand_password(self):
        self.ipmi.username = None
        self.ipmi.password = None
        password = factory.make_name("password")
        password_w_spec_chars = factory.make_name("password_w_spec_chars")
        self.patch(self.ipmi, "_generate_random_password").side_effect = (
            password,
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
        self.assertThat(
            mock_bmc_set,
            MockCallsMatch(
                call("User2", "Username", "maas"),
                call("User2", "Password", password),
                call("User2", "Lan_Privilege_Limit", "Operator"),
            ),
        )
        self.assertThat(
            mock_bmc_set_keys,
            MockCalledOnceWith(
                "User2",
                [
                    "Lan_Enable_Link_Auth",
                    "SOL_Payload_Access",
                    "Serial_Enable_Link_Auth",
                ],
                "Yes",
            ),
        )

    def test_add_bmc_user_rand_password_with_special_chars(self):
        self.ipmi.username = None
        self.ipmi.password = None
        password = factory.make_name("password")
        password_w_spec_chars = factory.make_name("password_w_spec_chars")
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
        self.assertThat(
            mock_bmc_set,
            MockCallsMatch(
                call("User2", "Username", "maas"),
                call("User2", "Password", password),
                call("User2", "Username", "maas"),
                call("User2", "Password", password_w_spec_chars),
                call("User2", "Lan_Privilege_Limit", "Operator"),
            ),
        )
        self.assertThat(
            mock_bmc_set_keys,
            MockCalledOnceWith(
                "User2",
                [
                    "Lan_Enable_Link_Auth",
                    "SOL_Payload_Access",
                    "Serial_Enable_Link_Auth",
                ],
                "Yes",
            ),
        )

    def test_add_bmc_user_fails(self):
        mock_bmc_set = self.patch(self.ipmi, "_bmc_set")
        mock_bmc_set.side_effect = factory.make_exception()

        self.assertRaises(SystemExit, self.ipmi.add_bmc_user)

    def test_set_ipmi_lan_channel_setting_verifies(self):
        self.ipmi._bmc_config = {
            "Lan_Channel": {
                "Volatile_Access_Mode": "Always_Available",
                "Non_Volatile_Access_Mode": "Always_Available",
            }
        }
        mock_bmc_set = self.patch(self.ipmi, "_bmc_set")
        mock_bmc_set_keys = self.patch(self.ipmi, "_bmc_set_keys")
        self.ipmi._config_ipmi_lan_channel_settings()
        self.assertThat(mock_bmc_set, MockNotCalled())
        self.assertThat(
            mock_bmc_set_keys,
            MockCalledOnceWith(
                "Lan_Channel",
                [
                    "%s_%s" % (auth_type, volatility)
                    for auth_type in [
                        "Enable_User_Level_Auth",
                        "Enable_Per_Message_Auth",
                        "Enable_Pef_Alerting",
                    ]
                    for volatility in ["Volatile", "Non_Volatile"]
                ],
                "Yes",
            ),
        )

    def test_set_ipmi_lan_channel_setting_enables(self):
        self.ipmi._bmc_config = {
            "Lan_Channel": {
                "Volatile_Access_Mode": "Disabled",
                "Non_Volatile_Access_Mode": "Pre_Boot_only",
            }
        }
        mock_bmc_set = self.patch(self.ipmi, "_bmc_set")
        mock_bmc_set_keys = self.patch(self.ipmi, "_bmc_set_keys")
        self.ipmi._config_ipmi_lan_channel_settings()
        self.assertThat(
            mock_bmc_set,
            MockCallsMatch(
                call(
                    "Lan_Channel", "Volatile_Access_Mode", "Always_Available"
                ),
                call(
                    "Lan_Channel",
                    "Non_Volatile_Access_Mode",
                    "Always_Available",
                ),
            ),
        )
        self.assertThat(
            mock_bmc_set_keys,
            MockCalledOnceWith(
                "Lan_Channel",
                [
                    "%s_%s" % (auth_type, volatility)
                    for auth_type in [
                        "Enable_User_Level_Auth",
                        "Enable_Per_Message_Auth",
                        "Enable_Pef_Alerting",
                    ]
                    for volatility in ["Volatile", "Non_Volatile"]
                ],
                "Yes",
            ),
        )

    def test_config_lan_conf_auth(self):
        self.ipmi._bmc_config = {"Lan_Channel_Auth": {}}
        mock_bmc_set_keys = self.patch(self.ipmi, "_bmc_set_keys")

        self.ipmi._config_lan_conf_auth()

        self.assertThat(
            mock_bmc_set_keys,
            MockCallsMatch(
                call(
                    "Lan_Channel_Auth",
                    [
                        "%s_Enable_Auth_Type_%s" % (user, enc_type)
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
            ),
        )

    def test_config_lan_conf_auth_does_nothing_if_missing(self):
        mock_bmc_set_keys = self.patch(self.ipmi, "_bmc_set_keys")

        self.ipmi._config_lan_conf_auth()

        self.assertThat(mock_bmc_set_keys, MockNotCalled())

    def test_get_ipmitool_cipher_suite_ids(self):
        supported_cipher_suite_ids = [
            i for i in range(0, 20) if factory.pick_bool()
        ]
        cipher_suite_privs = "".join(
            [
                random.choice(["X", "c", "u", "o", "a", "O"])
                for _ in range(0, 16)
            ]
        )
        ipmitool_output = (
            # Validate bmc-config ignores lines which are not key value
            # pairs.
            factory.make_string()
            + "\n"
            # Validate bmc-config ignores unknown key value pairs.
            + factory.make_string()
            + " : "
            + factory.make_string()
            + "\n"
            + "RMCP+ Cipher Suites   :  "
            + ",".join([str(i) for i in supported_cipher_suite_ids])
            + "\n"
            + "Cipher Suite Priv Max :  "
            + cipher_suite_privs
            + "\n"
            + factory.make_string()
            + " : "
            + factory.make_string()
            + "\n"
        )
        self.patch(self.ipmi, "_get_ipmitool_lan_print").return_value = (
            random.randint(0, 10),
            ipmitool_output,
        )

        (
            detected_cipher_suite_ids,
            detected_cipher_suite_privs,
        ) = self.ipmi._get_ipmitool_cipher_suite_ids()

        self.assertEqual(
            supported_cipher_suite_ids,
            detected_cipher_suite_ids,
            ipmitool_output,
        )
        self.assertEqual(
            cipher_suite_privs, detected_cipher_suite_privs, ipmitool_output
        )

    def test_get_ipmitool_cipher_suite_ids_ignores_bad_data(self):
        self.patch(self.ipmi, "_get_ipmitool_lan_print").return_value = (
            random.randint(0, 10),
            "RMCP+ Cipher Suites   : abc\n",
        )

        (
            detected_cipher_suite_ids,
            detected_cipher_suite_privs,
        ) = self.ipmi._get_ipmitool_cipher_suite_ids()

        self.assertEqual([], detected_cipher_suite_ids)
        self.assertIsNone(detected_cipher_suite_privs)

    def test_get_ipmitool_cipher_suite_ids_returns_none_when_not_found(self):
        self.patch(self.ipmi, "_get_ipmitool_lan_print").return_value = (
            random.randint(0, 10),
            factory.make_string() + " : " + factory.make_string() + "\n",
        )

        (
            detected_cipher_suite_ids,
            detected_cipher_suite_privs,
        ) = self.ipmi._get_ipmitool_cipher_suite_ids()

        self.assertEqual([], detected_cipher_suite_ids)
        self.assertIsNone(detected_cipher_suite_privs)

    def test_configure_ipmitool_cipher_suite_ids(self):
        channel = random.randint(0, 10)
        self.patch(self.ipmi, "_get_ipmitool_lan_print").return_value = (
            channel,
            "",
        )

        new_cipher_suite_privs = (
            self.ipmi._configure_ipmitool_cipher_suite_ids(
                3, "aaaXaaaaaaaaaaaaa"
            )
        )

        self.assertEqual("XXXaXXXXaXXXaXXXX", new_cipher_suite_privs)
        self.mock_check_call.assert_called_once_with(
            [
                "ipmitool",
                "lan",
                "set",
                channel,
                "cipher_privs",
                "XXXaXXXXaXXXaXXXX",
            ],
            timeout=60,
        )

    def test_configure_ipmitool_cipher_suite_ids_does_nothing_when_set(self):
        channel = random.randint(0, 10)
        self.patch(self.ipmi, "_get_ipmitool_lan_print").return_value = (
            channel,
            "",
        )

        new_cipher_suite_privs = (
            self.ipmi._configure_ipmitool_cipher_suite_ids(
                3, "XXXaXXXXXXXXXXXX"
            )
        )

        self.assertEqual("XXXaXXXXXXXXXXXX", new_cipher_suite_privs)
        self.mock_check_call.assert_not_called()

    def test_config_cipher_suite_id(self):
        self.patch(self.ipmi, "_get_ipmitool_lan_print").return_value = (
            random.randint(0, 10),
            (
                "RMCP+ Cipher Suites   :  0,3,17\n"
                + "Cipher Suite Priv Max :  XXXaXXXXXXXXXXXX\n"
            ),
        )

        self.ipmi._config_cipher_suite_id()

        self.assertEqual("17", self.ipmi._cipher_suite_id)

    def test_config_cipher_suite_id_does_nothing_if_not_detected(self):
        self.patch(self.ipmi, "_get_ipmitool_lan_print").return_value = (
            random.randint(0, 10),
            "",
        )

        self.ipmi._config_cipher_suite_id()

        self.mock_check_call.assert_not_called()
        self.assertEqual("", self.ipmi._cipher_suite_id)

    def test_config_cipher_suite_id_doesnt_set_id_on_error(self):
        channel = random.randint(0, 10)
        self.patch(self.ipmi, "_get_ipmitool_lan_print").return_value = (
            channel,
            (
                "RMCP+ Cipher Suites   :  0,3\n"
                + "Cipher Suite Priv Max :  aXXXXXXXXXXXXXXX\n"
            ),
        )
        self.mock_check_call.side_effect = random.choice(
            [
                CalledProcessError(
                    cmd="cmd", returncode=random.randint(1, 255)
                ),
                TimeoutExpired(cmd="cmd", timeout=random.randint(1, 100)),
            ]
        )

        self.ipmi._config_cipher_suite_id()

        self.mock_check_call.assert_called_once_with(
            [
                "ipmitool",
                "lan",
                "set",
                channel,
                "cipher_privs",
                "XXXaXXXXXXXXXXXX",
            ],
            timeout=60,
        )
        self.assertEqual("", self.ipmi._cipher_suite_id)

    def test_config_kg_set(self):
        mock_bmc_set = self.patch(self.ipmi, "_bmc_set")
        kg = factory.make_name("kg")
        self.ipmi._kg = kg

        self.ipmi._config_kg()

        self.assertThat(
            mock_bmc_set,
            MockCalledOnceWith("Lan_Conf_Security_Keys", "K_G", kg),
        )
        self.assertEqual(kg, self.ipmi._kg)

    def test_config_kg_set_does_nothing_if_already_set(self):
        kg = factory.make_name("kg")
        self.ipmi._bmc_config = {"Lan_Conf_Security_Keys": {"K_G": kg}}
        mock_bmc_set = self.patch(self.ipmi, "_bmc_set")
        self.ipmi._kg = kg

        self.ipmi._config_kg()

        self.assertThat(mock_bmc_set, MockNotCalled())
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

        self.assertThat(
            mock_bmc_set,
            MockCalledOnceWith("Lan_Conf_Security_Keys", "K_G", kg),
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
        mock_config_cipher_suite_id = self.patch(
            self.ipmi, "_config_cipher_suite_id"
        )
        mock_config_kg = self.patch(self.ipmi, "_config_kg")
        mock_bmc_set_keys = self.patch(self.ipmi, "_bmc_set_keys")

        self.ipmi.configure()

        self.assertThat(mock_bmc_get_config, MockCalledOnce())
        self.assertThat(
            mock_config_ipmi_lan_channel_settings, MockCalledOnce()
        )
        self.assertThat(mock_config_lang_conf_auth, MockCalledOnce())
        self.assertThat(mock_config_cipher_suite_id, MockCalledOnce())
        self.assertThat(mock_config_kg, MockCalledOnce())
        self.assertThat(
            mock_bmc_set_keys,
            MockCallsMatch(
                call(
                    "Serial_Channel",
                    [
                        "%s_%s" % (auth_type, volatility)
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
            ),
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
        self.assertEqual((ip, mac_address), self.ipmi._get_bmc_ip())

    def test_get_bmc_ipv6_static(self):
        ip = factory.make_ipv6_address()
        mac_address = factory.make_mac_address()
        self.ipmi._bmc_config = {
            "Lan6_Conf": {
                "IPv6_Static_Addresses": ip,
                "MAC_Address": mac_address,
            }
        }
        self.assertEqual((f"[{ip}]", mac_address), self.ipmi._get_bmc_ip())

    def test_get_bmc_ipv6_dynamic(self):
        ip = factory.make_ipv6_address()
        mac_address = factory.make_mac_address()
        self.ipmi._bmc_config = {
            "Lan6_Conf": {
                "IPv6_Dynamic_Addresses": ip,
                "MAC_Address": mac_address,
            }
        }
        self.assertEqual((f"[{ip}]", mac_address), self.ipmi._get_bmc_ip())

    def test_get_bmc_ipv6_gets_mac_From_ipv4(self):
        ip = factory.make_ipv6_address()
        mac_address = factory.make_mac_address()
        self.ipmi._bmc_config = {
            "Lan_Conf": {"MAC_Address": mac_address},
            "Lan6_Conf": {"IPv6_Dynamic_Addresses": ip},
        }
        self.assertEqual((f"[{ip}]", mac_address), self.ipmi._get_bmc_ip())

    def test_get_bmc_ip_finds_none(self):
        self.patch(self.ipmi, "_bmc_get").return_value = ""
        self.assertEqual((None, None), self.ipmi._get_bmc_ip())

    def test_get_bmc_ip(self):
        ip = factory.make_ip_address()
        mac_address = factory.make_mac_address()
        mock_bmc_set = self.patch(self.ipmi, "_bmc_set")
        mock_get_bmc_ip = self.patch(self.ipmi, "_get_bmc_ip")
        mock_get_bmc_ip.return_value = ip, mac_address

        self.assertEqual((ip, mac_address), self.ipmi.get_bmc_ip())
        self.assertThat(mock_bmc_set, MockNotCalled())
        self.assertThat(mock_get_bmc_ip, MockCalledOnceWith())

    def test_get_bmc_ip_enables_static(self):
        ip = factory.make_ip_address()
        mac_address = factory.make_mac_address()
        mock_bmc_set = self.patch(self.ipmi, "_bmc_set")
        mock_get_bmc_ip = self.patch(self.ipmi, "_get_bmc_ip")
        mock_get_bmc_ip.side_effect = (
            (None, mac_address),
            (None, mac_address),
            (ip, mac_address),
        )

        self.assertEqual((ip, mac_address), self.ipmi.get_bmc_ip())
        self.assertThat(
            mock_bmc_set,
            MockCalledOnceWith("Lan_Conf", "IP_Address_Source", "Static"),
        )
        self.assertThat(
            mock_get_bmc_ip, MockCallsMatch(call(), call(True), call(True))
        )

    def test_get_bmc_ip_enables_dynamic(self):
        ip = factory.make_ip_address()
        mac_address = factory.make_mac_address()
        mock_bmc_set = self.patch(self.ipmi, "_bmc_set")
        mock_get_bmc_ip = self.patch(self.ipmi, "_get_bmc_ip")
        mock_get_bmc_ip.side_effect = (
            *[(None, mac_address) for _ in range(8)],
            (ip, mac_address),
        )

        self.assertEqual((ip, mac_address), self.ipmi.get_bmc_ip())
        self.assertThat(
            mock_bmc_set,
            MockCallsMatch(
                call("Lan_Conf", "IP_Address_Source", "Static"),
                call("Lan_Conf", "IP_Address_Source", "Use_DHCP"),
            ),
        )
        self.assertThat(
            mock_get_bmc_ip,
            MockCallsMatch(call(), *[call(True) for _ in range(8)]),
        )

    def test_get_bmc_ip_fails(self):
        mock_bmc_set = self.patch(self.ipmi, "_bmc_set")
        mock_get_bmc_ip = self.patch(self.ipmi, "_get_bmc_ip")
        mock_get_bmc_ip.return_value = (None, None)

        self.assertRaises(SystemExit, self.ipmi.get_bmc_ip)
        self.assertThat(
            mock_bmc_set,
            MockCallsMatch(
                call("Lan_Conf", "IP_Address_Source", "Static"),
                call("Lan_Conf", "IP_Address_Source", "Use_DHCP"),
            ),
        )
        self.assertThat(
            mock_get_bmc_ip,
            MockCallsMatch(call(), *[call(True) for _ in range(12)]),
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
                "cipher_suite_id": "",
                "privilege_level": "",
                "mac_address": mac_address,
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
                "cipher_suite_id": "",
                "privilege_level": "",
                "mac_address": mac_address,
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
        self.mock_parse_args = self.patch(
            bmc_config.argparse.ArgumentParser, "parse_args"
        )
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
