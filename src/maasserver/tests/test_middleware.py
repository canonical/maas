# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import http.client
import json
import logging
import random

from crochet import TimeoutError
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpResponse
from fixtures import FakeLogger

from maasserver import middleware as middleware_module
from maasserver.exceptions import MAASAPIException, MAASAPINotFound
from maasserver.middleware import (
    AccessMiddleware,
    APIRPCErrorsMiddleware,
    CSRFHelperMiddleware,
    DebuggingLoggerMiddleware,
    ExceptionMiddleware,
    ExternalAuthInfoMiddleware,
    is_public_path,
    RBACMiddleware,
    RPCErrorsMiddleware,
)
from maasserver.rbac import rbac
from maasserver.secrets import SecretManager
from maasserver.testing import extract_redirect
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import (
    make_deadlock_failure,
    make_serialization_failure,
)
from maastesting.utils import sample_binary_data
from provisioningserver.rpc.exceptions import NoConnectionsAvailable
from provisioningserver.utils.shell import ExternalProcessError


class TestIsPublicPath(MAASServerTestCase):
    def test_public_path(self):
        self.assertTrue(is_public_path("/MAAS/accounts/login/"))
        self.assertTrue(is_public_path("/MAAS/rpc/someurl"))

    def test_path_not_public(self):
        self.assertFalse(is_public_path("/"))
        self.assertFalse(is_public_path("/MAAS/"))


class TestAccessMiddleware(MAASServerTestCase):
    def process_request(self, request, response=None):
        def get_response(request):
            if response:
                return response
            else:
                return HttpResponse(status=200)

        middleware = AccessMiddleware(get_response)
        return middleware(request)

    def test_return_request_on_public_path(self):
        request = factory.make_fake_request("/MAAS/accounts/login/")
        self.assertEqual(
            http.client.OK, self.process_request(request).status_code
        )

    def test_return_redirect_index(self):
        request = factory.make_fake_request("/MAAS/")
        request.user = AnonymousUser()
        self.assertEqual(
            "/MAAS/", extract_redirect(self.process_request(request))
        )


