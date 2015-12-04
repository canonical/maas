# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Utilities for the command-line interface."""

__all__ = [
    "dump_response_summary",
    "ensure_trailing_slash",
    "get_response_content_type",
    "handler_command_name",
    "is_response_textual",
    "parse_docstring",
    "print_response_content",
    "print_response_headers",
    "safe_name",
]

from email.message import Message
from functools import partial
from inspect import (
    cleandoc,
    getdoc,
)
import re
import sys
from urllib.parse import urlparse


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
    is_string = isinstance(thing, str)
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
    return "-".join(re_camelcase.findall(string))


def handler_command_name(string):
    """Create a handler command name from an arbitrary string.

    Camel-case parts of string will be extracted, converted to lowercase,
    joined with hyphens, and the rest discarded. The term "handler" will also
    be removed if discovered amongst the aforementioned parts.
    """
    parts = re_camelcase.findall(string)
    parts = (part.lower() for part in parts)
    parts = (part for part in parts if part != "handler")
    return "-".join(parts)


def ensure_trailing_slash(string):
    """Ensure that `string` has a trailing forward-slash."""
    slash = b"/" if isinstance(string, bytes) else "/"
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


def import_module(import_str):
    """Import a module."""
    __import__(import_str)
    return sys.modules[import_str]


def try_import_module(import_str, default=None):
    """Try to import a module."""
    try:
        return import_module(import_str)
    except ImportError:
        return default


def get_response_content_type(response):
    """Returns the response's content-type, without parameters.

    If the content-type was not set in the response, returns `None`.

    :type response: :class:`httplib2.Response`
    """
    try:
        content_type = response["content-type"]
    except KeyError:
        return None
    else:
        # It seems odd to create a Message instance here, but at the time of
        # writing it's the only place that has the smarts to correctly deal
        # with a Content-Type that contains a charset (or other parameters).
        message = Message()
        message.set_type(content_type)
        return message.get_content_type()


def is_response_textual(response):
    """Is the response body text?"""
    content_type = get_response_content_type(response)
    return (
        content_type.endswith("/json") or
        content_type.startswith("text/"))


def print_response_headers(headers, file=None):
    """Write the response's headers to stdout in a human-friendly way.

    :type headers: :class:`httplib2.Response`, or :class:`dict`
    """
    file = sys.stdout if file is None else file
    # Function to change headers like "transfer-encoding" into
    # "Transfer-Encoding".
    cap = lambda header: "-".join(
        part.capitalize() for part in header.split("-"))
    # Format string to prettify reporting of response headers.
    form = "%%%ds: %%s" % (
        max(len(header) for header in headers) + 2)
    # Print the response.
    for header in sorted(headers):
        print(form % (cap(header), headers[header]), file=file)


def print_response_content(response, content, file=None):
    """Write the response's content to stdout.

    If the response is textual, a trailing \n is appended.
    """
    file = sys.stdout if file is None else file
    if file.isatty():
        if is_response_textual(response) and response.status // 100 == 2:
            file.write("Success.\n")
            file.write("Machine-readable output follows:\n")

        file.write(content)

        if is_response_textual(response):
            file.write("\n")
    else:
        file.write(content)


def dump_response_summary(response, file=None):
    """Dump the response line and headers to stderr.

    Intended for debugging.
    """
    file = sys.stderr if file is None else file
    print(response.status, response.reason, file=file)
    print(file=file)
    print_response_headers(response, file=file)
    print(file=file)
