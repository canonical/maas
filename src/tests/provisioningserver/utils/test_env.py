# Copyright 2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import os

import pytest

from provisioningserver.path import get_maas_data_path
from provisioningserver.utils import env
from provisioningserver.utils.env import FileBackedValue


@pytest.fixture
def make_variable(factory):
    def make():
        return factory.make_name("testvar"), factory.make_name("value")

    yield make


class TestEnvironmentVariables:
    def test_sets_variables(self, make_variable):
        var, value = make_variable()
        with env.environment_variables({var: value}):
            environment = os.environ.copy()
        assert environment[var] == value

    def test_overrides_prior_values(self, factory, make_variable):
        var, prior_value = make_variable()
        temp_value = factory.make_name("temp-value")
        with env.environment_variables({var: prior_value}):
            with env.environment_variables({var: temp_value}):
                environment = os.environ.copy()
        assert environment[var] == temp_value

    def test_leaves_other_variables_intact(self, make_variable):
        untouched_var, untouched_value = make_variable()
        var, value = make_variable()
        with env.environment_variables({untouched_var: untouched_value}):
            with env.environment_variables({var: value}):
                environment = os.environ.copy()
        assert environment[untouched_var] == untouched_value

    def test_restores_variables_to_previous_values(
        self, factory, make_variable
    ):
        var, prior_value = make_variable()
        temp_value = factory.make_name("temp-value")
        with env.environment_variables({var: prior_value}):
            with env.environment_variables({var: temp_value}):
                pass
            environment = os.environ.copy()
        assert environment[var] == prior_value

    def test_restores_previously_unset_variables_to_being_unset(
        self, make_variable
    ):
        var, value = make_variable()
        assert var not in os.environ
        with env.environment_variables({var: value}):
            pass
        assert var not in os.environ

    def test_restores_even_after_exception(self, make_variable):
        var, value = make_variable()
        assert var not in os.environ

        class DeliberateException(Exception):
            pass

        with pytest.raises(DeliberateException):
            with env.environment_variables({var: value}):
                raise DeliberateException()


@pytest.fixture
def file_value(factory):
    """Return a new FileBackedValue with a random name.

    This is to ensure that tests don't collide on the same name.
    """
    yield FileBackedValue(factory.make_name("test_value"))


class TestFileBackedValue:
    def test_get_returns_None_if_file_does_not_exist(self, file_value):
        assert str(file_value.path) == get_maas_data_path(file_value.name)
        assert not file_value.path.exists()
        assert file_value.get() is None

    def test_get_returns_None_if_file_is_empty(self, file_value):
        file_value.path.write_text("")
        assert file_value.get() is None

    def test_get_returns_None_if_file_is_whitespace(self, file_value):
        file_value.path.write_text("    ")
        assert file_value.get() is None

    def test_get_returns_contents_if__file_contains_something(
        self, factory, file_value
    ):
        content = factory.make_name("content")
        file_value.path.write_text(content)
        assert file_value.get() == content

    def test_get_strips_contents_if_file_contains_something(
        self, factory, file_value
    ):
        content = factory.make_name("content")
        file_value.path.write_text(f"   {content}    ")
        assert file_value.get() == content

    def test_get_rejects_non_ASCII_content(self, factory, file_value):
        content = factory.make_unicode_non_ascii_string()
        file_value.path.write_text(f"   {content}    ")
        with pytest.raises(UnicodeDecodeError):
            file_value.get()

    def test_get_caches_result(self, factory, file_value):
        content = factory.make_name("content")
        file_value.path.write_text(content)
        assert file_value.get() == content
        file_value.path.unlink()
        assert file_value.get() == content

    def test_set_writes_argument_to_file(self, factory, file_value):
        content = factory.make_name("content")
        file_value.set(content)
        assert file_value.path.read_text() == content

    def test_set_deletes_file_if_argument_is_None(self, file_value):
        file_value.path.touch()
        file_value.set(None)
        assert not file_value.path.exists()
        assert file_value.get() is None

    def test_set_deletes_file_if_argument_is_whitespace(self, file_value):
        file_value.path.touch()
        file_value.set("            ")
        assert not file_value.path.exists()
        assert file_value.get() is None

    def test_set_None_does_nothing_if_maas_id_file_does_not_exist(
        self, file_value
    ):
        file_value.set(None)
        assert not file_value.path.exists()

    def test_set_rejects_non_ASCII_content(self, factory, file_value):
        content = factory.make_unicode_non_ascii_string()
        with pytest.raises(UnicodeEncodeError):
            file_value.set(content)

    def test_set_caches(self, factory, file_value):
        content = factory.make_name("content")
        file_value.set(content)
        file_value.path.unlink()
        assert file_value.get() == content

    def test_set_None_clears_cache(self, factory, file_value):
        content = factory.make_name("content")
        file_value.set(content)
        assert file_value.get() == content
        file_value.set(None)
        assert file_value.get() is None

    def test_set_None_clears_cache_if_file_does_not_exist(
        self, factory, file_value
    ):
        content = factory.make_name("content")
        file_value.set(content)
        assert file_value.get() == content
        file_value.path.unlink()
        file_value.set(None)
        assert file_value.get() is None

    def test_set_does_not_cache_when_write_fails(
        self, mocker, factory, file_value
    ):
        mock_atomic_write = mocker.patch.object(env, "atomic_write")
        exception = factory.make_exception()
        mock_atomic_write.side_effect = exception
        content = factory.make_name("content")
        with pytest.raises(type(exception)):
            file_value.set(content)
        assert file_value.get() is None

    def test_set_caches_to_normalized_value(self, factory, file_value):
        content = factory.make_name("contents")
        file_value.set(f"   {content}     ")
        assert file_value.get() == content

    def test_clear_cached_reads_again(self, factory, file_value):
        content = factory.make_name("content")
        file_value.set(content)
        assert file_value.get() == content
        file_value.clear_cached()
        file_value.path.write_text("new content")
        # the file is read again
        assert file_value.get() == "new content"
