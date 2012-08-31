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
import time
import types

from maastesting.factory import factory
from maastesting.fakemethod import FakeMethod
from maastesting.testcase import TestCase
from mock import Mock
import provisioningserver
from provisioningserver.utils import (
    ActionScript,
    atomic_write,
    AtomicWriteScript,
    get_mtime,
    incremental_write,
    MainScript,
    parse_key_value_file,
    pick_new_mtime,
    Safe,
    ShellTemplate,
    )
from testtools.matchers import (
    FileContains,
    MatchesStructure,
    )
from testtools.testcase import ExpectedException


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

    def test_atomic_write_does_not_overwrite_file_if_overwrite_false(self):
        content = factory.getRandomString()
        random_content = factory.getRandomString()
        filename = self.make_file(contents=random_content)
        atomic_write(content, filename, overwrite=False)
        self.assertThat(filename, FileContains(random_content))

    def test_atomic_write_writes_file_if_no_file_present(self):
        filename = os.path.join(self.make_dir(), factory.getRandomString())
        content = factory.getRandomString()
        atomic_write(content, filename, overwrite=False)
        self.assertThat(filename, FileContains(content))

    def test_atomic_write_does_not_leak_temp_file_when_not_overwriting(self):
        # If the file is not written because it already exists and
        # overwriting was disabled, atomic_write does not leak its
        # temporary file.
        filename = self.make_file()
        atomic_write(factory.getRandomString(), filename, overwrite=False)
        self.assertEqual(
            [os.path.basename(filename)],
            os.listdir(os.path.dirname(filename)))

    def test_atomic_write_does_not_leak_temp_file_on_failure(self):
        # If the overwrite fails, atomic_write does not leak its
        # temporary file.
        self.patch(os, 'rename', Mock(side_effect=OSError()))
        filename = self.make_file()
        with ExpectedException(OSError):
            atomic_write(factory.getRandomString(), filename)
        self.assertEqual(
            [os.path.basename(filename)],
            os.listdir(os.path.dirname(filename)))

    def test_atomic_write_sets_permissions(self):
        atomic_file = self.make_file()
        # Pick an unusual mode that is also likely to fall outside our
        # umask.  We want this mode set, not treated as advice that may
        # be tightened up by umask later.
        mode = 0323
        atomic_write(factory.getRandomString(), atomic_file, mode=mode)
        self.assertEqual(mode, stat.S_IMODE(os.stat(atomic_file).st_mode))

    def test_atomic_write_sets_permissions_before_moving_into_place(self):

        recorded_modes = []

        def record_mode(source, dest):
            """Stub for os.rename: get source file's access mode."""
            recorded_modes.append(os.stat(source).st_mode)

        self.patch(os, 'rename', Mock(side_effect=record_mode))
        playground = self.make_dir()
        atomic_file = os.path.join(playground, factory.make_name('atomic'))
        mode = 0323
        atomic_write(factory.getRandomString(), atomic_file, mode=mode)
        [recorded_mode] = recorded_modes
        self.assertEqual(mode, stat.S_IMODE(recorded_mode))


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


class TestGetMTime(TestCase):
    """Test `get_mtime`."""

    def test_get_mtime_returns_None_for_nonexistent_file(self):
        nonexistent_file = os.path.join(
            self.make_dir(), factory.make_name('nonexistent-file'))
        self.assertIsNone(get_mtime(nonexistent_file))

    def test_get_mtime_returns_mtime(self):
        existing_file = self.make_file()
        mtime = os.stat(existing_file).st_mtime - randint(0, 100)
        os.utime(existing_file, (mtime, mtime))
        # Some small rounding/representation errors can happen here.
        # That's just the way of floating-point numbers.  According to
        # Gavin there's a conversion to fixed-point along the way, which
        # would raise representability issues.
        self.assertAlmostEqual(mtime, get_mtime(existing_file), delta=0.00001)

    def test_get_mtime_passes_on_other_error(self):
        forbidden_file = self.make_file()
        self.patch(os, 'stat', FakeMethod(failure=OSError("Forbidden file")))
        self.assertRaises(OSError, get_mtime, forbidden_file)


class TestPickNewMTime(TestCase):
    """Test `pick_new_mtime`."""

    def test_pick_new_mtime_applies_starting_age_to_new_file(self):
        before = time.time()
        starting_age = randint(0, 5)
        recommended_age = pick_new_mtime(None, starting_age=starting_age)
        now = time.time()
        self.assertAlmostEqual(
            now - starting_age,
            recommended_age,
            delta=(now - before))

    def test_pick_new_mtime_increments_mtime_if_possible(self):
        past = time.time() - 2
        self.assertEqual(past + 1, pick_new_mtime(past))

    def test_pick_new_mtime_refuses_to_move_mtime_into_the_future(self):
        # Race condition: this will fail if the test gets held up for
        # a second between readings of the clock.
        now = time.time()
        self.assertEqual(now, pick_new_mtime(now))


