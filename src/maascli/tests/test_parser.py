# Copyright 2012, 2013 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maascli`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from maascli.parser import (
    ArgumentParser,
    get_profile_option,
    )
from maastesting.factory import factory
from maastesting.testcase import MAASTestCase


class TestArgumentParser(MAASTestCase):
    """Tests for `ArgumentParser`."""

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


class TestGetProfileOption(MAASTestCase):
    """Tests for `get_profile_option`."""

    def test_parses_profile_option(self):
        profile = factory.make_name('profile')
        self.assertEqual(profile, get_profile_option(['--profile', profile]))

    def test_ignores_other_options(self):
        profile = factory.make_name('profile')
        self.assertEqual(
            profile,
            get_profile_option([
                '--unrelated', 'option',
                '--profile', profile,
                factory.getRandomString(),
                ]))

    def test_ignores_help_option(self):
        # This is a bit iffy: the most likely symptom if this fails is
        # actually that the test process exits!
        profile = factory.make_name('profile')
        self.assertEqual(
            profile,
            get_profile_option(['--help', '--profile', profile]))
