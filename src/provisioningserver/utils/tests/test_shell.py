# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for utilities to execute external commands."""

__all__ = []

import os
from random import randint
import re
import signal
from subprocess import CalledProcessError
import time

from fixtures import EnvironmentVariable
from maastesting.factory import factory
from maastesting.fixtures import DetectLeakedFileDescriptors
from maastesting.matchers import MockCalledOnceWith
from maastesting.testcase import MAASTestCase
from provisioningserver.utils.shell import (
    call_and_check,
    ExternalProcessError,
    has_command_available,
    objectfork,
    pipefork,
    PipeForkError,
    select_c_utf8_locale,
)
import provisioningserver.utils.shell as shell_module
from testtools import ExpectedException
from testtools.matchers import (
    ContainsDict,
    Equals,
    Is,
    IsInstance,
    Not,
)


class TestCallAndCheck(MAASTestCase):
    """Tests `call_and_check`."""

    def patch_popen(self, returncode=0, stderr=''):
        """Replace `subprocess.Popen` with a mock."""
        popen = self.patch(shell_module, 'Popen')
        process = popen.return_value
        process.communicate.return_value = (None, stderr)
        process.returncode = returncode
        return process

    def test__returns_standard_output(self):
        output = factory.make_string().encode("ascii")
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
            b"/bin/cat: %s: No such file or directory"
            % nonfile.encode("ascii"), error.output)


class TestExternalProcessError(MAASTestCase):
    """Tests for the ExternalProcessError class."""

    def test_upgrade_upgrades_CalledProcessError(self):
        error = factory.make_CalledProcessError()
        self.expectThat(error, Not(IsInstance(ExternalProcessError)))
        ExternalProcessError.upgrade(error)
        self.expectThat(error, IsInstance(ExternalProcessError))

    def test_upgrade_does_not_change_CalledProcessError_subclasses(self):
        error_type = factory.make_exception_type(bases=(CalledProcessError,))
        error = factory.make_CalledProcessError()
        error.__class__ = error_type  # Change the class.
        self.expectThat(error, Not(IsInstance(ExternalProcessError)))
        ExternalProcessError.upgrade(error)
        self.expectThat(error, Not(IsInstance(ExternalProcessError)))
        self.expectThat(error.__class__, Is(error_type))

    def test_upgrade_does_not_change_other_errors(self):
        error_type = factory.make_exception_type()
        error = error_type()
        self.expectThat(error, Not(IsInstance(ExternalProcessError)))
        ExternalProcessError.upgrade(error)
        self.expectThat(error, Not(IsInstance(ExternalProcessError)))
        self.expectThat(error.__class__, Is(error_type))

    def test_upgrade_returns_None(self):
        self.expectThat(
            ExternalProcessError.upgrade(factory.make_exception()),
            Is(None))

    def test_to_unicode_decodes_to_unicode(self):
        # Byte strings are decoded as ASCII by _to_unicode(), replacing
        # all non-ASCII characters with U+FFFD REPLACEMENT CHARACTERs.
        byte_string = b"This string will be converted. \xe5\xb2\x81\xe5."
        expected_unicode_string = (
            "This string will be converted. \ufffd\ufffd\ufffd\ufffd.")
        converted_string = ExternalProcessError._to_unicode(byte_string)
        self.assertIsInstance(converted_string, str)
        self.assertEqual(expected_unicode_string, converted_string)

    def test_to_unicode_defers_to_unicode_constructor(self):
        # Unicode strings and non-byte strings are handed to unicode()
        # to undergo Python's normal coercion strategy. (For unicode
        # strings this is actually a no-op, but it's cheaper to do this
        # than special-case unicode strings.)
        self.assertEqual(
            str(self), ExternalProcessError._to_unicode(self))

    def test_to_ascii_encodes_to_bytes(self):
        # Yes, this is how you really spell "smorgasbord."  Look it up.
        unicode_string = "Sm\xf6rg\xe5sbord"
        expected_byte_string = b"Sm?rg?sbord"
        converted_string = ExternalProcessError._to_ascii(unicode_string)
        self.assertIsInstance(converted_string, bytes)
        self.assertEqual(expected_byte_string, converted_string)

    def test_to_ascii_defers_to_bytes(self):
        # Byte strings and non-unicode strings are handed to bytes() to
        # undergo Python's normal coercion strategy. (For byte strings
        # this is actually a no-op, but it's cheaper to do this than
        # special-case byte strings.)
        self.assertEqual(
            str(self).encode("ascii"),
            ExternalProcessError._to_ascii(self))

    def test_to_ascii_removes_non_printable_chars(self):
        # After conversion to a byte string, all non-printable and
        # non-ASCII characters are replaced with question marks.
        byte_string = b"*How* many roads\x01\x02\xb2\xfe"
        expected_byte_string = b"*How* many roads????"
        converted_string = ExternalProcessError._to_ascii(byte_string)
        self.assertIsInstance(converted_string, bytes)
        self.assertEqual(expected_byte_string, converted_string)

    def test__str__returns_unicode(self):
        error = ExternalProcessError(returncode=-1, cmd="foo-bar")
        self.assertIsInstance(error.__str__(), str)

    def test__str__contains_output(self):
        output = b"Mot\xf6rhead"
        unicode_output = "Mot\ufffdrhead"
        error = ExternalProcessError(
            returncode=-1, cmd="foo-bar", output=output)
        self.assertIn(unicode_output, error.__str__())

    def test_output_as_ascii(self):
        output = b"Joyeux No\xebl"
        ascii_output = b"Joyeux No?l"
        error = ExternalProcessError(
            returncode=-1, cmd="foo-bar", output=output)
        self.assertEqual(ascii_output, error.output_as_ascii)

    def test_output_as_unicode(self):
        output = b"Mot\xf6rhead"
        unicode_output = "Mot\ufffdrhead"
        error = ExternalProcessError(
            returncode=-1, cmd="foo-bar", output=output)
        self.assertEqual(unicode_output, error.output_as_unicode)


