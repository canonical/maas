# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for maas_ipmi_autodetect.py."""

__all__ = []

from collections import OrderedDict
import os.path
import platform
import re
import subprocess
from unittest.mock import call

from maastesting.factory import factory
from maastesting.matchers import (
    HasLength,
    MockAnyCall,
    MockCalledOnceWith,
    MockCallsMatch,
    MockNotCalled,
)
from maastesting.testcase import MAASTestCase
from snippets import maas_ipmi_autodetect
from snippets.maas_ipmi_autodetect import (
    apply_ipmi_user_settings,
    bmc_list_sections,
    bmc_supports_lan2_0,
    bmc_user_get,
    commit_ipmi_settings,
    configure_ipmi_user,
    format_user_key,
    generate_random_password,
    get_ipmi_ip_address,
    get_system_boot_type,
    IPMIError,
    list_user_numbers,
    make_ipmi_user_settings,
    pick_user_number,
    pick_user_number_from_list,
    run_command,
    set_ipmi_lan_channel_settings,
    verify_ipmi_user_settings,
)
from testtools.matchers import Equals


class TestRunCommand(MAASTestCase):
    """Tests for the run_command method."""

    def test_output_returned(self):
        """Ensure output from stdout/stderr is returned to caller."""

        test_stdout = factory.make_string()
        test_stderr = factory.make_string()
        command = "echo %s >&1 && echo %s >&2" % (test_stdout, test_stderr)

        output = run_command(["bash", "-c", command])

        self.assertEqual([test_stdout, test_stderr], output.split())

    def test_exception_on_failure(self):
        """"Failed commands should raise an exception."""

        self.assertRaises(subprocess.CalledProcessError, run_command, "false")


class TestFormatUserKey(MAASTestCase):
    """Tests the format_user_key method."""

    def test_format_user_key(self):
        """Ensure user key strings are properly constructed."""

        user = factory.make_string()
        field = factory.make_string()

        user_key = format_user_key(user, field)

        expected = "%s:%s" % (user, field)

        self.assertEqual(expected, user_key)


class TestBMCKeyPairMethods(MAASTestCase):
    """Tests for methods that use bmc-config --key-pair"""

    scenarios = [
        (
            "bmc_get",
            dict(
                method_name="bmc_get",
                args=["Test:Key"],
                key_pair_fmt="--key-pair=%s",
                direction="--checkout",
            ),
        ),
        (
            "bmc_set",
            dict(
                method_name="bmc_set",
                args=["Test:Key", "myval"],
                key_pair_fmt="--key-pair=%s=%s",
                direction="--commit",
            ),
        ),
        (
            "bmc_user_get",
            dict(
                method_name="bmc_user_get",
                args=["User10", "Username"],
                key_pair_fmt="--key-pair=%s:%s",
                direction="--checkout",
            ),
        ),
        (
            "bmc_user_set",
            dict(
                method_name="bmc_user_set",
                args=["User10", "Username", "maas"],
                key_pair_fmt="--key-pair=%s:%s=%s",
                direction="--commit",
            ),
        ),
    ]

    def test_runs_bmc_config(self):
        """Ensure bmc-config is run properly."""

        recorder = self.patch(maas_ipmi_autodetect, "run_command")
        recorder.return_value = "foo"

        # Grab the method from the class module where it lives.
        method = getattr(maas_ipmi_autodetect, self.method_name)

        method(*self.args)

        # Note that the fmt string must use positional argument specifiers
        # if the order of appearance of args in the fmt string doesn't match
        # the order of args to the method.
        key_pair_string = self.key_pair_fmt % tuple(self.args)

        expected_args = ("bmc-config", self.direction, key_pair_string)
        self.assertThat(recorder, MockCalledOnceWith(expected_args))


