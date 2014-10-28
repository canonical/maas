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
import random

from crochet import TimeoutError
from django.contrib.messages import constants
from django.core.exceptions import (
    PermissionDenied,
    ValidationError,
    )
from django.core.urlresolvers import reverse
from django.http import HttpResponse
from django.http.request import build_request_repr
from fixtures import FakeLogger
from maasserver.clusterrpc.utils import get_error_message_for_exception
from maasserver.components import (
    get_persistent_error,
    register_persistent_error,
    )
from maasserver.enum import (
    COMPONENT,
    NODEGROUP_STATUS,
    )
from maasserver.exceptions import (
    ExternalComponentException,
    MAASAPIException,
    MAASAPINotFound,
    MAASException,
    )
from maasserver.middleware import (
    APIErrorsMiddleware,
    APIRPCErrorsMiddleware,
    DebuggingLoggerMiddleware,
    ErrorsMiddleware,
    ExceptionMiddleware,
    ExternalComponentsMiddleware,
    RPCErrorsMiddleware,
    )
from maasserver.models import nodegroup as nodegroup_module
from maasserver.testing import extract_redirect
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maastesting.matchers import (
    MockCalledOnceWith,
    MockNotCalled,
    )
from maastesting.utils import sample_binary_data
from provisioningserver.rpc.exceptions import (
    MultipleFailures,
    NoConnectionsAvailable,
    PowerActionAlreadyInProgress,
    )
from provisioningserver.utils.text import normalise_whitespace
from testtools.matchers import (
    Contains,
    Not,
    )
from twisted.python.failure import Failure


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


