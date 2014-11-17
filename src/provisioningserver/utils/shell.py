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
    'pipefork',
    'PipeForkError',
    ]

from contextlib import contextmanager
import cPickle
import os
from pipes import quote
import signal
from string import printable
from subprocess import (
    CalledProcessError,
    PIPE,
    Popen,
    )
from sys import (
    stderr,
    stdout,
    )
from tempfile import TemporaryFile

from twisted.python.failure import Failure

# A mapping of signal numbers to names. It is strange that this isn't in the
# standard library (but I did check).
signal_names = {
    value: name for name, value in vars(signal).viewitems()
    if name.startswith('SIG') and '_' not in name
}

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

    @classmethod
    def upgrade(cls, error):
        """Upgrade the given error to an instance of this class.

        If `error` is an instance of :py:class:`CalledProcessError`, this will
        change its class, in-place, to :py:class:`ExternalProcessError`.

        There are two ways we could have done this:

        1. Change the class of `error` in-place.

        2. Capture ``exc_info``, create a new exception based on `error`, then
           re-raise with the 3-argument version of ``raise``.

        #1 seems a lot simpler so that's what this method does. The caller
        needs then only use a naked ``raise`` to get the utility of this class
        without losing the traceback.
        """
        if type(error) is CalledProcessError:
            error.__class__ = cls

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


class PipeForkError(Exception):
    """An error occurred in `pipefork`."""


@contextmanager
def pipefork():
    """Context manager that forks with pipes between parent and child.

    Use like so::

        with pipefork() as (pid, fin, fout):
            if pid == 0:
                # This is the child.
                ...
            else:
                # This is the parent.
                ...

    Pipes are set up so that the parent can write to the child, and
    vice-versa.

    In the child, ``fin`` is a file that reads from the parent, and ``fout``
    is a file that writes to the parent.

    In the parent, ``fin`` is a file that reads from the child, and ``fout``
    is a file that writes to the child.

    Be careful to think about closing these file objects to avoid deadlocks.
    For example, the following will deadlock:

        with pipefork() as (pid, fin, fout):
            if pid == 0:
                fin.read()  # Read from the parent.
                fout.write(b'Moien')  # Greet the parent.
            else:
                fout.write(b'Hello')  # Greet the child.
                fin.read()  # Read from the child *BLOCKS FOREVER*

    The reason is that the read in the child never returns because the pipe is
    never closed. Closing ``fout`` in the parent resolves the problem::

        with pipefork() as (pid, fin, fout):
            if pid == 0:
                fin.read()  # Read from the parent.
                fout.write(b'Moien')  # Greet the parent.
            else:
                fout.write(b'Hello')  # Greet the child.
                fout.close()  # Close the write pipe to the child.
                fin.read()  # Read from the child.

    Exceptions raised in the child are magically re-raised in the parent. When
    the child has died for another reason, a signal perhaps, a `PipeForkError`
    is raised with an explanatory message.

    :raises: `PipeForkError` when the child process dies a somewhat unnatural
        death, e.g. by a signal or when writing a crash-dump fails.
    """
    crashfile = TemporaryFile()

    c2pread, c2pwrite = os.pipe()
    p2cread, p2cwrite = os.pipe()

    pid = os.fork()

    if pid == 0:
        # Child: this conditional branch runs in the child process.
        try:
            os.close(c2pread)
            os.close(p2cwrite)

            with os.fdopen(p2cread, 'rb') as fin:
                with os.fdopen(c2pwrite, 'wb') as fout:
                    yield pid, fin, fout

            stdout.flush()
            stderr.flush()
        except SystemExit as se:
            # Exit hard, not soft.
            os._exit(se.code)
        except:
            try:
                # Pickle error to crash file.
                cPickle.dump(Failure(), crashfile, cPickle.HIGHEST_PROTOCOL)
                crashfile.flush()
            finally:
                # Exit hard.
                os._exit(2)
        finally:
            # Exit hard.
            os._exit(0)
    else:
        # Parent: this conditional branch runs in the parent process.
        os.close(c2pwrite)
        os.close(p2cread)

        with os.fdopen(c2pread, 'rb') as fin:
            with os.fdopen(p2cwrite, 'wb') as fout:
                yield pid, fin, fout

        # Wait for the child to finish.
        _, status = os.waitpid(pid, 0)
        signal = (status & 0xff)
        code = (status >> 8) & 0xff

        # Check for a saved crash.
        crashfile.seek(0)
        try:
            error = cPickle.load(crashfile)
        except EOFError:
            # No crash was recorded.
            error = None
        else:
            # Raise exception from child.
            error.raiseException()
        finally:
            crashfile.close()

        if os.WIFSIGNALED(status):
            # The child was killed by a signal.
            raise PipeForkError(
                "Child killed by signal %d (%s)" % (
                    signal, signal_names.get(signal, "?")))
        elif code != 0:
            # The child exited with a non-zero code.
            raise PipeForkError(
                "Child exited with code %d" % code)
        else:
            # All okay.
            pass


@contextmanager
def objectfork():
    """Like `pipefork`, but objects can be passed between parent and child.

    Usage::

        with objectfork() as (pid, recv, send):
            if pid == 0:
                # Child.
                for foo in bar():
                    send(foo)
                send(None)  # Done.
            else:
                for data in iter(recv, None):
                    ...  # Process data.

    In the child, ``recv`` receives objects sent -- via `send` -- from
    the parent.

    In the parent, ``recv`` receives objects sent -- via `send` -- from
    the child.

    All objects must be picklable.

    See `pipefork` for more details.
    """
    with pipefork() as (pid, fin, fout):

        def recv():
            return cPickle.load(fin)

        def send(obj):
            cPickle.dump(obj, fout, cPickle.HIGHEST_PROTOCOL)
            fout.flush()  # cPickle.dump() does not flush.

        yield pid, recv, send