class TestBMCListSections(MAASTestCase):
    """Tests for bmc_list_sections()."""

    def test_bmc_list_sections(self):
        """Ensure bmc-config is called with the correct args."""
        recorder = self.patch(maas_ipmi_autodetect, "run_command")
        bmc_list_sections()
        self.assertThat(recorder, MockCalledOnceWith(("bmc-config", "-L")))


class TestListUserNumbers(MAASTestCase):
    """Tests for list_user_numbers()."""

    section_names = (
        "User1\n"
        "User4\n"
        "User3\n"
        "User16\n"
        "User7more\n"
        "Userworld\n"
        "Otherwise\n"
        "4User5\n"
        "4User\n"
        "User\n"
        "3"
    )

    def test_matching(self):
        """Ensure only properly formatted User sections match."""
        self.patch(
            maas_ipmi_autodetect, "bmc_list_sections"
        ).return_value = self.section_names
        expected = ["User1", "User4", "User3", "User16"]
        user_numbers = list_user_numbers()
        self.assertEqual(expected, user_numbers)

    def test_empty(self):
        """Ensure an empty list is handled correctly."""
        self.patch(maas_ipmi_autodetect, "bmc_list_sections").return_value = ""
        results = list_user_numbers()
        self.assertEqual([], results)


class TestBMCUserGet(MAASTestCase):
    """Tests for bmc_user_get()."""

    scenarios = [
        (
            "No Leading Space",
            dict(text="Username Bob", key="Username", value="Bob"),
        ),
        (
            "Normal line.",
            dict(text="\tUsername\t\tJoe", key="Username", value="Joe"),
        ),
        (
            "Leading space, not tab",
            dict(text=" Enable_User\t\tNo", key="Enable_User", value="No"),
        ),
        (
            "Multiple leading tabs",
            dict(text="\t\tPassword\t\tPass", key="Password", value="Pass"),
        ),
        (
            "Separating space, not tab",
            dict(text="\tAnother  Value", key="Another", value="Value"),
        ),
        (
            "Gunk",
            dict(
                text="\tCharacters\t,./;:'\"[]{}|\\`~!@$%^&*()-_+=",
                key="Characters",
                value=",./;:'\"[]{}|\\`~!@$%^&*()-_+=",
            ),
        ),
        (
            "More than two words",
            dict(text="\tThree\tWord Line", key="Three", value="Word Line"),
        ),
        ("Blank line", dict(text="", key="Key", value=None)),
        ("Single word", dict(text="\tNotMe", key="NotMe", value=None)),
        ("Comment line", dict(text="\t#Or Me", key="Key", value=None)),
        (
            "Word followed by comment",
            dict(text="\tMe #Neither", key="Key", value=None),
        ),
        (
            "Word followed by two spaces",
            dict(text="\tMe  ", key="Me", value=None),
        ),
        (
            "Two words followed by space",
            dict(text="\tMe Two ", key="Me", value="Two "),
        ),
        ("One character value", dict(text="\tMe T", key="Me", value="T")),
    ]

    def test_matching(self):
        """Ensure only properly formatted record lines match."""
        user_number = "User2"
        response = ("Section %s\n" "%s\n" "EndSection") % (
            user_number,
            self.text,
        )

        self.patch(maas_ipmi_autodetect, "bmc_get").return_value = response

        value = bmc_user_get(user_number, self.key)
        self.assertEqual(self.value, value)


def make_user(update=None):
    """Make a simple user record."""

    base = {"Lan_Enable_IPMI_Msgs": "No"}

    if update:
        base.update(update)

    return base


def make_attributes(*attributes_update):
    """Base user records with updates in an OrderedDict."""

    attributes_template = {
        "User1": {"Enable_User": "Yes"},
        "User2": {"Username": "admin", "Enable_User": "Yes"},
    }

    base = OrderedDict(attributes_template)
    base.update(attributes_update)

    return base


