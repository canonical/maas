# Copyright 2012-2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test `provisioningserver.utils`."""

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
import doctest
import httplib
import json
import os
from random import randint
import re
from shutil import rmtree
import stat
import StringIO
import subprocess
from subprocess import (
    CalledProcessError,
    PIPE,
    Popen,
    )
import sys
import tempfile
from textwrap import dedent
import time
import types

from apiclient.maas_client import MAASClient
from apiclient.testing.credentials import make_api_credentials
from crochet import EventualResult
from fixtures import (
    EnvironmentVariableFixture,
    FakeLogger,
    )
from lxml import etree
from maastesting import (
    bindir,
    root,
    )
from maastesting.factory import factory
from maastesting.fakemethod import FakeMethod
from maastesting.matchers import (
    MockCalledOnceWith,
    MockNotCalled,
    )
from maastesting.testcase import MAASTestCase
from mock import (
    Mock,
    sentinel,
    )
import provisioningserver
from provisioningserver.testing.testcase import PservTestCase
import provisioningserver.utils
from provisioningserver.utils import (
    ActionScript,
    asynchronous,
    atomic_symlink,
    atomic_write,
    AtomicWriteScript,
    call_and_check,
    classify,
    compose_URL_on_IP,
    create_node,
    ensure_dir,
    escape_py_literal,
    ExternalProcessError,
    filter_dict,
    get_mtime,
    incremental_write,
    locate_config,
    maas_custom_config_markers,
    MainScript,
    map_enum,
    parse_key_value_file,
    pause,
    pick_new_mtime,
    read_text_file,
    retries,
    Safe,
    ShellTemplate,
    sudo_write_file,
    synchronous,
    tempdir,
    try_match_xpath,
    write_custom_config_section,
    write_text_file,
    )
from testscenarios import multiply_scenarios
from testtools.deferredruntest import AsynchronousDeferredRunTest
from testtools.matchers import (
    AfterPreprocessing,
    DirExists,
    DocTestMatches,
    EndsWith,
    Equals,
    FileContains,
    FileExists,
    HasLength,
    Is,
    IsInstance,
    MatchesAll,
    MatchesException,
    MatchesListwise,
    MatchesStructure,
    Not,
    Raises,
    SamePath,
    StartsWith,
    )
from testtools.testcase import ExpectedException
from twisted.internet import reactor
from twisted.internet.defer import (
    CancelledError,
    Deferred,
    inlineCallbacks,
    )
from twisted.internet.task import Clock
from twisted.internet.threads import deferToThread
from twisted.python.failure import Failure


def get_branch_dir(*path):
    """Locate a file or directory relative to this branch."""
    return os.path.abspath(os.path.join(root, *path))


class TestLocateConfig(MAASTestCase):
    """Tests for `locate_config`."""

    def test_returns_branch_etc_maas(self):
        self.assertEqual(get_branch_dir('etc/maas'), locate_config())
        self.assertThat(locate_config(), DirExists())

    def test_defaults_to_global_etc_maas_if_variable_is_unset(self):
        self.useFixture(EnvironmentVariableFixture('MAAS_CONFIG_DIR', None))
        self.assertEqual('/etc/maas', locate_config())

    def test_defaults_to_global_etc_maas_if_variable_is_empty(self):
        self.useFixture(EnvironmentVariableFixture('MAAS_CONFIG_DIR', ''))
        self.assertEqual('/etc/maas', locate_config())

    def test_returns_absolute_path(self):
        self.useFixture(EnvironmentVariableFixture('MAAS_CONFIG_DIR', '.'))
        self.assertTrue(os.path.isabs(locate_config()))

    def test_locates_config_file(self):
        filename = factory.make_string()
        self.assertEqual(
            get_branch_dir('etc/maas/', filename),
            locate_config(filename))

    def test_locates_full_path(self):
        path = [factory.make_string() for counter in range(3)]
        self.assertEqual(
            get_branch_dir('etc/maas/', *path),
            locate_config(*path))

    def test_normalizes_path(self):
        self.assertEquals(
            get_branch_dir('etc/maas/bar/szot'),
            locate_config('foo/.././bar///szot'))


class TestFilterDict(MAASTestCase):
    """Tests for `filter_dict`."""

    def test_keeps_desired_keys(self):
        key = factory.make_name('key')
        value = factory.make_name('value')
        self.assertEqual({key: value}, filter_dict({key: value}, {key}))

    def test_ignores_undesired_keys(self):
        items = {factory.make_name('key'): factory.make_name('value')}
        self.assertEqual({}, filter_dict(items, {factory.make_name('other')}))

    def test_leaves_original_intact(self):
        desired_key = factory.make_name('key')
        original = {
            desired_key: factory.make_name('value'),
            factory.make_name('otherkey'): factory.make_name('othervalue'),
        }
        copy = original.copy()

        result = filter_dict(copy, {desired_key})

        self.assertEqual({desired_key: original[desired_key]}, result)
        self.assertEqual(original, copy)

    def test_ignores_values_from_second_dict(self):
        key = factory.make_name('key')
        items = {key: factory.make_name('value')}
        keys = {key: factory.make_name('othervalue')}

        self.assertEqual(items, filter_dict(items, keys))


class TestSafe(MAASTestCase):
    """Test `Safe`."""

    def test_value(self):
        something = object()
        safe = Safe(something)
        self.assertIs(something, safe.value)

    def test_repr(self):
        string = factory.make_string()
        safe = Safe(string)
        self.assertEqual("<Safe %r>" % string, repr(safe))


