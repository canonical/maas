# Copyright 2014-2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""View utilities configuration."""


import http.client
from itertools import count
import logging
import sys
from time import sleep
from weakref import WeakSet

from django.conf import settings
from django.core import signals
from django.core.exceptions import ImproperlyConfigured, MiddlewareNotUsed
from django.core.handlers.wsgi import WSGIHandler
from django.db import transaction
from django.http import HttpResponse
from django.template.response import SimpleTemplateResponse
from django.urls import get_resolver
from django.utils.module_loading import import_string
from piston3.authentication import initialize_server_request
from piston3.models import Nonce
from piston3.oauth import OAuthError
from requests.structures import CaseInsensitiveDict
from twisted.internet import reactor as clock
from twisted.web import wsgi

from maasserver.utils.orm import (
    gen_retry_intervals,
    is_retryable_failure,
    post_commit_hooks,
    retry_context,
    RetryTransaction,
)
from provisioningserver.utils.twisted import retries

logger = logging.getLogger(__name__)

RETRY_AFTER_CONFLICT = 5


class InternalErrorResponse(BaseException):
    """Exception raised to exit the transaction context.

    Used when `get_response` of the handler returns a response of 500.
    """

    def __init__(self, response):
        super(InternalErrorResponse).__init__()
        self.response = response


def log_failed_attempt(request, attempt, elapsed, remaining, pause):
    """Log about a failed attempt to answer the given request."""
    logger.debug(
        "Attempt #%d for %s failed; will retry in %.0fms (%.1fs now elapsed, "
        "%.1fs remaining)",
        attempt,
        request.path,
        pause * 1000.0,
        elapsed,
        remaining,
    )


def log_final_failed_attempt(request, attempt, elapsed, exc_info=None):
    """Log about the final failed attempt to answer the given request."""
    logger.error(
        f"Attempt #{attempt} for {request.path} failed; "
        f"giving up ({elapsed:.1f}s elapsed in total)",
        exc_info=exc_info,
    )


def delete_oauth_nonce(request):
    """Delete the OAuth nonce for the given request from the database.

    This is to allow the exact same request to be retried.
    """
    _, oauth_request = initialize_server_request(request)
    if oauth_request is not None:
        try:
            consumer_key = oauth_request.get_parameter("oauth_consumer_key")
            token_key = oauth_request.get_parameter("oauth_token")
            nonce = oauth_request.get_parameter("oauth_nonce")
        except OAuthError:
            # Missing OAuth parameter: skip Nonce deletion.
            pass
        else:
            Nonce.objects.filter(
                consumer_key=consumer_key, token_key=token_key, key=nonce
            ).delete()


def reset_request(request):
    """Return a pristine new request object.

    Use this after a transaction failure, before retrying.

    This is needed so that we don't carry over cookies, for example.
    """
    wsgi_input = request.environ.get("wsgi.input")
    if isinstance(wsgi_input, wsgi._InputStream):
        # This is what we are going to see within Twisted. The wrapped
        # file supports seeking so this is safe.
        wsgi_input._wrapped.seek(0)
    else:
        # Neither PEP 0333 nor PEP 3333 require that the input stream
        # supports seeking, but we need it, and it would be better that
        # this crashed here than continuing on if it's not available.
        wsgi_input.seek(0)

    return request.__class__(request.environ)


def request_headers(request):
    """Return a dict with headers from a request.

    Header keys are case insensitive.
    """
    return CaseInsensitiveDict(
        (key[5:].lower().replace("_", "-"), value)
        for key, value in request.META.items()
        if key.startswith("HTTP_")
    )


class MAASDjangoTemplateResponse(SimpleTemplateResponse):
    def __init__(self, response=None):
        super().__init__("%d.html" % self.status_code)

        # If we are passed an original response object 'response',
        # transfer over the content from the original response
        # for type 200 responses, if such content exists.
        # Subsequently calling render() on the new object should
        # not replace the transfered content, while calling render()
        # on the new object when the original was content-less
        # will render as a template with the new status code.
        if response is not None and hasattr(response, "status_code"):
            if response.status_code == http.client.OK and hasattr(
                response, "content"
            ):
                self.content = response.content


