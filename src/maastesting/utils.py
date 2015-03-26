# Copyright 2012-2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Testing utilities."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "age_file",
    "content_from_file",
    "extract_word_list",
    "get_write_time",
    "FakeRandInt",
    "preexec_fn",
    "run_isolated",
    "sample_binary_data",
    ]

import codecs
import os
import re
import signal
from sys import (
    stderr,
    stdout,
)
from traceback import print_exc

import subunit
from testtools.content import Content
from testtools.content_type import UTF8_TEXT


def age_file(path, seconds):
    """Backdate a file's modification time so that it looks older."""
    stat_result = os.stat(path)
    atime = stat_result.st_atime
    mtime = stat_result.st_mtime
    os.utime(path, (atime, mtime - seconds))


def get_write_time(path):
    """Return last modification time of file at `path`."""
    return os.stat(path).st_mtime


def content_from_file(path):
    """Alternative to testtools' version.

    This keeps an open file-handle, so it can obtain the log even when the
    file has been unlinked.
    """
    fd = open(path, "rb")

    def iterate():
        fd.seek(0)
        return iter(fd)

    return Content(UTF8_TEXT, iterate)


def extract_word_list(string):
    """Return a list of words from a string.

    Words are any string of 1 or more characters, not including commas,
    semi-colons, or whitespace.
    """
    return re.findall("[^,;\s]+", string)


def preexec_fn():
    # Revert Python's handling of SIGPIPE. See
    # http://bugs.python.org/issue1652 for more info.
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)


def run_isolated(cls, self, result):
    """Run a test suite or case in a subprocess.

    This is derived from ``subunit.run_isolated``. Subunit's version
    clobbers stdout by dup'ing the subunit's stream over the top, which
    prevents effective debugging at the terminal. This variant does not
    suffer from the same issue.
    """
    c2pread, c2pwrite = os.pipe()
    pid = os.fork()
    if pid == 0:
        # Child: runs test and writes subunit to c2pwrite.
        try:
            os.close(c2pread)
            stream = os.fdopen(c2pwrite, 'wb')
            sender = subunit.TestProtocolClient(stream)
            cls.run(self, sender)
            stream.flush()
            stdout.flush()
            stderr.flush()
        except:
            # Print error and exit hard.
            try:
                print_exc(file=stderr)
                stderr.flush()
            finally:
                os._exit(2)
        finally:
            # Exit hard.
            os._exit(0)
    else:
        # Parent: receives subunit from c2pread.
        os.close(c2pwrite)
        stream = os.fdopen(c2pread, 'rb')
        receiver = subunit.TestProtocolServer(result)
        receiver.readFrom(stream)
        os.waitpid(pid, 0)


# Some horrible binary data that could never, ever, under any encoding
# known to man(1) survive mis-interpretation as text.
#
# The data contains a nul byte to trip up accidental string termination.
# Switch the bytes of the byte-order mark around and by design you get
# an invalid codepoint; put a byte with the high bit set between bytes
# that have it cleared, and you have a guaranteed non-UTF-8 sequence.
#
# (1) Provided, of course, that man know only about ASCII and
# UTF.
sample_binary_data = codecs.BOM64_LE + codecs.BOM64_BE + b'\x00\xff\x00'


class FakeRandInt:
    """Fake `randint` with forced limitations on its range.

    This lets you set a forced minimum, and/or a forced maximum, on the range
    of any call.  For example, if you pass `forced_maximum=3`, then a call
    will never return more than 3.  If you don't set a maximum, or if the
    call's maximum argument is less than the forced maximum, then the call's
    maximum will be respected.
    """
    def __init__(self, real_randint, forced_minimum=None, forced_maximum=None):
        self.real_randint = real_randint
        self.minimum = forced_minimum
        self.maximum = forced_maximum

    def __call__(self, minimum, maximum):
        if self.minimum is not None:
            minimum = max(minimum, self.minimum)
        if self.maximum is not None:
            maximum = min(maximum, self.maximum)
        return self.real_randint(minimum, maximum)
