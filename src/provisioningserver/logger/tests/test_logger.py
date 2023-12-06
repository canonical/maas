# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for log.py"""


import pathlib
import subprocess
import sys

from testtools.content import text_content

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from provisioningserver.logger import LoggingMode
from provisioningserver.logger.testing import find_log_lines
from provisioningserver.utils.shell import get_env_with_locale

here = pathlib.Path(__file__).parent


def log_something(
    name: str, *, verbosity: int, set_verbosity: int = None, mode: LoggingMode
):
    env = dict(get_env_with_locale(), PYTHONPATH=":".join(sys.path))
    script = here.parent.joinpath("testing", "logsomething.py")
    args = [
        "--name",
        name,
        "--verbosity",
        "%d" % verbosity,
        "--mode",
        mode.name,
    ]
    if set_verbosity is not None:
        args.extend(["--set-verbosity", "%d" % set_verbosity])
    cmd = [sys.executable, str(script)] + args
    output = subprocess.check_output(cmd, env=env, stderr=subprocess.STDOUT)
    return output.decode("utf-8")


class TestLogging(MAASTestCase):
    """Test logging in MAAS as configured by `p.logger.configure`.

    The "twistd" tests reflect usage under `twistd`.

    The "command" tests reflect usage at an interactive terminal, like when
    invoking `maas-rackd`. The chief difference here is that neither stdout
    nor stderr are wrapped.
    """

    scenarios = (
        ("initial_only", {"initial_only": True, "increasing": False}),
        ("increasing_verbosity", {"initial_only": False, "increasing": True}),
        ("decreasing_verbosity", {"initial_only": False, "increasing": False}),
    )

    def _get_log_levels(self, verbosity_under_test: int):
        if self.initial_only:
            verbosity = verbosity_under_test
            set_verbosity = None
        elif self.increasing:
            verbosity = 0
            set_verbosity = verbosity_under_test
        else:
            verbosity = 3
            set_verbosity = verbosity_under_test
        return verbosity, set_verbosity

    def test_twistd_default_verbosity(self):
        verbosity, set_verbosity = self._get_log_levels(2)
        name = factory.make_name("log.name")
        logged = log_something(
            name,
            verbosity=verbosity,
            set_verbosity=set_verbosity,
            mode=LoggingMode.TWISTD,
        )
        self.addDetail("logged", text_content(logged))
        observed = find_log_lines(logged)
        expected = [
            (name, "info", "From `twisted.logger`."),
            (name, "warn", "From `twisted.logger`."),
            (name, "error", "From `twisted.logger`."),
            (name, "info", "From `twisted.python.log`."),
            ("logsomething", "info", "From `twisted.python.log.logfile`."),
            (name, "info", "From `logging`."),
            (name, "warn", "From `logging`."),
            (name, "error", "From `logging`."),
            ("maas." + name, "info", "From `get_maas_logger`."),
            ("maas." + name, "warn", "From `get_maas_logger`."),
            ("maas." + name, "error", "From `get_maas_logger`."),
            ("stdout", "info", "Printing to stdout."),
            ("stderr", "error", "Printing to stderr."),
            ("-", "warn", "UserWarning: This is a warning!"),
        ]
        self.assertEqual(expected, observed)

    def test_twistd_high_verbosity(self):
        verbosity, set_verbosity = self._get_log_levels(3)
        name = factory.make_name("log.name")
        logged = log_something(
            name,
            verbosity=verbosity,
            set_verbosity=set_verbosity,
            mode=LoggingMode.TWISTD,
        )
        self.addDetail("logged", text_content(logged))
        observed = find_log_lines(logged)
        expected = [
            (name, "debug", "From `twisted.logger`."),
            (name, "info", "From `twisted.logger`."),
            (name, "warn", "From `twisted.logger`."),
            (name, "error", "From `twisted.logger`."),
            (name, "info", "From `twisted.python.log`."),
            ("logsomething", "info", "From `twisted.python.log.logfile`."),
            (name, "debug", "From `logging`."),
            (name, "info", "From `logging`."),
            (name, "warn", "From `logging`."),
            (name, "error", "From `logging`."),
            ("maas." + name, "debug", "From `get_maas_logger`."),
            ("maas." + name, "info", "From `get_maas_logger`."),
            ("maas." + name, "warn", "From `get_maas_logger`."),
            ("maas." + name, "error", "From `get_maas_logger`."),
            ("stdout", "info", "Printing to stdout."),
            ("stderr", "error", "Printing to stderr."),
            ("-", "warn", "UserWarning: This is a warning!"),
        ]
        self.assertEqual(expected, observed)

    def test_twistd_low_verbosity(self):
        verbosity, set_verbosity = self._get_log_levels(1)
        name = factory.make_name("log.name")
        logged = log_something(
            name,
            verbosity=verbosity,
            set_verbosity=set_verbosity,
            mode=LoggingMode.TWISTD,
        )
        self.addDetail("logged", text_content(logged))
        observed = find_log_lines(logged)
        expected = [
            (name, "warn", "From `twisted.logger`."),
            (name, "error", "From `twisted.logger`."),
            (name, "warn", "From `logging`."),
            (name, "error", "From `logging`."),
            ("maas." + name, "warn", "From `get_maas_logger`."),
            ("maas." + name, "error", "From `get_maas_logger`."),
            ("stderr", "error", "Printing to stderr."),
            ("-", "warn", "UserWarning: This is a warning!"),
        ]
        self.assertEqual(expected, observed)

    def test_twistd_lowest_verbosity(self):
        verbosity, set_verbosity = self._get_log_levels(0)
        name = factory.make_name("log.name")
        logged = log_something(
            name,
            verbosity=verbosity,
            set_verbosity=set_verbosity,
            mode=LoggingMode.TWISTD,
        )
        self.addDetail("logged", text_content(logged))
        observed = find_log_lines(logged)
        expected = [
            (name, "error", "From `twisted.logger`."),
            (name, "error", "From `logging`."),
            ("maas." + name, "error", "From `get_maas_logger`."),
            ("stderr", "error", "Printing to stderr."),
        ]
        self.assertEqual(expected, observed)

    def test_command_default_verbosity(self):
        verbosity, set_verbosity = self._get_log_levels(2)
        name = factory.make_name("log.name")
        logged = log_something(
            name,
            verbosity=verbosity,
            set_verbosity=set_verbosity,
            mode=LoggingMode.COMMAND,
        )
        self.addDetail("logged", text_content(logged))
        observed = find_log_lines(logged)
        expected = [
            (name, "info", "From `twisted.logger`."),
            (name, "warn", "From `twisted.logger`."),
            (name, "error", "From `twisted.logger`."),
            (name, "info", "From `twisted.python.log`."),
            ("logsomething", "info", "From `twisted.python.log.logfile`."),
            (name, "info", "From `logging`."),
            (name, "warn", "From `logging`."),
            (name, "error", "From `logging`."),
            ("maas." + name, "info", "From `get_maas_logger`."),
            ("maas." + name, "warn", "From `get_maas_logger`."),
            ("maas." + name, "error", "From `get_maas_logger`."),
        ]
        self.assertEqual(expected, observed)
        for needle in [
            "Printing to stdout.",
            "Printing to stderr.",
            "This is a warning",
        ]:
            self.assertIn(needle, logged)

    def test_command_high_verbosity(self):
        verbosity, set_verbosity = self._get_log_levels(3)
        name = factory.make_name("log.name")
        logged = log_something(
            name,
            verbosity=verbosity,
            set_verbosity=set_verbosity,
            mode=LoggingMode.COMMAND,
        )
        self.addDetail("logged", text_content(logged))
        observed = find_log_lines(logged)
        expected = [
            (name, "debug", "From `twisted.logger`."),
            (name, "info", "From `twisted.logger`."),
            (name, "warn", "From `twisted.logger`."),
            (name, "error", "From `twisted.logger`."),
            (name, "info", "From `twisted.python.log`."),
            ("logsomething", "info", "From `twisted.python.log.logfile`."),
            (name, "debug", "From `logging`."),
            (name, "info", "From `logging`."),
            (name, "warn", "From `logging`."),
            (name, "error", "From `logging`."),
            ("maas." + name, "debug", "From `get_maas_logger`."),
            ("maas." + name, "info", "From `get_maas_logger`."),
            ("maas." + name, "warn", "From `get_maas_logger`."),
            ("maas." + name, "error", "From `get_maas_logger`."),
        ]
        self.assertEqual(expected, observed)
        for needle in [
            "Printing to stdout.",
            "Printing to stderr.",
            "This is a warning",
        ]:
            self.assertIn(needle, logged)

    def test_command_low_verbosity(self):
        verbosity, set_verbosity = self._get_log_levels(1)
        name = factory.make_name("log.name")
        logged = log_something(
            name,
            verbosity=verbosity,
            set_verbosity=set_verbosity,
            mode=LoggingMode.COMMAND,
        )
        self.addDetail("logged", text_content(logged))
        observed = find_log_lines(logged)
        expected = [
            (name, "warn", "From `twisted.logger`."),
            (name, "error", "From `twisted.logger`."),
            (name, "warn", "From `logging`."),
            (name, "error", "From `logging`."),
            ("maas." + name, "warn", "From `get_maas_logger`."),
            ("maas." + name, "error", "From `get_maas_logger`."),
        ]
        self.assertEqual(expected, observed)
        for needle in [
            "Printing to stdout.",
            "Printing to stderr.",
            "This is a warning",
        ]:
            self.assertIn(needle, logged)

    def test_command_lowest_verbosity(self):
        verbosity, set_verbosity = self._get_log_levels(0)
        name = factory.make_name("log.name")
        logged = log_something(
            name,
            verbosity=verbosity,
            set_verbosity=set_verbosity,
            mode=LoggingMode.COMMAND,
        )
        self.addDetail("logged", text_content(logged))
        observed = find_log_lines(logged)
        expected = [
            (name, "error", "From `twisted.logger`."),
            (name, "error", "From `logging`."),
            ("maas." + name, "error", "From `get_maas_logger`."),
        ]
        self.assertEqual(expected, observed)
        for needle in [
            "Printing to stdout.",
            "Printing to stderr.",
            "This is a warning",
        ]:
            self.assertIn(needle, logged)
