# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test `provisioningserver.utils`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from argparse import (
    ArgumentParser,
    Namespace,
    )
from io import BytesIO
import os
import random
from random import randint
from subprocess import CalledProcessError
import sys
import types

from maastesting.factory import factory
from maastesting.testcase import TestCase
from provisioningserver.utils import (
    ActionScript,
    atomic_write,
    increment_age,
    incremental_write,
    Safe,
    ShellTemplate,
    )
from testtools.matchers import FileContains


class TestSafe(TestCase):
    """Test `Safe`."""

    def test_value(self):
        something = object()
        safe = Safe(something)
        self.assertIs(something, safe.value)

    def test_repr(self):
        string = factory.getRandomString()
        safe = Safe(string)
        self.assertEqual("<Safe %r>" % string, repr(safe))


class TestWriteAtomic(TestCase):
    """Test `atomic_write`."""

    def test_atomic_write_overwrites_dest_file(self):
        content = factory.getRandomString()
        filename = self.make_file(contents=factory.getRandomString())
        atomic_write(content, filename)
        self.assertThat(filename, FileContains(content))


class TestIncrementalWrite(TestCase):
    """Test `incremental_write`."""

    def test_incremental_write_increments_modification_time(self):
        content = factory.getRandomString()
        filename = self.make_file(contents=factory.getRandomString())
        # Pretend that this file is older than it is.  So that
        # incrementing its mtime won't put it in the future.
        old_mtime = os.stat(filename).st_mtime - 10
        os.utime(filename, (old_mtime, old_mtime))
        incremental_write(content, filename)
        self.assertAlmostEqual(
            os.stat(filename).st_mtime, old_mtime + 1, delta=0.01)


class TestIncrementAge(TestCase):
    """Test `increment_age`."""

    def setUp(self):
        super(TestIncrementAge, self).setUp()
        self.filename = self.make_file()
        self.now = os.stat(self.filename).st_mtime

    def test_increment_age_sets_mtime_in_the_past(self):
        delta = random.randint(100, 200)
        increment_age(self.filename, old_mtime=None, delta=delta)
        self.assertAlmostEqual(
            os.stat(self.filename).st_mtime,
            self.now - delta, delta=2)

    def test_increment_age_increments_mtime(self):
        old_mtime = self.now - 200
        increment_age(self.filename, old_mtime=old_mtime)
        self.assertAlmostEqual(
            os.stat(self.filename).st_mtime, old_mtime + 1, delta=0.01)

    def test_increment_age_does_not_increment_mtime_if_in_future(self):
        old_mtime = self.now + 200
        increment_age(self.filename, old_mtime=old_mtime)
        self.assertAlmostEqual(
            os.stat(self.filename).st_mtime, old_mtime, delta=0.01)


class TestShellTemplate(TestCase):
    """Test `ShellTemplate`."""

    def test_substitute_escapes(self):
        # Substitutions are shell-escaped.
        template = ShellTemplate("{{a}}")
        expected = "'1 2 3'"
        observed = template.substitute(a="1 2 3")
        self.assertEqual(expected, observed)

    def test_substitute_does_not_escape_safe(self):
        # Substitutions will not be escaped if they're marked with `safe`.
        template = ShellTemplate("{{a|safe}}")
        expected = "$ ! ()"
        observed = template.substitute(a="$ ! ()")
        self.assertEqual(expected, observed)

    def test_substitute_does_not_escape_safe_objects(self):
        # Substitutions will not be escaped if they're `safe` objects.
        template = ShellTemplate("{{safe(a)}}")
        expected = "$ ! ()"
        observed = template.substitute(a="$ ! ()")
        self.assertEqual(expected, observed)


class TestActionScript(TestCase):
    """Test `ActionScript`."""

    def setUp(self):
        super(TestActionScript, self).setUp()
        # ActionScript.setup() is not safe to run in the test suite.
        self.patch(ActionScript, "setup", lambda self: None)
        # ArgumentParser sometimes likes to print to stdout/err.
        self.patch(sys, "stdout", BytesIO())
        self.patch(sys, "stderr", BytesIO())

    def test_init(self):
        description = factory.getRandomString()
        script = ActionScript(description)
        self.assertIsInstance(script.parser, ArgumentParser)
        self.assertEqual(description, script.parser.description)

    def test_register(self):
        handler = types.ModuleType(b"handler")
        handler.add_arguments = lambda parser: (
            self.assertIsInstance(parser, ArgumentParser))
        handler.run = lambda args: (
            self.assertIsInstance(args, int))
        script = ActionScript("Description")
        script.register("slay", handler)
        self.assertIn("slay", script.subparsers.choices)
        action_parser = script.subparsers.choices["slay"]
        self.assertIsInstance(action_parser, ArgumentParser)

    def test_register_without_add_arguments(self):
        # ActionScript.register will crash if the handler has no
        # add_arguments() callable.
        handler = types.ModuleType(b"handler")
        handler.run = lambda args: None
        script = ActionScript("Description")
        error = self.assertRaises(
            AttributeError, script.register, "decapitate", handler)
        self.assertIn("'add_arguments'", "%s" % error)

    def test_register_without_run(self):
        # ActionScript.register will crash if the handler has no run()
        # callable.
        handler = types.ModuleType(b"handler")
        handler.add_arguments = lambda parser: None
        script = ActionScript("Description")
        error = self.assertRaises(
            AttributeError, script.register, "decapitate", handler)
        self.assertIn("'run'", "%s" % error)

    def test_call(self):
        handler_calls = []
        handler = types.ModuleType(b"handler")
        handler.add_arguments = lambda parser: None
        handler.run = handler_calls.append
        script = ActionScript("Description")
        script.register("amputate", handler)
        error = self.assertRaises(SystemExit, script, ["amputate"])
        self.assertEqual(0, error.code)
        self.assertEqual(1, len(handler_calls))
        self.assertIsInstance(handler_calls[0], Namespace)

    def test_call_invalid_choice(self):
        script = ActionScript("Description")
        self.assertRaises(SystemExit, script, ["disembowel"])
        self.assertIn(b"invalid choice", sys.stderr.getvalue())

    def test_call_with_exception(self):
        # Most exceptions from run() are propagated.
        handler = types.ModuleType(b"handler")
        handler.add_arguments = lambda parser: None
        handler.run = lambda args: 0 / 0
        script = ActionScript("Description")
        script.register("eviscerate", handler)
        self.assertRaises(ZeroDivisionError, script, ["eviscerate"])

    def test_call_with_process_exception(self):
        # CalledProcessError is converted into SystemExit.
        exception = CalledProcessError(
            randint(0, 256), [factory.getRandomString()],
            factory.getRandomString().encode("ascii"))

        def raise_exception():
            raise exception

        handler = types.ModuleType(b"handler")
        handler.add_arguments = lambda parser: None
        handler.run = lambda args: raise_exception()
        script = ActionScript("Description")
        script.register("sever", handler)
        error = self.assertRaises(SystemExit, script, ["sever"])
        self.assertEqual(exception.returncode, error.code)

    def test_call_with_keyboard_interrupt(self):
        # KeyboardInterrupt is silently converted into SystemExit, with an
        # exit code of 1.

        def raise_exception():
            raise KeyboardInterrupt()

        handler = types.ModuleType(b"handler")
        handler.add_arguments = lambda parser: None
        handler.run = lambda args: raise_exception()
        script = ActionScript("Description")
        script.register("smash", handler)
        error = self.assertRaises(SystemExit, script, ["smash"])
        self.assertEqual(1, error.code)
