# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test maasserver middleware classes."""

__all__ = []

import http.client
import json
import logging
import random

from crochet import TimeoutError
from django.conf import settings
from django.contrib.messages import constants
from django.core.exceptions import (
    PermissionDenied,
    ValidationError,
)
from django.core.urlresolvers import reverse
from django.http import HttpResponse
from django.http.request import build_request_repr
from fixtures import FakeLogger
from maasserver import middleware as middleware_module
from maasserver.components import (
    get_persistent_error,
    register_persistent_error,
)
from maasserver.enum import (
    COMPONENT,
    NODEGROUP_STATUS,
)
from maasserver.exceptions import (
    MAASAPIException,
    MAASAPINotFound,
)
from maasserver.middleware import (
    APIErrorsMiddleware,
    APIRPCErrorsMiddleware,
    DebuggingLoggerMiddleware,
    ExceptionMiddleware,
    ExternalComponentsMiddleware,
    RPCErrorsMiddleware,
)
from maasserver.models import nodegroup as nodegroup_module
from maasserver.testing import extract_redirect
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import make_serialization_failure
from maastesting.matchers import (
    MockCalledOnceWith,
    MockNotCalled,
)
from maastesting.utils import sample_binary_data
from mock import Mock
from provisioningserver.rpc.exceptions import (
    NoConnectionsAvailable,
    PowerActionAlreadyInProgress,
)
from provisioningserver.utils.shell import ExternalProcessError
from testtools.matchers import (
    Contains,
    Equals,
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

    def test_ignores_serialization_failures(self):
        base_path = self.make_base_path()
        middleware = self.make_middleware(base_path)
        request = factory.make_fake_request(base_path)
        exception = make_serialization_failure()
        self.assertIsNone(middleware.process_exception(request, exception))

    def test_unknown_exception_generates_internal_server_error(self):
        # An unknown exception generates an internal server error with the
        # exception message.
        error_message = factory.make_string()
        response = self.process_exception(RuntimeError(error_message))
        self.assertIsInstance(response.content, bytes)
        self.assertEqual(
            (http.client.INTERNAL_SERVER_ERROR, error_message),
            (response.status_code,
             response.content.decode(settings.DEFAULT_CHARSET)))

    def test_reports_MAASAPIException_with_appropriate_api_error(self):
        class MyException(MAASAPIException):
            api_error = http.client.UNAUTHORIZED

        error_message = factory.make_string()
        exception = MyException(error_message)
        response = self.process_exception(exception)
        self.assertIsInstance(response.content, bytes)
        self.assertEqual(
            (http.client.UNAUTHORIZED, error_message),
            (response.status_code,
             response.content.decode(settings.DEFAULT_CHARSET)))

    def test_renders_MAASAPIException_as_unicode(self):
        class MyException(MAASAPIException):
            api_error = http.client.UNAUTHORIZED

        error_message = "Error %s" % chr(233)
        response = self.process_exception(MyException(error_message))
        self.assertEqual(
            (http.client.UNAUTHORIZED, error_message),
            (response.status_code,
             response.content.decode(settings.DEFAULT_CHARSET)))

    def test_reports_ValidationError_as_Bad_Request(self):
        error_message = factory.make_string()
        response = self.process_exception(ValidationError(error_message))
        self.assertIsInstance(response.content, bytes)
        self.assertEqual(
            (http.client.BAD_REQUEST, error_message),
            (response.status_code,
             response.content.decode(settings.DEFAULT_CHARSET)))

    def test_returns_ValidationError_message_dict_as_json(self):
        exception_dict = {'hostname': ['invalid']}
        exception = ValidationError(exception_dict)
        response = self.process_exception(exception)
        self.assertIsInstance(response.content, bytes)
        self.assertEqual(exception_dict, json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)))
        self.assertIn('application/json', response['Content-Type'])

    def test_reports_PermissionDenied_as_Forbidden(self):
        error_message = factory.make_string()
        response = self.process_exception(PermissionDenied(error_message))
        self.assertIsInstance(response.content, bytes)
        self.assertEqual(
            (http.client.FORBIDDEN, error_message),
            (response.status_code,
             response.content.decode(settings.DEFAULT_CHARSET)))

    def test_api_500_error_is_logged(self):
        logger = self.useFixture(FakeLogger('maasserver'))
        error_text = factory.make_string()
        self.process_exception(MAASAPIException(error_text))
        self.assertThat(logger.output, Contains(error_text))

    def test_generic_500_error_is_logged(self):
        logger = self.useFixture(FakeLogger('maasserver'))
        error_text = factory.make_string()
        self.process_exception(Exception(error_text))
        self.assertThat(logger.output, Contains(error_text))

    def test_reports_ExternalProcessError_as_ServiceUnavailable(self):
        error_text = factory.make_string()
        exception = ExternalProcessError(1, ["cmd"], error_text)
        retry_after = random.randint(0, 10)
        self.patch(
            middleware_module, 'RETRY_AFTER_SERVICE_UNAVAILABLE', retry_after)
        response = self.process_exception(exception)
        self.expectThat(
            response.status_code, Equals(http.client.SERVICE_UNAVAILABLE))
        self.expectThat(
            response.content.decode(settings.DEFAULT_CHARSET),
            Equals(str(exception)))
        self.expectThat(response['Retry-After'], Equals("%s" % retry_after))


