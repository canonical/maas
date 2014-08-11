# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for utilities to execute external commands."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import os

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from provisioningserver.utils.shell import (
    call_and_check,
    ExternalProcessError,
    )
import provisioningserver.utils.shell as shell_module


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