class TestWriteAtomic(MAASTestCase):
    """Test `atomic_write`."""

    def test_atomic_write_overwrites_dest_file(self):
        content = factory.make_string()
        filename = self.make_file(contents=factory.make_string())
        atomic_write(content, filename)
        self.assertThat(filename, FileContains(content))

    def test_atomic_write_does_not_overwrite_file_if_overwrite_false(self):
        content = factory.make_string()
        random_content = factory.make_string()
        filename = self.make_file(contents=random_content)
        atomic_write(content, filename, overwrite=False)
        self.assertThat(filename, FileContains(random_content))

    def test_atomic_write_writes_file_if_no_file_present(self):
        filename = os.path.join(self.make_dir(), factory.make_string())
        content = factory.make_string()
        atomic_write(content, filename, overwrite=False)
        self.assertThat(filename, FileContains(content))

    def test_atomic_write_does_not_leak_temp_file_when_not_overwriting(self):
        # If the file is not written because it already exists and
        # overwriting was disabled, atomic_write does not leak its
        # temporary file.
        filename = self.make_file()
        atomic_write(factory.make_string(), filename, overwrite=False)
        self.assertEqual(
            [os.path.basename(filename)],
            os.listdir(os.path.dirname(filename)))

    def test_atomic_write_does_not_leak_temp_file_on_failure(self):
        # If the overwrite fails, atomic_write does not leak its
        # temporary file.
        self.patch(os, 'rename', Mock(side_effect=OSError()))
        filename = self.make_file()
        with ExpectedException(OSError):
            atomic_write(factory.make_string(), filename)
        self.assertEqual(
            [os.path.basename(filename)],
            os.listdir(os.path.dirname(filename)))

    def test_atomic_write_sets_permissions(self):
        atomic_file = self.make_file()
        # Pick an unusual mode that is also likely to fall outside our
        # umask.  We want this mode set, not treated as advice that may
        # be tightened up by umask later.
        mode = 0323
        atomic_write(factory.make_string(), atomic_file, mode=mode)
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
        atomic_write(factory.make_string(), atomic_file, mode=mode)
        [recorded_mode] = recorded_modes
        self.assertEqual(mode, stat.S_IMODE(recorded_mode))

    def test_atomic_write_sets_OSError_filename_if_undefined(self):
        # When the filename attribute of an OSError is undefined when
        # attempting to create a temporary file, atomic_write fills it in with
        # a representative filename, similar to the specification required by
        # mktemp(1).
        mock_mkstemp = self.patch(tempfile, "mkstemp")
        mock_mkstemp.side_effect = OSError()
        filename = os.path.join("directory", "basename")
        error = self.assertRaises(OSError, atomic_write, "content", filename)
        self.assertEqual(
            os.path.join("directory", ".basename.XXXXXX.tmp"),
            error.filename)

    def test_atomic_write_does_not_set_OSError_filename_if_defined(self):
        # When the filename attribute of an OSError is defined when attempting
        # to create a temporary file, atomic_write leaves it alone.
        mock_mkstemp = self.patch(tempfile, "mkstemp")
        mock_mkstemp.side_effect = OSError()
        mock_mkstemp.side_effect.filename = factory.make_name("filename")
        filename = os.path.join("directory", "basename")
        error = self.assertRaises(OSError, atomic_write, "content", filename)
        self.assertEqual(
            mock_mkstemp.side_effect.filename,
            error.filename)


class TestAtomicSymlink(MAASTestCase):
    """Test `atomic_symlink`."""

    def test_atomic_symlink_creates_symlink(self):
        filename = self.make_file(contents=factory.make_string())
        target_dir = self.make_dir()
        link_name = factory.make_name('link')
        target = os.path.join(target_dir, link_name)
        atomic_symlink(filename, target)
        self.assertTrue(
            os.path.islink(target), "atomic_symlink didn't create a symlink")
        self.assertThat(target, SamePath(filename))

    def test_atomic_symlink_overwrites_dest_file(self):
        filename = self.make_file(contents=factory.make_string())
        target_dir = self.make_dir()
        link_name = factory.make_name('link')
        # Create a file that will be overwritten.
        factory.make_file(location=target_dir, name=link_name)
        target = os.path.join(target_dir, link_name)
        atomic_symlink(filename, target)
        self.assertTrue(
            os.path.islink(target), "atomic_symlink didn't create a symlink")
        self.assertThat(target, SamePath(filename))

    def test_atomic_symlink_does_not_leak_temp_file_if_failure(self):
        # In the face of failure, no temp file is leaked.
        self.patch(os, 'rename', Mock(side_effect=OSError()))
        filename = self.make_file()
        target_dir = self.make_dir()
        link_name = factory.make_name('link')
        target = os.path.join(target_dir, link_name)
        with ExpectedException(OSError):
            atomic_symlink(filename, target)
        self.assertEqual(
            [],
            os.listdir(target_dir))


class TestIncrementalWrite(MAASTestCase):
    """Test `incremental_write`."""

    def test_incremental_write_increments_modification_time(self):
        content = factory.make_string()
        filename = self.make_file(contents=factory.make_string())
        # Pretend that this file is older than it is.  So that
        # incrementing its mtime won't put it in the future.
        old_mtime = os.stat(filename).st_mtime - 10
        os.utime(filename, (old_mtime, old_mtime))
        incremental_write(content, filename)
        self.assertAlmostEqual(
            os.stat(filename).st_mtime, old_mtime + 1, delta=0.01)

    def test_incremental_write_sets_permissions(self):
        atomic_file = self.make_file()
        mode = 0323
        incremental_write(factory.make_string(), atomic_file, mode=mode)
        self.assertEqual(mode, stat.S_IMODE(os.stat(atomic_file).st_mode))


