# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for maas_ipmi_autodetect.py."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import subprocess

from collections import OrderedDict

from maastesting.testcase import MAASTestCase
from maastesting.factory import factory

from snippets import maas_ipmi_autodetect

from snippets.maas_ipmi_autodetect import (
    bmc_get_section,
    bmc_list_sections,
    format_user_key,
    get_user_record,
    list_user_numbers,
    parse_section,
    pick_user_number,
    pick_user_number_from_list,
    run_command,
    IPMIUserError
    )


class TestRunCommand(MAASTestCase):
    """Tests for the run_command method."""

    def test_output_returned(self):
        """Ensure output from stdout/stderr is returned to caller."""

        test_stdout = factory.getRandomString()
        test_stderr = factory.getRandomString()
        command = 'echo %s >&1 && echo %s >&2' % (test_stdout, test_stderr)

        output = run_command(['bash', '-c', command])

        self.assertEqual([test_stdout, test_stderr], output.split())

    def test_exception_on_failure(self):
        """"Failed commands should raise an exception."""

        self.assertRaises(subprocess.CalledProcessError, run_command, 'false')


class TestFormatUserKey(MAASTestCase):
    """Tests the format_user_key method."""

    def test_format_user_key(self):
        """Ensure user key strings are properly constructed."""

        user = factory.getRandomString()
        field = factory.getRandomString()

        user_key = format_user_key(user, field)

        expected = '%s:%s' % (user, field)

        self.assertEqual(expected, user_key)


class TestBMCKeyPairMethods(MAASTestCase):
    """Tests for methods that use bmc-config --key-pair"""

    scenarios = [
        ('bmc_get', dict(
            method_name='bmc_get', args=['Test:Key'],
            key_pair_fmt='--key-pair=%s', direction='--checkout')),
        ('bmc_set', dict(
            method_name='bmc_set', args=['Test:Key', 'myval'],
            key_pair_fmt='--key-pair=%s=%s', direction='--commit')),
        ('bmc_user_set', dict(
            method_name='bmc_user_set', args=['User10', 'Username', 'maas'],
            key_pair_fmt='--key-pair=%s:%s=%s', direction='--commit'))
    ]

    def test_runs_bmc_config(self):
        """Ensure bmc-config is run properly."""

        recorder = self.patch(maas_ipmi_autodetect, 'run_command')

        # Grab the method from the class module where it lives.
        method = getattr(maas_ipmi_autodetect, self.method_name)

        method(*self.args)

        # Note that the fmt string must use positional argument specifiers
        # if the order of appearance of args in the fmt string doesn't match
        # the order of args to the method.
        key_pair_string = self.key_pair_fmt % tuple(self.args)

        expected_args = ('bmc-config', self.direction, key_pair_string)
        recorder.assert_called_once_with(expected_args)


class TestBMCGetSection(MAASTestCase):
    """Tests for bmc_get_section()."""

    def test_runs_bmc_config(self):
        """Ensure bmc-config is called with the correct args."""
        recorder = self.patch(maas_ipmi_autodetect, 'run_command')

        section = 'foo'
        bmc_get_section(section)

        recorder.assert_called_once_with(
            ('bmc-config', '--checkout', '--section', section))


class TestGetUserRecord(MAASTestCase):
    """Tests for get_user_record()."""

    def test_get_user_record(self):
        """Ensure get_user_record() processes requests properly."""
        user_number = 'User1'
        user_text = 'some text'
        user_record = {'bar': 'baz'}

        bgs_mock = self.patch(maas_ipmi_autodetect, 'bmc_get_section')
        bgs_mock.return_value = user_text
        ps_mock = self.patch(maas_ipmi_autodetect, 'parse_section')
        ps_mock.return_value = (user_number, user_record)

        record = get_user_record(user_number)
        self.assertEqual(record, user_record)
        bgs_mock.assert_called_once_with(user_number)
        ps_mock.assert_called_once_with(user_text)


class TestBMCListSections(MAASTestCase):
    """Tests for bmc_list_sections()."""

    def test_bmc_list_sections(self):
        """Ensure bmc-config is called with the correct args."""
        recorder = self.patch(maas_ipmi_autodetect, 'run_command')
        bmc_list_sections()
        recorder.assert_called_once_with(('bmc-config', '-L'))


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
        mock = self.patch(maas_ipmi_autodetect, 'bmc_list_sections')
        mock.return_value = self.section_names
        expected = ['User1', 'User4', 'User3', 'User16']
        user_numbers = list_user_numbers()
        self.assertEqual(expected, user_numbers)

    def test_empty(self):
        """Ensure an empty list is handled correctly."""
        mock = self.patch(maas_ipmi_autodetect, 'bmc_list_sections')
        mock.return_value = ''
        results = list_user_numbers()
        self.assertEqual([], results)


