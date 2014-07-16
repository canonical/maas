# Copyright 2012-2014 Canonical Ltd.  This software is licensed under the
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
from maasserver.testing.testcase import MAASServerTestCase
from maastesting.utils import sample_binary_data
from testtools.matchers import (
    Contains,
    Not,
    )


class ExceptionMiddlewareTest(MAASServerTestCase):

    def make_base_path(self):
        """Return a path to handle exceptions for."""
        return "/%s" % factory.make_string()

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
        request = factory.make_fake_request(base_path)
        return middleware.process_exception(request, exception)

    def test_ignores_paths_outside_path_regex(self):
        middleware = self.make_middleware(self.make_base_path())
        request = factory.make_fake_request(self.make_base_path())
        exception = MAASAPINotFound("Huh?")
        self.assertIsNone(middleware.process_exception(request, exception))

    def test_unknown_exception_generates_internal_server_error(self):
        # An unknown exception generates an internal server error with the
        # exception message.
        error_message = factory.make_string()
        response = self.process_exception(RuntimeError(error_message))
        self.assertEqual(
            (httplib.INTERNAL_SERVER_ERROR, error_message),
            (response.status_code, response.content))

    def test_reports_MAASAPIException_with_appropriate_api_error(self):
        class MyException(MAASAPIException):
            api_error = httplib.UNAUTHORIZED

        error_message = factory.make_string()
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
        error_message = factory.make_string()
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
        error_message = factory.make_string()
        response = self.process_exception(PermissionDenied(error_message))
        self.assertEqual(
            (httplib.FORBIDDEN, error_message),
            (response.status_code, response.content))


class APIErrorsMiddlewareTest(MAASServerTestCase):

    def test_handles_error_on_API(self):
        middleware = APIErrorsMiddleware()
        non_api_request = factory.make_fake_request("/api/1.0/hello")
        error_message = factory.make_string()
        exception = MAASAPINotFound(error_message)
        response = middleware.process_exception(non_api_request, exception)
        self.assertEqual(
            (httplib.NOT_FOUND, error_message),
            (response.status_code, response.content))

    def test_ignores_error_outside_API(self):
        middleware = APIErrorsMiddleware()
        non_api_request = factory.make_fake_request("/middleware/api/hello")
        exception = MAASAPINotFound(factory.make_string())
        self.assertIsNone(
            middleware.process_exception(non_api_request, exception))


class ExceptionLoggerMiddlewareTest(MAASServerTestCase):

    def test_exception_logger_logs_error(self):
        logger = self.useFixture(FakeLogger('maasserver'))
        error_text = factory.make_string()
        ExceptionLoggerMiddleware().process_exception(
            factory.make_fake_request('/middleware/api/hello'),
            ValueError(error_text))
        self.assertThat(logger.output, Contains(error_text))


class DebuggingLoggerMiddlewareTest(MAASServerTestCase):

    def test_debugging_logger_does_not_log_request_if_info_level(self):
        logger = self.useFixture(FakeLogger('maasserver', logging.INFO))
        request = factory.make_fake_request("/api/1.0/nodes/")
        DebuggingLoggerMiddleware().process_request(request)
        self.assertThat(
            logger.output,
            Not(Contains(build_request_repr(request))))

    def test_debugging_logger_does_not_log_response_if_info_level(self):
        logger = self.useFixture(FakeLogger('maasserver', logging.INFO))
        request = factory.make_fake_request("/api/1.0/nodes/")
        response = HttpResponse(
            content="test content",
            status=httplib.OK,
            mimetype=b"text/plain; charset=utf-8")
        DebuggingLoggerMiddleware().process_response(request, response)
        self.assertThat(
            logger.output, Not(Contains(build_request_repr(request))))

    def test_debugging_logger_logs_request(self):
        logger = self.useFixture(FakeLogger('maasserver', logging.DEBUG))
        request = factory.make_fake_request("/api/1.0/nodes/")
        request.content = "test content"
        DebuggingLoggerMiddleware().process_request(request)
        self.assertThat(logger.output, Contains(build_request_repr(request)))

    def test_debugging_logger_logs_response(self):
        logger = self.useFixture(FakeLogger('maasserver', logging.DEBUG))
        request = factory.make_fake_request("foo")
        response = HttpResponse(
            content="test content",
            status=httplib.OK,
            mimetype=b"text/plain; charset=utf-8")
        DebuggingLoggerMiddleware().process_response(request, response)
        self.assertThat(
            logger.output, Contains(response.content))

    def test_debugging_logger_logs_binary_response(self):
        logger = self.useFixture(FakeLogger('maasserver', logging.DEBUG))
        request = factory.make_fake_request("foo")
        response = HttpResponse(
            content=sample_binary_data,
            status=httplib.OK,
            mimetype=b"application/octet-stream")
        DebuggingLoggerMiddleware().process_response(request, response)
        self.assertThat(
            logger.output,
            Contains("non-utf-8 (binary?) content"))


class ErrorsMiddlewareTest(MAASServerTestCase):

    def test_error_middleware_ignores_GET_requests(self):
        self.client_log_in()
        request = factory.make_fake_request(factory.make_string(), 'GET')
        exception = MAASException()
        error_middleware = ErrorsMiddleware()
        response = error_middleware.process_exception(request, exception)
        self.assertIsNone(response)

    def test_error_middleware_ignores_non_ExternalComponentException(self):
        self.client_log_in()
        request = factory.make_fake_request(factory.make_string(), 'GET')
        exception = ValueError()
        error_middleware = ErrorsMiddleware()
        response = error_middleware.process_exception(request, exception)
        self.assertIsNone(response)

    def test_error_middleware_handles_ExternalComponentException(self):
        self.client_log_in()
        url = factory.make_string()
        request = factory.make_fake_request(url, 'POST')
        error_message = factory.make_string()
        exception = ExternalComponentException(error_message)
        error_middleware = ErrorsMiddleware()
        response = error_middleware.process_exception(request, exception)
        # The response is a redirect.
        self.assertEqual(request.path, extract_redirect(response))
        # An error message has been published.
        self.assertEqual(
            [(constants.ERROR, error_message, '')], request._messages.messages)