class TestGetMTime(MAASTestCase):
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


class TestPickNewMTime(MAASTestCase):
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


class WriteCustomConfigSectionTest(MAASTestCase):
    """Test `write_custom_config_section`."""

    def test_appends_custom_section_initially(self):
        original = factory.make_name('Original-text')
        custom_text = factory.make_name('Custom-text')
        header, footer = maas_custom_config_markers
        self.assertEqual(
            [original, header, custom_text, footer],
            write_custom_config_section(original, custom_text).splitlines())

    def test_custom_section_ends_with_newline(self):
        self.assertThat(write_custom_config_section("x", "y"), EndsWith('\n'))

    def test_replaces_custom_section_only(self):
        header, footer = maas_custom_config_markers
        original = [
            "Text before custom section.",
            header,
            "Old custom section.",
            footer,
            "Text after custom section.",
            ]
        expected = [
            "Text before custom section.",
            header,
            "New custom section.",
            footer,
            "Text after custom section.",
            ]
        self.assertEqual(
            expected,
            write_custom_config_section(
                '\n'.join(original), "New custom section.").splitlines())

    def test_ignores_header_without_footer(self):
        # If the footer of the custom config section is not found,
        # write_custom_config_section will pretend that the header is not
        # there and append a new custom section.  This does mean that there
        # will be two headers and one footer; a subsequent rewrite will
        # replace everything from the first header to the footer.
        header, footer = maas_custom_config_markers
        original = [
            header,
            "Old custom section (probably).",
            ]
        expected = [
            header,
            "Old custom section (probably).",
            header,
            "New custom section.",
            footer,
            ]
        self.assertEqual(
            expected,
            write_custom_config_section(
                '\n'.join(original), "New custom section.").splitlines())

    def test_ignores_second_header(self):
        # If there are two custom-config headers but only one footer,
        # write_custom_config_section will treat everything between the
        # first header and the footer as custom config section, which it
        # will overwrite.
        header, footer = maas_custom_config_markers
        original = [
            header,
            "Old custom section (probably).",
            header,
            "More custom section.",
            footer,
            ]
        expected = [
            header,
            "New custom section.",
            footer,
            ]
        self.assertEqual(
            expected,
            write_custom_config_section(
                '\n'.join(original), "New custom section.").splitlines())

    def test_ignores_footer_before_header(self):
        # Custom-section footers before the custom-section header are
        # ignored.  You might see this if there was an older custom
        # config section whose header has been changed or deleted.
        header, footer = maas_custom_config_markers
        original = [
            footer,
            "Possible old custom section.",
            ]
        expected = [
            footer,
            "Possible old custom section.",
            header,
            "New custom section.",
            footer,
            ]
        self.assertEqual(
            expected,
            write_custom_config_section(
                '\n'.join(original), "New custom section.").splitlines())

    def test_preserves_indentation_in_original(self):
        indented_text = "   text."
        self.assertIn(
            indented_text,
            write_custom_config_section(indented_text, "Custom section."))

    def test_preserves_indentation_in_custom_section(self):
        indented_text = "   custom section."
        self.assertIn(
            indented_text,
            write_custom_config_section("Original.", indented_text))

    def test_produces_sensible_text(self):
        # The other tests mostly operate on lists of lines, because it
        # eliminates problems with line endings.  This test here
        # verifies that the actual text you get is sensible, preserves
        # newlines, and generally looks normal.
        header, footer = maas_custom_config_markers
        original = dedent("""\
            Top.


            More.
            %s
            Old custom section.
            %s
            End.

            """) % (header, footer)
        new_custom_section = dedent("""\
            New custom section.

            With blank lines.""")
        expected = dedent("""\
            Top.


            More.
            %s
            New custom section.

            With blank lines.
            %s
            End.

            """) % (header, footer)
        self.assertEqual(
            expected,
            write_custom_config_section(original, new_custom_section))


class SudoWriteFileTest(MAASTestCase):
    """Testing for `sudo_write_file`."""

    def patch_popen(self, return_value=0):
        process = Mock()
        process.returncode = return_value
        process.communicate = Mock(return_value=('output', 'error output'))
        self.patch(
            provisioningserver.utils, 'Popen', Mock(return_value=process))
        return process

    def test_calls_atomic_write(self):
        self.patch_popen()
        path = os.path.join(self.make_dir(), factory.make_name('file'))
        contents = factory.make_string()

        sudo_write_file(path, contents)

        self.assertThat(provisioningserver.utils.Popen, MockCalledOnceWith([
            'sudo', '-n', 'maas-provision', 'atomic-write',
            '--filename', path, '--mode', '0644',
            ],
            stdin=PIPE))

    def test_encodes_contents(self):
        process = self.patch_popen()
        contents = factory.make_string()
        encoding = 'utf-16'
        sudo_write_file(self.make_file(), contents, encoding=encoding)
        self.assertThat(
            process.communicate,
            MockCalledOnceWith(contents.encode(encoding)))

    def test_catches_failures(self):
        self.patch_popen(1)
        self.assertRaises(
            CalledProcessError,
            sudo_write_file, self.make_file(), factory.make_string())


class ParseConfigTest(MAASTestCase):
    """Testing for `parse_key_value_file`."""

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


class TestShellTemplate(MAASTestCase):
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
            provisioningserver.utils, 'atomic_write')
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


