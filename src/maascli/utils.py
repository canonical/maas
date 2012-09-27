# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Utilities for the command-line interface."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    "ensure_trailing_slash",
    "handler_command_name",
    "parse_docstring",
    "safe_name",
    "urlencode",
    ]

from functools import partial
from inspect import getdoc
import re
from textwrap import dedent
from urllib import quote_plus


re_paragraph_splitter = re.compile(
    r"(?:\r\n){2,}|\r{2,}|\n{2,}", re.MULTILINE)

paragraph_split = re_paragraph_splitter.split
docstring_split = partial(paragraph_split, maxsplit=1)
remove_line_breaks = lambda string: (
    " ".join(line.strip() for line in string.splitlines()))

newline = "\n"
empty = ""


def parse_docstring(thing):
    doc = thing if isinstance(thing, (str, unicode)) else getdoc(thing)
    doc = empty if doc is None else doc.expandtabs().strip()
    # Break the docstring into two parts: title and body.
    parts = docstring_split(doc)
    if len(parts) == 2:
        title, body = parts[0], dedent(parts[1])
    else:
        title, body = parts[0], empty
    # Remove line breaks from the title line.
    title = remove_line_breaks(title)
    # Remove line breaks from non-indented paragraphs in the body.
    paragraphs = []
    for paragraph in paragraph_split(body):
        if not paragraph[:1].isspace():
            paragraph = remove_line_breaks(paragraph)
        paragraphs.append(paragraph)
    # Rejoin the paragraphs, normalising on newline.
    body = (newline + newline).join(
        paragraph.replace("\r\n", newline).replace("\r", newline)
        for paragraph in paragraphs)
    return title, body


re_camelcase = re.compile(
    r"([A-Z]*[a-z0-9]+|[A-Z]+)(?:(?=[^a-z0-9])|\Z)")


def safe_name(string):
    """Return a munged version of string, suitable as an ASCII filename."""
    hyphen = "-" if isinstance(string, unicode) else b"-"
    return hyphen.join(re_camelcase.findall(string))


def handler_command_name(string):
    """Create a handler command name from an arbitrary string.

    Camel-case parts of string will be extracted, converted to lowercase,
    joined with hyphens, and the rest discarded. The term "handler" will also
    be removed if discovered amongst the aforementioned parts.
    """
    parts = re_camelcase.findall(string)
    parts = (part.lower().encode("ascii") for part in parts)
    parts = (part for part in parts if part != b"handler")
    return b"-".join(parts)


def ensure_trailing_slash(string):
    """Ensure that `string` has a trailing forward-slash."""
    slash = b"/" if isinstance(string, bytes) else u"/"
    return (string + slash) if not string.endswith(slash) else string


def urlencode(data):
    """A version of `urllib.urlencode` that isn't insane.

    This only cares that `data` is an iterable of iterables. Each sub-iterable
    must be of overall length 2, i.e. a name/value pair.

    Unicode strings will be encoded to UTF-8. This is what Django expects; see
    `smart_text` in the Django documentation.
    """
    enc = lambda string: quote_plus(
        string.encode("utf-8") if isinstance(string, unicode) else string)
    return b"&".join(
        b"%s=%s" % (enc(name), enc(value))
        for name, value in data)
