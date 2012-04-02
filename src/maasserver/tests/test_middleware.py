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

from django.core.exceptions import (
    PermissionDenied,
    ValidationError,
    )
from django.test.client import RequestFactory
from maasserver.exceptions import (
    MAASAPIException,
    MAASAPINotFound,
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
        exception = MAASAPINotFound("Huh?")
        self.assertIsNone(middleware.process_exception(request, exception))

    def test_unknown_exception_generates_internal_server_error(self):
        # An unknown exception generates an internal server error with the
        # exception message.
        error_message = factory.getRandomString()
        response = self.process_exception(RuntimeError(error_message))
        self.assertEqual(
            (httplib.INTERNAL_SERVER_ERROR, error_message),
            (response.status_code, response.content))

    def test_reports_MAASAPIException_with_appropriate_api_error(self):
        class MyException(MAASAPIException):
            api_error = httplib.UNAUTHORIZED

        error_message = factory.getRandomString()
        exception = MyException(error_message)
        response = self.process_exception(exception)
        self.assertEqual(
            (httplib.UNAUTHORIZED, error_message),
            (response.status_code, response.content))

    def test_renders_MAASAPIException_as_unicode(self):
        class MyException(MAASAPIException):
            api_error = httplib.UNAUTHORIZED

        error_message = "Error %s" % unichr(233)
        response = self.process_exception(MyException(error_message))
        self.assertEqual(
            (httplib.UNAUTHORIZED, error_message),
            (response.status_code, response.content.decode('utf-8')))

    def test_reports_ValidationError_as_Bad_Request(self):
        error_message = factory.getRandomString()
        response = self.process_exception(ValidationError(error_message))
        self.assertEqual(
            (httplib.BAD_REQUEST, error_message),
            (response.status_code, response.content))

    def test_returns_ValidationError_message_dict_as_json(self):
        exception = ValidationError(factory.getRandomString())
        exception_dict = {'hostname': 'invalid'}
        setattr(exception, 'message_dict', exception_dict)
        response = self.process_exception(exception)
        self.assertEqual(exception_dict, json.loads(response.content))
        self.assertIn('application/json', response['Content-Type'])

    def test_reports_PermissionDenied_as_Forbidden(self):
        error_message = factory.getRandomString()
        response = self.process_exception(PermissionDenied(error_message))
        self.assertEqual(
            (httplib.FORBIDDEN, error_message),
            (response.status_code, response.content))


class APIErrorsMiddlewareTest(TestCase):

    def test_handles_error_on_API(self):
        middleware = APIErrorsMiddleware()
        non_api_request = fake_request("/api/1.0/hello")
        error_message = factory.getRandomString()
        exception = MAASAPINotFound(error_message)
        response = middleware.process_exception(non_api_request, exception)
        self.assertEqual(
            (httplib.NOT_FOUND, error_message),
            (response.status_code, response.content))

    def test_ignores_error_outside_API(self):
        middleware = APIErrorsMiddleware()
        non_api_request = fake_request("/middleware/api/hello")
        exception = MAASAPINotFound(factory.getRandomString())
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