class TestEnsureDir(MAASTestCase):
    def test_succeeds_if_directory_already_existed(self):
        path = self.make_dir()
        ensure_dir(path)
        self.assertThat(path, DirExists())

    def test_fails_if_path_is_already_a_file(self):
        path = self.make_file()
        self.assertRaises(OSError, ensure_dir, path)
        self.assertThat(path, FileExists())

    def test_creates_dir_if_not_present(self):
        path = os.path.join(self.make_dir(), factory.make_name())
        ensure_dir(path)
        self.assertThat(path, DirExists())

    def test_passes_on_other_errors(self):
        not_a_dir = self.make_file()
        self.assertRaises(
            OSError,
            ensure_dir,
            os.path.join(not_a_dir, factory.make_name('impossible')))

    def test_creates_multiple_layers_of_directories_if_needed(self):
        path = os.path.join(
            self.make_dir(), factory.make_name('subdir'),
            factory.make_name('sbusubdir'))
        ensure_dir(path)
        self.assertThat(path, DirExists())


class TestTempDir(MAASTestCase):
    def test_creates_real_fresh_directory(self):
        stored_text = factory.make_string()
        filename = factory.make_name('test-file')
        with tempdir() as directory:
            self.assertThat(directory, DirExists())
            write_text_file(os.path.join(directory, filename), stored_text)
            retrieved_text = read_text_file(os.path.join(directory, filename))
            files = os.listdir(directory)

        self.assertEqual(stored_text, retrieved_text)
        self.assertEqual([filename], files)

    def test_creates_unique_directory(self):
        with tempdir() as dir1, tempdir() as dir2:
            pass
        self.assertNotEqual(dir1, dir2)

    def test_cleans_up_on_successful_exit(self):
        with tempdir() as directory:
            file_path = factory.make_file(directory)

        self.assertThat(directory, Not(DirExists()))
        self.assertThat(file_path, Not(FileExists()))

    def test_cleans_up_on_exception_exit(self):
        class DeliberateFailure(Exception):
            pass

        with ExpectedException(DeliberateFailure):
            with tempdir() as directory:
                file_path = factory.make_file(directory)
                raise DeliberateFailure("Exiting context by exception")

        self.assertThat(directory, Not(DirExists()))
        self.assertThat(file_path, Not(FileExists()))

    def test_tolerates_disappearing_dir(self):
        with tempdir() as directory:
            rmtree(directory)

        self.assertThat(directory, Not(DirExists()))

    def test_uses_location(self):
        temp_location = self.make_dir()
        with tempdir(location=temp_location) as directory:
            self.assertThat(directory, DirExists())
            location_listing = os.listdir(temp_location)

        self.assertNotEqual(temp_location, directory)
        self.assertThat(directory, StartsWith(temp_location + os.path.sep))
        self.assertIn(os.path.basename(directory), location_listing)
        self.assertThat(temp_location, DirExists())
        self.assertThat(directory, Not(DirExists()))

    def test_yields_unicode(self):
        with tempdir() as directory:
            pass

        self.assertIsInstance(directory, unicode)

    def test_accepts_unicode_from_mkdtemp(self):
        fake_dir = os.path.join(self.make_dir(), factory.make_name('tempdir'))
        self.assertIsInstance(fake_dir, unicode)
        self.patch(tempfile, 'mkdtemp').return_value = fake_dir

        with tempdir() as directory:
            pass

        self.assertEqual(fake_dir, directory)
        self.assertIsInstance(directory, unicode)

    def test_decodes_bytes_from_mkdtemp(self):
        encoding = 'utf-16'
        self.patch(sys, 'getfilesystemencoding').return_value = encoding
        fake_dir = os.path.join(self.make_dir(), factory.make_name('tempdir'))
        self.patch(tempfile, 'mkdtemp').return_value = fake_dir.encode(
            encoding)
        self.patch(provisioningserver.utils, 'rmtree')

        with tempdir() as directory:
            pass

        self.assertEqual(fake_dir, directory)
        self.assertIsInstance(directory, unicode)

    def test_uses_prefix(self):
        prefix = factory.make_string(3)
        with tempdir(prefix=prefix) as directory:
            pass

        self.assertThat(os.path.basename(directory), StartsWith(prefix))

    def test_uses_suffix(self):
        suffix = factory.make_string(3)
        with tempdir(suffix=suffix) as directory:
            pass

        self.assertThat(os.path.basename(directory), EndsWith(suffix))

    def test_restricts_access(self):
        with tempdir() as directory:
            mode = os.stat(directory).st_mode
        self.assertEqual(
            stat.S_IMODE(mode),
            stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)


class TestReadTextFile(MAASTestCase):
    def test_reads_file(self):
        text = factory.make_string()
        self.assertEqual(text, read_text_file(self.make_file(contents=text)))

    def test_defaults_to_utf8(self):
        # Test input: "registered trademark" (ringed R) symbol.
        text = '\xae'
        self.assertEqual(
            text,
            read_text_file(self.make_file(contents=text.encode('utf-8'))))

    def test_uses_given_encoding(self):
        # Test input: "registered trademark" (ringed R) symbol.
        text = '\xae'
        self.assertEqual(
            text,
            read_text_file(
                self.make_file(contents=text.encode('utf-16')),
                encoding='utf-16'))


