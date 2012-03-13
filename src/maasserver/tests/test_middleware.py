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
import logging
from tempfile import NamedTemporaryFile

from django.core.exceptions import ValidationError
from django.test.client import RequestFactory
from maasserver.exceptions import (
    MaaSAPIException,
    MaaSAPINotFound,
    )
from maasserver.middleware import (
    APIErrorsMiddleware,
    ExceptionLoggerMiddleware,
    ExceptionMiddleware,
    )
from maasserver.testing.factory import factory
from maasserver.testing.testcase import TestCase


def fake_request(base_path):
    """Create a fake request.

    :param base_path: The base path to make the request to.
    """
    rf = RequestFactory()
    return rf.get('%s/hello/' % base_path)


class ExceptionMiddlewareTest(TestCase):

    def make_base_path(self):
        """Return a path to handle exceptions for."""
        return "/%s" % factory.getRandomString()

    def make_middleware(self, base_path):
        """Create an ExceptionMiddleware for base_path."""
        class TestingExceptionMiddleware(ExceptionMiddleware):
            path_regex = base_path

        return TestingExceptionMiddleware()

    def process_exception(self, exception):
        """Run a given exception through a fake ExceptionMiddleware.

        :param exception: The exception to simulate.
        :type exception: Exception
        :return: The response as returned by the ExceptionMiddleware.
        :rtype: HttpResponse or None.
        """
        base_path = self.make_base_path()
        middleware = self.make_middleware(base_path)
        request = fake_request(base_path)
        return middleware.process_exception(request, exception)

    def test_ignores_paths_outside_path_regex(self):
        middleware = self.make_middleware(self.make_base_path())
        request = fake_request(self.make_base_path())
        exception = MaaSAPINotFound("Huh?")
        self.assertIsNone(middleware.process_exception(request, exception))

    def test_ignores_unknown_exception(self):
        # An unknown exception is not processed by the middleware
        # (returns None).
        self.assertIsNone(
            self.process_exception(ValueError("Error occurred!")))

    def test_reports_MaaSAPIException_with_appropriate_api_error(self):
        class MyException(MaaSAPIException):
            api_error = httplib.UNAUTHORIZED

        exception = MyException("Error occurred!")
        response = self.process_exception(exception)
        self.assertEqual(
            (httplib.UNAUTHORIZED, "Error occurred!"),
            (response.status_code, response.content))

    def test_renders_MaaSAPIException_as_unicode(self):
        class MyException(MaaSAPIException):
            api_error = httplib.UNAUTHORIZED

        error_message = "Error %s" % unichr(233)
        response = self.process_exception(MyException(error_message))
        self.assertEqual(
            (httplib.UNAUTHORIZED, error_message),
            (response.status_code, response.content.decode('utf-8')))

    def test_reports_ValidationError_as_Bad_Request(self):
        response = self.process_exception(ValidationError("Validation Error"))
        self.assertEqual(
            (httplib.BAD_REQUEST, "Validation Error"),
            (response.status_code, response.content))

    def test_returns_ValidationError_message_dict_as_json(self):
        exception = ValidationError("Error")
        exception_dict = {'hostname': 'invalid'}
        setattr(exception, 'message_dict', exception_dict)
        response = self.process_exception(exception)
        self.assertEqual(exception_dict, json.loads(response.content))
        self.assertIn('application/json', response['Content-Type'])


class APIErrorsMiddlewareTest(TestCase):

    def test_handles_error_on_API(self):
        middleware = APIErrorsMiddleware()
        non_api_request = fake_request("/api/1.0/hello")
        exception = MaaSAPINotFound("Have you looked under the couch?")
        response = middleware.process_exception(non_api_request, exception)
        self.assertEqual(
            (httplib.NOT_FOUND, "Have you looked under the couch?"),
            (response.status_code, response.content))

    def test_ignores_error_outside_API(self):
        middleware = APIErrorsMiddleware()
        non_api_request = fake_request("/middleware/api/hello")
        exception = MaaSAPINotFound("Have you looked under the couch?")
        self.assertIsNone(
            middleware.process_exception(non_api_request, exception))


class ExceptionLoggerMiddlewareTest(TestCase):

    def set_up_logger(self, filename):
        logger = logging.getLogger('maas')
        handler = logging.handlers.RotatingFileHandler(filename)
        logger.addHandler(handler)
        self.addCleanup(logger.removeHandler, handler)

    def test_exception_logger_logs_error(self):
        error_text = factory.getRandomString()
        with NamedTemporaryFile() as logfile:
            self.set_up_logger(logfile.name)
            ExceptionLoggerMiddleware().process_exception(
                fake_request('/middleware/api/hello'),
                ValueError(error_text))
            self.assertIn(error_text, open(logfile.name).read())