class TestPickUserNumberFromList(MAASTestCase):
    """Tests for pick_user_number_from_list()."""

    scenarios = [
        ("Empty user list", dict(user_attributes={}, expected=None)),
        (
            "Existing MAAS user",
            dict(
                user_attributes=make_attributes(
                    ("User4", make_user()), ("User5", {"Username": "maas"})
                ),
                expected="User5",
            ),
        ),
        (
            "One blank user",
            dict(
                user_attributes=make_attributes(("User7", make_user())),
                expected="User7",
            ),
        ),
        (
            "Multiple blank users",
            dict(
                user_attributes=make_attributes(
                    ("User7", make_user()), ("User8", make_user())
                ),
                expected="User7",
            ),
        ),
        (
            "One not blank user",
            dict(
                user_attributes=make_attributes(
                    ("User7", make_user({"Username": "foo"}))
                ),
                expected=None,
            ),
        ),
        (
            "Username is (Empty User)",
            dict(
                user_attributes=make_attributes(
                    ("User7", make_user({"Username": "(Empty User)"}))
                ),
                expected="User7",
            ),
        ),
        (
            "One enabled blank user",
            dict(
                user_attributes=make_attributes(
                    ("User7", {"Enable_User": "Yes"})
                ),
                expected="User7",
            ),
        ),
        (
            "Skip User1",
            dict(
                user_attributes=make_attributes(("User1", make_user())),
                expected=None,
            ),
        ),
    ]

    def bmc_user_get(self, user_number, parameter):
        """Return mock user data."""
        return self.user_attributes[user_number].get(parameter)

    def test_user_choice(self):
        """Ensure the correct user, if any, is chosen."""
        self.patch(
            maas_ipmi_autodetect, "bmc_user_get"
        ).side_effect = self.bmc_user_get
        current_users = list(self.user_attributes.keys())
        user = pick_user_number_from_list("maas", current_users)
        self.assertEqual(self.expected, user)


class TestPickUserNumber(MAASTestCase):
    """Tests for pick_user_number()."""

    def test_pick_user_number(self):
        """Ensure proper listing and selection of a user."""
        self.patch(maas_ipmi_autodetect, "list_user_numbers").return_value = [
            "User1",
            "User2",
        ]
        self.patch(
            maas_ipmi_autodetect, "pick_user_number_from_list"
        ).return_value = "User2"
        user_number = pick_user_number("maas")
        self.assertEqual("User2", user_number)

    def test_fail_raise_exception(self):
        """Ensure an exception is raised if no acceptable user is found."""
        self.patch(maas_ipmi_autodetect, "list_user_numbers").return_value = []
        self.assertRaises(IPMIError, pick_user_number, "maas")


class TestVerifyIpmiUserSettings(MAASTestCase):
    """Tests for verify_ipmi_user_settings()."""

    def test_fail_missing_key(self):
        """Ensure missing settings cause raise an IPMIError."""
        key = "Username"
        value = factory.make_name("username")
        expected_settings = {key: value}
        self.patch(maas_ipmi_autodetect, "bmc_user_get").return_value = None
        ipmi_error = self.assertRaises(
            IPMIError, verify_ipmi_user_settings, "User2", expected_settings
        )

        expected_message = (
            "IPMI user setting verification failures: "
            "for '%s', expected '%s', actual 'None'."
        ) % (key, value)
        self.assertEqual(expected_message, str(ipmi_error))

    def test_fail_incorrect_keys(self):
        """Ensure settings that don't match raise an IPMIError."""
        bad_settings = {"Enable_Bad": "Yes", "Enable_Bad2": "Yes"}
        good_settings = {"Enable_Good": "No", "Enable_Good2": "No"}

        expected_settings = bad_settings.copy()
        expected_settings.update(good_settings)

        self.patch(maas_ipmi_autodetect, "bmc_user_get").return_value = "No"
        ipmi_error = self.assertRaises(
            IPMIError, verify_ipmi_user_settings, "User2", expected_settings
        )

        self.assertRegex(
            str(ipmi_error), r"^IPMI user setting verification failures: "
        )

        for setting, expected_value in bad_settings.items():
            expected_match = r"for '%s', expected '%s', actual 'No" % (
                setting,
                expected_value,
            )
            self.assertRegex(str(ipmi_error), expected_match)

        for setting in good_settings:
            unexpected_match = r"for '%s'" % setting
            self.assertNotRegexpMatches(str(ipmi_error), unexpected_match)

    def test_accept_some_missing_keys(self):
        """Ensure no exception is raised if these keys are missing.

        Password and Enable_User are both missing on some systems so we
        don't try to verify them.
        """
        expected_settings = {"Password": "bar", "Enable_User": "yes"}
        value = verify_ipmi_user_settings("User2", expected_settings)
        self.assertIsNone(value)


