# Copyright 2012-2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Testing utilities."""

__all__ = [
    "age_file",
    "extract_word_list",
    "sample_binary_data",
]

import codecs
import os
import re


def age_file(path, seconds):
    """Backdate a file's modification time so that it looks older."""
    stat_result = os.stat(path)
    atime = stat_result.st_atime
    mtime = stat_result.st_mtime
    os.utime(path, (atime, mtime - seconds))


def extract_word_list(string):
    """Return a list of words from a string.

    Words are any string of 1 or more characters, not including commas,
    semi-colons, or whitespace.
    """
    return re.findall("[^,;\s]+", string)


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
