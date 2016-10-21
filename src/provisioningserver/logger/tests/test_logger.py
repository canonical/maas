# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for log.py"""

__all__ = []

import logging
import logging.handlers
import pathlib
import re
import subprocess
import sys

from maastesting.factory import factory
from maastesting.matchers import DocTestMatches
from maastesting.testcase import MAASTestCase
from provisioningserver.logger import (
    log,
    LoggingMode,
)
from provisioningserver.logger.log import (
    get_maas_logger,
    MAASLogger,
)
from provisioningserver.utils import typed
from provisioningserver.utils.shell import select_c_utf8_locale
from testtools.content import text_content


here = pathlib.Path(__file__).parent


@typed
def log_something(name: str, *, verbosity: int, mode: LoggingMode):
    env = dict(select_c_utf8_locale(), PYTHONPATH=":".join(sys.path))
    script = here.parent.joinpath("testing", "logsomething.py")
    args = "--name", name, "--verbosity", "%d" % verbosity, "--mode", mode.name
    cmd = (sys.executable, str(script)) + args
    output = subprocess.check_output(cmd, env=env, stderr=subprocess.STDOUT)
    return output.decode("utf-8")


# Matches lines like: 2016-10-18 14:23:55 [namespace#level] message
find_log_lines_re = re.compile(
    r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) [[](.*?)(?:#(.*))?[]] (.*)$",
    re.MULTILINE)


def find_log_lines(text):
    """Find logs in `text` that match `find_log_lines_re`.

    Checks for well-formed date/times but throws them away.
    """
    return [
        (ns, level, line) for (ts, ns, level, line) in
        find_log_lines_re.findall(text)
    ]


class TestLogging(MAASTestCase):
    """Test logging in MAAS as configured by `p.logger.configure`.

    The "twistd" tests reflect usage under `twistd`.

    The "command" tests reflect usage at an interactive terminal, like when
    invoking `maas-rackd`. The chief difference here is that neither stdout
    nor stderr are wrapped.
    """

    def test__twistd_default_verbosity(self):
        name = factory.make_name("log.name")
        logged = log_something(name, verbosity=2, mode=LoggingMode.TWISTD)
        self.addDetail("logged", text_content(logged))
        observed = find_log_lines(logged)
        expected = [
            (name, 'info', 'From `twisted.logger`.'),
            (name, 'warn', 'From `twisted.logger`.'),
            (name, 'error', 'From `twisted.logger`.'),
            (name, '', 'From `twisted.python.log`.'),
            (name, 'info', 'From `logging`.'),
            (name, 'warn', 'From `logging`.'),
            (name, 'error', 'From `logging`.'),
            ('maas.' + name, 'info', 'From `get_maas_logger`.'),
            ('maas.' + name, 'warn', 'From `get_maas_logger`.'),
            ('maas.' + name, 'error', 'From `get_maas_logger`.'),
            ('stdout', 'info', 'Printing to stdout.'),
            ('stderr', 'error', 'Printing to stderr.'),
            ('__main__', 'warn', 'UserWarning: This is a warning!'),
        ]
        self.assertSequenceEqual(expected, observed)

    def test__twistd_high_verbosity(self):
        name = factory.make_name("log.name")
        logged = log_something(name, verbosity=3, mode=LoggingMode.TWISTD)
        self.addDetail("logged", text_content(logged))
        observed = find_log_lines(logged)
        expected = [
            (name, 'debug', 'From `twisted.logger`.'),
            (name, 'info', 'From `twisted.logger`.'),
            (name, 'warn', 'From `twisted.logger`.'),
            (name, 'error', 'From `twisted.logger`.'),
            (name, '', 'From `twisted.python.log`.'),
            (name, 'debug', 'From `logging`.'),
            (name, 'info', 'From `logging`.'),
            (name, 'warn', 'From `logging`.'),
            (name, 'error', 'From `logging`.'),
            ('maas.' + name, 'debug', 'From `get_maas_logger`.'),
            ('maas.' + name, 'info', 'From `get_maas_logger`.'),
            ('maas.' + name, 'warn', 'From `get_maas_logger`.'),
            ('maas.' + name, 'error', 'From `get_maas_logger`.'),
            ('stdout', 'info', 'Printing to stdout.'),
            ('stderr', 'error', 'Printing to stderr.'),
            ('__main__', 'warn', 'UserWarning: This is a warning!'),
        ]
        self.assertSequenceEqual(expected, observed)

    def test__twistd_low_verbosity(self):
        name = factory.make_name("log.name")
        logged = log_something(name, verbosity=1, mode=LoggingMode.TWISTD)
        self.addDetail("logged", text_content(logged))
        observed = find_log_lines(logged)
        expected = [
            (name, 'warn', 'From `twisted.logger`.'),
            (name, 'error', 'From `twisted.logger`.'),
            (name, 'warn', 'From `logging`.'),
            (name, 'error', 'From `logging`.'),
            ('maas.' + name, 'warn', 'From `get_maas_logger`.'),
            ('maas.' + name, 'error', 'From `get_maas_logger`.'),
            ('stderr', 'error', 'Printing to stderr.'),
            ('__main__', 'warn', 'UserWarning: This is a warning!'),
        ]
        self.assertSequenceEqual(expected, observed)

    def test__twistd_lowest_verbosity(self):
        name = factory.make_name("log.name")
        logged = log_something(name, verbosity=0, mode=LoggingMode.TWISTD)
        self.addDetail("logged", text_content(logged))
        observed = find_log_lines(logged)
        expected = [
            (name, 'error', 'From `twisted.logger`.'),
            (name, 'error', 'From `logging`.'),
            ('maas.' + name, 'error', 'From `get_maas_logger`.'),
            ('stderr', 'error', 'Printing to stderr.'),
        ]
        self.assertSequenceEqual(expected, observed)

    def test__command_default_verbosity(self):
        name = factory.make_name("log.name")
        logged = log_something(name, verbosity=2, mode=LoggingMode.COMMAND)
        self.addDetail("logged", text_content(logged))
        observed = find_log_lines(logged)
        expected = [
            (name, 'info', 'From `twisted.logger`.'),
            (name, 'warn', 'From `twisted.logger`.'),
            (name, 'error', 'From `twisted.logger`.'),
            (name, '', 'From `twisted.python.log`.'),
            (name, 'info', 'From `logging`.'),
            (name, 'warn', 'From `logging`.'),
            (name, 'error', 'From `logging`.'),
            ('maas.' + name, 'info', 'From `get_maas_logger`.'),
            ('maas.' + name, 'warn', 'From `get_maas_logger`.'),
            ('maas.' + name, 'error', 'From `get_maas_logger`.'),
        ]
        self.assertSequenceEqual(expected, observed)
        self.assertThat(logged, DocTestMatches("""\
        ...
        Printing to stdout.
        Printing to stderr.
        This is a warning!
        """))

    def test__command_high_verbosity(self):
        name = factory.make_name("log.name")
        logged = log_something(name, verbosity=3, mode=LoggingMode.COMMAND)
        self.addDetail("logged", text_content(logged))
        observed = find_log_lines(logged)
        expected = [
            (name, 'debug', 'From `twisted.logger`.'),
            (name, 'info', 'From `twisted.logger`.'),
            (name, 'warn', 'From `twisted.logger`.'),
            (name, 'error', 'From `twisted.logger`.'),
            (name, '', 'From `twisted.python.log`.'),
            (name, 'debug', 'From `logging`.'),
            (name, 'info', 'From `logging`.'),
            (name, 'warn', 'From `logging`.'),
            (name, 'error', 'From `logging`.'),
            ('maas.' + name, 'debug', 'From `get_maas_logger`.'),
            ('maas.' + name, 'info', 'From `get_maas_logger`.'),
            ('maas.' + name, 'warn', 'From `get_maas_logger`.'),
            ('maas.' + name, 'error', 'From `get_maas_logger`.'),
        ]
        self.assertSequenceEqual(expected, observed)
        self.assertThat(logged, DocTestMatches("""\
        ...
        Printing to stdout.
        Printing to stderr.
        This is a warning!
        """))

    def test__command_low_verbosity(self):
        name = factory.make_name("log.name")
        logged = log_something(name, verbosity=1, mode=LoggingMode.COMMAND)
        self.addDetail("logged", text_content(logged))
        observed = find_log_lines(logged)
        expected = [
            (name, 'warn', 'From `twisted.logger`.'),
            (name, 'error', 'From `twisted.logger`.'),
            (name, 'warn', 'From `logging`.'),
            (name, 'error', 'From `logging`.'),
            ('maas.' + name, 'warn', 'From `get_maas_logger`.'),
            ('maas.' + name, 'error', 'From `get_maas_logger`.'),
        ]
        self.assertSequenceEqual(expected, observed)
        self.assertThat(logged, DocTestMatches("""\
        ...
        Printing to stdout.
        Printing to stderr.
        This is a warning!
        """))

    def test__command_lowest_verbosity(self):
        name = factory.make_name("log.name")
        logged = log_something(name, verbosity=0, mode=LoggingMode.COMMAND)
        self.addDetail("logged", text_content(logged))
        observed = find_log_lines(logged)
        expected = [
            (name, 'error', 'From `twisted.logger`.'),
            (name, 'error', 'From `logging`.'),
            ('maas.' + name, 'error', 'From `get_maas_logger`.'),
        ]
        self.assertSequenceEqual(expected, observed)
        self.assertThat(logged, DocTestMatches("""\
        ...
        Printing to stdout.
        Printing to stderr.
        This is a warning!
        """))


class TestMAASLogger(MAASTestCase):
    """Tests for the logger returned by `get_maas_logger`."""

    def test_sets_logger_name(self):
        self.patch(log, 'SysLogHandler')
        self.patch(logging, 'Formatter')
        name = factory.make_string()
        maaslog = get_maas_logger(name)
        self.assertEqual("maas.%s" % name, maaslog.name)

    def test_returns_same_logger_if_called_twice(self):
        self.patch(log, 'SysLogHandler')
        self.patch(logging, 'Formatter')
        name = factory.make_string()
        maaslog = get_maas_logger(name)
        maaslog_2 = get_maas_logger(name)
        self.assertIs(maaslog, maaslog_2)

    def test_exception_calls_disallowed(self):
        self.patch(log, 'SysLogHandler')
        self.patch(logging, 'Formatter')
        name = factory.make_string()
        maaslog = get_maas_logger(name)
        self.assertRaises(
            NotImplementedError, maaslog.exception,
            factory.make_string())

    def test_returns_MAASLogger_instances(self):
        self.patch(log, 'SysLogHandler')
        self.patch(logging, 'Formatter')
        name = factory.make_string()
        maaslog = get_maas_logger(name)
        self.assertIsInstance(maaslog, MAASLogger)

    def test_doesnt_affect_general_logger_class(self):
        self.patch(logging, 'Formatter')
        name = factory.make_string()
        get_maas_logger(name)
        self.assertIsNot(
            MAASLogger, logging.getLoggerClass())

    def test_general_logger_class_accepts_exceptions(self):
        self.patch(logging, 'Formatter')
        name = factory.make_string()
        get_maas_logger(name)
        other_logger = logging.getLogger()
        self.assertIsNone(other_logger.exception(factory.make_string()))