class TestWriteTextFile(MAASTestCase):
    def test_creates_file(self):
        path = os.path.join(self.make_dir(), factory.make_name('text'))
        text = factory.make_string()
        write_text_file(path, text)
        self.assertThat(path, FileContains(text))

    def test_overwrites_file(self):
        path = self.make_file(contents="original text")
        text = factory.make_string()
        write_text_file(path, text)
        self.assertThat(path, FileContains(text))

    def test_defaults_to_utf8(self):
        path = self.make_file()
        # Test input: "registered trademark" (ringed R) symbol.
        text = '\xae'
        write_text_file(path, text)
        self.assertThat(path, FileContains(text.encode('utf-8')))

    def test_uses_given_encoding(self):
        path = self.make_file()
        # Test input: "registered trademark" (ringed R) symbol.
        text = '\xae'
        write_text_file(path, text, encoding='utf-16')
        self.assertThat(path, FileContains(text.encode('utf-16')))


class TestTryMatchXPathScenarios(MAASTestCase):

    doctest_flags = doctest.ELLIPSIS | doctest.NORMALIZE_WHITESPACE

    def scenario(name, xpath, doc, expected_result, expected_log=""):
        """Return a scenario (for `testscenarios`) to test `try_match_xpath`.

        This is a convenience function to reduce the amount of
        boilerplate when constructing `scenarios_inputs` later on.

        The scenario it constructs defines an XML document, and XPath
        expression, the expectation as to whether it will match or
        not, and the expected log output.
        """
        doc = etree.fromstring(doc).getroottree()
        return name, dict(
            xpath=xpath, doc=doc, expected_result=expected_result,
            expected_log=dedent(expected_log))

    # Exercise try_match_xpath with a variety of different inputs.
    scenarios_inputs = (
        scenario(
            "expression matches",
            "/foo", "<foo/>", True),
        scenario(
            "expression does not match",
            "/foo", "<bar/>", False),
        scenario(
            "text expression matches",
            "/foo/text()", '<foo>bar</foo>', True),
        scenario(
            "text expression does not match",
            "/foo/text()", '<foo></foo>', False),
        scenario(
            "string expression matches",
            "string()", '<foo>bar</foo>', True),
        scenario(
            "string expression does not match",
            "string()", '<foo></foo>', False),
        scenario(
            "unrecognised namespace",
            "/foo:bar", '<foo/>', False,
            expected_log="""\
            Invalid expression: /foo:bar
            Traceback (most recent call last):
            ...
            XPathEvalError: Undefined namespace prefix
            """),
    )

    # Exercise try_match_xpath with and without compiled XPath
    # expressions.
    scenarios_xpath_compiler = (
        ("xpath-compiler=XPath", dict(xpath_compile=etree.XPath)),
        ("xpath-compiler=None", dict(xpath_compile=lambda expr: expr)),
    )

    # Exercise try_match_xpath with and without documents wrapped in
    # an XPathDocumentEvaluator.
    scenarios_doc_compiler = (
        ("doc-compiler=XPathDocumentEvaluator", dict(
            doc_compile=etree.XPathDocumentEvaluator)),
        ("doc-compiler=None", dict(doc_compile=lambda doc: doc)),
    )

    scenarios = multiply_scenarios(
        scenarios_inputs, scenarios_xpath_compiler,
        scenarios_doc_compiler)

    def setUp(self):
        super(TestTryMatchXPathScenarios, self).setUp()
        self.logger = self.useFixture(FakeLogger())

    def test(self):
        xpath = self.xpath_compile(self.xpath)
        doc = self.doc_compile(self.doc)
        self.assertIs(self.expected_result, try_match_xpath(xpath, doc))
        self.assertThat(
            self.logger.output, DocTestMatches(
                self.expected_log, self.doctest_flags))


class TestTryMatchXPath(MAASTestCase):

    def test_logs_to_specified_logger(self):
        xpath = etree.XPath("/foo:bar")
        doc = etree.XML("<foo/>")
        root_logger = self.useFixture(FakeLogger())
        callers_logger = Mock()
        try_match_xpath(xpath, doc, callers_logger)
        self.assertEqual("", root_logger.output)
        self.assertThat(
            callers_logger.exception,
            MockCalledOnceWith("Invalid expression: %s", xpath.path))


class TestClassify(MAASTestCase):

    def test_no_subjects(self):
        self.assertSequenceEqual(
            ([], []), classify(sentinel.func, []))

    def test_subjects(self):
        subjects = [("one", 1), ("two", 2), ("three", 3)]
        is_even = lambda subject: subject % 2 == 0
        self.assertSequenceEqual(
            (['two'], ['one', 'three']),
            classify(is_even, subjects))


class TestCallAndCheck(MAASTestCase):
    """Tests `call_and_check`."""

    def patch_popen(self, returncode=0, stderr=''):
        """Replace `subprocess.Popen` with a mock."""
        popen = self.patch(subprocess, 'Popen')
        process = popen.return_value
        process.communicate.return_value = (None, stderr)
        process.returncode = returncode
        return process

    def test__returns_standard_output(self):
        output = factory.make_string()
        self.assertEqual(output, call_and_check(['/bin/echo', '-n', output]))

    def test__raises_ExternalProcessError_on_failure(self):
        command = factory.make_name('command')
        message = factory.make_string()
        self.patch_popen(returncode=1, stderr=message)
        error = self.assertRaises(
            ExternalProcessError, call_and_check, command)
        self.assertEqual(1, error.returncode)
        self.assertEqual(command, error.cmd)
        self.assertEqual(message, error.output)

    def test__reports_stderr_on_failure(self):
        nonfile = os.path.join(self.make_dir(), factory.make_name('nonesuch'))
        error = self.assertRaises(
            ExternalProcessError,
            call_and_check, ['/bin/cat', nonfile], env={'LC_ALL': 'C'})
        self.assertEqual(
            "/bin/cat: %s: No such file or directory" % nonfile,
            error.output)


