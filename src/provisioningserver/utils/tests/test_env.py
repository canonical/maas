# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for environment-related helpers."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import os

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from provisioningserver.utils.env import environment_variables
from testtools.testcase import ExpectedException


class TestEnvironmentVariables(MAASTestCase):
    """Tests for `environment_variables`."""

    def make_variable(self):
        return factory.make_name('testvar'), factory.make_name('value')

    def test__sets_variables(self):
        var, value = self.make_variable()
        with environment_variables({var: value}):
            env = os.environ.copy()
        self.assertEqual(value, env[var])

    def test__overrides_prior_values(self):
        var, prior_value = self.make_variable()
        temp_value = factory.make_name('temp-value')
        with environment_variables({var: prior_value}):
            with environment_variables({var: temp_value}):
                env = os.environ.copy()
        self.assertEqual(temp_value, env[var])

    def test__leaves_other_variables_intact(self):
        untouched_var, untouched_value = self.make_variable()
        var, value = self.make_variable()
        with environment_variables({untouched_var: untouched_value}):
            with environment_variables({var: value}):
                env = os.environ.copy()
        self.assertEqual(untouched_value, env[untouched_var])

    def test__restores_variables_to_previous_values(self):
        var, prior_value = self.make_variable()
        temp_value = factory.make_name('temp-value')
        with environment_variables({var: prior_value}):
            with environment_variables({var: temp_value}):
                pass
            env = os.environ.copy()
        self.assertEqual(prior_value, env[var])

    def test__restores_previously_unset_variables_to_being_unset(self):
        var, value = self.make_variable()
        self.assertNotIn(var, os.environ)
        with environment_variables({var: value}):
            pass
        self.assertNotIn(var, os.environ)

    def test__restores_even_after_exception(self):
        var, value = self.make_variable()
        self.assertNotIn(var, os.environ)

        class DeliberateException(Exception):
            pass

        with ExpectedException(DeliberateException):
            with environment_variables({var: value}):
                raise DeliberateException()

        self.assertNotIn(var, os.environ)
