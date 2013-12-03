# Copyright 2012, 2013 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test maasserver middleware classes."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import httplib
import json
import logging

from django.contrib.messages import constants
from django.core.exceptions import (
    PermissionDenied,
    ValidationError,
    )
from django.http import HttpResponse
from django.http.request import build_request_repr
from django.test.client import RequestFactory
from fixtures import FakeLogger
from maasserver.exceptions import (
    ExternalComponentException,
    MAASAPIException,
    MAASAPINotFound,
    MAASException,
    )
from maasserver.middleware import (
    APIErrorsMiddleware,
    DebuggingLoggerMiddleware,
    ErrorsMiddleware,
    ExceptionLoggerMiddleware,
    ExceptionMiddleware,
    )
from maasserver.testing import extract_redirect
from maasserver.testing.factory import factory
from maasserver.testing.testcase import (
    LoggedInTestCase,
    MAASServerTestCase,
    )
from maastesting.utils import sample_binary_data
from testtools.matchers import (
    Contains,
    Not,
    )


class Messages:
    """A class to record messages published by Django messaging
    framework.
    """

    messages = []

    def add(self, level, message, extras):
        self.messages.append((level, message, extras))


def fake_request(path, method='GET'):
    """Create a fake request.

    :param path: The path to make the request to.
    :param method: The method to use for the reques
        ('GET' or 'POST').
    """
    rf = RequestFactory()
    request = rf.get(path)
    request.method = method
    request._messages = Messages()
    return request


class ExceptionMiddlewareTest(MAASServerTestCase):

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
        exception_dict = {'hostname': ['invalid']}
        exception = ValidationError(exception_dict)
        response = self.process_exception(exception)
        self.assertEqual(exception_dict, json.loads(response.content))
        self.assertIn('application/json', response['Content-Type'])

    def test_reports_PermissionDenied_as_Forbidden(self):
        error_message = factory.getRandomString()
        response = self.process_exception(PermissionDenied(error_message))
        self.assertEqual(
            (httplib.FORBIDDEN, error_message),
            (response.status_code, response.content))


class APIErrorsMiddlewareTest(MAASServerTestCase):

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


class ExceptionLoggerMiddlewareTest(MAASServerTestCase):

    def test_exception_logger_logs_error(self):
        logger = self.useFixture(FakeLogger('maasserver'))
        error_text = factory.getRandomString()
        ExceptionLoggerMiddleware().process_exception(
            fake_request('/middleware/api/hello'),
            ValueError(error_text))
        self.assertThat(logger.output, Contains(error_text))


class DebuggingLoggerMiddlewareTest(MAASServerTestCase):

    def test_debugging_logger_does_not_log_request_if_info_level(self):
        logger = self.useFixture(FakeLogger('maasserver', logging.INFO))
        request = fake_request("/api/1.0/nodes/")
        DebuggingLoggerMiddleware().process_request(request)
        self.assertThat(
            logger.output,
            Not(Contains(build_request_repr(request))))

    def test_debugging_logger_does_not_log_response_if_info_level(self):
        logger = self.useFixture(FakeLogger('maasserver', logging.INFO))
        request = fake_request("/api/1.0/nodes/")
        response = HttpResponse(
            content="test content",
            status=httplib.OK,
            mimetype=b"text/plain; charset=utf-8")
        DebuggingLoggerMiddleware().process_response(request, response)
        self.assertThat(
            logger.output, Not(Contains(build_request_repr(request))))

    def test_debugging_logger_logs_request(self):
        logger = self.useFixture(FakeLogger('maasserver', logging.DEBUG))
        request = fake_request("/api/1.0/nodes/")
        request.content = "test content"
        DebuggingLoggerMiddleware().process_request(request)
        self.assertThat(logger.output, Contains(build_request_repr(request)))

    def test_debugging_logger_logs_response(self):
        logger = self.useFixture(FakeLogger('maasserver', logging.DEBUG))
        request = fake_request("foo")
        response = HttpResponse(
            content="test content",
            status=httplib.OK,
            mimetype=b"text/plain; charset=utf-8")
        DebuggingLoggerMiddleware().process_response(request, response)
        self.assertThat(
            logger.output, Contains(response.content))

    def test_debugging_logger_logs_binary_response(self):
        logger = self.useFixture(FakeLogger('maasserver', logging.DEBUG))
        request = fake_request("foo")
        response = HttpResponse(
            content=sample_binary_data,
            status=httplib.OK,
            mimetype=b"application/octet-stream")
        DebuggingLoggerMiddleware().process_response(request, response)
        self.assertThat(
            logger.output,
            Contains("non-utf-8 (binary?) content"))


class ErrorsMiddlewareTest(LoggedInTestCase):

    def test_error_middleware_ignores_GET_requests(self):
        request = fake_request(factory.getRandomString(), 'GET')
        exception = MAASException()
        error_middleware = ErrorsMiddleware()
        response = error_middleware.process_exception(request, exception)
        self.assertIsNone(response)

    def test_error_middleware_ignores_non_ExternalComponentException(self):
        request = fake_request(factory.getRandomString(), 'GET')
        exception = ValueError()
        error_middleware = ErrorsMiddleware()
        response = error_middleware.process_exception(request, exception)
        self.assertIsNone(response)

    def test_error_middleware_handles_ExternalComponentException(self):
        url = factory.getRandomString()
        request = fake_request(url, 'POST')
        error_message = factory.getRandomString()
        exception = ExternalComponentException(error_message)
        error_middleware = ErrorsMiddleware()
        response = error_middleware.process_exception(request, exception)
        # The response is a redirect.
        self.assertEqual(request.path, extract_redirect(response))
        # An error message has been published.
        self.assertEqual(
            [(constants.ERROR, error_message, '')], request._messages.messages)