class APIErrorsMiddlewareTest(MAASServerTestCase):

    def test_handles_error_on_API(self):
        middleware = APIErrorsMiddleware()
        api_request = factory.make_fake_request("/api/1.0/hello")
        error_message = factory.make_string()
        exception = MAASAPINotFound(error_message)
        response = middleware.process_exception(api_request, exception)
        self.assertIsInstance(response.content, bytes)
        self.assertEqual(
            (http.client.NOT_FOUND, error_message),
            (response.status_code,
             response.content.decode(settings.DEFAULT_CHARSET)))

    def test_ignores_error_outside_API(self):
        middleware = APIErrorsMiddleware()
        non_api_request = factory.make_fake_request("/middleware/api/hello")
        exception = MAASAPINotFound(factory.make_string())
        self.assertIsNone(
            middleware.process_exception(non_api_request, exception))

    def test_503_response_includes_retry_after_header(self):
        middleware = APIErrorsMiddleware()
        request = factory.make_fake_request(
            "/api/1.0/" + factory.make_string(), 'POST')
        error = ExternalProcessError(returncode=-1, cmd="foo-bar")
        response = middleware.process_exception(request, error)

        self.assertEqual(
            (
                http.client.SERVICE_UNAVAILABLE,
                '%s' % middleware_module.RETRY_AFTER_SERVICE_UNAVAILABLE,
            ),
            (response.status_code, response['Retry-after']))


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
            status=http.client.OK,
            content_type=b"text/plain; charset=utf-8")
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
            status=http.client.OK,
            content_type=b"text/plain; charset=utf-8")
        DebuggingLoggerMiddleware().process_response(request, response)
        self.assertThat(
            logger.output,
            Contains(response.content.decode(settings.DEFAULT_CHARSET)))

    def test_debugging_logger_logs_binary_response(self):
        logger = self.useFixture(FakeLogger('maasserver', logging.DEBUG))
        request = factory.make_fake_request("foo")
        response = HttpResponse(
            content=sample_binary_data,
            status=http.client.OK,
            content_type=b"application/octet-stream")
        DebuggingLoggerMiddleware().process_response(request, response)
        self.assertThat(
            logger.output,
            Contains("non-utf-8 (binary?) content"))


