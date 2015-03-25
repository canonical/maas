# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for :py:module:`maasserver.utils.views`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import httplib
import io
import logging
from random import (
    randint,
    random,
    )
from weakref import WeakSet

from apiclient.multipart import encode_multipart_data
from django.core import signals
from django.core.handlers.wsgi import (
    WSGIHandler,
    WSGIRequest,
    )
from django.core.urlresolvers import get_resolver
from django.db import connection
from django.http import HttpResponse
from django.http.response import HttpResponseServerError
from fixtures import FakeLogger
from maasserver.testing.testcase import SerializationFailureTestCase
from maasserver.utils import views
from maasserver.utils.orm import validate_in_transaction
from maastesting.factory import factory
from maastesting.matchers import (
    MockCalledOnceWith,
    MockCallsMatch,
    )
from maastesting.testcase import MAASTestCase
from maastesting.utils import sample_binary_data
from mock import (
    ANY,
    call,
    sentinel,
    )
from testtools.matchers import (
    Contains,
    Equals,
    HasLength,
    Is,
    IsInstance,
    Not,
    )
from twisted.internet.task import Clock
from twisted.python import log
from twisted.web import wsgi


def make_request():
    # Return a minimal WSGIRequest.
    return WSGIRequest({
        "REQUEST_METHOD": "GET",
        "wsgi.input": wsgi._InputStream(io.BytesIO()),
    })


class TestLogFunctions(MAASTestCase):
    """Tests for `log_failed_attempt` and `log_final_failed_attempt`."""

    def capture_logs(self):
        return FakeLogger(
            views.__name__, level=logging.DEBUG,
            format="%(levelname)s: %(message)s")

    def test_log_failed_attempt_logs_warning(self):
        request = make_request()
        request.path = factory.make_name("path")
        attempt = randint(1, 10)
        elapsed = random() * 10
        remaining = random() * 10
        pause = random()

        with self.capture_logs() as logger:
            views.log_failed_attempt(
                request, attempt, elapsed, remaining, pause)

        self.assertEqual(
            "DEBUG: Attempt #%d for %s failed; will retry in %.0fms (%.1fs "
            "now elapsed, %.1fs remaining)\n" % (
                attempt, request.path, pause * 1000.0, elapsed, remaining),
            logger.output)

    def test_log_final_failed_attempt_logs_error(self):
        request = make_request()
        request.path = factory.make_name("path")
        attempt = randint(1, 10)
        elapsed = random() * 10

        with self.capture_logs() as logger:
            views.log_final_failed_attempt(request, attempt, elapsed)

        self.assertEqual(
            "ERROR: Attempt #%d for %s failed; giving up (%.1fs elapsed in "
            "total)\n" % (attempt, request.path, elapsed),
            logger.output)


class TestResetRequest(MAASTestCase):
    """Tests for :py:func:`maasserver.utils.views.reset_request`."""

    def test__clears_messages_from_cookies(self):
        request = make_request()
        request.COOKIES["messages"] = sentinel.messages
        request = views.reset_request(request)
        self.assertEqual({}, request.COOKIES)


