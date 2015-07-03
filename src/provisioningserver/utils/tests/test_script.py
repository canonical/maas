# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the subcommand utilities."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from argparse import (
    ArgumentParser,
    Namespace,
)
import os
from random import randint
import stat
import StringIO
from subprocess import (
    CalledProcessError,
    PIPE,
    Popen,
)
import sys
import types

from maastesting import bindir
from maastesting.factory import factory
from maastesting.matchers import MockCalledOnceWith
from maastesting.testcase import MAASTestCase
import provisioningserver.utils
from provisioningserver.utils.script import (
    ActionScript,
    AtomicWriteScript,
)
from testtools.matchers import (
    FileContains,
    MatchesStructure,
)


class TestActionScript(MAASTestCase):
    """Test `ActionScript`."""

    factory = ActionScript

    def setUp(self):
        super(TestActionScript, self).setUp()
        # ActionScript.setup() is not safe to run in the test suite.
        self.patch(ActionScript, "setup", lambda self: None)
        # ArgumentParser sometimes likes to print to stdout/err. Use
        # StringIO.StringIO to be relaxed about bytes/unicode (argparse uses
        # bytes). When moving to Python 3 this will need to be tightened up.
        self.patch(sys, "stdout", StringIO.StringIO())
        self.patch(sys, "stderr", StringIO.StringIO())

    def test_init(self):
        description = factory.make_string()
        script = self.factory(description)
        self.assertIsInstance(script.parser, ArgumentParser)
        self.assertEqual(description, script.parser.description)

    def test_register(self):
        handler = types.ModuleType(b"handler")
        handler.add_arguments = lambda parser: (
            self.assertIsInstance(parser, ArgumentParser))
        handler.run = lambda args: (
            self.assertIsInstance(args, int))
        script = self.factory("Description")
        script.register("slay", handler)
        self.assertIn("slay", script.subparsers.choices)
        action_parser = script.subparsers.choices["slay"]
        self.assertIsInstance(action_parser, ArgumentParser)

    def test_register_without_add_arguments(self):
        # ActionScript.register will crash if the handler has no
        # add_arguments() callable.
        handler = types.ModuleType(b"handler")
        handler.run = lambda args: None
        script = self.factory("Description")
        error = self.assertRaises(
            AttributeError, script.register, "decapitate", handler)
        self.assertIn("'add_arguments'", "%s" % error)

    def test_register_without_run(self):
        # ActionScript.register will crash if the handler has no run()
        # callable.
        handler = types.ModuleType(b"handler")
        handler.add_arguments = lambda parser: None
        script = self.factory("Description")
        error = self.assertRaises(
            AttributeError, script.register, "decapitate", handler)
        self.assertIn("'run'", "%s" % error)

    def test_call(self):
        handler_calls = []
        handler = types.ModuleType(b"handler")
        handler.add_arguments = lambda parser: None
        handler.run = handler_calls.append
        script = self.factory("Description")
        script.register("amputate", handler)
        error = self.assertRaises(SystemExit, script, ["amputate"])
        self.assertEqual(0, error.code)
        self.assertEqual(1, len(handler_calls))
        self.assertIsInstance(handler_calls[0], Namespace)

    def test_call_invalid_choice(self):
        script = self.factory("Description")
        self.assertRaises(SystemExit, script, ["disembowel"])
        self.assertIn(b"invalid choice", sys.stderr.getvalue())

    def test_call_with_exception(self):
        # Most exceptions from run() are propagated.
        handler = types.ModuleType(b"handler")
        handler.add_arguments = lambda parser: None
        handler.run = lambda args: 0 / 0
        script = self.factory("Description")
        script.register("eviscerate", handler)
        self.assertRaises(ZeroDivisionError, script, ["eviscerate"])

    def test_call_with_process_exception(self):
        # CalledProcessError is converted into SystemExit.
        exception = CalledProcessError(
            randint(0, 256), [factory.make_string()],
            factory.make_string().encode("ascii"))

        def raise_exception():
            raise exception

        handler = types.ModuleType(b"handler")
        handler.add_arguments = lambda parser: None
        handler.run = lambda args: raise_exception()
        script = self.factory("Description")
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
        script = self.factory("Description")
        script.register("smash", handler)
        error = self.assertRaises(SystemExit, script, ["smash"])
        self.assertEqual(1, error.code)


class TestAtomicWriteScript(MAASTestCase):

    def setUp(self):
        super(TestAtomicWriteScript, self).setUp()
        # Silence ArgumentParser.
        self.patch(sys, "stdout", StringIO.StringIO())
        self.patch(sys, "stderr", StringIO.StringIO())

    def get_parser(self):
        parser = ArgumentParser()
        AtomicWriteScript.add_arguments(parser)
        return parser

    def get_and_run_mocked_script(self, content, filename, *args):
        self.patch(sys, "stdin", StringIO.StringIO(content))
        parser = self.get_parser()
        parsed_args = parser.parse_args(*args)
        mocked_atomic_write = self.patch(
            provisioningserver.utils.script, 'atomic_write')
        AtomicWriteScript.run(parsed_args)
        return mocked_atomic_write

    def test_arg_setup(self):
        parser = self.get_parser()
        filename = factory.make_string()
        args = parser.parse_args((
            '--no-overwrite',
            '--filename', filename,
            '--mode', "111"))
        self.assertThat(
            args, MatchesStructure.byEquality(
                no_overwrite=True,
                filename=filename,
                mode="111"))

    def test_filename_arg_required(self):
        parser = self.get_parser()
        self.assertRaises(SystemExit, parser.parse_args, ('--no-overwrite',))

    def test_no_overwrite_defaults_to_false(self):
        parser = self.get_parser()
        filename = factory.make_string()
        args = parser.parse_args(('--filename', filename))
        self.assertFalse(args.no_overwrite)

    def test_script_executable(self):
        content = factory.make_string()
        script = [os.path.join(bindir, "maas-provision"), 'atomic-write']
        target_file = self.make_file()
        script.extend(('--filename', target_file, '--mode', '615'))
        cmd = Popen(
            script, stdin=PIPE,
            env=dict(PYTHONPATH=":".join(sys.path)))
        cmd.communicate(content)
        self.assertThat(target_file, FileContains(content))
        self.assertEqual(0615, stat.S_IMODE(os.stat(target_file).st_mode))

    def test_passes_overwrite_flag(self):
        content = factory.make_string()
        filename = factory.make_string()
        mocked_atomic_write = self.get_and_run_mocked_script(
            content, filename,
            ('--filename', filename, '--no-overwrite'))

        self.assertThat(
            mocked_atomic_write,
            MockCalledOnceWith(content, filename, mode=0600, overwrite=False))

    def test_passes_mode_flag(self):
        content = factory.make_string()
        filename = factory.make_string()
        # Mode that's unlikely to occur in the wild.
        mode = 0377
        mocked_atomic_write = self.get_and_run_mocked_script(
            content, filename,
            ('--filename', filename, '--mode', oct(mode)))

        self.assertThat(
            mocked_atomic_write,
            MockCalledOnceWith(content, filename, mode=mode, overwrite=True))

    def test_default_mode(self):
        content = factory.make_string()
        filename = factory.make_string()
        mocked_atomic_write = self.get_and_run_mocked_script(
            content, filename,
            ('--filename', filename))

        self.assertThat(
            mocked_atomic_write,
            MockCalledOnceWith(content, filename, mode=0600, overwrite=True))
