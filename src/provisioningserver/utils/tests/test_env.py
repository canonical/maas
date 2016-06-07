# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for environment-related helpers."""

__all__ = []

import os
import string

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from provisioningserver.path import get_path
from provisioningserver.utils.env import (
    environment_variables,
    get_maas_id,
    set_maas_id,
)
from testtools.matchers import (
    Equals,
    FileContains,
    FileExists,
    Is,
    Not,
)
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


def unlink_if_exists(path):
    """Unlink `path`, suppressing `FileNotFoundError`."""
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass


class TestMAASID(MAASTestCase):
    """Tests for `get_maas_id` and `set_maas_id`."""

    def setUp(self):
        super(TestMAASID, self).setUp()
        self.maas_id_path = get_path('/var/lib/maas/maas_id')
        self.addCleanup(unlink_if_exists, self.maas_id_path)

    def test_get_returns_None_if_maas_id_file_does_not_exist(self):
        self.assertThat(self.maas_id_path, Not(FileExists()))
        self.assertThat(get_maas_id(), Is(None))

    def test_get_returns_None_if_maas_id_file_is_empty(self):
        with open(self.maas_id_path, "w"):
            pass  # Write nothing.
        self.assertThat(get_maas_id(), Is(None))

    def test_get_returns_None_if_maas_id_file_is_whitespace(self):
        with open(self.maas_id_path, "w") as fd:
            fd.write(string.whitespace)
        self.assertThat(get_maas_id(), Is(None))

    def test_get_returns_contents_if_maas_id_file_contains_something(self):
        contents = factory.make_name("contents")
        with open(self.maas_id_path, "w") as fd:
            fd.write(contents)
        self.assertThat(get_maas_id(), Equals(contents))

    def test_get_strips_contents_if_maas_id_file_contains_something(self):
        contents = factory.make_name("contents")
        with open(self.maas_id_path, "w") as fd:
            fd.write(string.whitespace)
            fd.write(contents)
            fd.write(string.whitespace)
        self.assertThat(get_maas_id(), Equals(contents))

    def test_get_rejects_non_ASCII_content(self):
        contents = factory.make_unicode_non_ascii_string()
        with open(self.maas_id_path, "w") as fd:
            fd.write(contents)
        self.assertRaises(UnicodeDecodeError, get_maas_id)

    def test_set_writes_argument_to_maas_id_file(self):
        contents = factory.make_name("contents")
        set_maas_id(contents)
        self.assertThat(self.maas_id_path, FileContains(contents))

    def test_set_deletes_maas_id_file_if_argument_is_None(self):
        with open(self.maas_id_path, "w") as fd:
            fd.write("This file will be deleted.")
        set_maas_id(None)
        self.assertThat(self.maas_id_path, Not(FileExists()))

    def test_set_deletes_maas_id_file_if_argument_is_whitespace(self):
        with open(self.maas_id_path, "w") as fd:
            fd.write("This file will be deleted.")
        set_maas_id(string.whitespace)
        self.assertThat(self.maas_id_path, Not(FileExists()))

    def test_set_None_does_nothing_if_maas_id_file_idoes_not_exist(self):
        self.assertThat(self.maas_id_path, Not(FileExists()))
        set_maas_id(None)

    def test_set_rejects_non_ASCII_content(self):
        contents = factory.make_unicode_non_ascii_string()
        self.assertRaises(UnicodeEncodeError, set_maas_id, contents)
