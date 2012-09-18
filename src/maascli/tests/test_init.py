# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maascli`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

import new

from maascli import (
    ArgumentParser,
    register,
    )
from maastesting.testcase import TestCase
from mock import sentinel


class TestArgumentParser(TestCase):

    def test_add_subparsers_disabled(self):
        parser = ArgumentParser()
        self.assertRaises(NotImplementedError, parser.add_subparsers)

    def test_subparsers_property(self):
        parser = ArgumentParser()
        # argparse.ArgumentParser.add_subparsers populates a _subparsers
        # attribute when called. Its contents are not the same as the return
        # value from add_subparsers, so we just use it an indicator here.
        self.assertIsNone(parser._subparsers)
        # Reference the subparsers property.
        subparsers = parser.subparsers
        # _subparsers is populated, meaning add_subparsers has been called on
        # the superclass.
        self.assertIsNotNone(parser._subparsers)
        # The subparsers property, once populated, always returns the same
        # object.
        self.assertIs(subparsers, parser.subparsers)


class TestRegister(TestCase):
    """Tests for `maascli.register`."""

    def test_empty(self):
        module = new.module(b"%s.test" % __name__)
        parser = ArgumentParser()
        register(module, parser)
        # No subparsers were registered.
        self.assertIsNone(parser._subparsers)

    def test_command(self):
        module = new.module(b"%s.test" % __name__)
        cmd = self.patch(module, "cmd_one")
        cmd.return_value = sentinel.execute
        parser = ArgumentParser()
        register(module, parser)
        # Subparsers were registered.
        self.assertIsNotNone(parser._subparsers)
        # The command was called once with a subparser called "one".
        subparser_one = parser.subparsers.choices["one"]
        cmd.assert_called_once_with(subparser_one)
        # The subparser has an appropriate execute default.
        self.assertIs(
            sentinel.execute,
            subparser_one.get_default("execute"))

    def test_commands(self):
        module = new.module(b"%s.test" % __name__)
        cmd_one = self.patch(module, "cmd_one")
        cmd_one.return_value = sentinel.x_one
        cmd_two = self.patch(module, "cmd_two")
        cmd_two.return_value = sentinel.x_two
        parser = ArgumentParser()
        register(module, parser)
        # The commands were called with appropriate subparsers.
        subparser_one = parser.subparsers.choices["one"]
        cmd_one.assert_called_once_with(subparser_one)
        subparser_two = parser.subparsers.choices["two"]
        cmd_two.assert_called_once_with(subparser_two)
        # The subparsers have appropriate execute defaults.
        self.assertIs(sentinel.x_one, subparser_one.get_default("execute"))
        self.assertIs(sentinel.x_two, subparser_two.get_default("execute"))

    def test_register(self):
        module = new.module(b"%s.test" % __name__)
        module_register = self.patch(module, "register")
        parser = ArgumentParser()
        register(module, parser)
        # No subparsers were registered; calling module.register does not
        # imply that this happens.
        self.assertIsNone(parser._subparsers)
        # The command was called once with a subparser called "one".
        module_register.assert_called_once_with(module, parser)

    def test_command_and_register(self):
        module = new.module(b"%s.test" % __name__)
        module_register = self.patch(module, "register")
        cmd = self.patch(module, "cmd_one")
        parser = ArgumentParser()
        register(module, parser)
        # Subparsers were registered because a command was found.
        self.assertIsNotNone(parser._subparsers)
        # The command was called once with a subparser called "one".
        module_register.assert_called_once_with(module, parser)
        # The command was called once with a subparser called "one".
        cmd.assert_called_once_with(
            parser.subparsers.choices["one"])