class TestParseSection(MAASTestCase):
    """Tests for parse_section()."""

    section_template = (
        "Section Test\n"                # Section line, no leading space.
        "\tUsername\t\tBob\n"           # Normal line.
        " Enabled_User\t\tNo\n"         # Leading space, not tab.
        "\t\tPassword\t\tBobPass\n"     # Multiple leading tab.
        "\tAnother  Value\n"            # Separating space, not tab.
        "\tCharacters\t,./;:'\"[]{}|\\`~!@$%^&*()-_+="  # Gunk.
        "\n"                            # Blank line.
        "\tNotMe\n"                     # Single word.
        "\t#Or Me\n"                    # Comment line.
        "\tMe #Neither\n"               # Word followed by comment.
        "\tThree\tWord\tLine\n"         # More than two words.
        "\tFinal\tLine"                 # No trailing whitespace.
    )

    def test_matching(self):
        """Ensure only properly formatted User sections match."""

        record = parse_section(self.section_template)

        expected_attributes = {
            'Username': 'Bob',
            'Enabled_User': 'No',
            'Password': 'BobPass',
            'Another': 'Value',
            'Characters': ",./;:'\"[]{}|\\`~!@$%^&*()-_+=",
            'Three': 'Word',
            'Final': 'Line'
        }

        self.assertEqual('Test', record[0])
        self.assertEqual(expected_attributes, record[1])

    def test_fail_missing_section_line(self):
        """Ensure an exception is raised if the section header is missing."""
        no_section = self.section_template.replace('Section Test', '')
        self.assertRaises(Exception, parse_section, no_section)


def make_user(update=None):
    """Make a simple user record."""

    base = {'Lan_Enable_IPMI_Msgs': 'No'}

    if update:
        base.update(update)

    return base


def make_attributes(attributes_update=None):
    """Base user records with updates in an OrderedDict."""

    attributes_template = {
        'User1': {
            'Enable_User': 'Yes'
        },
        'User2': {
            'Username': 'admin',
            'Enable_User': 'Yes'
        }
    }

    base = OrderedDict(attributes_template)

    if attributes_update is not None:
        base.update(attributes_update)

    return base


class TestPickUserNumberFromList(MAASTestCase):
    """Tests for pick_user_number_from_list()."""

    scenarios = [
        ('Empty user list', dict(
            user_attributes={},
            expected=None)),
        ('Existing MAAS user', dict(
            user_attributes=make_attributes({
                'User4': make_user(),
                'User5': {'Username': 'maas'}}),
            expected='User5')),
        ('One blank user', dict(
            user_attributes=make_attributes(
                {'User7': make_user()}),
            expected='User7')),
        ('Multiple blank users', dict(
            user_attributes=make_attributes({
                'User7': make_user(),
                'User8': make_user()}),
            expected='User7')),
        ('One not blank user', dict(
            user_attributes=make_attributes(
                {'User7': make_user({'Username': 'foo'})}),
            expected=None)),
        ('One enabled blank user', dict(
            user_attributes=make_attributes({
                'User7': {'Enable_User': 'Yes'}}),
            expected='User7')),
        ('Skip User1', dict(
            user_attributes=make_attributes(
                {'User1': make_user()}),
            expected=None))
    ]

    def fetch_user_record(self, user_number):
        """Return the mock user data for a user_number."""
        return self.user_attributes[user_number]

    def test_user_choice(self):
        """Ensure the correct user, if any, is chosen."""

        mock = self.patch(maas_ipmi_autodetect, 'get_user_record')
        mock.side_effect = self.fetch_user_record
        current_users = self.user_attributes.keys()
        user = pick_user_number_from_list('maas', current_users)
        self.assertEqual(self.expected, user)


class TestPickUserNumber(MAASTestCase):
    """Tests for pick_user_number()."""

    def test_pick_user_number(self):
        """Ensure proper listing and selection of a user."""
        lun_mock = self.patch(maas_ipmi_autodetect, 'list_user_numbers')
        lun_mock.return_value = ['User1', 'User2']
        punfl_mock = self.patch(maas_ipmi_autodetect,
                                'pick_user_number_from_list')
        punfl_mock.return_value = 'User2'
        user_number = pick_user_number('maas')
        self.assertEqual('User2', user_number)

    def test_fail_raise_exception(self):
        """Ensure an exception is raised if no acceptable user is found."""
        mock = self.patch(maas_ipmi_autodetect, 'list_user_numbers')
        mock.return_value = []
        self.assertRaises(IPMIUserError, pick_user_number, 'maas')
