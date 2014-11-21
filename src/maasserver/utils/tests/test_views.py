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

from itertools import count
from random import randint
from textwrap import dedent

from django.db import transaction
from django.http import HttpRequest
from fixtures import FakeLogger
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils import views
from maasserver.utils.orm import (
    is_serialization_failure,
    request_transaction_retry,
    )
from maastesting.factory import factory
from maastesting.matchers import (
    IsCallable,
    MockCalledOnceWith,
    MockCallsMatch,
    )
from maastesting.testcase import MAASTestCase
from mock import (
    call,
    sentinel,
    )
from testtools.matchers import (
    AllMatch,
    Equals,
    Is,
    IsInstance,
    MatchesPredicate,
    Not,
    )


class TestLogRetry(MAASTestCase):
    """Tests for :py:func:`maasserver.utils.views.log_retry`."""

    def test__logs_warning(self):
        request = HttpRequest()
        request.path = factory.make_name("path")
        attempt = randint(1, 10)

        with FakeLogger("maas", format="%(levelname)s: %(message)s") as logger:
            views.log_retry(request, attempt)

        self.assertEqual(
            "WARNING: Retry #%d for %s\n" % (attempt, request.path),
            logger.output)


class TestResetRequest(MAASTestCase):
    """Tests for :py:func:`maasserver.utils.views.reset_request`."""

    def test__clears_messages_from_cookies(self):
        request = HttpRequest()
        request.COOKIES["messages"] = sentinel.messages
        views.reset_request(request)
        self.assertEqual({}, request.COOKIES)

    def test__clears_only_messages_from_cookies(self):
        request = HttpRequest()
        request.COOKIES["messages"] = sentinel.messages
        request.COOKIES.update({
            factory.make_name("cookie"): sentinel.cookie
            for _ in xrange(10)
        })
        keys_before = set(request.COOKIES)
        views.reset_request(request)
        keys_after = set(request.COOKIES)
        self.assertEqual({"messages"}, keys_before - keys_after)