class TestPipeFork(MAASTestCase):

    def setUp(self):
        super(TestPipeFork, self).setUp()
        self.useFixture(DetectLeakedFileDescriptors())

    def test__forks(self):
        with pipefork() as (pid, fin, fout):
            if pid == 0:
                # Child.
                message_in = fin.read()
                message_out = b"Hello %s!" % message_in
                fout.write(message_out)
                fout.close()
            else:
                # Parent.
                message_out = factory.make_name("Parent").encode("ascii")
                fout.write(message_out)
                fout.close()
                message_in = fin.read()
                self.assertEqual(b"Hello %s!" % message_out, message_in)

    def test__raises_childs_exception_when_child_crashes(self):
        # If the child process exits with an exception, it is passed back to
        # the parent via a pickled t.p.failure.Failure, and re-raised.
        with ExpectedException(ZeroDivisionError):
            with pipefork() as (pid, fin, fout):
                if pid == 0:
                    # Child.
                    raise ZeroDivisionError()

    def test__raises_parents_exception_when_parent_crashes(self):
        # If the parent raises an exception, it is propagated. During
        # tear-down of the pipefork's context the child is reaped, but any
        # exceptions (via the crash file, or raised on behalf of the child
        # because of a non-zero exit code or non-zero signal) propagating back
        # from the child are masked by the exception in the parent.
        with ExpectedException(ZeroDivisionError):
            with pipefork() as (pid, fin, fout):
                if pid != 0:
                    # Parent.
                    raise ZeroDivisionError()

    def test__raises_exception_when_child_killed_by_signal(self):
        expected_message = re.escape("Child killed by signal 15 (SIGTERM)")
        with ExpectedException(PipeForkError, expected_message):
            with pipefork() as (pid, fin, fout):
                if pid == 0:
                    # Reset SIGTERM to the default handler; the Twisted
                    # reactor may have clobbered it in the parent.
                    signal.signal(signal.SIGTERM, signal.SIG_DFL)
                    # Close `fout` to signal to parent that we're running.
                    fout.close()
                    time.sleep(10)
                else:
                    # Wait for child to close its `fout` before signalling.
                    fin.read()
                    os.kill(pid, signal.SIGTERM)

    def test__raises_exception_when_child_exits_with_non_zero_code(self):
        exit_code = randint(1, 99)
        expected_message = re.escape("Child exited with code %s" % exit_code)
        with ExpectedException(PipeForkError, expected_message):
            with pipefork() as (pid, fin, fout):
                if pid == 0:
                    os._exit(exit_code)

    def test__SystemExit_in_child_is_not_raised_in_parent(self):
        # All exceptions are pickled and passed back to the parent process,
        # except for SystemExit. It instead results in a call to os._exit().
        exit_code = randint(1, 99)
        expected_message = re.escape("Child exited with code %s" % exit_code)
        with ExpectedException(PipeForkError, expected_message):
            with pipefork() as (pid, fin, fout):
                if pid == 0:
                    raise SystemExit(exit_code)


