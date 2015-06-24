# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test the `local_config_{get,reset,set}` management commands."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from functools import partial
import json

from django.core.management import call_command
from maasserver.config import RegionConfiguration
from maasserver.management.commands import _config as config
from maasserver.testing.config import RegionConfigurationFixture
from maasserver.testing.factory import factory
from maastesting.fixtures import CaptureStandardIO
from maastesting.testcase import MAASTestCase
from provisioningserver.config import ConfigurationOption
from testtools.matchers import (
    AfterPreprocessing,
    AllMatch,
    Contains,
    Equals,
    HasLength,
    Is,
    IsInstance,
    MatchesAll,
    MatchesListwise,
    MatchesStructure,
    Not,
)
import yaml


def call_nnn(command, **options):
    """Call `command`, return captures standard IO.

    See `call_command`.

    :return: :class:`CaptureStandardIO` instance.
    """
    with CaptureStandardIO() as stdio:
        call_command(command, **options)
    return stdio

call_get = partial(call_nnn, "local_config_get")
call_reset = partial(call_nnn, "local_config_reset")
call_set = partial(call_nnn, "local_config_set")


class TestConfigurationGet(MAASTestCase):

    scenarios = tuple(
        (option.dest, {"option": option})
        for option in config.gen_configuration_options_for_getting()
    )

    def test__dumps_yaml_to_stdout_by_default(self):
        stdio = call_get(**{self.option.dest: True})
        settings = yaml.safe_load(stdio.getOutput())
        self.assertThat(settings, Contains(self.option.dest))

    def test__dumps_yaml_to_stdout(self):
        stdio = call_get(**{self.option.dest: True, "dump": config.dump_yaml})
        settings = yaml.safe_load(stdio.getOutput())
        self.assertThat(settings, Contains(self.option.dest))

    def test__dumps_json_to_stdout(self):
        stdio = call_get(**{self.option.dest: True, "dump": config.dump_json})
        settings = json.loads(stdio.getOutput())
        self.assertThat(settings, Contains(self.option.dest))

    def test__dumps_plain_string_to_stdout(self):
        stdio = call_get(**{self.option.dest: True, "dump": config.dump_plain})
        settings = stdio.getOutput()
        self.assertThat(settings, Not(Contains(self.option.dest)))
        with RegionConfiguration.open() as configuration:
            self.assertThat(settings, Contains(
                getattr(configuration, self.option.dest)))


class TestConfigurationReset(MAASTestCase):

    scenarios = tuple(
        (option.dest, {"option": option})
        for option in config.gen_configuration_options_for_resetting()
    )

    def test__options_are_reset(self):
        self.useFixture(RegionConfigurationFixture())
        # Give the option a random value.
        value = factory.make_name("foobar")
        with RegionConfiguration.open() as configuration:
            setattr(configuration, self.option.dest, value)
        stdio = call_reset(**{self.option.dest: True})
        # Nothing is echoed back to the user.
        self.assertThat(stdio.getOutput(), Equals(""))
        self.assertThat(stdio.getError(), Equals(""))
        # There is no custom value in the configuration file.
        with open(RegionConfiguration.DEFAULT_FILENAME, "rb") as fd:
            settings = yaml.safe_load(fd)
        self.assertThat(settings, Equals({}))


class TestConfigurationSet(MAASTestCase):

    scenarios = tuple(
        (option.dest, {"option": option})
        for option in config.gen_configuration_options_for_setting()
    )

    def test__options_are_saved(self):
        self.useFixture(RegionConfigurationFixture())
        # Set the option to a random value.
        value = factory.make_name("foobar")
        stdio = call_set(**{self.option.dest: value})
        # Nothing is echoed back to the user.
        self.assertThat(stdio.getOutput(), Equals(""))
        self.assertThat(stdio.getError(), Equals(""))
        # Some validators alter the given option, like adding an HTTP scheme
        # to a "bare" URL, so we merely check that the value contains the
        # given value, not that it exactly matches.
        with RegionConfiguration.open() as configuration:
            self.assertThat(
                getattr(configuration, self.option.dest),
                Contains(value))


class TestConfigurationCommon(MAASTestCase):

    is_string = IsInstance(unicode)
    is_single_line = AfterPreprocessing(unicode.splitlines, HasLength(1))
    is_help_string = MatchesAll(is_string, is_single_line, first_only=True)

    def test_gen_configuration_options(self):
        self.assertThat(
            config.gen_configuration_options(),
            AllMatch(
                MatchesListwise([
                    IsInstance(unicode, bytes),
                    IsInstance(ConfigurationOption, property),
                ]),
            ))

    def test_gen_mutable_configuration_options(self):
        self.assertThat(
            config.gen_mutable_configuration_options(),
            AllMatch(
                MatchesListwise([
                    IsInstance(unicode, bytes),
                    IsInstance(ConfigurationOption),
                ]),
            ))

    def test_gen_configuration_options_for_getting(self):
        self.assertThat(
            config.gen_configuration_options_for_getting(),
            AllMatch(
                MatchesStructure(
                    _long_opts=MatchesListwise([Not(Contains("_"))]),
                    _short_opts=MatchesListwise([]),
                    action=Equals("store_true"),
                    default=Is(False),
                    dest=IsInstance(unicode, bytes),
                    help=self.is_help_string,
                ),
            ))

    def test_gen_configuration_options_for_resetting(self):
        self.assertThat(
            config.gen_configuration_options_for_resetting(),
            AllMatch(
                MatchesStructure(
                    _long_opts=MatchesListwise([Not(Contains("_"))]),
                    _short_opts=MatchesListwise([]),
                    action=Equals("store_true"),
                    default=Is(False),
                    dest=IsInstance(unicode, bytes),
                    help=self.is_help_string,
                ),
            ))

    def test_gen_configuration_options_for_setting(self):
        self.assertThat(
            config.gen_configuration_options_for_setting(),
            AllMatch(
                MatchesStructure(
                    _long_opts=MatchesListwise([Not(Contains("_"))]),
                    _short_opts=MatchesListwise([]),
                    action=Equals("store"),
                    default=Is(None),
                    dest=IsInstance(unicode, bytes),
                    help=self.is_help_string,
                ),
            ))
