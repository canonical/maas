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

from maastesting.testcase import MAASTestCase
from maastesting.factory import factory

import snippets.maas_ipmi_autodetect

from snippets.maas_ipmi_autodetect import (
    format_user_key,
    run_command,
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


class TestBMCMethods(MAASTestCase):
    """Tests for the bmc_* methods."""

    scenarios = [
        ('bmc_get', dict(
            method_name='bmc_get', args=['Test:Key'],
            key_pair_fmt='--key-pair=%s', direction='--checkout')),
        ('bmc_set', dict(
            method_name='bmc_set', args=['Test:Key', 'myval'],
            key_pair_fmt='--key-pair=%s=%s', direction='--commit')),
        ('bmc_user_get', dict(
            method_name='bmc_user_get', args=['User10', 'Username'],
            key_pair_fmt='--key-pair=%s:%s', direction='--checkout')),
        ('bmc_user_set', dict(
            method_name='bmc_user_set', args=['User10', 'Username', 'maas'],
            key_pair_fmt='--key-pair=%s:%s=%s', direction='--commit'))
    ]

    def test_runs_bmc_config(self):
        """Ensure bmc-config is run properly."""

        recorder = self.patch(snippets.maas_ipmi_autodetect, 'run_command')

        # Grab the method from the class module where it lives.
        method = getattr(snippets.maas_ipmi_autodetect, self.method_name)

        method(*self.args)

        # call_args[0] is a tuple of ordered args to run_command.
        tokens = recorder.call_args[0][0]

        # Ensure bmc-config is being called.
        self.assertEqual(tokens[0], 'bmc-config')

        # Ensure the correct --commit or --checkout is used.
        self.assertIn(self.direction, tokens)

        # Note that the fmt string must use positional argument specifiers
        # if the order of appearance of args in the fmt string doesn't match
        # the order of args to the method.
        key_pair_string = self.key_pair_fmt % tuple(self.args)
        self.assertIn(key_pair_string, tokens)