class TestExceptionMiddleware(MAASServerTestCase):
    def make_base_path(self):
        """Return a path to handle exceptions for."""
        return "/%s" % factory.make_string()

    def make_fake_request(self):
        return factory.make_fake_request(self.make_base_path())

    def process_exception(self, request, exception):
        def get_response(request):
            raise exception

        middleware = ExceptionMiddleware(get_response)
        return middleware(request)

    def test_ignores_serialization_failures(self):
        request = self.make_fake_request()
        exception = make_serialization_failure()
        self.assertRaises(
            type(exception), self.process_exception, request, exception
        )

    def test_ignores_deadlock_failures(self):
        request = self.make_fake_request()
        exception = make_deadlock_failure()
        self.assertRaises(
            type(exception), self.process_exception, request, exception
        )

    def test_unknown_exception_generates_internal_server_error(self):
        # An unknown exception generates an internal server error with the
        # exception message.
        request = self.make_fake_request()
        error_message = factory.make_string()
        response = self.process_exception(request, RuntimeError(error_message))
        self.assertIsInstance(response.content, bytes)
        self.assertEqual(
            (http.client.INTERNAL_SERVER_ERROR, error_message),
            (
                response.status_code,
                response.content.decode(settings.DEFAULT_CHARSET),
            ),
        )

    def test_reports_MAASAPIException_with_appropriate_api_error(self):
        class MyException(MAASAPIException):
            api_error = int(http.client.UNAUTHORIZED)

        error_message = factory.make_string()
        exception = MyException(error_message)
        request = self.make_fake_request()
        response = self.process_exception(request, exception)
        self.assertIsInstance(response.content, bytes)
        self.assertEqual(
            (http.client.UNAUTHORIZED, error_message),
            (
                response.status_code,
                response.content.decode(settings.DEFAULT_CHARSET),
            ),
        )

    def test_renders_MAASAPIException_as_unicode(self):
        class MyException(MAASAPIException):
            api_error = int(http.client.UNAUTHORIZED)

        error_message = "Error %s" % chr(233)
        exception = MyException(error_message)
        request = self.make_fake_request()
        response = self.process_exception(request, exception)
        self.assertEqual(
            (http.client.UNAUTHORIZED, error_message),
            (
                response.status_code,
                response.content.decode(settings.DEFAULT_CHARSET),
            ),
        )

    def test_reports_ValidationError_as_Bad_Request(self):
        error_message = factory.make_string()
        exception = ValidationError(error_message)
        request = self.make_fake_request()
        response = self.process_exception(request, exception)
        self.assertIsInstance(response.content, bytes)
        self.assertEqual(
            (http.client.BAD_REQUEST, error_message),
            (
                response.status_code,
                response.content.decode(settings.DEFAULT_CHARSET),
            ),
        )

    def test_returns_ValidationError_message_dict_as_json(self):
        exception_dict = {"hostname": ["invalid"]}
        exception = ValidationError(exception_dict)
        request = self.make_fake_request()
        response = self.process_exception(request, exception)
        self.assertIsInstance(response.content, bytes)
        self.assertEqual(
            exception_dict,
            json.loads(response.content.decode(settings.DEFAULT_CHARSET)),
        )
        self.assertIn("application/json", response["Content-Type"])

    def test_reports_PermissionDenied_as_Forbidden(self):
        error_message = factory.make_string()
        exception = PermissionDenied(error_message)
        request = self.make_fake_request()
        response = self.process_exception(request, exception)
        self.assertIsInstance(response.content, bytes)
        self.assertEqual(
            (http.client.FORBIDDEN, error_message),
            (
                response.status_code,
                response.content.decode(settings.DEFAULT_CHARSET),
            ),
        )

    def test_api_500_error_is_logged(self):
        logger = self.useFixture(FakeLogger("maasserver"))
        error_text = factory.make_string()
        exception = MAASAPIException(error_text)
        request = self.make_fake_request()
        self.process_exception(request, exception)
        self.assertIn(error_text, logger.output)

    def test_generic_500_error_is_logged(self):
        logger = self.useFixture(FakeLogger("maasserver"))
        error_text = factory.make_string()
        exception = Exception(error_text)
        request = self.make_fake_request()
        self.process_exception(request, exception)
        self.assertIn(error_text, logger.output)

    def test_reports_ExternalProcessError_as_ServiceUnavailable(self):
        error_text = factory.make_string()
        exception = ExternalProcessError(1, ["cmd"], error_text)
        retry_after = random.randint(0, 10)
        self.patch(
            middleware_module, "RETRY_AFTER_SERVICE_UNAVAILABLE", retry_after
        )
        request = self.make_fake_request()
        response = self.process_exception(request, exception)
        self.assertEqual(response.status_code, http.client.SERVICE_UNAVAILABLE)
        self.assertEqual(
            response.content.decode(settings.DEFAULT_CHARSET),
            str(exception),
        )
        self.assertEqual(response["Retry-After"], str(retry_after))

    def test_handles_error_on_API(self):
        error_message = factory.make_string()
        exception = MAASAPINotFound(error_message)
        request = self.make_fake_request()
        response = self.process_exception(request, exception)
        self.assertIsInstance(response.content, bytes)
        self.assertEqual(
            (http.client.NOT_FOUND, error_message),
            (
                response.status_code,
                response.content.decode(settings.DEFAULT_CHARSET),
            ),
        )

    def test_503_response_includes_retry_after_header(self):
        error = ExternalProcessError(returncode=-1, cmd="foo-bar")
        request = self.make_fake_request()
        response = self.process_exception(request, error)
        self.assertEqual(
            (
                http.client.SERVICE_UNAVAILABLE,
                "%s" % middleware_module.RETRY_AFTER_SERVICE_UNAVAILABLE,
            ),
            (response.status_code, response["Retry-after"]),
        )


