# Copyright 2012-2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Testing utilities."""

import codecs
import os
from pathlib import Path
import re

from testtools.content import Content
from testtools.content_type import UTF8_TEXT


def running_in_docker() -> bool:
    """Return whether tests are running in a docker container."""
    return Path("/.dockerenv").exists()


def age_file(path, seconds):
    """Backdate a file's modification time so that it looks older."""
    stat_result = os.stat(path)
    atime = stat_result.st_atime
    mtime = stat_result.st_mtime
    os.utime(path, (atime, mtime - seconds))


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
    return re.findall(r"[^,;\s]+", string)


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
sample_binary_data = codecs.BOM64_LE + codecs.BOM64_BE + b"\x00\xff\x00"