class HttpResponseConflict(MAASDjangoTemplateResponse):
    status_code = int(http.client.CONFLICT)
    reason_phrase = http.client.responses[http.client.CONFLICT]

    def __init__(self, response=None, exc_info=None):
        super().__init__(response=response)
        # Responses with status code 409 should be retried by the clients
        # see https://bugs.launchpad.net/maas/+bug/2034014/comments/6 for more information
        self["Retry-After"] = RETRY_AFTER_CONFLICT
        self.exc_info = exc_info


class WebApplicationHandler(WSGIHandler):
    """Request handler that retries when there are serialisation failures.

    :ivar __retry_attempts: The number of times to attempt each request.
    :ivar __retry_timeout: The number of seconds after which this request will
        no longer be considered for a retry.
    :ivar __retry: A weak set containing responses that have been generated as
        a result of a retryable failure.
    """

    def __init__(self, attempts=10, timeout=90.0):
        super().__init__()
        assert attempts >= 1, "The minimum attempts is 1, not %d" % attempts
        self.__retry_attempts = attempts
        self.__retry_timeout = timeout
        self.__retry = WeakSet()

    def load_middleware(self):
        """Override `BaseHandler.load_middleware`.

        Remove the use of built-in convert_exception_to_response, use the ones
        provided by the class. That allows exceptions to propogate up the
        middleware instead of wrapping each middleware.
        """
        self._request_middleware = []
        self._view_middleware = []
        self._template_response_middleware = []
        self._response_middleware = []
        self._exception_middleware = []

        if settings.MIDDLEWARE is None:
            raise ImproperlyConfigured(
                "Old-style middleware is not supported with "
                "`WebApplicationHandler`. Use the new settings.MIDDLEWARE "
                "instead."
            )
        else:
            handler = self._get_response
            for middleware_path in reversed(settings.MIDDLEWARE):
                middleware = import_string(middleware_path)
                try:
                    mw_instance = middleware(handler)
                except MiddlewareNotUsed:
                    continue

                if mw_instance is None:
                    raise ImproperlyConfigured(
                        "Middleware factory %s returned None."
                        % middleware_path
                    )

                if hasattr(mw_instance, "process_view"):
                    self._view_middleware.insert(0, mw_instance.process_view)
                if hasattr(mw_instance, "process_template_response"):
                    self._template_response_middleware.append(
                        mw_instance.process_template_response
                    )
                if hasattr(mw_instance, "process_exception"):
                    self._exception_middleware.append(
                        mw_instance.process_exception
                    )

                handler = mw_instance

        self._middleware_chain = handler

    def handle_uncaught_exception(
        self, request, resolver, exc_info, reraise=True
    ):
        """Override `BaseHandler.handle_uncaught_exception`.

        If a retryable failure is detected, a retry is requested. It's up
        to ``get_response`` to actually do the retry.
        """
        exc_type, exc_value, exc_traceback = exc_info
        exc = exc_type(exc_value)
        exc.__traceback__ = exc_traceback
        exc.__cause__ = exc_value.__cause__

        if reraise:
            raise exc from exc.__cause__

        # Re-perform the exception so the process_exception_by_middlware
        # can process the exception. Any exceptions that cause a retry to
        # occur place it in the __retry so the `get_response` can handle
        # performing the retry.
        try:
            try:
                raise exc from exc.__cause__
            except Exception as exc:
                return self.process_exception_by_middleware(exc, request)
        except SystemExit:
            raise
        except RetryTransaction:
            response = HttpResponseConflict(exc_info=sys.exc_info())
            self.__retry.add(response)
            return response
        except Exception as exc:
            exc_info = sys.exc_info()
            if is_retryable_failure(exc):
                response = HttpResponseConflict(exc_info=exc_info)
                self.__retry.add(response)
                return response
            else:
                logger.error(
                    "500 Internal Server Error @ %s" % request.path,
                    exc_info=exc_info,
                )
                return HttpResponse(
                    content=str(exc).encode("utf-8"),
                    status=int(http.client.INTERNAL_SERVER_ERROR),
                    content_type="text/plain; charset=utf-8",
                )

    def make_view_atomic(self, view):
        """Make `view` atomic and with a post-commit hook savepoint.

        This view will be executed within a transaction as it is -- that's a
        core purpose of this class -- so wrapping the view in an extra atomic
        layer means that it will run within a *savepoint*.

        This prevents middleware exception handlers that suppress exceptions
        from inadvertently allowing failed requests to be committed.

        In addition this also holds a post-commit hook savepoint around the
        view. If the view crashes those post-commit hooks that were created
        with this savepoint will be discarded.

        """
        view_atomic = super().make_view_atomic(view)

        def view_atomic_with_post_commit_savepoint(*args, **kwargs):
            with post_commit_hooks.savepoint():
                return view_atomic(*args, **kwargs)

        return view_atomic_with_post_commit_savepoint

    def get_response(self, request):
        """Override `BaseHandler.get_response`.

        Wrap Django's default get_response(). Middleware and templates will
        thus also run within the same transaction, but streaming responses
        will *not* run within the same transaction, or any transaction at all
        by default.
        """
        django_get_response = super().get_response

        def get_response(request):
            # Up-call to Django's get_response() in a transaction. This
            # transaction may fail because of a retryable conflict, so
            # pass errors to handle_uncaught_exception().
            try:
                with post_commit_hooks:
                    with transaction.atomic():
                        response = django_get_response(request)
                        if response.status_code == 500:
                            raise InternalErrorResponse(response)
                        return response
            except SystemExit:
                # Allow sys.exit() to actually exit, reproducing behaviour
                # found in Django's BaseHandler.
                raise
            except InternalErrorResponse as exc:
                # Response is good, but the transaction needed to be rolled
                # back because the response was a 500 error.
                return exc.response
            except BaseException:
                # Catch *everything* else, also reproducing behaviour found in
                # Django's BaseHandler. In practice, we should only really see
                # transaction failures here from the outermost atomic block as
                # all other exceptions are handled by django_get_response. The
                # setting DEBUG_PROPAGATE_EXCEPTIONS upsets this, so be on
                # your guard when tempted to use it.
                signals.got_request_exception.send(
                    sender=self.__class__, request=request
                )
                return self.handle_uncaught_exception(
                    request, get_resolver(None), sys.exc_info(), reraise=False
                )

        # Attempt to start new transactions for up to `__retry_timeout`
        # seconds, at intervals defined by `gen_retry_intervals`, but don't
        # try more than `__retry_attempts` times.
        retry_intervals = gen_retry_intervals()
        retry_details = retries(self.__retry_timeout, retry_intervals, clock)
        retry_attempts = self.__retry_attempts
        retry_set = self.__retry

        with retry_context:
            for attempt in count(1):
                retry_context.prepare()
                response = get_response(request)
                if response in retry_set:
                    elapsed, remaining, wait = next(retry_details)
                    if attempt == retry_attempts or wait == 0:
                        # Time's up: this was the final attempt.
                        exc_info = getattr(response, "exc_info", None)
                        log_final_failed_attempt(
                            request, attempt, elapsed, exc_info=exc_info
                        )
                        conflict_response = HttpResponseConflict(response)
                        conflict_response.render()
                        return conflict_response
                    else:
                        # We'll retry after a brief interlude.
                        log_failed_attempt(
                            request, attempt, elapsed, remaining, wait
                        )
                        delete_oauth_nonce(request)
                        request = reset_request(request)
                        sleep(wait)
                else:
                    return response
