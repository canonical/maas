# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the subcommand utilities."""

__all__ = []

from argparse import (
    ArgumentParser,
    Namespace,
)
import io
import os
from random import randint
import stat
from subprocess import (
    CalledProcessError,
    PIPE,
    Popen,
)
import sys
import types

from maastesting import bindir
from maastesting.factory import factory
from maastesting.fixtures import CaptureStandardIO
from maastesting.matchers import (
    FileContains,
    MockCalledOnceWith,
)
from maastesting.testcase import MAASTestCase
import provisioningserver.utils
from provisioningserver.utils.script import (
    ActionScript,
    AtomicDeleteScript,
    AtomicWriteScript,
)
from provisioningserver.utils.shell import select_c_utf8_locale
from testtools.matchers import MatchesStructure


class TestActionScript(MAASTestCase):
    """Test `ActionScript`."""

    factory = ActionScript

    def setUp(self):
        super(TestActionScript, self).setUp()
        # ActionScript.setup() is not safe to run in the test suite.
        self.patch(ActionScript, "setup", lambda self: None)
        # ArgumentParser sometimes likes to print to stdout/err.
        self.stdio = self.useFixture(CaptureStandardIO())

    def test_init(self):
        description = factory.make_string()
        script = self.factory(description)
        self.assertIsInstance(script.parser, ArgumentParser)
        self.assertEqual(description, script.parser.description)

    def test_register(self):
        handler = types.ModuleType("handler")
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
        handler = types.ModuleType("handler")
        handler.run = lambda args: None
        script = self.factory("Description")
        error = self.assertRaises(
            AttributeError, script.register, "decapitate", handler)
        self.assertIn("'add_arguments'", "%s" % error)

    def test_register_without_run(self):
        # ActionScript.register will crash if the handler has no run()
        # callable.
        handler = types.ModuleType("handler")
        handler.add_arguments = lambda parser: None
        script = self.factory("Description")
        error = self.assertRaises(
            AttributeError, script.register, "decapitate", handler)
        self.assertIn("'run'", "%s" % error)

    def test_call(self):
        handler_calls = []
        handler = types.ModuleType("handler")
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
        self.assertIn("invalid choice", self.stdio.getError())

    def test_call_with_exception(self):
        # Most exceptions from run() are propagated.
        handler = types.ModuleType("handler")
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

        handler = types.ModuleType("handler")
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

        handler = types.ModuleType("handler")
        handler.add_arguments = lambda parser: None
        handler.run = lambda args: raise_exception()
        script = self.factory("Description")
        script.register("smash", handler)
        error = self.assertRaises(SystemExit, script, ["smash"])
        self.assertEqual(1, error.code)


class TestAtomicWriteScript(MAASTestCase):

    def setUp(self):
        super(TestAtomicWriteScript, self).setUp()
        # ArgumentParser sometimes likes to print to stdout/err.
        self.stdio = self.useFixture(CaptureStandardIO())

    def get_parser(self):
        parser = ArgumentParser()
        AtomicWriteScript.add_arguments(parser)
        return parser

    def get_and_run_mocked_script(self, content, filename, *args):
        self.stdio.addInput(content)
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
        cmd = Popen(script, stdin=PIPE, env=select_c_utf8_locale())
        cmd.communicate(content.encode("ascii"))
        self.assertThat(target_file, FileContains(content, encoding="ascii"))
        self.assertEqual(0o615, stat.S_IMODE(os.stat(target_file).st_mode))

    def test_passes_overwrite_flag(self):
        content = factory.make_string()
        filename = factory.make_string()
        mocked_atomic_write = self.get_and_run_mocked_script(
            content, filename,
            ('--filename', filename, '--no-overwrite'))

        self.assertThat(
            mocked_atomic_write,
            MockCalledOnceWith(
                content.encode("ascii"), filename,
                mode=0o600, overwrite=False))

    def test_passes_mode_flag(self):
        content = factory.make_string()
        filename = factory.make_string()
        # Mode that's unlikely to occur in the wild.
        mode = 0o377
        mocked_atomic_write = self.get_and_run_mocked_script(
            content, filename,
            ('--filename', filename, '--mode', oct(mode)))

        self.assertThat(
            mocked_atomic_write,
            MockCalledOnceWith(
                content.encode("ascii"), filename, mode=mode, overwrite=True))

    def test_default_mode(self):
        content = factory.make_string()
        filename = factory.make_string()
        mocked_atomic_write = self.get_and_run_mocked_script(
            content, filename,
            ('--filename', filename))

        self.assertThat(
            mocked_atomic_write,
            MockCalledOnceWith(
                content.encode("ascii"), filename, mode=0o600, overwrite=True))


class TestAtomicDeleteScript(MAASTestCase):

    def setUp(self):
        super(TestAtomicDeleteScript, self).setUp()
        # Silence ArgumentParser.
        self.patch(sys, "stdout", io.StringIO())
        self.patch(sys, "stderr", io.StringIO())

    def get_parser(self):
        parser = ArgumentParser()
        AtomicDeleteScript.add_arguments(parser)
        return parser

    def get_and_run_mocked_script(self, *args):
        parser = self.get_parser()
        parsed_args = parser.parse_args(*args)
        mocked_atomic_delete = self.patch(
            provisioningserver.utils.script, 'atomic_delete')
        AtomicDeleteScript.run(parsed_args)
        return mocked_atomic_delete

    def test_arg_setup(self):
        parser = self.get_parser()
        filename = factory.make_string()
        args = parser.parse_args((
            '--filename', filename))
        self.assertThat(
            args, MatchesStructure.byEquality(
                filename=filename))

    def test_filename_arg_required(self):
        parser = self.get_parser()
        self.assertRaises(SystemExit, parser.parse_args, tuple())

    def test_calls_atomic_delete_with_filename(self):
        filename = factory.make_string()
        mocked_atomic_delete = self.get_and_run_mocked_script(
            ('--filename', filename))

        self.assertThat(
            mocked_atomic_delete,
            MockCalledOnceWith(filename))