class TestApplyIpmiUserSettings(MAASTestCase):
    """Tests for apply_ipmi_user_settings()."""

    def test_use_username(self):
        """Ensure the username provided is used."""
        user_number = "User2"
        pun_mock = self.patch(maas_ipmi_autodetect, "pick_user_number")
        pun_mock.return_value = user_number
        self.patch(maas_ipmi_autodetect, "bmc_user_set")
        self.patch(maas_ipmi_autodetect, "verify_ipmi_user_settings")
        username = "foo"
        apply_ipmi_user_settings({"Username": username})
        self.assertThat(pun_mock, MockCalledOnceWith(username))

    def test_verify_user_settings(self):
        """Ensure the user settings are committed and verified."""
        user_number = "User2"
        self.patch(
            maas_ipmi_autodetect, "pick_user_number"
        ).return_value = user_number
        bus_mock = self.patch(maas_ipmi_autodetect, "bmc_user_set")
        vius_mock = self.patch(
            maas_ipmi_autodetect, "verify_ipmi_user_settings"
        )
        user_settings = {"Username": user_number, "b": 2}
        apply_ipmi_user_settings(user_settings)

        for key, value in user_settings.items():
            self.assertThat(bus_mock, MockAnyCall(user_number, key, value))

        self.assertThat(
            vius_mock, MockCalledOnceWith(user_number, user_settings)
        )

    def test_preserves_settings_order(self):
        """Ensure user settings are applied in order of iteration."""
        user_number = "User2"
        self.patch(
            maas_ipmi_autodetect, "pick_user_number"
        ).return_value = user_number
        bus_mock = self.patch(maas_ipmi_autodetect, "bmc_user_set")
        self.patch(maas_ipmi_autodetect, "verify_ipmi_user_settings")
        user_settings = OrderedDict((("Username", 1), ("b", 2), ("c", 3)))
        apply_ipmi_user_settings(user_settings)
        expected_calls = (
            call(user_number, key, value)
            for key, value in user_settings.items()
        )
        self.assertThat(bus_mock, MockCallsMatch(*expected_calls))


class TestMakeIPMIUserSettings(MAASTestCase):
    """Tests for make_ipmi_user_settings()."""

    def test_settings_ordered_correctly(self):
        """Ensure user settings are listed in the right order."""
        settings = make_ipmi_user_settings("user", "pass")
        expected = [
            "Username",
            "Password",
            "Enable_User",
            "Lan_Privilege_Limit",
            "Lan_Enable_IPMI_Msgs",
        ]
        self.assertEqual(expected, list(settings.keys()))

    def test_uses_username_and_password(self):
        """Ensure username and password supplied are used."""
        username = "user"
        password = "pass"
        settings = make_ipmi_user_settings(username, password)
        self.assertEqual(username, settings["Username"])
        self.assertEqual(password, settings["Password"])


