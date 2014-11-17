# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Text-processing utilities."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'make_bullet_list',
    'normalise_whitespace',
    ]

from textwrap import TextWrapper


def normalise_whitespace(text):
    """Replace any whitespace sequence in `text` with just a single space."""
    return ' '.join(text.split())


def make_bullet_list(messages):
    """Join `messages` into a bullet list.

    Each message is reformatted to 70 columns wide, indented by 2 columns,
    making 72 columns in all. The first line of each message is denoted by a
    asterisk in the first column.

    :type messages: An iterable of strings.
    :return: A string.
    """
    fill = TextWrapper(72, initial_indent="* ", subsequent_indent="  ").fill
    return "\n".join(fill(message) for message in messages)
