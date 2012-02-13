# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test maasserver middleware classes."""

from __future__ import (
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

import httplib
import json

from django.core.exceptions import ValidationError
from django.test.client import RequestFactory
from maasserver.exceptions import MaasAPIException
from maasserver.middleware import APIErrorsMiddleware
from maasserver.testing import TestCase


class APIErrorsMiddlewareTest(TestCase):

    def get_fake_api_request(self):
        rf = RequestFactory()
        return rf.get('/api/hello/')

    def test_process_UnknownException(self):
        # An unknown exception is not processed by the middleware
        # (returns None).
        middleware = APIErrorsMiddleware()
        exception = ValueError("Error occurred!")
        fake_request = self.get_fake_api_request()
        response = middleware.process_exception(fake_request, exception)
        self.assertIsNone(response)

    def test_process_MaasAPIException(self):
        middleware = APIErrorsMiddleware()

        class MyException(MaasAPIException):
            api_error = httplib.UNAUTHORIZED
        exception = MyException("Error occurred!")
        fake_request = self.get_fake_api_request()
        response = middleware.process_exception(fake_request, exception)
        self.assertEqual(httplib.UNAUTHORIZED, response.status_code)
        self.assertEqual("Error occurred!", response.content)

    def test_process_MaasAPIException_unicode(self):
        middleware = APIErrorsMiddleware()

        class MyException(MaasAPIException):
            api_error = httplib.UNAUTHORIZED
        exception = MyException("Error %s" % unichr(233))
        fake_request = self.get_fake_api_request()
        response = middleware.process_exception(fake_request, exception)
        self.assertEqual(httplib.UNAUTHORIZED, response.status_code)
        self.assertEqual(
            "Error %s" % unichr(233),
            response.content.decode('utf8'))

    def test_process_ValidationError_message_dict(self):
        middleware = APIErrorsMiddleware()
        exception = ValidationError("Error")
        setattr(exception, 'message_dict', {'hostname': 'invalid'})
        fake_request = self.get_fake_api_request()
        response = middleware.process_exception(fake_request, exception)
        self.assertEqual(httplib.BAD_REQUEST, response.status_code)
        self.assertEqual(
            {'hostname': 'invalid'},
            json.loads(response.content))

    def test_process_ValidationError(self):
        middleware = APIErrorsMiddleware()
        exception = ValidationError("Validation Error")
        fake_request = self.get_fake_api_request()
        response = middleware.process_exception(fake_request, exception)
        self.assertEqual(httplib.BAD_REQUEST, response.status_code)
        self.assertEqual("Validation Error", response.content)