class TestObjectFork(MAASTestCase):

    def setUp(self):
        super(TestObjectFork, self).setUp()
        self.useFixture(DetectLeakedFileDescriptors())

    def test__can_send_and_receive_objects(self):

        def child(recv, send):
            # Sum numbers until we get None through.
            for numbers in iter(recv, None):
                send(sum(numbers))
            # Now echo things until we get None.
            for things in iter(recv, None):
                send(things)

        def parent(recv, send):
            # Send numbers to the child first.
            for _ in range(randint(3, 10)):
                numbers = list(randint(1, 100) for _ in range(10))
                send(numbers)
                self.assertEqual(sum(numbers), recv())
            # Signal that we're done with numbers.
            send(None)
            # Send some other things and see that they come back.
            picklable_things = {
                "foo": [randint(1, 1000) for _ in range(10)],
                (1, 2, b"three", 4.0): {self.__class__, "bar"},
            }
            send(picklable_things)
            self.assertEqual(picklable_things, recv())
            # Signal that we're done again.
            send(None)

        with objectfork() as (pid, recv, send):
            if pid == 0:
                child(recv, send)
            else:
                parent(recv, send)


class TestHasCommandAvailable(MAASTestCase):

    def test__calls_which(self):
        mock_call_and_check = self.patch(shell_module, "call_and_check")
        cmd = factory.make_name("cmd")
        has_command_available(cmd)
        self.assertThat(
            mock_call_and_check, MockCalledOnceWith(["which", cmd]))

    def test__returns_False_when_ExternalProcessError_raised(self):
        self.patch(shell_module, "call_and_check").side_effect = (
            ExternalProcessError(1, "cmd"))
        self.assertFalse(has_command_available(factory.make_name("cmd")))

    def test__returns_True_when_ExternalProcessError_not_raised(self):
        self.patch(shell_module, "call_and_check")
        self.assertTrue(has_command_available(factory.make_name("cmd")))


class TestSelectCUTF8Locale(MAASTestCase):
    """Tests for `select_c_utf8_locale`."""

    # Taken from locale(7).
    LC_VAR_NAMES = {
        "LC_ADDRESS", "LC_COLLATE", "LC_CTYPE", "LC_IDENTIFICATION",
        "LC_MONETARY", "LC_MESSAGES", "LC_MEASUREMENT", "LC_NAME",
        "LC_NUMERIC", "LC_PAPER", "LC_TELEPHONE", "LC_TIME",
    }

    def test__sets_LANG_and_LC_ALL(self):
        self.assertThat(
            select_c_utf8_locale({}),
            Equals({
                "LANG": "C.UTF-8",
                "LC_ALL": "C.UTF-8",
            }),
        )

    def test__overwrites_LANG(self):
        self.assertThat(
            select_c_utf8_locale({
                "LANG": factory.make_name("LANG"),
            }),
            Equals({
                "LANG": "C.UTF-8",
                "LC_ALL": "C.UTF-8",
            }),
        )

    def test__removes_other_LC_variables(self):
        self.assertThat(
            select_c_utf8_locale({
                name: factory.make_name(name)
                for name in self.LC_VAR_NAMES
            }),
            Equals({
                "LANG": "C.UTF-8",
                "LC_ALL": "C.UTF-8",
            }),
        )

    def test__passes_other_variables_through(self):
        basis = {
            factory.make_name("name"): factory.make_name("value")
            for _ in range(5)
        }
        expected = dict(basis, LANG="C.UTF-8", LC_ALL="C.UTF-8")
        observed = select_c_utf8_locale(basis)
        self.assertThat(observed, Equals(expected))

    def test__defaults_to_process_environment(self):
        name = factory.make_name("name")
        value = factory.make_name("value")
        with EnvironmentVariable(name, value):
            self.assertThat(
                select_c_utf8_locale(),
                ContainsDict({name: Equals(value)}),
            )
