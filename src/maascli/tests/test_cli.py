# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maascli.cli`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from maascli import cli
from maascli.parser import ArgumentParser
from maastesting.testcase import TestCase


class TestRegisterCLICommands(TestCase):
    """Tests for `register_cli_commands`."""

    def test_registers_subparsers(self):
        parser = ArgumentParser()
        self.assertIsNone(parser._subparsers)
        cli.register_cli_commands(parser)
        self.assertIsNotNone(parser._subparsers)

    def test_subparsers_have_appropriate_execute_defaults(self):
        parser = ArgumentParser()
        cli.register_cli_commands(parser)
        self.assertIsInstance(
            parser.subparsers.choices['login'].get_default('execute'),
            cli.cmd_login)
