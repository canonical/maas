# Copyright 2012, 2013 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Integration-test the `maascli` command."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import os.path
from subprocess import (
    CalledProcessError,
    check_output,
    STDOUT,
    )

from maastesting import root
from maastesting.testcase import MAASTestCase


def locate_maascli():
    return os.path.join(root, 'bin', 'maascli')


class TestMAASCli(MAASTestCase):

    def run_command(self, *args):
        check_output([locate_maascli()] + list(args), stderr=STDOUT)

    def test_run_without_args_fails(self):
        self.assertRaises(CalledProcessError, self.run_command)

    def test_run_without_args_shows_help_reminder(self):
        self.output_file = self.make_file('output')
        try:
            self.run_command()
        except CalledProcessError as e:
            pass
        self.assertIn(
            "Run %s --help for usage details." % locate_maascli(),
            e.output)

    def test_help_option_succeeds(self):
        self.run_command('-h')
        # The test is that we get here without error.
        pass

    def test_list_command_succeeds(self):
        self.run_command('list')
        # The test is that we get here without error.
        pass