class RPCErrorsMiddlewareTest(MAASServerTestCase):

    def test_handles_PowerActionAlreadyInProgress(self):
        middleware = RPCErrorsMiddleware()
        request = factory.make_fake_request(factory.make_string(), 'POST')
        error_message = (
            "Unable to execute power action: another action is "
            "already in progress for node %s" % factory.make_name('node'))
        error = PowerActionAlreadyInProgress(error_message)
        response = middleware.process_exception(request, error)

        # The response is a redirect.
        self.assertEqual(request.path, extract_redirect(response))
        # An error message has been published.
        self.assertEqual(
            [(constants.ERROR, "Error: %s" % error_message, '')],
            request._messages.messages)

    def test_handles_NoConnectionsAvailable(self):
        middleware = RPCErrorsMiddleware()
        request = factory.make_fake_request(factory.make_string(), 'POST')
        error_message = (
            "No connections available for cluster %s" %
            factory.make_name('cluster'))
        error = NoConnectionsAvailable(error_message)
        response = middleware.process_exception(request, error)

        # The response is a redirect.
        self.assertEqual(request.path, extract_redirect(response))
        # An error message has been published.
        self.assertEqual(
            [(constants.ERROR, "Error: " + error_message, '')],
            request._messages.messages)

    def test_handles_TimeoutError(self):
        middleware = RPCErrorsMiddleware()
        request = factory.make_fake_request(factory.make_string(), 'POST')
        error_message = "Here, have a picture of Queen Victoria!"
        error = TimeoutError(error_message)
        response = middleware.process_exception(request, error)

        # The response is a redirect.
        self.assertEqual(request.path, extract_redirect(response))
        # An error message has been published.
        self.assertEqual(
            [(constants.ERROR, "Error: " + error_message, '')],
            request._messages.messages)

    def test_ignores_non_rpc_errors(self):
        middleware = RPCErrorsMiddleware()
        request = factory.make_fake_request(factory.make_string(), 'POST')
        exception = ZeroDivisionError(
            "You may think it's a long walk down the street to the chemist "
            "but that's just peanuts to space!")
        response = middleware.process_exception(request, exception)
        self.assertIsNone(response)

    def test_ignores_error_on_API(self):
        middleware = RPCErrorsMiddleware()
        non_api_request = factory.make_fake_request("/api/1.0/ohai")
        exception_class = random.choice(
            (NoConnectionsAvailable, PowerActionAlreadyInProgress))
        exception = exception_class(factory.make_string())
        self.assertIsNone(
            middleware.process_exception(non_api_request, exception))

    def test_no_connections_available_has_usable_cluster_name_in_msg(self):
        # If a NoConnectionsAvailable exception carries a reference to
        # the cluster UUID, RPCErrorsMiddleware will look up the
        # cluster's name and make the error message it displays more
        # useful.
        middleware = RPCErrorsMiddleware()
        request = factory.make_fake_request(factory.make_string(), 'POST')
        cluster = factory.make_NodeGroup()
        error = NoConnectionsAvailable(
            factory.make_name('msg'), uuid=cluster.uuid)
        middleware.process_exception(request, error)

        expected_error_message = (
            "Error: Unable to connect to cluster '%s' (%s); no connections "
            "available." % (cluster.cluster_name, cluster.uuid))
        self.assertEqual(
            [(constants.ERROR, expected_error_message, '')],
            request._messages.messages)


class APIRPCErrorsMiddlewareTest(MAASServerTestCase):

    def test_handles_error_on_API(self):
        middleware = APIRPCErrorsMiddleware()
        api_request = factory.make_fake_request("/api/1.0/hello")
        error_message = factory.make_string()
        exception_class = random.choice(
            (NoConnectionsAvailable, PowerActionAlreadyInProgress))
        exception = exception_class(error_message)
        response = middleware.process_exception(api_request, exception)
        self.assertEqual(
            (middleware.handled_exceptions[exception_class], error_message),
            (response.status_code,
             response.content.decode(settings.DEFAULT_CHARSET)))

    def test_ignores_error_outside_API(self):
        middleware = APIRPCErrorsMiddleware()
        non_api_request = factory.make_fake_request("/middleware/api/hello")
        exception_class = random.choice(
            (NoConnectionsAvailable, PowerActionAlreadyInProgress))
        exception = exception_class(factory.make_string())
        self.assertIsNone(
            middleware.process_exception(non_api_request, exception))

    def test_no_connections_available_returned_as_503(self):
        middleware = APIRPCErrorsMiddleware()
        request = factory.make_fake_request(
            "/api/1.0/" + factory.make_string(), 'POST')
        error_message = (
            "Unable to connect to cluster '%s'; no connections available" %
            factory.make_name('cluster'))
        error = NoConnectionsAvailable(error_message)
        response = middleware.process_exception(request, error)

        self.assertEqual(
            (http.client.SERVICE_UNAVAILABLE, error_message),
            (response.status_code,
             response.content.decode(settings.DEFAULT_CHARSET)))

    def test_503_response_includes_retry_after_header_by_default(self):
        middleware = APIRPCErrorsMiddleware()
        request = factory.make_fake_request(
            "/api/1.0/" + factory.make_string(), 'POST')
        error = NoConnectionsAvailable(factory.make_name())
        response = middleware.process_exception(request, error)

        self.assertEqual(
            (
                http.client.SERVICE_UNAVAILABLE,
                '%s' % middleware_module.RETRY_AFTER_SERVICE_UNAVAILABLE,
            ),
            (response.status_code, response['Retry-after']))

    def test_power_action_already_in_progress_returned_as_503(self):
        middleware = APIRPCErrorsMiddleware()
        request = factory.make_fake_request(
            "/api/1.0/" + factory.make_string(), 'POST')
        error_message = (
            "Unable to execute power action: another action is already in "
            "progress for node %s" % factory.make_name('node'))
        error = PowerActionAlreadyInProgress(error_message)
        response = middleware.process_exception(request, error)

        self.assertEqual(
            (http.client.SERVICE_UNAVAILABLE, error_message),
            (response.status_code,
             response.content.decode(settings.DEFAULT_CHARSET)))

    def test_handles_TimeoutError(self):
        middleware = APIRPCErrorsMiddleware()
        request = factory.make_fake_request(
            "/api/1.0/" + factory.make_string(), 'POST')
        error_message = "No thanks, I'm trying to give them up."
        error = TimeoutError(error_message)
        response = middleware.process_exception(request, error)

        self.assertEqual(
            (http.client.GATEWAY_TIMEOUT, error_message),
            (response.status_code,
             response.content.decode(settings.DEFAULT_CHARSET)))

    def test_ignores_non_rpc_errors(self):
        middleware = APIRPCErrorsMiddleware()
        request = factory.make_fake_request(
            "/api/1.0/" + factory.make_string(), 'POST')
        exception = ZeroDivisionError(
            "You may think it's a long walk down the street to the chemist "
            "but that's just peanuts to space!")
        response = middleware.process_exception(request, exception)
        self.assertIsNone(response)


