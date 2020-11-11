# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maascli`."""


import sys

from maascli.parser import ArgumentParser, prepare_parser
from maastesting.factory import factory
from maastesting.matchers import MockCalledOnceWith
from maastesting.testcase import MAASTestCase


class TestArgumentParser(MAASTestCase):
    """Tests for `ArgumentParser`."""

    def test_add_subparsers_single_only(self):
        parser = ArgumentParser()
        parser.add_subparsers()
        self.assertRaises(AssertionError, parser.add_subparsers)

    def test_add_subparsers_returns_subparsers(self):
        parser = ArgumentParser()
        added_subparsers = parser.add_subparsers()
        self.assertIs(added_subparsers, parser.subparsers)

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

    def test_bad_arguments_prints_help_to_stderr(self):
        argv = ["maas", factory.make_name(prefix="profile"), "nodes"]
        parser = prepare_parser(argv)
        mock_print_help = self.patch(ArgumentParser, "print_help")
        self.patch(sys.exit)
        self.patch(ArgumentParser, "_print_error")
        # We need to catch this TypeError, because after our overridden error()
        # method is called, argparse expects the system to exit. Without
        # catching it, when we mock sys.exit() it will continue unexpectedly
        # and crash with the TypeError later.
        try:
            parser.parse_args(argv[1:])
        except TypeError:
            pass
        self.assertThat(mock_print_help, MockCalledOnceWith(sys.stderr))

    def test_bad_arguments_calls_sys_exit_2(self):
        argv = ["maas", factory.make_name(prefix="profile"), "nodes"]
        parser = prepare_parser(argv)
        self.patch(ArgumentParser, "print_help")
        mock_exit = self.patch(sys.exit)
        self.patch(ArgumentParser, "_print_error")
        # We need to catch this TypeError, because after our overridden error()
        # method is called, argparse expects the system to exit. Without
        # catching it, when we mock sys.exit() it will continue unexpectedly
        # and crash with the TypeError later.
        try:
            parser.parse_args(argv[1:])
        except TypeError:
            pass
        self.assertThat(mock_exit, MockCalledOnceWith(2))