class ParseConfigTest(TestCase):
    """Testing for the method `parse_key_value_file`."""

    def test_parse_key_value_file_parses_config_file(self):
        contents = """
            key1: value1
            key2  :  value2
            """
        file_name = self.make_file(contents=contents)
        self.assertEqual(
            {'key1': 'value1', 'key2': 'value2'},
            parse_key_value_file(file_name))

    def test_parse_key_value_copes_with_empty_lines(self):
        contents = """
            key1: value1

            """
        file_name = self.make_file(contents=contents)
        self.assertEqual(
            {'key1': 'value1'}, parse_key_value_file(file_name))

    def test_parse_key_value_file_parse_alternate_separator(self):
        contents = """
            key1= value1
            key2   =  value2
            """
        file_name = self.make_file(contents=contents)
        self.assertEqual(
            {'key1': 'value1', 'key2': 'value2'},
            parse_key_value_file(file_name, separator='='))

    def test_parse_key_value_additional_eparator(self):
        contents = """
            key1: value1:value11
            """
        file_name = self.make_file(contents=contents)
        self.assertEqual(
            {'key1': 'value1:value11'}, parse_key_value_file(file_name))


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

    factory = ActionScript

    def setUp(self):
        super(TestActionScript, self).setUp()
        # ActionScript.setup() is not safe to run in the test suite.
        self.patch(ActionScript, "setup", lambda self: None)
        # ArgumentParser sometimes likes to print to stdout/err. Use
        # StringIO.StringIO to be relaxed about str/unicode (argparse uses
        # str). When moving to Python 3 this will need to be tightened up.
        self.patch(sys, "stdout", StringIO.StringIO())
        self.patch(sys, "stderr", StringIO.StringIO())

    def test_init(self):
        description = factory.getRandomString()
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
            randint(0, 256), [factory.getRandomString()],
            factory.getRandomString().encode("ascii"))

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


class TestMainScript(TestActionScript):

    factory = MainScript

    def test_default_arguments(self):
        # MainScript accepts a --config-file parameter. The value of this is
        # passed through into the args namespace object as config_file.
        handler_calls = []
        handler = types.ModuleType(b"handler")
        handler.add_arguments = lambda parser: None
        handler.run = handler_calls.append
        script = self.factory("Description")
        script.register("dislocate", handler)
        dummy_config_file = factory.make_name("config-file")
        # --config-file is specified before the action.
        args = ["--config-file", dummy_config_file, "dislocate"]
        error = self.assertRaises(SystemExit, script, args)
        self.assertEqual(0, error.code)
        namespace = handler_calls[0]
        self.assertEqual(
            {"config_file": dummy_config_file, "handler": handler},
            vars(namespace))


class TestAtomicWriteScript(TestCase):

    def setUp(self):
        super(TestAtomicWriteScript, self).setUp()
        # Silence ArgumentParser.
        self.patch(sys, "stdout", StringIO.StringIO())
        self.patch(sys, "stderr", StringIO.StringIO())

    def get_parser(self):
        parser = ArgumentParser()
        AtomicWriteScript.add_arguments(parser)
        return parser

    def test_arg_setup(self):
        parser = self.get_parser()
        filename = factory.getRandomString()
        args = parser.parse_args((
            '--no-overwrite',
            '--filename', filename))
        self.assertThat(
            args, MatchesStructure.byEquality(
                no_overwrite=True,
                filename=filename))

    def test_filename_arg_required(self):
        parser = self.get_parser()
        self.assertRaises(SystemExit, parser.parse_args, ('--no-overwrite',))

    def test_no_overwrite_defaults_to_false(self):
        parser = self.get_parser()
        filename = factory.getRandomString()
        args = parser.parse_args(('--filename', filename))
        self.assertFalse(args.no_overwrite)

    def test_script_executable(self):
        dev_root = os.path.join(
            os.path.dirname(provisioningserver.__file__),
            os.pardir, os.pardir)
        content = factory.getRandomString()
        test_data_file = self.make_file(contents=content)
        script = ["%s/bin/maas-provision" % dev_root, 'atomic_write']
        target_file = self.make_file()
        script.extend(('--filename', target_file))
        with open(test_data_file, "rb") as stdin:
            cmd = Popen(
                script, stdin=stdin, stdout=PIPE,
                env=dict(PYTHONPATH=":".join(sys.path)))
            cmd.communicate()
        self.assertThat(target_file, FileContains(content))

    def test_passes_overwrite_flag(self):
        content = factory.getRandomString()
        self.patch(sys, "stdin", StringIO.StringIO(content))
        parser = self.get_parser()
        filename = factory.getRandomString()
        args = parser.parse_args(('--filename', filename, '--no-overwrite'))
        mock = Mock()
        self.patch(provisioningserver.utils, 'atomic_write', mock)
        AtomicWriteScript.run(args)

        mock.assert_called_once_with(content, filename, overwrite=False)