class TestExternalProcessError(MAASTestCase):
    """Tests for the ExternalProcessError class."""

    def test_to_unicode_decodes_to_unicode(self):
        # Byte strings are decoded as ASCII by _to_unicode(), replacing
        # all non-ASCII characters with U+FFFD REPLACEMENT CHARACTERs.
        byte_string = b"This string will be converted. \xe5\xb2\x81\xe5."
        expected_unicode_string = (
            u"This string will be converted. \ufffd\ufffd\ufffd\ufffd.")
        converted_string = ExternalProcessError._to_unicode(byte_string)
        self.assertIsInstance(converted_string, unicode)
        self.assertEqual(expected_unicode_string, converted_string)

    def test_to_unicode_defers_to_unicode_constructor(self):
        # Unicode strings and non-byte strings are handed to unicode()
        # to undergo Python's normal coercion strategy. (For unicode
        # strings this is actually a no-op, but it's cheaper to do this
        # than special-case unicode strings.)
        self.assertEqual(
            unicode(self), ExternalProcessError._to_unicode(self))

    def test_to_ascii_encodes_to_bytes(self):
        # Yes, this is how you really spell "smorgasbord."  Look it up.
        unicode_string = u"Sm\xf6rg\xe5sbord"
        expected_byte_string = b"Sm?rg?sbord"
        converted_string = ExternalProcessError._to_ascii(unicode_string)
        self.assertIsInstance(converted_string, bytes)
        self.assertEqual(expected_byte_string, converted_string)

    def test_to_ascii_defers_to_bytes(self):
        # Byte strings and non-unicode strings are handed to bytes() to
        # undergo Python's normal coercion strategy. (For byte strings
        # this is actually a no-op, but it's cheaper to do this than
        # special-case byte strings.)
        self.assertEqual(bytes(self), ExternalProcessError._to_ascii(self))

    def test_to_ascii_removes_non_printable_chars(self):
        # After conversion to a byte string, all non-printable and
        # non-ASCII characters are replaced with question marks.
        byte_string = b"*How* many roads\x01\x02\xb2\xfe"
        expected_byte_string = b"*How* many roads????"
        converted_string = ExternalProcessError._to_ascii(byte_string)
        self.assertIsInstance(converted_string, bytes)
        self.assertEqual(expected_byte_string, converted_string)

    def test__str__returns_bytes(self):
        error = ExternalProcessError(returncode=-1, cmd="foo-bar")
        self.assertIsInstance(error.__str__(), bytes)

    def test__unicode__returns_unicode(self):
        error = ExternalProcessError(returncode=-1, cmd="foo-bar")
        self.assertIsInstance(error.__unicode__(), unicode)

    def test__str__contains_output(self):
        output = b"Joyeux No\xebl"
        ascii_output = "Joyeux No?l"
        error = ExternalProcessError(
            returncode=-1, cmd="foo-bar", output=output)
        self.assertIn(ascii_output, error.__str__())

    def test__unicode__contains_output(self):
        output = b"Mot\xf6rhead"
        unicode_output = "Mot\ufffdrhead"
        error = ExternalProcessError(
            returncode=-1, cmd="foo-bar", output=output)
        self.assertIn(unicode_output, error.__unicode__())

    def test_output_as_ascii(self):
        output = b"Joyeux No\xebl"
        ascii_output = "Joyeux No?l"
        error = ExternalProcessError(
            returncode=-1, cmd="foo-bar", output=output)
        self.assertEqual(ascii_output, error.output_as_ascii)

    def test_output_as_unicode(self):
        output = b"Mot\xf6rhead"
        unicode_output = "Mot\ufffdrhead"
        error = ExternalProcessError(
            returncode=-1, cmd="foo-bar", output=output)
        self.assertEqual(unicode_output, error.output_as_unicode)


class TestAsynchronousDecorator(MAASTestCase):

    run_tests_with = AsynchronousDeferredRunTest.make_factory(timeout=5)

    @asynchronous
    def return_args(self, *args, **kwargs):
        return args, kwargs

    def test_in_reactor_thread(self):
        result = self.return_args(1, 2, three=3)
        self.assertEqual(((1, 2), {"three": 3}), result)

    @inlineCallbacks
    def test_in_other_thread(self):
        def do_stuff_in_thread():
            result = self.return_args(3, 4, five=5)
            self.assertThat(result, IsInstance(EventualResult))
            return result.wait()
        # Call do_stuff_in_thread() from another thread.
        result = yield deferToThread(do_stuff_in_thread)
        # do_stuff_in_thread() waited for the result of return_args().
        # The arguments passed back match those passed in from
        # do_stuff_in_thread().
        self.assertEqual(((3, 4), {"five": 5}), result)


class TestSynchronousDecorator(MAASTestCase):

    run_tests_with = AsynchronousDeferredRunTest.make_factory(timeout=5)

    @synchronous
    def return_args(self, *args, **kwargs):
        return args, kwargs

    def test_in_reactor_thread(self):
        expected = MatchesException(
            AssertionError, re.escape(
                "Function return_args(...) must not be called "
                "in the reactor thread."))
        self.assertThat(self.return_args, Raises(expected))

    @inlineCallbacks
    def test_in_other_thread(self):
        def do_stuff_in_thread():
            return self.return_args(3, 4, five=5)
        # Call do_stuff_in_thread() from another thread.
        result = yield deferToThread(do_stuff_in_thread)
        # do_stuff_in_thread() ran straight through, without
        # modification. The arguments passed back match those passed in
        # from do_stuff_in_thread().
        self.assertEqual(((3, 4), {"five": 5}), result)

    def test_allows_call_in_any_thread_when_reactor_not_running(self):
        self.patch(reactor, "running", False)
        self.assertEqual(((3, 4), {"five": 5}), self.return_args(3, 4, five=5))