class TestConfigureIPMIUser(MAASTestCase):
    """Tests for configure_ipmi_user()."""

    def test_preserves_setting_order(self):
        """Ensure the order of user settings isn't modified."""
        expected = OrderedDict((("a", 1), ("b", 2), ("c", 3)))
        self.patch(
            maas_ipmi_autodetect, "make_ipmi_user_settings"
        ).return_value = expected.copy()
        recorder = self.patch(maas_ipmi_autodetect, "apply_ipmi_user_settings")
        configure_ipmi_user("DC")
        self.assertThat(recorder, MockCalledOnceWith(expected))

    def test_configures_user_with_standard_password(self):
        """Test that it returns the configured password if successful"""
        password = "standard123"
        self.patch(
            maas_ipmi_autodetect, "generate_random_password"
        ).return_value = password
        self.patch(maas_ipmi_autodetect, "apply_ipmi_user_settings")
        configured_password = configure_ipmi_user("DC")
        self.assertEqual(configured_password, password)

    def test_raises_ipmi_error_if_cant_configure_user(self):
        """Test that IPMIError is raised if it cannot set a password"""
        recorder = self.patch(maas_ipmi_autodetect, "apply_ipmi_user_settings")
        recorder.side_effect = subprocess.CalledProcessError(1, "bmc-set")
        self.patch(maas_ipmi_autodetect, "configure_ipmi_user")
        self.assertRaises(IPMIError, configure_ipmi_user, "maas")


class TestGeneratesAcceptablePasswords(MAASTestCase):

    scenarios = [
        (
            "maas",
            {
                "special_chars": "!\"#$%&'()*+-./:;<=>?@[\\]^_`{|}~",
                "min_len": 10,
                "max_len": 15,
            },
        ),
        (
            "huawei",
            {
                "special_chars": "`~!@#$%^&*()-_=+\\|[{}];:'\",<.>/?",
                "min_len": 8,
                "max_len": 20,
            },
        ),
    ]

    def test_generates_acceptable_random_passwords(self):
        def is_acceptable_password(password):
            acceptable_length = self.min_len <= len(password) <= self.max_len
            if not acceptable_length:
                return False
            special = set(self.special_chars)
            has_special = any((c in special) for c in password)
            if not has_special:
                return False
            required_character_sets = 0
            if re.match(r".*[a-z].*", password) is not None:
                required_character_sets += 1
            if re.match(r".*[A-Z].*", password) is not None:
                required_character_sets += 1
            if re.match(r".*[0-9].*", password) is not None:
                required_character_sets += 1
            if required_character_sets < 2:
                return False
            # Test password doesn't have two or more occurrences of the
            # the same consecutive character.
            if bool(re.search(r"(.)\1", password)):
                return False
            return True

        max_attempts = 100
        acceptable = 0
        unacceptable = []
        for attempt in range(1, max_attempts + 1):
            candidate = generate_random_password(with_special_chars=True)
            if is_acceptable_password(candidate):
                acceptable += 1
            else:
                unacceptable.append(candidate)
        self.assertThat(
            acceptable,
            Equals(max_attempts),
            "%d unacceptable passwords out of %d attempted: %r"
            % (max_attempts - acceptable, max_attempts, unacceptable),
        )


class TestCommitIPMISettings(MAASTestCase):
    """Test commit_ipmi_settings()."""

    def test_commit_ipmi_settings(self):
        """Ensure bmc-config is run properly."""
        recorder = self.patch(maas_ipmi_autodetect, "run_command")
        filename = "foo"
        commit_ipmi_settings(filename)
        self.assertThat(
            recorder,
            MockCalledOnceWith(
                ("bmc-config", "--commit", "--filename", filename)
            ),
        )