class APIErrorsMiddlewareTest(MAASServerTestCase):

    def test_handles_error_on_API(self):
        middleware = APIErrorsMiddleware()
        api_request = factory.make_fake_request("/api/1.0/hello")
        error_message = factory.make_string()
        exception = MAASAPINotFound(error_message)
        response = middleware.process_exception(api_request, exception)
        self.assertEqual(
            (httplib.NOT_FOUND, error_message),
            (response.status_code, response.content))

    def test_ignores_error_outside_API(self):
        middleware = APIErrorsMiddleware()
        non_api_request = factory.make_fake_request("/middleware/api/hello")
        exception = MAASAPINotFound(factory.make_string())
        self.assertIsNone(
            middleware.process_exception(non_api_request, exception))


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

    def test_handles_MultipleFailures(self):
        middleware = RPCErrorsMiddleware()
        request = factory.make_fake_request(factory.make_string(), 'POST')
        failures = []
        for _ in range(3):
            error_message = factory.make_name("error-")
            exception_class = random.choice(
                (NoConnectionsAvailable, PowerActionAlreadyInProgress))
            failures.append(Failure(exception_class(error_message)))
        exception = MultipleFailures(*failures)
        response = middleware.process_exception(request, exception)

        # The response is a redirect.
        self.assertEqual(request.path, extract_redirect(response))
        # An error message has been published for each exception.
        self.assertEqual(
            [(constants.ERROR, "Error: %s" % unicode(failure.value), '')
                for failure in failures],
            request._messages.messages)

    def test_handles_NoConnectionsAvailable(self):
        middleware = RPCErrorsMiddleware()
        request = factory.make_fake_request(factory.make_string(), 'POST')
        error_message = (
            "No connections availble for cluster %s" %
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

    def test_adds_message_for_unknown_errors_in_multiple_failures(self):
        # If an exception has no message, the middleware will generate a
        # useful one and display it to the user.
        middleware = RPCErrorsMiddleware()
        request = factory.make_fake_request(factory.make_string(), 'POST')
        unknown_exception = ZeroDivisionError()
        failures = [
            Failure(unknown_exception),
            Failure(PowerActionAlreadyInProgress("Unzip a banana!")),
            ]
        exception = MultipleFailures(*failures)
        response = middleware.process_exception(request, exception)
        self.assertEqual(request.path, extract_redirect(response))

        expected_messages = [
            (
                constants.ERROR,
                "Error: %s" % get_error_message_for_exception(
                    unknown_exception),
                '',
            ),
            (constants.ERROR, "Error: %s" % unicode(failures[1].value), ''),
            ]
        self.assertEqual(
            expected_messages,
            request._messages.messages)

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
            (response.status_code, response.content))

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
            (httplib.SERVICE_UNAVAILABLE, error_message),
            (response.status_code, response.content))

    def test_503_response_includes_retry_after_header_by_default(self):
        middleware = APIRPCErrorsMiddleware()
        request = factory.make_fake_request(
            "/api/1.0/" + factory.make_string(), 'POST')
        error = NoConnectionsAvailable(factory.make_name())
        response = middleware.process_exception(request, error)

        self.assertEqual(
            (
                httplib.SERVICE_UNAVAILABLE,
                '%s' % middleware.RETRY_AFTER_SERVICE_UNAVAILABLE,
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
            (httplib.SERVICE_UNAVAILABLE, error_message),
            (response.status_code, response.content))

    def test_multiple_failures_returned_as_500(self):
        middleware = APIRPCErrorsMiddleware()
        request = factory.make_fake_request(
            "/api/1.0/" + factory.make_string(), 'POST')
        failures = []
        error_messages = []
        for _ in range(3):
            error_message = factory.make_name("error-")
            error_messages.append(error_message)
            exception_class = random.choice(
                (NoConnectionsAvailable, PowerActionAlreadyInProgress))
            failures.append(Failure(exception_class(error_message)))
        exception = MultipleFailures(*failures)
        response = middleware.process_exception(request, exception)

        expected_error_message = "\n".join(error_messages)
        self.assertEqual(
            (httplib.INTERNAL_SERVER_ERROR, expected_error_message),
            (response.status_code, response.content))

    def test_handles_TimeoutError(self):
        middleware = APIRPCErrorsMiddleware()
        request = factory.make_fake_request(
            "/api/1.0/" + factory.make_string(), 'POST')
        error_message = "No thanks, I'm trying to give them up."
        error = TimeoutError(error_message)
        response = middleware.process_exception(request, error)

        self.assertEqual(
            (httplib.GATEWAY_TIMEOUT, error_message),
            (response.status_code, response.content))

    def test_adds_message_for_unknown_errors_in_multiple_failures(self):
        # If an exception has no message, the middleware will generate a
        # useful one and display it to the user.
        middleware = APIRPCErrorsMiddleware()
        request = factory.make_fake_request(
            "/api/1.0/" + factory.make_string(), 'POST')
        unknown_exception = ZeroDivisionError()
        error_message = "It ain't 'alf 'ot mum!"
        expected_error_message = "\n".join([
            get_error_message_for_exception(unknown_exception),
            error_message])
        failures = [
            Failure(unknown_exception),
            Failure(PowerActionAlreadyInProgress(error_message)),
            ]
        exception = MultipleFailures(*failures)
        response = middleware.process_exception(request, exception)

        self.assertEqual(
            (httplib.INTERNAL_SERVER_ERROR, expected_error_message),
            (response.status_code, response.content))

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
        get_client_for = self.patch(nodegroup_module, 'getClientFor')
        middleware = ExternalComponentsMiddleware()
        cluster = factory.make_NodeGroup(status=NODEGROUP_STATUS.ACCEPTED)

        request = factory.make_fake_request(factory.make_string(), 'GET')
        middleware.process_request(request)

        self.assertThat(
            get_client_for, MockCalledOnceWith(cluster.uuid, timeout=0))

    def test__ignores_non_accepted_clusters(self):
        get_client_for = self.patch(nodegroup_module, 'getClientFor')
        factory.make_NodeGroup(
            status=factory.pick_enum(
                NODEGROUP_STATUS, but_not=[NODEGROUP_STATUS.ACCEPTED]))
        middleware = ExternalComponentsMiddleware()
        request = factory.make_fake_request(factory.make_string(), 'GET')
        middleware.process_request(request)

        self.assertThat(get_client_for, MockNotCalled())

    def test__registers_error_if_all_clusters_are_disconnected(self):
        get_client_for = self.patch(nodegroup_module, 'getClientFor')
        get_client_for.side_effect = NoConnectionsAvailable(
            "Why, it's a jet-propelled, guided NAAFI!")
        middleware = ExternalComponentsMiddleware()
        factory.make_NodeGroup(status=NODEGROUP_STATUS.ACCEPTED)

        request = factory.make_fake_request(factory.make_string(), 'GET')
        middleware.process_request(request)

        error = get_persistent_error(COMPONENT.CLUSTERS)
        self.assertEqual(
            "One or more clusters are currently disconnected. Visit the "
            "<a href=\"%s\">clusters page</a> for more information." %
            reverse('cluster-list'),
            error)

    def test__registers_error_if_any_clusters_are_disconnected(self):
        get_client_for = self.patch(nodegroup_module, 'getClientFor')
        get_client_for.side_effect = [
            NoConnectionsAvailable("Why, it's a jet-propelled, guided NAAFI!"),
            None,
            ]
        middleware = ExternalComponentsMiddleware()
        factory.make_NodeGroup(status=NODEGROUP_STATUS.ACCEPTED)

        request = factory.make_fake_request(factory.make_string(), 'GET')
        middleware.process_request(request)

        error = get_persistent_error(COMPONENT.CLUSTERS)
        self.assertEqual(
            "One or more clusters are currently disconnected. Visit the "
            "<a href=\"%s\">clusters page</a> for more information." %
            reverse('cluster-list'),
            error)

    def test__removes_error_once_all_clusters_are_connected(self):
        # Patch getClientFor() to ensure that we don't actually try to
        # connect to the cluster.
        self.patch(nodegroup_module, 'getClientFor')
        middleware = ExternalComponentsMiddleware()
        factory.make_NodeGroup(status=NODEGROUP_STATUS.ACCEPTED)

        register_persistent_error(
            COMPONENT.CLUSTERS, "Who flung that batter pudding?")
        request = factory.make_fake_request(factory.make_string(), 'GET')
        middleware.process_request(request)
        self.assertIsNone(get_persistent_error(COMPONENT.CLUSTERS))

    def test__adds_warning_if_boot_image_import_not_started(self):
        middleware = ExternalComponentsMiddleware()

        request = factory.make_fake_request(factory.make_string(), 'GET')
        middleware.process_request(request)

        error = get_persistent_error(COMPONENT.IMPORT_PXE_FILES)
        self.assertEqual(
            normalise_whitespace(
                "Boot image import process not started. Nodes will not be "
                "able to provision without boot images. Visit the "
                "<a href=\"%s\">boot images</a> page to start the import." % (
                    reverse('images'))),
            error)

    def test__removes_warning_if_boot_image_process_started(self):
        middleware = ExternalComponentsMiddleware()
        register_persistent_error(
            COMPONENT.IMPORT_PXE_FILES,
            "You rotten swine, you! You have deaded me!")

        # Add a BootResource so that the middleware thinks the import
        # process has started.
        factory.make_BootResource()
        request = factory.make_fake_request(factory.make_string(), 'GET')
        middleware.process_request(request)

        error = get_persistent_error(COMPONENT.IMPORT_PXE_FILES)
        self.assertIsNone(error)