class TestDebuggingLoggerMiddleware(MAASServerTestCase):
    def process_request(self, request, response=None):
        def get_response(request):
            if response:
                return response
            else:
                return HttpResponse(status=200)

        middleware = DebuggingLoggerMiddleware(get_response)
        return middleware(request)

    def test_debugging_logger_does_not_log_response_if_info_level(self):
        logger = self.useFixture(FakeLogger("maasserver", logging.INFO))
        request = factory.make_fake_request("/MAAS/api/2.0/nodes/")
        response = HttpResponse(
            content="test content", content_type=b"text/plain; charset=utf-8"
        )
        self.process_request(request, response)
        debug_output = DebuggingLoggerMiddleware._build_request_repr(request)
        self.assertNotIn(debug_output, logger.output)

    def test_debugging_logger_does_not_log_response_if_no_debug_http(self):
        logger = self.useFixture(FakeLogger("maasserver", logging.DEBUG))
        request = factory.make_fake_request("/MAAS/api/2.0/nodes/")
        response = HttpResponse(
            content="test content", content_type=b"text/plain; charset=utf-8"
        )
        self.process_request(request, response)
        debug_output = DebuggingLoggerMiddleware._build_request_repr(request)
        self.assertNotIn(debug_output, logger.output)

    def test_debugging_logger_logs_request(self):
        self.patch(settings, "DEBUG_HTTP", True)
        logger = self.useFixture(FakeLogger("maasserver", logging.DEBUG))
        request = factory.make_fake_request("/MAAS/api/2.0/nodes/")
        request.content = "test content"
        self.process_request(request)
        debug_output = DebuggingLoggerMiddleware._build_request_repr(request)
        self.assertIn(debug_output, logger.output)

    def test_debugging_logger_logs_response(self):
        self.patch(settings, "DEBUG_HTTP", True)
        logger = self.useFixture(FakeLogger("maasserver", logging.DEBUG))
        request = factory.make_fake_request("foo")
        response = HttpResponse(
            content="test content", content_type=b"text/plain; charset=utf-8"
        )
        self.process_request(request, response)
        self.assertIn(
            response.content.decode(settings.DEFAULT_CHARSET),
            logger.output,
        )

    def test_debugging_logger_logs_binary_response(self):
        self.patch(settings, "DEBUG_HTTP", True)
        logger = self.useFixture(FakeLogger("maasserver", logging.DEBUG))
        request = factory.make_fake_request("foo")
        response = HttpResponse(
            content=sample_binary_data,
            content_type=b"application/octet-stream",
        )
        self.process_request(request, response)
        self.assertIn("non-utf-8 (binary?) content", logger.output)


class TestRPCErrorsMiddleware(MAASServerTestCase):
    def process_request(self, request, exception=None):
        def get_response(request):
            if exception:
                raise exception
            else:
                return None

        middleware = RPCErrorsMiddleware(get_response)
        return middleware(request)

    def test_handles_NoConnectionsAvailable(self):
        request = factory.make_fake_request(factory.make_string(), "POST")
        error_message = (
            "No connections available for cluster %s"
            % factory.make_name("cluster")
        )
        error = NoConnectionsAvailable(error_message)
        response = self.process_request(request, error)

        # The response is a redirect.
        self.assertEqual(request.path, extract_redirect(response))

    def test_handles_TimeoutError(self):
        request = factory.make_fake_request(factory.make_string(), "POST")
        error_message = "Here, have a picture of Queen Victoria!"
        error = TimeoutError(error_message)
        response = self.process_request(request, error)

        # The response is a redirect.
        self.assertEqual(request.path, extract_redirect(response))

    def test_ignores_non_rpc_errors(self):
        request = factory.make_fake_request(factory.make_string(), "POST")
        exception = ZeroDivisionError(
            "You may think it's a long walk down the street to the chemist "
            "but that's just peanuts to space!"
        )
        self.assertRaises(
            ZeroDivisionError, self.process_request, request, exception
        )

    def test_ignores_error_on_API(self):
        non_api_request = factory.make_fake_request("/MAAS/api/2.0/ohai")
        exception_class = NoConnectionsAvailable
        exception = exception_class(factory.make_string())
        self.assertRaises(
            exception_class, self.process_request, non_api_request, exception
        )

    def test_no_connections_available_has_usable_cluster_name_in_msg(self):
        # If a NoConnectionsAvailable exception carries a reference to
        # the cluster UUID, RPCErrorsMiddleware will look up the
        # cluster's name and make the error message it displays more
        # useful.
        request = factory.make_fake_request(factory.make_string(), "POST")
        rack_controller = factory.make_RackController()
        error = NoConnectionsAvailable(
            factory.make_name("msg"), uuid=rack_controller.system_id
        )
        self.process_request(request, error)


