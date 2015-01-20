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

import sys
from weakref import WeakSet

from django.core import signals
from django.core.handlers.wsgi import WSGIHandler
from django.core.urlresolvers import get_resolver
from django.db import transaction
from maasserver.utils.orm import is_serialization_failure
from provisioningserver.logger.log import get_maas_logger


maaslog = get_maas_logger("views")


def log_retry(request, attempt):
    """Log a message about retrying the given request."""
    maaslog.warning("Retry #%d for %s", attempt, request.path)


def reset_request(request):
    """Undo non-transaction changes to the request.

    Clear any message from the previous attempt. TODO: this assumes
    we're using the cookies as a container for messages; we need to
    clear the session as well.
    """
    request.COOKIES.pop('messages', None)


class WebApplicationHandler(WSGIHandler):
    """Request handler that retries when there are serialisation failures.

    :ivar __attempts: The number of times to attempt each request.
    :ivar __retry: A weak set containing responses that have been generated as
        a result of a serialization failure.
    """

    def __init__(self, attempts=10):
        super(WebApplicationHandler, self).__init__()
        self.__attempts = attempts
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

        # Loop up to (attempts - 1) times.
        for attempt in xrange(1, self.__attempts):
            response = get_response(request)
            if response in self.__retry:
                log_retry(request, attempt)
                reset_request(request)
                continue
            else:
                return response
        else:
            # Last chance, unadorned by retry logic.
            return get_response(request)