class ExternalComponentsMiddlewareTest(MAASServerTestCase):
    """Tests for the ExternalComponentsMiddleware."""

    def test__checks_connectivity_of_accepted_clusters(self):
        getAllClients = self.patch(middleware_module, 'getAllClients')

        request = factory.make_fake_request(factory.make_string(), 'GET')
        middleware = ExternalComponentsMiddleware()
        middleware.process_request(request)

        self.assertThat(getAllClients, MockCalledOnceWith())

    def test__ignores_non_accepted_clusters(self):
        factory.make_NodeGroup(status=factory.pick_enum(
            NODEGROUP_STATUS, but_not=[NODEGROUP_STATUS.ENABLED]))

        getAllClients = self.patch(nodegroup_module, 'getAllClients')

        request = factory.make_fake_request(factory.make_string(), 'GET')
        middleware = ExternalComponentsMiddleware()
        middleware.process_request(request)

        self.assertThat(getAllClients, MockNotCalled())

    def test__registers_error_if_all_clusters_are_disconnected(self):
        factory.make_NodeGroup(status=NODEGROUP_STATUS.ENABLED)

        getAllClients = self.patch(nodegroup_module, 'getAllClients')
        getAllClients.return_value = []

        request = factory.make_fake_request(factory.make_string(), 'GET')
        middleware = ExternalComponentsMiddleware()
        middleware.process_request(request)

        error = get_persistent_error(COMPONENT.CLUSTERS)
        self.assertEqual(
            "One cluster is not yet connected to the region. Visit the "
            "<a href=\"%s\">clusters page</a> for more information." %
            reverse('cluster-list'),
            error)

    def test__registers_error_if_any_clusters_are_disconnected(self):
        clusters = [
            factory.make_NodeGroup(status=NODEGROUP_STATUS.ENABLED),
            factory.make_NodeGroup(status=NODEGROUP_STATUS.ENABLED),
            factory.make_NodeGroup(status=NODEGROUP_STATUS.ENABLED),
        ]

        getAllClients = self.patch(middleware_module, 'getAllClients')
        getAllClients.return_value = [Mock(ident=clusters[0].uuid)]

        request = factory.make_fake_request(factory.make_string(), 'GET')
        middleware = ExternalComponentsMiddleware()
        middleware.process_request(request)

        error = get_persistent_error(COMPONENT.CLUSTERS)
        self.assertEqual(
            "2 clusters are not yet connected to the region. Visit the "
            "<a href=\"%s\">clusters page</a> for more information." %
            reverse('cluster-list'),
            error)

    def test__removes_error_once_all_clusters_are_connected(self):
        clusters = [
            factory.make_NodeGroup(status=NODEGROUP_STATUS.ENABLED),
            factory.make_NodeGroup(status=NODEGROUP_STATUS.ENABLED),
        ]

        getAllClients = self.patch(middleware_module, 'getAllClients')
        getAllClients.return_value = [
            Mock(ident=cluster.uuid) for cluster in clusters
        ]

        register_persistent_error(
            COMPONENT.CLUSTERS, "Who flung that batter pudding?")

        request = factory.make_fake_request(factory.make_string(), 'GET')
        middleware = ExternalComponentsMiddleware()
        middleware.process_request(request)

        error = get_persistent_error(COMPONENT.CLUSTERS)
        self.assertIsNone(error)

    def test__does_not_suppress_exceptions_from_connectivity_checks(self):
        middleware = ExternalComponentsMiddleware()
        error_type = factory.make_exception_type()
        check_cluster_connectivity = self.patch(
            middleware, "_check_cluster_connectivity")
        check_cluster_connectivity.side_effect = error_type
        self.assertRaises(error_type, middleware.process_request, None)
        self.assertThat(check_cluster_connectivity, MockCalledOnceWith())