class TestBMCSupportsLANPlus(MAASTestCase):
    """Tests for bmc_supports_lan2_0()."""

    scenarios = [
        ("Supports LAN 2.0", dict(output="IPMI Version: 2.0", support=True)),
        ("Supports LAN 1.5", dict(output="IPMI Version: 1.5", support=False)),
    ]

    def test_support_detection(self):
        """Test for positive and negative matches."""
        run_command = self.patch(maas_ipmi_autodetect, "run_command")
        run_command.return_value = self.output
        detected = bmc_supports_lan2_0()
        self.assertEqual(self.support, detected)

    def test_support_detection_ppc64el(self):
        """Test that ppc64el returns 2.0"""
        run_command = self.patch(maas_ipmi_autodetect, "run_command")
        run_command.return_value = ""
        ppc64le_platform = self.patch(platform, "machine")
        ppc64le_platform.return_value = "ppc64le"
        detected = bmc_supports_lan2_0()
        self.assertEqual(True, detected)


class TestGetIPMIIPAddress(MAASTestCase):
    """Tests for get_ipmi_ip_address()."""

    scenarios = [
        (
            "none",
            dict(
                output4="  IP_Address    \n\n",
                output_st="",
                output_dy="",
                expected=None,
            ),
        ),
        (
            "bogus",
            dict(
                output4="  IP_Address    bogus\n\n",
                output_st="",
                output_dy="",
                expected=None,
            ),
        ),
        (
            "ipv4",
            dict(
                output4="  IP_Address    192.168.1.1\n\n",
                output_st="",
                output_dy="",
                expected="192.168.1.1",
            ),
        ),
        (
            "ipv4-ipv6",
            dict(
                output4="  IP_Address    192.168.1.1\n\n",
                output_st="  IPv6_Static_Addresses 2001:db8::3\n\n",
                output_dy="",
                expected="192.168.1.1",
            ),
        ),
        (
            "static6",
            dict(
                output4="  IP_Address    0.0.0.0\n\n",
                output_st="  IPv6_Static_Addresses 2001:db8::3\n\n",
                output_dy="",
                expected="[2001:db8::3]",
            ),
        ),
        (
            "static6 multiple",
            dict(
                output4="  IP_Address    0.0.0.0\n\n",
                output_st="  IPv6_Static_Addresses fe80::3:7 2001:db8::3\n\n",
                output_dy="",
                expected="[2001:db8::3]",
            ),
        ),
        (
            "mixed6",
            dict(
                output4="  IP_Address    0.0.0.0\n\n",
                output_st="  IPv6_Static_Addresses 2001:db8::9:5\n\n",
                output_dy="  ## IPv6_Dynamic_Addresses 2001:db8::3\n\n",
                expected="[2001:db8::9:5]",
            ),
        ),
        (
            "dynamic6",
            dict(
                output4="  IP_Address    0.0.0.0\n\n",
                output_st="",
                output_dy="  ## IPv6_Dynamic_Addresses 2001:db8::3\n\n",
                expected="[2001:db8::3]",
            ),
        ),
        (
            "dynamic6 with link-local",
            dict(
                output4="  IP_Address    0.0.0.0\n\n",
                output_st="",
                output_dy="  ## IPv6_Dynamic_Addresses fe80::3:7 2001:db8::3\n\n",
                expected="[2001:db8::3]",
            ),
        ),
        (
            "dynamic6 multiple",
            dict(
                output4="  IP_Address    0.0.0.0\n\n",
                output_st="",
                output_dy="  ## IPv6_Dynamic_Addresses fe80::7 2001:db8::3 2001::5\n\n",
                expected="[2001:db8::3]",
            ),
        ),
        (
            "link-local",
            dict(
                output4="",
                output_st="",
                output_dy="  ## IPv6_Dynamic_IP_Addresses  fe80::7 fe80::3:9\n\n",
                expected=None,
            ),
        ),
        (
            "0.0.0.0",
            dict(
                output4="  IP_Address    0.0.0.0\n\n",
                output_st="",
                output_dy="",
                expected=None,
            ),
        ),
    ]

    def test_get_ipmi_ip_address(self):
        ret_values = {
            "Lan_Conf:IP_Address": self.output4,
            "Lan6_Conf:IPv6_Static_Addresses": self.output_st,
            "Lan6_Conf:IPv6_Dynamic_Addresses": self.output_dy,
        }

        def ret_val(arg):
            return ret_values[arg]

        self.patch(
            maas_ipmi_autodetect, "_bmc_get_ipmi_addresses"
        ).side_effect = ret_val
        actual = get_ipmi_ip_address()
        self.assertEqual(self.expected, actual)