class TestRetryView(MAASServerTestCase):
    """Tests for :py:class:`maasserver.utils.views.RetryView`."""

    def test__annotates_returned_view_with_original_view(self):
        view = lambda: None
        retry_view = views.RetryView.make(view)
        self.expectThat(retry_view, IsCallable())
        self.expectThat(retry_view, Not(Is(view)))
        self.expectThat(retry_view.original_view, Is(view))

    def test__annotates_returned_view_with_atomic_view(self):
        atomic = self.patch_autospec(transaction, "atomic")
        retry_view = views.RetryView.make(sentinel.view, db_alias=sentinel.db)
        self.expectThat(atomic, MockCalledOnceWith(using=sentinel.db))
        atomic_decorator = atomic.return_value
        self.expectThat(atomic_decorator, MockCalledOnceWith(sentinel.view))
        atomic_view = atomic_decorator.return_value
        self.expectThat(retry_view.atomic_view, Is(atomic_view))

    def test__renders_docs_of_returned_view(self):

        def view_with_a_name(request):
            return sentinel.response

        self.assertDocTestMatches(
            dedent("""\
            View wrapper that retries when serialization failures occur.

            This will retry maasserver...view_with_a_name up to 666 times.

            ...
            """),
            views.RetryView.make(view_with_a_name, 666).__doc__)

    def test__returns_naked_view_if_non_atomic_request_is_set(self):
        view = transaction.non_atomic_requests(lambda: None)
        self.expectThat(views.RetryView.make(view), Is(view))

    def test__retry_view_returns_first_response_if_okay(self):
        view = lambda request: sentinel.response
        retry_view = views.RetryView.make(view)
        self.assertThat(retry_view(sentinel.request), Is(sentinel.response))

    def test__retry_view_raises_non_serialization_exceptions(self):
        exception_type = factory.make_exception_type()

        def broken_view(request):
            raise exception_type()

        retry_view = views.RetryView.make(broken_view)
        self.assertRaises(exception_type, retry_view, sentinel.request)

    def test__retry_view_retries_serialization_exceptions(self):

        def broken_view(request, arg, kwarg):
            request_transaction_retry()

        retries = randint(1, 10)
        retry_view = views.RetryView.make(broken_view, retries=retries)
        atomic_view_original = retry_view.atomic_view
        atomic_view = self.patch(retry_view, "atomic_view")
        atomic_view.side_effect = atomic_view_original
        request = HttpRequest()

        error = self.assertRaises(
            Exception, retry_view, request,
            sentinel.arg, kwarg=sentinel.kwarg)

        self.expectThat(error, MatchesPredicate(
            is_serialization_failure, "%r is not a serialization failure."))
        expected_call = call(request, sentinel.arg, kwarg=sentinel.kwarg)
        expected_calls = [expected_call] * (retries + 1)
        self.expectThat(atomic_view, MockCallsMatch(*expected_calls))

    def test__logs_retries(self):
        log_retry = self.patch_autospec(views, "log_retry")

        def broken_view(request):
            request_transaction_retry()

        retry_view = views.RetryView.make(broken_view, 1)
        request = HttpRequest()
        request.path = factory.make_name("path")

        error = self.assertRaises(Exception, retry_view, request)

        self.expectThat(error, MatchesPredicate(
            is_serialization_failure, "%r is not a serialization failure."))
        self.assertThat(log_retry, MockCalledOnceWith(request, 1))

    def test__resets_request(self):
        reset_request = self.patch_autospec(views, "reset_request")

        def broken_view(request):
            request_transaction_retry()

        retry_view = views.RetryView.make(broken_view, 1)
        request = HttpRequest()

        error = self.assertRaises(Exception, retry_view, request)

        self.expectThat(error, MatchesPredicate(
            is_serialization_failure, "%r is not a serialization failure."))
        self.assertThat(reset_request, MockCalledOnceWith(request))

    def test__stops_retrying_on_success(self):

        def view(request, attempt=count(1)):
            if next(attempt) == 3:
                return sentinel.response
            else:
                request_transaction_retry()

        retry_view = views.RetryView.make(view, 4)

        response = retry_view(HttpRequest())

        self.assertThat(response, Is(sentinel.response))

    def test__make_does_not_double_wrap(self):
        view = lambda: None
        retry_view = views.RetryView.make(view)
        self.assertThat(views.RetryView.make(retry_view), Is(retry_view))


class TestRetryURL(MAASTestCase):
    """Tests for :py:func:`maasserver.utils.views.retry_url`."""

    def test__creates_url_for_plain_views(self):
        view = lambda: None
        view_name = factory.make_name("view")
        view_regex = "^%s/" % factory.make_name("path")
        url = views.retry_url(view_regex, view, sentinel.kwargs, view_name)
        self.expectThat(url.name, Equals(view_name))
        self.expectThat(url.regex.pattern, Equals(view_regex))
        self.expectThat(url.default_args, Is(sentinel.kwargs))
        # The view has been wrapped into a RetryView.
        self.assertThat(url.callback, IsInstance(views.RetryView))
        self.expectThat(url.callback.original_view, Is(view))

    def test__creates_url_for_api_views(self):
        # Use real-world code.
        from maasserver.api.support import OperationsResource
        from maasserver.api.nodes import NodeHandler

        view = OperationsResource(NodeHandler)
        view_name = factory.make_name("view")
        view_regex = "^%s/" % factory.make_name("path")
        url = views.retry_url(view_regex, view, sentinel.kwargs, view_name)
        self.expectThat(url.name, Equals(view_name))
        self.expectThat(url.regex.pattern, Equals(view_regex))
        self.expectThat(url.default_args, Is(sentinel.kwargs))
        # The view has NOT been wrapped into a RetryView. Instead, each of the
        # handler's exports have been wrapped.
        self.assertThat(url.callback, Not(IsInstance(views.RetryView)))
        self.assertThat(
            url.callback.handler.exports.viewvalues(),
            AllMatch(IsInstance(views.RetryView)))