class TestWebApplicationHandler(SerializationFailureTestCase):

    def setUp(self):
        super(TestWebApplicationHandler, self).setUp()
        # Wire time.sleep() directly up to clock.advance() to avoid needless
        # sleeps, and to simulate the march of time without intervention.
        clock = self.patch(views, "clock", Clock())
        self.patch(views, "sleep", clock.advance)

    def test__init_defaults(self):
        handler = views.WebApplicationHandler()
        self.expectThat(
            handler._WebApplicationHandler__retry_attempts,
            Equals(10))
        self.expectThat(
            handler._WebApplicationHandler__retry_timeout,
            Equals(90))
        self.expectThat(
            handler._WebApplicationHandler__retry,
            IsInstance(WeakSet))
        self.expectThat(
            handler._WebApplicationHandler__retry,
            HasLength(0))

    def test__init_attempts_can_be_set(self):
        attempts = randint(1, 100)
        handler = views.WebApplicationHandler(attempts)
        self.expectThat(
            handler._WebApplicationHandler__retry_attempts,
            Equals(attempts))

    def test__init_timeout_can_be_set(self):
        handler = views.WebApplicationHandler(timeout=sentinel.timeout)
        self.expectThat(
            handler._WebApplicationHandler__retry_timeout,
            Is(sentinel.timeout))

    def test__handle_uncaught_exception_notes_serialization_failure(self):
        handler = views.WebApplicationHandler()
        request = make_request()
        request.path = factory.make_name("path")
        failure = self.capture_serialization_failure()
        response = handler.handle_uncaught_exception(
            request=request, resolver=get_resolver(None), exc_info=failure)
        # HTTP 500 is returned...
        self.expectThat(
            response.status_code,
            Equals(httplib.INTERNAL_SERVER_ERROR))
        # ... but the response is recorded as needing a retry.
        self.expectThat(
            handler._WebApplicationHandler__retry,
            Contains(response))

    def test__handle_uncaught_exception_does_not_note_other_failure(self):
        handler = views.WebApplicationHandler()
        request = make_request()
        request.path = factory.make_name("path")
        failure_type = factory.make_exception_type()
        failure = failure_type, failure_type(), None
        response = handler.handle_uncaught_exception(
            request=request, resolver=get_resolver(None), exc_info=failure)
        # HTTP 500 is returned...
        self.expectThat(
            response.status_code,
            Equals(httplib.INTERNAL_SERVER_ERROR))
        # ... but the response is NOT recorded as needing a retry.
        self.expectThat(
            handler._WebApplicationHandler__retry,
            Not(Contains(response)))

    def test__handle_uncaught_exception_logs_other_failure(self):
        handler = views.WebApplicationHandler()
        request = make_request()
        request.path = factory.make_name("path")
        exc_type = factory.make_exception_type()
        exc_info = exc_type, exc_type(), None
        mock_err = self.patch(log, "err")
        handler.handle_uncaught_exception(
            request=request, resolver=get_resolver(None), exc_info=exc_info)
        # Cannot use MockCalledOnceWith as the Failure objects will not match
        # even with them created the same. Must check the contents of the
        # failure.
        failure = mock_err.call_args[0][0]
        _why = mock_err.call_args_list[0][1]['_why']
        self.expectThat(failure.type, Equals(exc_type))
        self.expectThat(failure.value, Equals(exc_info[1]))
        self.expectThat(_why, Equals("500 Error - %s" % request.path))

    def test__get_response_catches_serialization_failures(self):
        get_response = self.patch(WSGIHandler, "get_response")
        get_response.side_effect = (
            lambda request: self.cause_serialization_failure())

        handler = views.WebApplicationHandler(1)
        request = make_request()
        request.path = factory.make_name("path")
        response = handler.get_response(request)

        self.assertThat(
            get_response, MockCalledOnceWith(request))
        self.assertThat(
            response, IsInstance(HttpResponseServerError))

    def test__get_response_sends_signal_on_serialization_failures(self):
        get_response = self.patch(WSGIHandler, "get_response")
        get_response.side_effect = (
            lambda request: self.cause_serialization_failure())

        send_request_exception = self.patch_autospec(
            signals.got_request_exception, "send")

        handler = views.WebApplicationHandler(1)
        request = make_request()
        request.path = factory.make_name("path")
        handler.get_response(request)

        self.assertThat(
            send_request_exception, MockCalledOnceWith(
                sender=views.WebApplicationHandler, request=request))

    def test__get_response_tries_only_once(self):
        get_response = self.patch(WSGIHandler, "get_response")
        get_response.return_value = sentinel.response

        handler = views.WebApplicationHandler()
        request = make_request()
        request.path = factory.make_name("path")
        response = handler.get_response(request)

        self.assertThat(
            get_response, MockCalledOnceWith(request))
        self.assertThat(
            response, Is(sentinel.response))

    def test__get_response_tries_multiple_times(self):
        handler = views.WebApplicationHandler(3)
        # An iterable of responses, the last of which will be the final result
        # of get_response().
        responses = iter((sentinel.r1, sentinel.r2, sentinel.r3))

        def set_retry(request):
            response = next(responses)
            handler._WebApplicationHandler__retry.add(response)
            return response

        get_response = self.patch(WSGIHandler, "get_response")
        get_response.side_effect = set_retry

        reset_request = self.patch_autospec(views, "reset_request")
        reset_request.side_effect = lambda request: request

        request = make_request()
        request.path = factory.make_name("path")
        response = handler.get_response(request)

        self.assertThat(
            get_response, MockCallsMatch(
                call(request), call(request), call(request)))
        self.assertThat(response, Is(sentinel.r3))

    def test__get_response_logs_retry_and_resets_request(self):
        timeout = 1.0 + (random() * 99)
        handler = views.WebApplicationHandler(2, timeout)

        def set_retry(request):
            response = sentinel.response
            handler._WebApplicationHandler__retry.add(response)
            return response

        get_response = self.patch(WSGIHandler, "get_response")
        get_response.side_effect = set_retry

        self.patch_autospec(views, "log_failed_attempt")
        self.patch_autospec(views, "log_final_failed_attempt")
        reset_request = self.patch_autospec(views, "reset_request")
        reset_request.side_effect = lambda request: request

        request = make_request()
        request.path = factory.make_name("path")
        handler.get_response(request)

        self.expectThat(
            views.log_failed_attempt,
            MockCalledOnceWith(request, 1, ANY, ANY, ANY))
        self.expectThat(
            views.log_final_failed_attempt,
            MockCalledOnceWith(request, 2, ANY))
        self.expectThat(reset_request, MockCalledOnceWith(request))

    def test__get_response_up_calls_in_transaction(self):
        handler = views.WebApplicationHandler(2)

        def check_in_transaction(request):
            validate_in_transaction(connection)

        get_response = self.patch(WSGIHandler, "get_response")
        get_response.side_effect = check_in_transaction

        request = make_request()
        request.path = factory.make_name("path")
        handler.get_response(request)

        self.assertThat(get_response, MockCalledOnceWith(request))

    def test__get_response_restores_files_across_requests(self):
        handler = views.WebApplicationHandler(3)
        file_content = sample_binary_data
        file_name = 'content'

        recorder = []

        def get_response_read_content_files(self, request):
            # Simple get_response method which returns the 'file_name' file
            # from the request in the response.
            content = request.FILES[file_name].read()
            # Record calls.
            recorder.append(content)
            response = HttpResponse(
                content=content,
                status=httplib.OK,
                mimetype=b"text/plain; charset=utf-8")
            handler._WebApplicationHandler__retry.add(response)
            return response

        self.patch(
            WSGIHandler, "get_response", get_response_read_content_files)

        body, headers = encode_multipart_data(
            [], [[file_name, io.BytesIO(file_content)]])
        env = {
            'REQUEST_METHOD': 'POST',
            'wsgi.input': wsgi._InputStream(io.BytesIO(body)),
            'CONTENT_TYPE': headers['Content-Type'],
            'CONTENT_LENGTH': headers['Content-Length'],
            'HTTP_MIME_VERSION': headers['MIME-Version'],
        }
        request = WSGIRequest(env)

        response = handler.get_response(request)
        self.assertEqual(file_content, response.content)
        self.assertEqual(recorder, [file_content] * 3)
