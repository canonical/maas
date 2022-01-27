# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Encoding of MIME multipart data."""

__all__ = ["encode_multipart_data"]

from collections.abc import Iterable, Mapping
from email.generator import Generator
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from io import IOBase, StringIO
from itertools import chain
import mimetypes


def get_content_type(*names):
    """Return the MIME content type for the file with the given name."""
    for name in names:
        if name is not None:
            mimetype, encoding = mimetypes.guess_type(name)
            if mimetype is not None:
                return mimetype
    else:
        return "application/octet-stream"


def make_bytes_payload(name, content):
    payload = MIMEApplication(content)
    payload.add_header("Content-Disposition", "form-data", name=name)
    return payload


def make_string_payload(name, content):
    payload = MIMEApplication(content.encode("utf-8"), charset="utf-8")
    payload.add_header("Content-Disposition", "form-data", name=name)
    payload.set_type("text/plain")
    return payload


def make_file_payload(name, content):
    payload = MIMEApplication(content.read())
    payload.add_header(
        "Content-Disposition", "form-data", name=name, filename=name
    )
    names = name, getattr(content, "name", None)
    payload.set_type(get_content_type(*names))
    return payload


def make_payloads(name, content):
    """Constructs payload(s) for the given `name` and `content`.

    If `content` is a byte string, this calls `make_bytes_payload` to
    construct the payload, which this then yields.

    If `content` is a unicode string, this calls `make_string_payload`.

    If `content` is file-like -- it inherits from `IOBase` or `file` --
    this calls `make_file_payload`.

    If `content` is iterable, this calls `make_payloads` for each item,
    with the same name, and then re-yields each payload generated.

    If `content` is callable, this calls it with no arguments, and then
    uses the result as a context manager. This can be useful if the
    callable returns an open file, for example, because the context
    protocol means it will be closed after use.

    This raises `AssertionError` if it encounters anything else.
    """
    if isinstance(content, bytes):
        yield make_bytes_payload(name, content)
    elif isinstance(content, str):
        yield make_string_payload(name, content)
    elif isinstance(content, IOBase):
        yield make_file_payload(name, content)
    elif callable(content):
        with content() as content:
            yield from make_payloads(name, content)
    elif isinstance(content, Iterable):
        for part in content:
            yield from make_payloads(name, part)
    else:
        raise AssertionError(f"{name!r} is unrecognised: {content!r}")


def build_multipart_message(data):
    message = MIMEMultipart("form-data")
    for name, content in data:
        for payload in make_payloads(name, content):
            message.attach(payload)
    return message


def encode_multipart_message(message):
    # The message must be multipart.
    assert message.is_multipart()
    # The body length cannot yet be known.
    assert "Content-Length" not in message
    # So line-endings can be fixed-up later on, component payloads must have
    # no Content-Length and their Content-Transfer-Encoding must be base64
    # (and not quoted-printable, which Django doesn't appear to understand).
    for part in message.get_payload():
        assert "Content-Length" not in part
        assert part["Content-Transfer-Encoding"] == "base64"
    # Flatten the message without headers.
    buf = StringIO()
    generator = Generator(buf, False)  # Don't mangle "^From".
    generator._write_headers = lambda self: None  # Ignore.
    generator.flatten(message)
    # Ensure the body has CRLF-delimited lines. See
    # http://bugs.python.org/issue1349106.
    body = "\r\n".join(buf.getvalue().splitlines())
    # Only now is it safe to set the content length.
    message.add_header("Content-Length", "%d" % len(body))
    return list(message.items()), body


def encode_multipart_data(data=(), files=()):
    """Create a MIME multipart payload from L{data} and L{files}.

    **Note** that this function is deprecated. Use `build_multipart_message`
    and `encode_multipart_message` instead.

    @param data: A mapping of names (ASCII strings) to data (byte string).
    @param files: A mapping of names (ASCII strings) to file objects ready to
        be read.
    @return: A 2-tuple of C{(body, headers)}, where C{body} is a a byte string
        and C{headers} is a dict of headers to add to the enclosing request in
        which this payload will travel.
    """
    if isinstance(data, Mapping):
        data = data.items()
    if isinstance(files, Mapping):
        files = files.items()
    message = build_multipart_message(chain(data, files))
    headers, body = encode_multipart_message(message)
    return body, dict(headers)
