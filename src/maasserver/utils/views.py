# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""View utilities configuration."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'WebApplicationHandler',
]

from itertools import count
import logging
import sys
from time import sleep
from weakref import WeakSet

from django.core import signals
from django.core.handlers.wsgi import WSGIHandler
from django.core.urlresolvers import get_resolver
from django.db import transaction
from maasserver.utils.orm import (
    gen_retry_intervals,
    is_serialization_failure,
    post_commit_hooks,
)
from oauth.oauth import OAuthError
from piston.authentication import initialize_server_request
from piston.models import Nonce
from provisioningserver.utils.twisted import retries
from twisted.internet import reactor as clock
from twisted.python import log
from twisted.python.failure import Failure
from twisted.web import wsgi


logger = logging.getLogger(__name__)


def log_failed_attempt(request, attempt, elapsed, remaining, pause):
    """Log about a failed attempt to answer the given request."""
    logger.debug(
        "Attempt #%d for %s failed; will retry in %.0fms (%.1fs now elapsed, "
        "%.1fs remaining)", attempt, request.path, pause * 1000.0, elapsed,
        remaining)


def log_final_failed_attempt(request, attempt, elapsed):
    """Log about the final failed attempt to answer the given request."""
    logger.error(
        "Attempt #%d for %s failed; giving up (%.1fs elapsed in total)",
        attempt, request.path, elapsed)


def delete_oauth_nonce(request):
    """Delete the OAuth nonce for the given request from the database.

    This is to allow the exact same request to be retried.
    """
    _, oauth_request = initialize_server_request(request)
    if oauth_request is not None:
        try:
            consumer_key = oauth_request.get_parameter('oauth_consumer_key')
            token_key = oauth_request.get_parameter('oauth_token')
            nonce = oauth_request.get_parameter('oauth_nonce')
        except OAuthError:
            # Missing OAuth parameter: skip Nonce deletion.
            pass
        else:
            Nonce.objects.filter(
                consumer_key=consumer_key, token_key=token_key,
                key=nonce).delete()


def reset_request(request):
    """Return a pristine new request object.

    Use this after a transaction failure, before retrying.

    This is needed so that we don't carry over messages, for example.
    TODO: this assumes we're using the cookies as a container for
    messages; we need to clear the session as well.

    This also resets the input stream.
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


class WebApplicationHandler(WSGIHandler):
    """Request handler that retries when there are serialisation failures.

    :ivar __retry_attempts: The number of times to attempt each request.
    :ivar __retry_timeout: The number of seconds after which this request will
        no longer be considered for a retry.
    :ivar __retry: A weak set containing responses that have been generated as
        a result of a serialization failure.
    """

    def __init__(self, attempts=10, timeout=90.0):
        super(WebApplicationHandler, self).__init__()
        assert attempts >= 1, "The minimum attempts is 1, not %d" % attempts
        self.__retry_attempts = attempts
        self.__retry_timeout = timeout
        self.__retry = WeakSet()

    def handle_uncaught_exception(self, request, resolver, exc_info):
        """Override `BaseHandler.handle_uncaught_exception`.

        If a serialization failure is detected, a retry is requested. It's up
        to ``get_response`` to actually do the retry.
        """
        upcall = super(WebApplicationHandler, self).handle_uncaught_exception
        response = upcall(request, resolver, exc_info)
        # Add it to the retry set if this response was caused by a
        # serialization failure.
        exc_type, exc_value, exc_traceback = exc_info
        if is_serialization_failure(exc_value):
            self.__retry.add(response)
        else:
            # Log the error to the regiond.log.
            failure = Failure(
                exc_value=exc_value, exc_type=exc_type, exc_tb=exc_traceback)
            log.err(failure, _why="500 Error - %s" % request.path)
        # Return the response regardless. This means that we'll get Django's
        # error page when there's a persistent serialization failure.
        return response

    def get_response(self, request):
        """Override `BaseHandler.get_response`.

        Wrap Django's default get_response(). Middleware and templates will
        thus also run within the same transaction, but streaming responses
        will *not* run within the same transaction, or any transaction at all
        by default.
        """
        django_get_response = super(WebApplicationHandler, self).get_response

        def get_response(request):
            # Up-call to Django's get_response() in a transaction. This
            # transaction may fail because of a serialization conflict, so
            # pass errors to handle_uncaught_exception().
            try:
                with post_commit_hooks:
                    with transaction.atomic():
                        return django_get_response(request)
            except SystemExit:
                # Allow sys.exit() to actually exit, reproducing behaviour
                # found in Django's BaseHandler.
                raise
            except:
                # Catch *everything* else, also reproducing behaviour found in
                # Django's BaseHandler. In practice, we should only really see
                # transaction failures here from the outermost atomic block as
                # all other exceptions are handled by django_get_response. The
                # setting DEBUG_PROPAGATE_EXCEPTIONS upsets this, so be on
                # your guard when tempted to use it.
                signals.got_request_exception.send(
                    sender=self.__class__, request=request)
                return self.handle_uncaught_exception(
                    request, get_resolver(None), sys.exc_info())

        # Attempt to start new transactions for up to `__retry_timeout`
        # seconds, at intervals defined by `gen_retry_intervals`, but don't
        # try more than `__retry_attempts` times.
        retry_intervals = gen_retry_intervals()
        retry_details = retries(self.__retry_timeout, retry_intervals, clock)
        retry_attempts = self.__retry_attempts
        retry_set = self.__retry

        for attempt in count(1):
            response = get_response(request)
            if response in retry_set:
                elapsed, remaining, wait = next(retry_details)
                if attempt == retry_attempts or wait == 0:
                    # Time's up: this was the final attempt.
                    log_final_failed_attempt(request, attempt, elapsed)
                    return response
                # We'll retry after a brief interlude.
                log_failed_attempt(request, attempt, elapsed, remaining, wait)
                delete_oauth_nonce(request)
                request = reset_request(request)
                sleep(wait)
            else:
                return response