class TestAPIRPCErrorsMiddleware(MAASServerTestCase):
    def process_request(self, request, exception=None):
        def get_response(request):
            if exception:
                raise exception
            else:
                return None

        middleware = APIRPCErrorsMiddleware(get_response)
        return middleware(request)

    def test_handles_error_on_API(self):
        middleware = APIRPCErrorsMiddleware(lambda request: None)
        api_request = factory.make_fake_request("/MAAS/api/2.0/hello")
        error_message = factory.make_string()
        exception_class = NoConnectionsAvailable
        exception = exception_class(error_message)
        response = self.process_request(api_request, exception)
        self.assertEqual(
            (middleware.handled_exceptions[exception_class], error_message),
            (
                response.status_code,
                response.content.decode(settings.DEFAULT_CHARSET),
            ),
        )

    def test_ignores_error_outside_API(self):
        non_api_request = factory.make_fake_request(
            "/MAAS/middleware/api/hello"
        )
        exception_class = NoConnectionsAvailable
        exception = exception_class(factory.make_string())
        self.assertRaises(
            exception_class, self.process_request, non_api_request, exception
        )

    def test_no_connections_available_returned_as_503(self):
        request = factory.make_fake_request(
            "/MAAS/api/2.0/" + factory.make_string(), "POST"
        )
        error_message = (
            "Unable to connect to cluster '%s'; no connections available"
            % factory.make_name("cluster")
        )
        error = NoConnectionsAvailable(error_message)
        response = self.process_request(request, error)

        self.assertEqual(
            (http.client.SERVICE_UNAVAILABLE, error_message),
            (
                response.status_code,
                response.content.decode(settings.DEFAULT_CHARSET),
            ),
        )

    def test_503_response_includes_retry_after_header_by_default(self):
        request = factory.make_fake_request(
            "/MAAS/api/2.0/" + factory.make_string(), "POST"
        )
        error = NoConnectionsAvailable(factory.make_name())
        response = self.process_request(request, error)

        self.assertEqual(
            (
                http.client.SERVICE_UNAVAILABLE,
                "%s" % middleware_module.RETRY_AFTER_SERVICE_UNAVAILABLE,
            ),
            (response.status_code, response["Retry-after"]),
        )

    def test_handles_TimeoutError(self):
        request = factory.make_fake_request(
            "/MAAS/api/2.0/" + factory.make_string(), "POST"
        )
        error_message = "No thanks, I'm trying to give them up."
        error = TimeoutError(error_message)
        response = self.process_request(request, error)

        self.assertEqual(
            (http.client.GATEWAY_TIMEOUT, error_message),
            (
                response.status_code,
                response.content.decode(settings.DEFAULT_CHARSET),
            ),
        )

    def test_ignores_non_rpc_errors(self):
        request = factory.make_fake_request(
            "/MAAS/api/2.0/" + factory.make_string(), "POST"
        )
        exception = ZeroDivisionError(
            "You may think it's a long walk down the street to the chemist "
            "but that's just peanuts to space!"
        )
        self.assertRaises(
            ZeroDivisionError, self.process_request, request, exception
        )