class TestEnableLanChannel(MAASTestCase):
    def test_enable_lan_channel_if_disabled(self):
        """Test that Lan_Channel gets enabled if it is disabled"""
        # Mock the response of the BMC
        response = (
            "Section Lan_Channel\n"
            "    Volatile_Access_Mode    Disabled\n"
            "    Non_Volatile_Access_Mode    Disabled\n"
            "EndSection"
        )
        self.patch(maas_ipmi_autodetect, "bmc_get").return_value = response

        # Mock the function 'bmc_set'
        bmc_set_mock = self.patch(maas_ipmi_autodetect, "bmc_set")

        # Call the function
        set_ipmi_lan_channel_settings()

        # Check that the 'bmc_set_mock' was called
        self.assertThat(
            bmc_set_mock,
            MockAnyCall(
                "Lan_Channel:Volatile_Access_Mode", "Always_Available"
            ),
        )
        self.assertThat(
            bmc_set_mock,
            MockAnyCall(
                "Lan_Channel:Non_Volatile_Access_Mode", "Always_Available"
            ),
        )

    def test_dont_enable_lan_channel_if_already_enabled(self):
        """Test that Lan_Channel doesn't get enabled if disabled."""
        # Mock the response of the BMC
        response = (
            "Section Lan_Channel\n"
            "    Volatile_Access_Mode    Always_Available\n"
            "    Non_Volatile_Access_Mode    Always_Available\n"
            "EndSection"
        )
        self.patch(maas_ipmi_autodetect, "bmc_get").return_value = response

        # Mock the function 'bmc_set'
        bmc_set_mock = self.patch(maas_ipmi_autodetect, "bmc_set")

        # Call the function
        set_ipmi_lan_channel_settings()

        # Check that the 'bmc_set' mock function (bmc_set_mock) was not called.
        self.assertThat(bmc_set_mock, MockNotCalled())

    def test_set_ipmi_lan_channel_handles_calledprocesserror(self):
        "Test that set_ipmi_lan_channel handles CalledProcessError"
        response = (
            "Section Lan_Channel\n"
            "    Volatile_Access_Mode    Always_Available\n"
            "    Non_Volatile_Access_Mode    Always_Available\n"
            "EndSection"
        )
        self.patch(maas_ipmi_autodetect, "bmc_get").return_value = response
        bmc_set_mock = self.patch(maas_ipmi_autodetect, "bmc_set")
        bmc_set_mock.side_effect = subprocess.CalledProcessError(1, "bmc-set")
        set_ipmi_lan_channel_settings()
        self.assertRaises(subprocess.CalledProcessError, bmc_set_mock)
        self.assertThat(bmc_set_mock.call_args_list, HasLength(1))


class TestGetSystemBootType(MAASTestCase):
    def test_get_system_boot_type_efi(self):
        """Test that returns ."""
        boot_type = "efi"
        # path os.path.isdir to return True to simulate
        # that /sys/firmware/efi exists.
        self.patch(os.path, "isdir").return_value = True
        actual_boot_type = get_system_boot_type()
        self.assertEqual(boot_type, actual_boot_type)

    def test_get_system_boot_type_non_efi(self):
        """Test """
        boot_type = "auto"
        # path os.path.isdir to return False to simulate
        # that /sys/firmware/efi doesn't exist.
        self.patch(os.path, "isdir").return_value = False
        actual_boot_type = get_system_boot_type()
        self.assertEqual(boot_type, actual_boot_type)
