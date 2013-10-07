# Copyright 2013 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the `maastesting` package."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from os.path import splitext
from warnings import (
    catch_warnings,
    warn,
    )

import maastesting
from maastesting.testcase import MAASTestCase
from testtools.matchers import (
    Equals,
    IsInstance,
    MatchesAll,
    MatchesListwise,
    MatchesStructure,
    StartsWith,
    )


class TestWarnings(MAASTestCase):

    scenarios = sorted(
        (package_name, dict(package_name=package_name))
        for package_name in maastesting.packages
        )

    def test_pattern_matches_package(self):
        self.assertRegexpMatches(
            self.package_name, maastesting.packages_expr)

    def test_pattern_matches_subpackage(self):
        self.assertRegexpMatches(
            self.package_name + ".foo", maastesting.packages_expr)

    def assertWarningsEnabled(self, category):
        message = "%s from %s" % (category.__name__, self.package_name)
        filename, ext = splitext(__file__)
        with catch_warnings(record=True) as log:
            warn(message, category=category)
        self.assertThat(log, MatchesListwise([
            MatchesStructure(
                message=MatchesAll(
                    IsInstance(category),
                    MatchesStructure.byEquality(args=(message,)),
                ),
                category=Equals(category),
                filename=StartsWith(filename),
            ),
        ]))

    def test_BytesWarning_enabled(self):
        self.assertWarningsEnabled(BytesWarning)

    def test_DeprecationWarning_enabled(self):
        self.assertWarningsEnabled(DeprecationWarning)

    def test_ImportWarning_enabled(self):
        self.assertWarningsEnabled(ImportWarning)
