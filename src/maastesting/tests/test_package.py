# Copyright 2013-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the `maastesting` package."""


from random import randint
from warnings import catch_warnings, warn_explicit

from testtools.matchers import (
    Equals,
    IsInstance,
    MatchesAll,
    MatchesListwise,
    MatchesStructure,
)

import maastesting
from maastesting.factory import factory
from maastesting.testcase import MAASTestCase


class TestWarnings(MAASTestCase):

    scenarios = sorted(
        (package_name, dict(package_name=package_name))
        for package_name in maastesting.packages
    )

    def test_pattern_matches_package(self):
        self.assertRegex(self.package_name, maastesting.packages_expr)

    def test_pattern_matches_subpackage(self):
        self.assertRegex(self.package_name + ".foo", maastesting.packages_expr)

    def warn(self, message, category):
        warn_explicit(
            message,
            category=category,
            filename=factory.make_name("file"),
            lineno=randint(1, 1000),
            module=self.package_name,
        )

    def assertWarningsEnabled(self, category):
        message = "%s from %s" % (category.__name__, self.package_name)
        with catch_warnings(record=True) as log:
            self.warn(message, category=category)
        self.assertThat(
            log,
            MatchesListwise(
                [
                    MatchesStructure(
                        message=MatchesAll(
                            IsInstance(category),
                            MatchesStructure.byEquality(args=(message,)),
                        ),
                        category=Equals(category),
                    )
                ]
            ),
        )

    def test_BytesWarning_enabled(self):
        self.assertRaises(
            BytesWarning,
            self.warn,
            factory.make_name("message"),
            category=BytesWarning,
        )

    def test_DeprecationWarning_enabled(self):
        self.assertWarningsEnabled(DeprecationWarning)

    def test_ImportWarning_enabled(self):
        self.assertWarningsEnabled(ImportWarning)
