# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test the `local_config_{get,reset,set}` management commands."""


from functools import partial
import json
import random

from django.core.management import call_command
from django.core.management.base import CommandError
import yaml

from maasserver.config import RegionConfiguration
from maasserver.management.commands import _config as config
from maasserver.testing.config import RegionConfigurationFixture
from maasserver.testing.factory import factory
from maastesting.fixtures import CaptureStandardIO
from maastesting.testcase import MAASTestCase
from provisioningserver.config import ConfigurationOption


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
        (option, {"option": option.lstrip("-").replace("-", "_")})
        for option, args in config.gen_configuration_options_for_getting()
    )

    def test_dumps_yaml_to_stdout_by_default(self):
        stdio = call_get(**{self.option: True})
        settings = yaml.safe_load(stdio.getOutput())
        self.assertIn(self.option, settings)

    def test_dumps_yaml_to_stdout(self):
        stdio = call_get(**{self.option: True, "dump": config.dump_yaml})
        settings = yaml.safe_load(stdio.getOutput())
        self.assertIn(self.option, settings)

    def test_dumps_json_to_stdout(self):
        stdio = call_get(**{self.option: True, "dump": config.dump_json})
        settings = json.loads(stdio.getOutput())
        self.assertIn(self.option, settings)

    def test_dumps_plain_string_to_stdout(self):
        stdio = call_get(**{self.option: True, "dump": config.dump_plain})
        settings = stdio.getOutput()
        self.assertNotIn(self.option, settings)
        with RegionConfiguration.open() as configuration:
            self.assertIn(str(getattr(configuration, self.option)), settings)


class TestConfigurationReset(MAASTestCase):
    scenarios = tuple(
        (option, {"option": option.lstrip("-").replace("-", "_")})
        for option, args in config.gen_configuration_options_for_resetting()
    )

    def test_options_are_reset(self):
        self.useFixture(RegionConfigurationFixture())
        with RegionConfiguration.open_for_update() as configuration:
            # Give the option a random value.
            if isinstance(getattr(configuration, self.option), str):
                value = factory.make_name("foobar")
            else:
                value = factory.pick_port()
            setattr(configuration, self.option, value)
        stdio = call_reset(**{self.option: True})
        # Nothing is echoed back to the user.
        self.assertEqual("", stdio.getOutput())
        self.assertEqual("", stdio.getError())
        # There is no custom value in the configuration file.
        with open(RegionConfiguration.DEFAULT_FILENAME, "rb") as fd:
            settings = yaml.safe_load(fd)
        self.assertEqual({}, settings)


class TestConfigurationSet(MAASTestCase):
    scenarios = tuple(
        (option, {"option": option.lstrip("-").replace("-", "_")})
        for option, args in config.gen_configuration_options_for_setting()
    )

    def test_options_are_saved(self):
        self.useFixture(RegionConfigurationFixture())
        # Set the option to a random value.
        if self.option == "database_port":
            value = factory.pick_port()
        elif self.option in (
            "database_conn_max_age",
            "database_keepalive_count",
            "database_keepalive_interval",
            "database_keepalive_idle",
        ):
            value = random.randint(0, 60)
        elif self.option == "num_workers":
            value = random.randint(1, 16)
        elif self.option in [
            "debug",
            "debug_queries",
            "debug_http",
            "database_keepalive",
        ]:
            value = random.choice([True, False])
        else:
            value = factory.make_name("foobar")

        # Values are coming from the command-line so stringify.
        stdio = call_set(**{self.option: str(value)})

        # Nothing is echoed back to the user.
        self.assertEqual("", stdio.getOutput())
        self.assertEqual("", stdio.getError())

        # Some validators alter the given option, like adding an HTTP scheme
        # to a "bare" URL, so we merely check that the value contains the
        # given value, not that it exactly matches. Values are converted to a
        # str so Contains works with int values.
        with RegionConfiguration.open() as configuration:
            self.assertIn(str(value), str(getattr(configuration, self.option)))


class TestConfigurationSet_DatabasePort(MAASTestCase):
    """Tests for setting the database port.

    Setting the port is slightly special because the other options are mostly
    (at the time of writing) defined using `UnicodeString` validators, roughly
    meaning that anything goes, but the port is defined with `Int`.
    """

    def test_exception_when_port_is_not_an_integer(self):
        self.useFixture(RegionConfigurationFixture())
        error = self.assertRaises(CommandError, call_set, database_port="foo")
        self.assertEqual(
            "database-port: Please enter an integer value.", str(error)
        )

    def test_exception_when_port_is_too_low(self):
        self.useFixture(RegionConfigurationFixture())
        error = self.assertRaises(CommandError, call_set, database_port=0)
        self.assertEqual(
            str(error),
            "database-port: Please enter a number that is 1 or greater.",
        )

    def test_exception_when_port_is_too_high(self):
        self.useFixture(RegionConfigurationFixture())
        error = self.assertRaises(
            CommandError, call_set, database_port=2**16
        )
        self.assertEqual(
            str(error),
            "database-port: Please enter a number that is 65535 or smaller.",
        )


class TestConfigurationCommon(MAASTestCase):
    def test_gen_configuration_options(self):
        for name, option in config.gen_configuration_options():
            self.assertIsInstance(name, (str, bytes))
            self.assertIsInstance(option, (ConfigurationOption, property))

    def test_gen_mutable_configuration_options(self):
        for name, option in config.gen_mutable_configuration_options():
            self.assertIsInstance(name, (str, bytes))
            self.assertIsInstance(option, ConfigurationOption)

    def test_gen_configuration_options_for_getting(self):
        for name, option in config.gen_configuration_options_for_getting():
            self.assertNotIn("_", name)
            self.assertIsInstance(option, dict)

    def test_gen_configuration_options_for_resetting(self):
        for name, option in config.gen_configuration_options_for_resetting():
            self.assertNotIn("_", name)
            self.assertIsInstance(option, dict)

    def test_gen_configuration_options_for_setting(self):
        for name, option in config.gen_configuration_options_for_setting():
            self.assertNotIn("_", name)
            self.assertIsInstance(option, dict)