class TestQuotePyLiteral(MAASTestCase):

    def test_uses_repr(self):
        string = factory.make_name('string')
        repr_mock = self.patch(provisioningserver.utils, 'repr')
        escape_py_literal(string)
        self.assertThat(repr_mock, MockCalledOnceWith(string))

    def test_decodes_ascii(self):
        string = factory.make_name('string')
        output = factory.make_name('output')
        repr_mock = self.patch(provisioningserver.utils, 'repr')
        ascii_value = Mock()
        ascii_value.decode = Mock(return_value=output)
        repr_mock.return_value = ascii_value
        value = escape_py_literal(string)
        self.assertThat(ascii_value.decode, MockCalledOnceWith('ascii'))
        self.assertEqual(value, output)


class TestCreateNode(PservTestCase):

    def test_passes_on_no_duplicate_macs(self):
        url = '/api/1.0/nodes/'
        uuid = 'node-' + factory.make_UUID()
        macs = [factory.getRandomMACAddress() for x in range(3)]
        arch = factory.make_name('architecture')
        power_type = factory.make_name('power_type')
        power_parameters = {
            'power_address': factory.getRandomIPAddress(),
            'power_user': factory.make_name('power_user'),
            'power_pass': factory.make_name('power_pass'),
            'power_control': None,
            'system_id': uuid
        }

        make_api_credentials()
        provisioningserver.auth.record_api_credentials(
            ':'.join(make_api_credentials()))
        self.set_maas_url()
        get = self.patch(MAASClient, 'get')
        post = self.patch(MAASClient, 'post')

        # Test for no duplicate macs
        get_data = []
        response = factory.make_response(
            httplib.OK, json.dumps(get_data),
            'application/json')
        get.return_value = response
        create_node(macs, arch, power_type, power_parameters)
        post_data = {
            'architecture': arch,
            'power_type': power_type,
            'power_parameters': json.dumps(power_parameters),
            'mac_addresses': macs,
            'autodetect_nodegroup': 'true'
        }
        self.assertThat(post, MockCalledOnceWith(url, 'new', **post_data))

    def test_errors_on_duplicate_macs(self):
        url = '/api/1.0/nodes/'
        uuid = 'node-' + factory.make_UUID()
        macs = [factory.getRandomMACAddress() for x in range(3)]
        arch = factory.make_name('architecture')
        power_type = factory.make_name('power_type')
        power_parameters = {
            'power_address': factory.getRandomIPAddress(),
            'power_user': factory.make_name('power_user'),
            'power_pass': factory.make_name('power_pass'),
            'power_control': None,
            'system_id': uuid
        }

        make_api_credentials()
        provisioningserver.auth.record_api_credentials(
            ':'.join(make_api_credentials()))
        self.set_maas_url()
        get = self.patch(MAASClient, 'get')
        post = self.patch(MAASClient, 'post')

        # Test for a duplicate mac
        resource_uri1 = url + "%s/macs/%s/" % (uuid, macs[0])
        get_data = [
            {
                "macaddress_set": [
                    {
                        "resource_uri": resource_uri1,
                        "mac_address": macs[0]
                    }
                ]
            }
        ]
        response = factory.make_response(
            httplib.OK, json.dumps(get_data),
            'application/json')
        get.return_value = response
        create_node(macs, arch, power_type, power_parameters)
        self.assertThat(post, MockNotCalled())


class TestComposeURLOnIP(MAASTestCase):

    def make_path(self):
        """Return an arbitrary URL path part."""
        return '%s/%s' % (factory.make_name('root'), factory.make_name('sub'))

    def test__inserts_IPv4(self):
        ip = factory.getRandomIPAddress()
        path = self.make_path()
        self.assertEqual(
            'http://%s/%s' % (ip, path),
            compose_URL_on_IP('http:///%s' % path, ip))

    def test__inserts_IPv6_with_brackets(self):
        ip = factory.make_ipv6_address()
        path = self.make_path()
        self.assertEqual(
            'http://[%s]/%s' % (ip, path),
            compose_URL_on_IP('http:///%s' % path, ip))

    def test__preserves_query(self):
        ip = factory.getRandomIPAddress()
        key = factory.make_name('key')
        value = factory.make_name('value')
        self.assertEqual(
            'https://%s?%s=%s' % (ip, key, value),
            compose_URL_on_IP('https://?%s=%s' % (key, value), ip))

    def test__preserves_port_with_IPv4(self):
        ip = factory.getRandomIPAddress()
        port = factory.pick_port()
        self.assertEqual(
            'https://%s:%s/' % (ip, port),
            compose_URL_on_IP('https://:%s/' % port, ip))

    def test__preserves_port_with_IPv6(self):
        ip = factory.make_ipv6_address()
        port = factory.pick_port()
        self.assertEqual(
            'https://[%s]:%s/' % (ip, port),
            compose_URL_on_IP('https://:%s/' % port, ip))


