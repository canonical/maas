# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Integration-test the `maascli` command."""


import os.path
import random
from subprocess import CalledProcessError, check_output, STDOUT

from fixtures import EnvironmentVariableFixture

from maascli import main
from maascli.config import ProfileConfig
from maascli.testing.config import make_configs
from maascli.utils import handler_command_name
from maastesting import dev_root
from maastesting.fixtures import CaptureStandardIO
from maastesting.testcase import MAASTestCase


def locate_maascli():
    return os.path.join(dev_root, "bin", "maas")


class TestMAASCli(MAASTestCase):
    def setUp(self):
        new_home = self.make_dir()
        self.useFixture(EnvironmentVariableFixture("HOME", new_home))
        return super().setUp()

    def run_command(self, *args):
        check_output([locate_maascli()] + list(args), stderr=STDOUT)

    def test_run_without_args_fails(self):
        self.assertRaises(CalledProcessError, self.run_command)

    def test_run_without_args_shows_help_reminder(self):
        try:
            self.run_command()
        except CalledProcessError as error:
            self.assertTrue(
                error.output.decode("utf-8").startswith(
                    "usage: maas [-h] COMMAND"
                )
            )

    def test_help_option_succeeds(self):
        try:
            self.run_command("-h")
        except CalledProcessError as error:
            self.fail(error.output.decode("ascii"))
        else:
            # The test is that we get here without error.
            pass

    def test_list_command_succeeds(self):
        try:
            self.run_command("list")
        except CalledProcessError as error:
            self.fail(error.output.decode("ascii"))
        else:
            # The test is that we get here without error.
            pass


class TestMain(MAASTestCase):
    """Tests of `maascli.main` directly."""

    def fake_profile(self):
        """Fake a profile."""
        configs = make_configs()  # Instance of FakeConfig.
        self.patch(ProfileConfig, "open").return_value = configs
        return configs

    def test_complains_about_too_few_arguments(self):
        configs = self.fake_profile()
        [profile_name] = configs
        resources = configs[profile_name]["description"]["resources"]
        resource_name = random.choice(resources)["name"]
        handler_name = handler_command_name(resource_name)
        command = "maas", profile_name, handler_name

        with CaptureStandardIO() as stdio:
            error = self.assertRaises(SystemExit, main, command)

        self.assertEqual(error.code, 2)
        error = stdio.getError()
        self.assertIn(
            f"usage: maas {profile_name} {handler_name} [-h] COMMAND ...",
            error,
        )
        self.assertIn("too few arguments", error)
