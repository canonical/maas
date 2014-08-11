# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Utilities for executing external commands."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'call_and_check',
    'ExternalProcessError',
    ]


from pipes import quote
from string import printable
from subprocess import (
    CalledProcessError,
    PIPE,
    Popen,
    )

# A table suitable for use with str.translate() to replace each
# non-printable and non-ASCII character in a byte string with a question
# mark, mimicking the "replace" strategy when encoding and decoding.
non_printable_replace_table = b"".join(
    chr(i) if chr(i) in printable else b"?"
    for i in xrange(0xff + 0x01))


class ExternalProcessError(CalledProcessError):
    """Raised when there's a problem calling an external command.

    Unlike `CalledProcessError`:

    - `__str__()` returns a string containing the output of the failed
      external process, if available. All non-printable and non-ASCII
      characters are filtered out, replaced by question marks.

    - `__unicode__()` is defined, and tries to return something
      analagous to `__str__()` but keeping in valid unicode characters
      from the error message.

    """

    @staticmethod
    def _to_unicode(string):
        if isinstance(string, bytes):
            return string.decode("ascii", "replace")
        else:
            return unicode(string)

    @staticmethod
    def _to_ascii(string, table=non_printable_replace_table):
        if isinstance(string, unicode):
            return string.encode("ascii", "replace")
        else:
            return bytes(string).translate(table)

    def __unicode__(self):
        cmd = u" ".join(quote(self._to_unicode(part)) for part in self.cmd)
        output = self._to_unicode(self.output)
        return u"Command `%s` returned non-zero exit status %d:\n%s" % (
            cmd, self.returncode, output)

    def __str__(self):
        cmd = b" ".join(quote(self._to_ascii(part)) for part in self.cmd)
        output = self._to_ascii(self.output)
        return b"Command `%s` returned non-zero exit status %d:\n%s" % (
            cmd, self.returncode, output)

    @property
    def output_as_ascii(self):
        """The command's output as printable ASCII.

        Non-printable and non-ASCII characters are filtered out.
        """
        return self._to_ascii(self.output)

    @property
    def output_as_unicode(self):
        """The command's output as Unicode text.

        Invalid Unicode characters are filtered out.
        """
        return self._to_unicode(self.output)


def call_and_check(command, *args, **kwargs):
    """Execute a command, similar to `subprocess.check_call()`.

    :param command: Command line, as a list of strings.
    :return: The command's output from standard output.
    :raise ExternalProcessError: If the command returns nonzero.
    """
    process = Popen(command, *args, stdout=PIPE, stderr=PIPE, **kwargs)
    stdout, stderr = process.communicate()
    stderr = stderr.strip()
    if process.returncode != 0:
        raise ExternalProcessError(process.returncode, command, output=stderr)
    return stdout
