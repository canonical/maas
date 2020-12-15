# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for environment-related helpers."""


import os
import string

from testtools import ExpectedException
from testtools.matchers import Equals, FileContains, FileExists, Is, Not

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from provisioningserver.path import get_maas_data_path
from provisioningserver.utils import env
from provisioningserver.utils.fs import atomic_delete


class TestEnvironmentVariables(MAASTestCase):
    """Tests for `env.environment_variables`."""

    def make_variable(self):
        return factory.make_name("testvar"), factory.make_name("value")

    def test_sets_variables(self):
        var, value = self.make_variable()
        with env.environment_variables({var: value}):
            environment = os.environ.copy()
        self.assertEqual(value, environment[var])

    def test_overrides_prior_values(self):
        var, prior_value = self.make_variable()
        temp_value = factory.make_name("temp-value")
        with env.environment_variables({var: prior_value}):
            with env.environment_variables({var: temp_value}):
                environment = os.environ.copy()
        self.assertEqual(temp_value, environment[var])

    def test_leaves_other_variables_intact(self):
        untouched_var, untouched_value = self.make_variable()
        var, value = self.make_variable()
        with env.environment_variables({untouched_var: untouched_value}):
            with env.environment_variables({var: value}):
                environment = os.environ.copy()
        self.assertEqual(untouched_value, environment[untouched_var])

    def test_restores_variables_to_previous_values(self):
        var, prior_value = self.make_variable()
        temp_value = factory.make_name("temp-value")
        with env.environment_variables({var: prior_value}):
            with env.environment_variables({var: temp_value}):
                pass
            environment = os.environ.copy()
        self.assertEqual(prior_value, environment[var])

    def test_restores_previously_unset_variables_to_being_unset(self):
        var, value = self.make_variable()
        self.assertNotIn(var, os.environ)
        with env.environment_variables({var: value}):
            pass
        self.assertNotIn(var, os.environ)

    def test_restores_even_after_exception(self):
        var, value = self.make_variable()
        self.assertNotIn(var, os.environ)

        class DeliberateException(Exception):
            pass

        with ExpectedException(DeliberateException):
            with env.environment_variables({var: value}):
                raise DeliberateException()

        self.assertNotIn(var, os.environ)


def unlink_if_exists(path):
    """Unlink `path`, suppressing `FileNotFoundError`."""
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass


class TestMAASID(MAASTestCase):
    """Tests for `env.get_maas_id` and `env.set_maas_id`."""

    def setUp(self):
        super().setUp()
        self.maas_id_path = get_maas_data_path("maas_id")
        self.addCleanup(env.set_maas_id, None)
        env.set_maas_id(None)

    def test_get_returns_None_if_maas_id_file_does_not_exist(self):
        self.assertThat(self.maas_id_path, Not(FileExists()))
        self.assertThat(env.get_maas_id(), Is(None))

    def test_get_returns_None_if_maas_id_file_is_empty(self):
        with open(self.maas_id_path, "w"):
            pass  # Write nothing.
        self.assertThat(env.get_maas_id(), Is(None))

    def test_get_returns_None_if_maas_id_file_is_whitespace(self):
        with open(self.maas_id_path, "w") as fd:
            fd.write(string.whitespace)
        self.assertThat(env.get_maas_id(), Is(None))

    def test_get_returns_contents_if_maas_id_file_contains_something(self):
        contents = factory.make_name("contents")
        with open(self.maas_id_path, "w") as fd:
            fd.write(contents)
        self.assertThat(env.get_maas_id(), Equals(contents))

    def test_get_strips_contents_if_maas_id_file_contains_something(self):
        contents = factory.make_name("contents")
        with open(self.maas_id_path, "w") as fd:
            fd.write(string.whitespace)
            fd.write(contents)
            fd.write(string.whitespace)
        self.assertThat(env.get_maas_id(), Equals(contents))

    def test_get_rejects_non_ASCII_content(self):
        contents = factory.make_unicode_non_ascii_string()
        with open(self.maas_id_path, "w") as fd:
            fd.write(contents)
        self.assertRaises(UnicodeDecodeError, env.get_maas_id)

    def test_get_caches_result(self):
        contents = factory.make_name("contents")
        with open(self.maas_id_path, "w") as fd:
            fd.write(contents)
        self.assertEqual(contents, env.get_maas_id())
        os.unlink(self.maas_id_path)
        self.assertEqual(contents, env.get_maas_id())

    def test_set_writes_argument_to_maas_id_file(self):
        contents = factory.make_name("contents")
        env.set_maas_id(contents)
        self.assertThat(self.maas_id_path, FileContains(contents))

    def test_set_deletes_maas_id_file_if_argument_is_None(self):
        with open(self.maas_id_path, "w") as fd:
            fd.write("This file will be deleted.")
        env.set_maas_id(None)
        self.assertThat(self.maas_id_path, Not(FileExists()))
        self.assertIsNone(env.get_maas_id())

    def test_set_deletes_maas_id_file_if_argument_is_whitespace(self):
        with open(self.maas_id_path, "w") as fd:
            fd.write("This file will be deleted.")
        env.set_maas_id(string.whitespace)
        self.assertThat(self.maas_id_path, Not(FileExists()))
        self.assertIsNone(env.get_maas_id())

    def test_set_None_does_nothing_if_maas_id_file_does_not_exist(self):
        self.assertThat(self.maas_id_path, Not(FileExists()))
        env.set_maas_id(None)

    def test_set_rejects_non_ASCII_content(self):
        contents = factory.make_unicode_non_ascii_string()
        self.assertRaises(UnicodeEncodeError, env.set_maas_id, contents)

    def test_set_caches(self):
        contents = factory.make_name("contents")
        env.set_maas_id(contents)
        os.unlink(self.maas_id_path)
        self.assertEqual(contents, env.get_maas_id())

    def test_set_None_clears_cache(self):
        contents = factory.make_name("contents")
        env.set_maas_id(contents)
        self.assertThat(env.get_maas_id(), Equals(contents))
        env.set_maas_id(None)
        self.assertThat(env.get_maas_id(), Is(None))

    def test_set_None_clears_cache_if_maas_id_file_does_not_exist(self):
        contents = factory.make_name("contents")
        env.set_maas_id(contents)
        self.assertThat(env.get_maas_id(), Equals(contents))
        os.unlink(self.maas_id_path)
        env.set_maas_id(None)
        self.assertThat(env.get_maas_id(), Is(None))

    def test_set_does_not_cache_when_write_fails(self):
        mock_atomic_write = self.patch_autospec(env, "atomic_write")
        exception = factory.make_exception()
        mock_atomic_write.side_effect = exception
        contents = factory.make_name("contents")
        with ExpectedException(type(exception)):
            env.set_maas_id(contents)
        self.assertIsNone(env.get_maas_id())

    def test_set_caches_to_normalized_value(self):
        contents = "  %s  " % factory.make_name("contents")
        env.set_maas_id(contents)
        self.assertEqual(env._normalise_maas_id(contents), env.get_maas_id())

    def test_set_none_clears_cache(self):
        contents = factory.make_name("contents")
        env.set_maas_id(contents)
        self.assertEqual(contents, env.get_maas_id())
        env.set_maas_id(None)
        self.assertIsNone(env.get_maas_id())
        self.assertFalse(os.path.exists(self.maas_id_path))

    def test_set_none_works_with_missing_file(self):
        contents = factory.make_name("contents")
        env.set_maas_id(contents)
        atomic_delete(self.maas_id_path)
        env.set_maas_id(None)
        self.assertIsNone(env.get_maas_id())
        self.assertFalse(os.path.exists(self.maas_id_path))
