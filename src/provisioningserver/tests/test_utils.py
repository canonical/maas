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
import tempfile
from textwrap import dedent
import time
import types

from maastesting import root
from maastesting.factory import factory
from maastesting.fakemethod import FakeMethod
from maastesting.testcase import TestCase
from mock import Mock
import netifaces
from netifaces import (
    AF_LINK,
    AF_INET,
    AF_INET6,
    )
import provisioningserver
from provisioningserver.utils import (
    ActionScript,
    atomic_write,
    AtomicWriteScript,
    get_all_interface_addresses,
    get_mtime,
    incremental_write,
    maas_custom_config_markers,
    MainScript,
    parse_key_value_file,
    pick_new_mtime,
    Safe,
    ShellTemplate,
    sudo_write_file,
    write_custom_config_section,
    )
from testtools.matchers import (
    EndsWith,
    FileContains,
    MatchesStructure,
    )
from testtools.testcase import ExpectedException


class TestInterfaceFunctions(TestCase):
    """Tests for functions relating to network interfaces."""

    example_interfaces = {
        'eth0': {
            AF_LINK: [{'addr': '00:1d:ba:86:aa:fe',
                       'broadcast': 'ff:ff:ff:ff:ff:ff'}],
            },
        'lo': {
            AF_INET: [{'addr': '127.0.0.1',
                       'netmask': '255.0.0.0',
                       'peer': '127.0.0.1'}],
            AF_INET6: [{'addr': '::1',
                        'netmask': 'ff:ff:ff:ff:ff:ff'}],
            AF_LINK: [{'addr': '00:00:00:00:00:00',
                       'peer': '00:00:00:00:00:00'}],
            },
        'lxcbr0': {
            AF_INET: [{'addr': '10.0.3.1',
                       'broadcast': '10.0.3.255',
                       'netmask': '255.255.255.0'}],
            AF_INET6: [{'addr': 'fe80::9894:6fff:fe8b:22%lxcbr0',
                        'netmask': 'ffff:ffff:ffff:ffff::'}],
            AF_LINK: [{'addr': '9a:94:6f:8b:00:22',
                       'broadcast': 'ff:ff:ff:ff:ff:ff'}]},
        'tun0': {
            AF_INET: [{'addr': '10.99.244.250',
                       'netmask': '255.255.255.255',
                       'peer': '10.99.244.249'}],
            },
        'wlan0': {
            AF_INET: [{'addr': '10.155.1.159',
                       'broadcast': '10.155.31.255',
                       'netmask': '255.255.224.0'}],
            AF_INET6: [{'addr': 'fe80::221:5dff:fe85:d2e4%wlan0',
                        'netmask': 'ffff:ffff:ffff:ffff::'}],
            AF_LINK: [{'addr': '00:21:5d:85:dAF_INET:e4',
                       'broadcast': 'ff:ff:ff:ff:ff:ff'}],
            },
        }

    def test_get_all_interface_addresses(self):
        # get_all_interface_addresses() returns the IPv4 addresses associated
        # with each of the network devices present on the system, as reported
        # by netifaces. IPv6 is ignored.
        self.patch(netifaces, "interfaces", self.example_interfaces.keys)
        self.patch(netifaces, "ifaddresses", self.example_interfaces.get)
        self.assertEqual(
            ["127.0.0.1", "10.0.3.1", "10.99.244.250", "10.155.1.159"],
            list(get_all_interface_addresses()))


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

    def test_incremental_write_sets_permissions(self):
        atomic_file = self.make_file()
        mode = 0323
        incremental_write(factory.getRandomString(), atomic_file, mode=mode)
        self.assertEqual(mode, stat.S_IMODE(os.stat(atomic_file).st_mode))


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


class WriteCustomConfigSectionTest(TestCase):
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


class SudoWriteFileTest(TestCase):
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
        contents = factory.getRandomString()

        sudo_write_file(path, contents)

        provisioningserver.utils.Popen.assert_called_once_with([
            'sudo', '-n', 'maas-provision', 'atomic-write',
            '--filename', path, '--mode', '0644',
            ],
            stdin=PIPE)

    def test_encodes_contents(self):
        process = self.patch_popen()
        contents = factory.getRandomString()
        encoding = 'utf-16'
        sudo_write_file(self.make_file(), contents, encoding=encoding)
        process.communicate.assert_called_once_with(contents.encode(encoding))

    def test_catches_failures(self):
        self.patch_popen(1)
        self.assertRaises(
            CalledProcessError,
            sudo_write_file, self.make_file(), factory.getRandomString())


class ParseConfigTest(TestCase):
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
        filename = factory.getRandomString()
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
        filename = factory.getRandomString()
        args = parser.parse_args(('--filename', filename))
        self.assertFalse(args.no_overwrite)

    def test_script_executable(self):
        content = factory.getRandomString()
        script = ["%s/bin/maas-provision" % root, 'atomic-write']
        target_file = self.make_file()
        script.extend(('--filename', target_file, '--mode', '615'))
        cmd = Popen(
            script, stdin=PIPE,
            env=dict(PYTHONPATH=":".join(sys.path)))
        cmd.communicate(content)
        self.assertThat(target_file, FileContains(content))
        self.assertEqual(0615, stat.S_IMODE(os.stat(target_file).st_mode))

    def test_passes_overwrite_flag(self):
        content = factory.getRandomString()
        filename = factory.getRandomString()
        mocked_atomic_write = self.get_and_run_mocked_script(
            content, filename,
            ('--filename', filename, '--no-overwrite'))

        mocked_atomic_write.assert_called_once_with(
            content, filename, mode=0600, overwrite=False)

    def test_passes_mode_flag(self):
        content = factory.getRandomString()
        filename = factory.getRandomString()
        # Mode that's unlikely to occur in the wild.
        mode = 0377
        mocked_atomic_write = self.get_and_run_mocked_script(
            content, filename,
            ('--filename', filename, '--mode', oct(mode)))

        mocked_atomic_write.assert_called_once_with(
            content, filename, mode=mode, overwrite=True)

    def test_default_mode(self):
        content = factory.getRandomString()
        filename = factory.getRandomString()
        mocked_atomic_write = self.get_and_run_mocked_script(
            content, filename,
            ('--filename', filename))

        mocked_atomic_write.assert_called_once_with(
            content, filename, mode=0600, overwrite=True)