class TestEnum(MAASTestCase):

    def test_map_enum_includes_all_enum_values(self):

        class Enum:
            ONE = 1
            TWO = 2

        self.assertItemsEqual(['ONE', 'TWO'], map_enum(Enum).keys())

    def test_map_enum_omits_private_or_special_methods(self):

        class Enum:
            def __init__(self):
                pass

            def __repr__(self):
                return "Enum"

            def _save(self):
                pass

            VALUE = 9

        self.assertItemsEqual(['VALUE'], map_enum(Enum).keys())

    def test_map_enum_maps_values(self):

        class Enum:
            ONE = 1
            THREE = 3

        self.assertEqual({'ONE': 1, 'THREE': 3}, map_enum(Enum))


class TestRetries(MAASTestCase):

    def assertRetry(
            self, clock, observed, expected_elapsed, expected_remaining,
            expected_wait):
        """Assert that the retry tuple matches the given expectations.

        Retry tuples are those returned by `retries`.
        """
        self.assertThat(observed, MatchesListwise([
            Equals(expected_elapsed),  # elapsed
            Equals(expected_remaining),  # remaining
            Equals(expected_wait),  # wait
        ]))

    def test_yields_elapsed_remaining_and_sleeper(self):
        # Take control of time.
        clock = Clock()

        gen_retries = retries(5, 2, clock=clock)
        # No time has passed, 5 seconds remain, and it suggests sleeping
        # for 2 seconds.
        self.assertRetry(clock, next(gen_retries), 0, 5, 2)
        # Mimic sleeping for the suggested sleep time.
        clock.advance(2)
        # Now 2 seconds have passed, 3 seconds remain, and it suggests
        # sleeping for 2 more seconds.
        self.assertRetry(clock, next(gen_retries), 2, 3, 2)
        # Mimic sleeping for the suggested sleep time.
        clock.advance(2)
        # Now 4 seconds have passed, 1 second remains, and it suggests
        # sleeping for just 1 more second.
        self.assertRetry(clock, next(gen_retries), 4, 1, 1)
        # Mimic sleeping for the suggested sleep time.
        clock.advance(1)
        # All done.
        self.assertRaises(StopIteration, next, gen_retries)

    def test_calculates_times_with_reference_to_current_time(self):
        # Take control of time.
        clock = Clock()

        gen_retries = retries(5, 2, clock=clock)
        # No time has passed, 5 seconds remain, and it suggests sleeping
        # for 2 seconds.
        self.assertRetry(clock, next(gen_retries), 0, 5, 2)
        # Mimic sleeping for 4 seconds, more than the suggested.
        clock.advance(4)
        # Now 4 seconds have passed, 1 second remains, and it suggests
        # sleeping for just 1 more second.
        self.assertRetry(clock, next(gen_retries), 4, 1, 1)
        # Don't sleep, ask again immediately, and the same answer is given.
        self.assertRetry(clock, next(gen_retries), 4, 1, 1)
        # Mimic sleeping for 100 seconds, much more than the suggested.
        clock.advance(100)
        # All done.
        self.assertRaises(StopIteration, next, gen_retries)


class TestPause(MAASTestCase):

    p_deferred_called = AfterPreprocessing(
        lambda d: bool(d.called), Is(True))
    p_deferred_cancelled = AfterPreprocessing(
        lambda d: d.result, MatchesAll(
            IsInstance(Failure), AfterPreprocessing(
                lambda failure: failure.value,
                IsInstance(CancelledError))))
    p_call_cancelled = AfterPreprocessing(
        lambda call: bool(call.cancelled), Is(True))
    p_call_called = AfterPreprocessing(
        lambda call: bool(call.called), Is(True))

    def test_pause_returns_a_deferred_that_fires_after_a_delay(self):
        # Take control of time.
        clock = Clock()
        wait = randint(4, 4000)

        p_call_scheduled_in_wait_seconds = AfterPreprocessing(
            lambda call: call.getTime(), Equals(wait))

        d = pause(wait, clock=clock)

        # pause() returns an uncalled deferred.
        self.assertIsInstance(d, Deferred)
        self.assertThat(d, Not(self.p_deferred_called))
        # pause() has scheduled a call to happen in `wait` seconds.
        self.assertThat(clock.getDelayedCalls(), HasLength(1))
        [delayed_call] = clock.getDelayedCalls()
        self.assertThat(delayed_call, MatchesAll(
            p_call_scheduled_in_wait_seconds,
            Not(self.p_call_cancelled),
            Not(self.p_call_called),
        ))
        # Nothing has changed right before the deadline.
        clock.advance(wait - 1)
        self.assertThat(d, Not(self.p_deferred_called))
        self.assertThat(delayed_call, MatchesAll(
            Not(self.p_call_cancelled), Not(self.p_call_called)))
        # After `wait` seconds the deferred is called.
        clock.advance(1)
        self.assertThat(d, self.p_deferred_called)
        self.assertThat(delayed_call, MatchesAll(
            Not(self.p_call_cancelled), self.p_call_called))
        # The result is unexciting.
        self.assertIsNone(d.result)

    def test_pause_can_be_cancelled(self):
        # Take control of time.
        clock = Clock()
        wait = randint(4, 4000)

        d = pause(wait, clock=clock)
        [delayed_call] = clock.getDelayedCalls()

        d.cancel()

        # The deferred has been cancelled.
        self.assertThat(d, MatchesAll(
            self.p_deferred_called, self.p_deferred_cancelled,
            first_only=True))

        # We must suppress the cancellation error here or the test suite
        # will get huffy about it.
        d.addErrback(lambda failure: None)

        # The delayed call was cancelled too.
        self.assertThat(delayed_call, MatchesAll(
            self.p_call_cancelled, Not(self.p_call_called)))
