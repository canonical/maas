# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test maasserver middleware classes."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

import httplib
import json
import logging

from django.contrib.messages import constants
from django.core.cache import cache
from django.core.exceptions import (
    PermissionDenied,
    ValidationError,
    )
from django.test.client import RequestFactory
from maasserver import (
    components,
    middleware as middleware_module,
    provisioning,
    )
from maasserver.exceptions import (
    ExternalComponentException,
    MAASAPIException,
    MAASAPINotFound,
    MAASException,
    )
from maasserver.middleware import (
    APIErrorsMiddleware,
    check_profiles_cached,
    clear_profiles_check_cache,
    ErrorsMiddleware,
    ExceptionLoggerMiddleware,
    ExceptionMiddleware,
    ExternalComponentsMiddleware,
    PROFILES_CHECK_DONE_KEY,
    )
from maasserver.testing import extract_redirect
from maasserver.testing.factory import factory
from maasserver.testing.testcase import (
    LoggedInTestCase,
    TestCase,
    )
from testtools.matchers import (
    Contains,
    FileContains,
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
        logfile = self.make_file(contents="")
        self.set_up_logger(logfile)
        ExceptionLoggerMiddleware().process_exception(
            fake_request('/middleware/api/hello'),
            ValueError(error_text))
        self.assertThat(logfile, FileContains(matcher=Contains(error_text)))


class ExternalComponentsMiddlewareTest(TestCase):

    def patch_papi_get_profiles_by_name(self, method):
        self.patch(components, '_PERSISTENT_ERRORS', {})
        papi = provisioning.get_provisioning_api_proxy()
        self.patch(papi.proxy, 'get_profiles_by_name', method)

    def test_middleware_calls_check_profiles_cached(self):
        calls = []
        self.patch(
            middleware_module, "check_profiles_cached",
            lambda: calls.append(1))
        middleware = ExternalComponentsMiddleware()
        response = middleware.process_request(None)
        self.assertIsNone(response)
        self.assertEqual(1, len(calls))

    def test_check_profiles_cached_sets_cache_key(self):
        def return_all_profiles(profiles):
            return profiles
        self.patch_papi_get_profiles_by_name(return_all_profiles)

        check_profiles_cached()
        self.assertTrue(cache.get(PROFILES_CHECK_DONE_KEY, False))

    def test_check_profiles_cached_sets_cache_key_if_exception_raised(self):
        # The cache key PROFILES_CHECK_DONE_KEY is set to True even if
        # the call to papi.get_profiles_by_name raises an exception.
        def raise_exception(profiles):
            raise Exception()
        self.patch_papi_get_profiles_by_name(raise_exception)
        try:
            check_profiles_cached()
        except Exception:
            pass
        self.assertTrue(cache.get(PROFILES_CHECK_DONE_KEY, False))

    def test_check_profiles_cached_does_nothing_if_cache_key_set(self):
        # If the cache key PROFILES_CHECK_DONE_KE is set to True
        # the call to check_profiles_cached is silent.
        def raise_exception(profiles):
            raise Exception()
        cache.set(PROFILES_CHECK_DONE_KEY, True)
        self.patch_papi_get_profiles_by_name(raise_exception)
        check_profiles_cached()
        # No exception, get_profiles_by_name has not been called.

    def test_clear_profiles_check_cache_deletes_PROFILES_CHECK_DONE_KEY(self):
        cache.set(PROFILES_CHECK_DONE_KEY, factory.getRandomString())
        self.assertTrue(cache.get(PROFILES_CHECK_DONE_KEY, False))
        clear_profiles_check_cache()
        self.assertFalse(cache.get(PROFILES_CHECK_DONE_KEY, False))

    def test_middleware_returns_none_if_exception_raised(self):
        def raise_exception(profiles):
            raise Exception()

        self.patch_papi_get_profiles_by_name(raise_exception)
        middleware = ExternalComponentsMiddleware()
        request = fake_request(factory.getRandomString())
        response = middleware.process_request(request)
        self.assertIsNone(response)

    def test_middleware_does_not_catch_keyboardinterrupt_exception(self):
        def raise_exception(profiles):
            raise KeyboardInterrupt()

        self.patch_papi_get_profiles_by_name(raise_exception)
        middleware = ExternalComponentsMiddleware()
        request = fake_request(factory.getRandomString())
        self.assertRaises(
            KeyboardInterrupt, middleware.process_request, request)


class ErrorsMiddlewareTest(LoggedInTestCase):

    def test_error_middleware_ignores_GET_requests(self):
        request = fake_request(factory.getRandomString(), 'GET')
        exception = MAASException()
        middleware = ErrorsMiddleware()
        response = middleware.process_exception(request, exception)
        self.assertIsNone(response)

    def test_error_middleware_ignores_non_ExternalComponentException(self):
        request = fake_request(factory.getRandomString(), 'GET')
        exception = ValueError()
        middleware = ErrorsMiddleware()
        response = middleware.process_exception(request, exception)
        self.assertIsNone(response)

    def test_error_middleware_handles_ExternalComponentException(self):
        url = factory.getRandomString()
        request = fake_request(url, 'POST')
        error_message = factory.getRandomString()
        exception = ExternalComponentException(error_message)
        middleware = ErrorsMiddleware()
        response = middleware.process_exception(request, exception)
        # The response is a redirect.
        self.assertEqual(url, extract_redirect(response))
        # An error message has been published.
        self.assertEqual(
            [(constants.ERROR, error_message, '')], request._messages.messages)
