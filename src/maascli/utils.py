# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Utilities for the command-line interface."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "ensure_trailing_slash",
    "handler_command_name",
    "parse_docstring",
    "safe_name",
    ]

from functools import partial
from inspect import (
    cleandoc,
    getdoc,
    )
import re
from urlparse import urlparse


re_paragraph_splitter = re.compile(
    r"(?:\r\n){2,}|\r{2,}|\n{2,}", re.MULTILINE)

paragraph_split = re_paragraph_splitter.split
docstring_split = partial(paragraph_split, maxsplit=1)
remove_line_breaks = lambda string: (
    " ".join(line.strip() for line in string.splitlines()))

newline = "\n"
empty = ""


def parse_docstring(thing):
    """Parse python docstring for `thing`.

    Returns a tuple: (title, body).  As per docstring convention, title is
    the docstring's first paragraph and body is the rest.
    """
    assert not isinstance(thing, bytes)
    is_string = isinstance(thing, unicode)
    doc = cleandoc(thing) if is_string else getdoc(thing)
    doc = empty if doc is None else doc
    assert not isinstance(doc, bytes)
    # Break the docstring into two parts: title and body.
    parts = docstring_split(doc)
    if len(parts) == 2:
        title, body = parts[0], parts[1]
    else:
        title, body = parts[0], empty
    # Remove line breaks from the title line.
    title = remove_line_breaks(title)
    # Normalise line-breaks on newline.
    body = body.replace("\r\n", newline).replace("\r", newline)
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


def api_url(string):
    """Ensure that `string` looks like a URL to the API.

    This ensures that the API version is specified explicitly (i.e. the path
    ends with /api/{version}). If not, version 1.0 is selected. It also
    ensures that the path ends with a forward-slash.

    This is suitable for use as an argument type with argparse.
    """
    url = urlparse(string)
    url = url._replace(path=ensure_trailing_slash(url.path))
    if re.search("/api/[0-9.]+/?$", url.path) is None:
        url = url._replace(path=url.path + "api/1.0/")
    return url.geturl()
