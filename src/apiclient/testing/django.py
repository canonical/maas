# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Convenience functions for testing against Django."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from io import BytesIO

from django.core.files.uploadhandler import MemoryFileUploadHandler
from django.http.multipartparser import MultiPartParser


def parse_headers_and_body_with_django(headers, body):
    """Parse `headers` and `body` with Django's :class:`MultiPartParser`.

    `MultiPartParser` is a curiously ugly and RFC non-compliant concoction.

    Amongst other things, it coerces all field names, field data, and
    filenames into Unicode strings using the "replace" error strategy, so be
    warned that your data may be silently mangled.

    It also, in 1.3.1 at least, does not recognise any transfer encodings at
    *all* because its header parsing code was broken.

    I'm also fairly sure that it'll fall over on headers than span more than
    one line.

    In short, it's a piece of code that inspires little confidence, yet we
    must work with it, hence we need to round-trip test multipart handling
    with it.
    """
    handler = MemoryFileUploadHandler()
    meta = {
        "HTTP_CONTENT_TYPE": headers["Content-Type"],
        "HTTP_CONTENT_LENGTH": headers["Content-Length"],
        }
    parser = MultiPartParser(
        META=meta, input_data=BytesIO(body),
        upload_handlers=[handler])
    return parser.parse()
