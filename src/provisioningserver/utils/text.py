# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Text-processing utilities."""

__all__ = [
    'normalise_whitespace',
    'normalise_to_comma_list',
    'split_string_list',
]

import re


def normalise_whitespace(text):
    """Replace any whitespace sequence in `text` with just a single space."""
    return ' '.join(text.split())


def normalise_to_comma_list(string):
    """Take a space- or comma-separated list and return a comma-separated list.

    ISC dhcpd is quite picky about comma-separated lists. When in doubt,
    normalise using this function.
    """
    return ", ".join(split_string_list(string))


def split_string_list(string):
    """Take a space- or comma-separated list and generate the parts."""
    return (part for part in re.split(r'[,\s]+', string) if len(part) != 0)
