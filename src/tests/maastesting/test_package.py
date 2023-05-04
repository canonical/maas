# Copyright 2013-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


from random import randint
import re
from warnings import catch_warnings, warn_explicit

import pytest

import maastesting
from maastesting.factory import factory


@pytest.mark.parametrize("package_name", sorted(maastesting.packages))
class TestWarnings:
    def warn(self, package_name, message, category):
        warn_explicit(
            message,
            category=category,
            filename=factory.make_name("file"),
            lineno=randint(1, 1000),
            module=package_name,
        )

    def assertWarningsEnabled(self, package_name, category):
        message = f"{category.__name__} from {package_name}"
        with catch_warnings(record=True) as log:
            self.warn(package_name, message, category=category)
        for warning in log:
            assert isinstance(warning.message, category)
            assert str(warning.message) == message
            assert warning.category == category

    def test_pattern_matches_package(self, package_name):
        assert re.search(maastesting.packages_expr, package_name)

    def test_pattern_matches_subpackage(self, package_name):
        assert re.search(maastesting.packages_expr, package_name + ".foo")

    def test_BytesWarning_enabled(self, package_name):
        with pytest.raises(BytesWarning):
            self.warn(package_name, factory.make_name("message"), BytesWarning)

    def test_DeprecationWarning_enabled(self, package_name):
        self.assertWarningsEnabled(package_name, DeprecationWarning)

    def test_ImportWarning_enabled(self, package_name):
        self.assertWarningsEnabled(package_name, ImportWarning)
