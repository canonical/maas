# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Convenience functions for testing against Django."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from io import BytesIO
import os

from django.core.files.uploadhandler import MemoryFileUploadHandler
from django.http.multipartparser import MultiPartParser
from maasserver.utils import ignore_unused


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


def parse_headers_and_body_with_mimer(headers, body):
    """Use piston's Mimer functionality to handle the content.

    :return: The value of 'request.data' after using Piston's translate_mime on
        the input.
    """
    # JAM 2012-10-09 Importing emitters has a side effect of registering mime
    #   type handlers with utils.translate_mime. So we must import it, even
    #   though we don't use it.  However, piston loads Django's QuerySet code
    #   which fails if you don't have a settings.py available. Which we don't
    #   during 'test.pserv'. So we import this late.
    from piston import emitters
    ignore_unused(emitters)
    from piston.utils import translate_mime

    environ = {'wsgi.input': BytesIO(body)}
    for name, value in headers.items():
        environ[name.upper().replace('-', '_')] = value
    environ['REQUEST_METHOD'] = 'POST'
    environ['SCRIPT_NAME'] = ''
    environ['PATH_INFO'] = ''
    # Django 1.6 needs DJANGO_SETTINGS_MODULE to be defined
    # when importing WSGIRequest.
    os.environ['DJANGO_SETTINGS_MODULE'] = 'maas.development'
    from django.core.handlers.wsgi import WSGIRequest
    request = WSGIRequest(environ)
    translate_mime(request)
    return request.data