class TestCSRFHelperMiddleware(MAASServerTestCase):
    def process_request(self, request):
        def get_response(request):
            return None

        middleware = CSRFHelperMiddleware(get_response)
        return middleware(request)

    def test_sets_csrf_exception_if_no_session_cookie(self):
        cookies = {}
        request = factory.make_fake_request(
            factory.make_string(), "GET", cookies=cookies
        )
        self.process_request(request)
        self.assertTrue(getattr(request, "csrf_processing_done", None))

    def test_doesnt_set_csrf_exception_if_session_cookie(self):
        cookies = {settings.SESSION_COOKIE_NAME: factory.make_name("session")}
        request = factory.make_fake_request(
            factory.make_string(), "GET", cookies=cookies
        )
        self.process_request(request)
        self.assertIsNone(getattr(request, "csrf_processing_done", None))


class TestExternalAuthInfoMiddleware(MAASServerTestCase):
    def process_request(self, request):
        def get_response(request):
            return None

        middleware = ExternalAuthInfoMiddleware(get_response)
        return middleware(request)

    def test_without_external_auth(self):
        request = factory.make_fake_request("/")
        self.process_request(request)
        self.assertIsNone(request.external_auth_info)

    def test_with_external_auth_candid(self):
        SecretManager().set_composite_secret(
            "external-auth",
            {
                "url": "https://example.com/",
                "domain": "ldap",
                "admin-group": "admins",
            },
        )
        request = factory.make_fake_request("/")
        self.process_request(request)
        self.assertEqual(request.external_auth_info.type, "candid")
        self.assertEqual(request.external_auth_info.url, "https://example.com")
        self.assertEqual(request.external_auth_info.domain, "ldap")
        self.assertEqual(request.external_auth_info.admin_group, "admins")

    def test_with_external_auth_rbac(self):
        SecretManager().set_composite_secret(
            "external-auth", {"rbac-url": "https://rbac.example.com/"}
        )
        request = factory.make_fake_request("/")
        self.process_request(request)
        self.assertEqual(request.external_auth_info.type, "rbac")
        self.assertEqual(
            request.external_auth_info.url, "https://rbac.example.com/auth"
        )
        self.assertEqual(request.external_auth_info.domain, "")
        self.assertEqual(request.external_auth_info.admin_group, "")

    def test_with_external_auth_rbac_ignore_candid_settings(self):
        SecretManager().set_composite_secret(
            "external-auth",
            {
                "url": "https://candid.example.com/",
                "domain": "example.com",
                "admin-group": "admins",
                "rbac-url": "https://rbac.example.com/",
            },
        )
        request = factory.make_fake_request("/")
        self.process_request(request)
        self.assertEqual(request.external_auth_info.type, "rbac")
        self.assertEqual(
            request.external_auth_info.url, "https://rbac.example.com/auth"
        )
        self.assertEqual(request.external_auth_info.domain, "")
        self.assertEqual(request.external_auth_info.admin_group, "")

    def test_with_external_auth_strip_trailing_slash(self):
        SecretManager().set_composite_secret(
            "external-auth", {"url": "https://example.com/"}
        )
        request = factory.make_fake_request("/")
        self.process_request(request)
        self.assertEqual(request.external_auth_info.type, "candid")
        self.assertEqual(request.external_auth_info.url, "https://example.com")


class TestRBACMiddleware(MAASServerTestCase):
    def process_request(self, request):
        def get_response(request):
            return None

        middleware = RBACMiddleware(get_response)
        return middleware(request)

    def test_calls_rbac_clear(self):
        mock_clear = self.patch(rbac, "clear")
        request = factory.make_fake_request(factory.make_string(), "GET")
        self.process_request(request)
        mock_clear.assert_called_once_with()
