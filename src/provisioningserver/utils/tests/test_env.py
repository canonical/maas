# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import os

from testtools import ExpectedException

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from provisioningserver.path import get_maas_data_path
from provisioningserver.utils import env
from provisioningserver.utils.env import FileBackedID


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


class TestFileBackedID(MAASTestCase):
    def test_get_returns_None_if_file_does_not_exist(self):
        file_id = FileBackedID("test_id")
        self.assertEqual(str(file_id.path), get_maas_data_path("test_id"))
        self.assertFalse(file_id.path.exists())
        self.assertIsNone(file_id.get())

    def test_get_returns_None_if_file_is_empty(self):
        file_id = FileBackedID("test_id")
        file_id.path.write_text("")
        self.assertIsNone(file_id.get())

    def test_get_returns_None_if_file_is_whitespace(self):
        file_id = FileBackedID("test_id")
        file_id.path.write_text("    ")
        self.assertIsNone(file_id.get())

    def test_get_returns_contents_if__file_contains_something(self):
        content = factory.make_name("content")
        file_id = FileBackedID("test_id")
        file_id.path.write_text(content)
        self.assertEqual(file_id.get(), content)

    def test_get_strips_contents_if_file_contains_something(self):
        content = factory.make_name("content")
        file_id = FileBackedID("test_id")
        file_id.path.write_text(f"   {content}    ")
        self.assertEqual(file_id.get(), content)

    def test_get_rejects_non_ASCII_content(self):
        content = factory.make_unicode_non_ascii_string()
        file_id = FileBackedID("test_id")
        file_id.path.write_text(f"   {content}    ")
        self.assertRaises(UnicodeDecodeError, file_id.get)

    def test_get_caches_result(self):
        content = factory.make_name("content")
        file_id = FileBackedID("test_id")
        file_id.path.write_text(content)
        self.assertEqual(file_id.get(), content)
        file_id.path.unlink()
        self.assertEqual(file_id.get(), content)

    def test_set_writes_argument_to_file(self):
        content = factory.make_name("content")
        file_id = FileBackedID("test_id")
        file_id.set(content)
        self.assertEqual(file_id.path.read_text(), content)

    def test_set_deletes_file_if_argument_is_None(self):
        file_id = FileBackedID("test_id")
        file_id.path.touch()
        file_id.set(None)
        self.assertFalse(file_id.path.exists())
        self.assertIsNone(file_id.get())

    def test_set_deletes_file_if_argument_is_whitespace(self):
        file_id = FileBackedID("test_id")
        file_id.path.touch()
        file_id.set("            ")
        self.assertFalse(file_id.path.exists())
        self.assertIsNone(file_id.get())

    def test_set_None_does_nothing_if_maas_id_file_does_not_exist(self):
        file_id = FileBackedID("test_id")
        file_id.set(None)
        self.assertFalse(file_id.path.exists())

    def test_set_rejects_non_ASCII_content(self):
        content = factory.make_unicode_non_ascii_string()
        file_id = FileBackedID("test_id")
        self.assertRaises(UnicodeEncodeError, file_id.set, content)

    def test_set_caches(self):
        content = factory.make_name("content")
        file_id = FileBackedID("test_id")
        file_id.set(content)
        file_id.path.unlink()
        self.assertEqual(file_id.get(), content)

    def test_set_None_clears_cache(self):
        content = factory.make_name("content")
        file_id = FileBackedID("test_id")
        file_id.set(content)
        self.assertEqual(file_id.get(), content)
        file_id.set(None)
        self.assertIsNone(file_id.get())

    def test_set_None_clears_cache_if_file_does_not_exist(self):
        content = factory.make_name("content")
        file_id = FileBackedID("test_id")
        file_id.set(content)
        self.assertEqual(file_id.get(), content)
        file_id.path.unlink()
        file_id.set(None)
        self.assertIsNone(file_id.get())

    def test_set_does_not_cache_when_write_fails(self):
        mock_atomic_write = self.patch_autospec(env, "atomic_write")
        exception = factory.make_exception()
        mock_atomic_write.side_effect = exception
        content = factory.make_name("content")
        file_id = FileBackedID("test_id")
        self.assertRaises(type(exception), file_id.set, content)
        self.assertIsNone(file_id.get())

    def test_set_caches_to_normalized_value(self):
        content = factory.make_name("contents")
        file_id = FileBackedID("test_id")
        file_id.set(f"   {content}     ")
        self.assertEqual(file_id.get(), content)
