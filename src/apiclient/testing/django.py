# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Convenience functions for testing against Django."""

from io import BytesIO

import django.conf
from django.core.files.uploadhandler import MemoryFileUploadHandler
from django.http import multipartparser
from fixtures import TestWithFixtures


class APIClientTestCase(TestWithFixtures):
    """
    Provide django and django-piston based content/header parsing methods.

    Since they use MultiPartParser and WSGIRequest from Django, they require
    configuring Django which we want to clear after tests are done.
    """

    def setUp(self):
        super().setUp()
        # Django 1.8 and 1.11 need to be configured before we can use
        # WSGIRequest and MultiPartParser.
        if not django.conf.settings.configured:
            django.conf.settings.configure(DEBUG=True)

    def tearDown(self):
        # Reset django settings after each test since configuring Django breaks
        # tests for maascli commands which attempt to really load Django.
        django.conf.settings = django.conf.LazySettings()
        super().tearDown()

    @classmethod
    def parse_headers_and_body_with_django(cls, headers, body):
        """Parse `headers` and `body` with Django's :class:`MultiPartParser`.

        `MultiPartParser` is a curiously ugly and RFC non-compliant concoction.

        Amongst other things, it coerces all field names, field data, and
        filenames into Unicode strings using the "replace" error strategy, so
        be warned that your data may be silently mangled.

        It also, in 1.3.1 at least, does not recognise any transfer encodings
        at *all* because its header parsing code was broken.

        I'm also fairly sure that it'll fall over on headers than span more
        than one line.

        In short, it's a piece of code that inspires little confidence, yet we
        must work with it, hence we need to round-trip test multipart handling
        with it.
        """
        handler = MemoryFileUploadHandler()
        meta = {
            "CONTENT_TYPE": headers["Content-Type"],
            "CONTENT_LENGTH": headers["Content-Length"],
            # To make things even more entertaining, 1.8 prefixed meta vars
            # with "HTTP_" and 1.11 does not.
            "HTTP_CONTENT_TYPE": headers["Content-Type"],
            "HTTP_CONTENT_LENGTH": headers["Content-Length"],
        }
        parser = multipartparser.MultiPartParser(
            META=meta,
            input_data=BytesIO(body.encode("ascii")),
            upload_handlers=[handler],
        )
        return parser.parse()

    @classmethod
    def parse_headers_and_body_with_mimer(cls, headers, body):
        """Use piston's Mimer functionality to handle the content.

        :return: The value of 'request.data' after using Piston's
            translate_mime on the input.
        """
        # JAM 2012-10-09 Importing emitters has a side effect of registering
        #   mime type handlers with utils.translate_mime.
        from piston3 import emitters

        emitters  # Imported for side-effects.
        from piston3.utils import translate_mime

        environ = {"wsgi.input": BytesIO(body.encode("utf8"))}
        for name, value in headers.items():
            environ[name.upper().replace("-", "_")] = value
        environ["REQUEST_METHOD"] = "POST"
        environ["SCRIPT_NAME"] = ""
        environ["PATH_INFO"] = ""
        from django.core.handlers.wsgi import WSGIRequest

        request = WSGIRequest(environ)
        translate_mime(request)
        return request.data
