# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Text-processing utilities."""

import re


def quote(string):
    """Surrounds the specified string in double-quotes (`"`)."""
    return '"%s"' % string


def normalise_whitespace(text):
    """Replace any whitespace sequence in `text` with just a single space."""
    return " ".join(text.split())


def normalise_to_comma_list(string, quoted=False):
    """Take a space- or comma-separated list and return a comma-separated list.

    ISC dhcpd is quite picky about comma-separated lists. When in doubt,
    normalise using this function.
    """
    if not quoted:
        return ", ".join(split_string_list(string))
    else:
        return ", ".join(quote(string) for string in split_string_list(string))


def split_string_list(string):
    """Take a space- or comma-separated list and generate the parts."""
    return (part for part in re.split(r"[,\s]+", string) if len(part) != 0)


def make_gecos_field(
    fullname=None, room=None, worktel=None, hometel=None, other=None
):
    """Construct a GECOS field.

    Based on a reading of chfn(1).

    All strings passed in will be coerced to US-ASCII, replacing non-ASCII
    characters with question marks. Colons and commas will be replaced with
    underscores, and leading and trailing whitespace is stripped.

    :param fullname: The user's full name.
    :param room: The user's room number.
    :param worktel: The user's work telephone number.
    :param hometel: The user's home telephone number.
    :param other: Other useful information.

    :return: A string suitable for use as the GECOS field in ``/etc/passwd``.
    """
    fields = fullname, room, worktel, hometel, other

    def clean(string):
        if string is None:
            return ""
        else:
            return (
                string.replace(",", "_")
                .replace(":", "_")
                .encode("ascii", "replace")
                .decode("ascii")
                .strip()
            )

    return ",".join(map(clean, fields))
