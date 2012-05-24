# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Encoding of MIME multipart data."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    'encode_multipart_data',
    ]

import mimetypes
import random
import string


def make_random_boundary(length=30):
    """Create a random string for use in MIME boundary lines."""
    return b''.join(random.choice(string.letters) for ii in range(length))


def get_content_type(filename):
    """Return the MIME content type for the file with the given name."""
    return mimetypes.guess_type(filename)[0] or b'application/octet-stream'


def encode_field(field_name, data, boundary):
    """MIME-encode a form field."""
    field_name = field_name.encode('ascii')
    return (
        b'--' + boundary,
        b'Content-Disposition: form-data; name="%s"' % field_name,
        b'',
        bytes(data),
        )


def encode_file(name, fileObj, boundary):
    """MIME-encode a file upload."""
    content_type = get_content_type(name)
    name = name.encode('ascii')
    return (
        b'--' + boundary,
        b'Content-Disposition: form-data; name="%s"; filename="%s"' %
            (name, name),
        b'Content-Type: %s' % content_type,
        b'',
        fileObj.read(),
        )


def encode_multipart_data(data, files):
    """Create a MIME multipart payload from L{data} and L{files}.

    @param data: A mapping of names (ASCII strings) to data (byte string).
    @param files: A mapping of names (ASCII strings) to file objects ready to
        be read.
    @return: A 2-tuple of C{(body, headers)}, where C{body} is a a byte string
        and C{headers} is a dict of headers to add to the enclosing request in
        which this payload will travel.
    """
    boundary = make_random_boundary()

    lines = []
    for name, content in data.items():
        lines.extend(encode_field(name, content, boundary))
    for name, file_obj in files.items():
        lines.extend(encode_file(name, file_obj, boundary))
    lines.extend((b'--%s--' % boundary, b''))
    body = b'\r\n'.join(lines)

    headers = {
        b'content-type': b'multipart/form-data; boundary=' + boundary,
        b'content-length': b'%s' % (len(body)),
        }

    return body, headers
