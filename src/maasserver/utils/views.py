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
    'retry_url',
    'RetryView',
]

from inspect import getmodule
from textwrap import dedent

from django import http
from django.conf.urls import url
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


class RetryView:
    """\
    View wrapper that retries when serialization failures occur.

    This will retry %(module)s.%(view)s up to %(retries)d times.

    :ivar original_view: The view passed in.
    :ivar atomic_view: The view, wrapped using Django's atomic mechanism.
    :ivar retries: The number of retries to attempt.
    """

    @classmethod
    def make(cls, view, retries=9, db_alias="default"):
        """Create a new view that will retry `view` when serialization fails.

        :param retries: The number of retries to attempt. The total count of
            potential calls to the view be 1 more than the number of retries.

        :returns: An instance of `cls`.
        """
        non_atomic_requests = getattr(view, '_non_atomic_requests', set())
        if db_alias in non_atomic_requests:
            # This view is marked as non-atomic (i.e. a view that manages
            # transactions manually); return the view unchanged.
            return view
        elif isinstance(view, cls):
            return view
        else:
            atomic_view = transaction.atomic(using=db_alias)(view)
            return cls(view, atomic_view, retries)

    def __init__(self, original_view, atomic_view, retries):
        """See `make`."""
        super(RetryView, self).__init__()
        self.original_view = original_view
        self.atomic_view = atomic_view
        self.retries = retries
        self.__doc__ = dedent(
            self.__doc__ % {
                "module": getmodule(original_view).__name__,
                "view": getattr(original_view, "__name__", original_view),
                "retries": retries,
            }
        )

    def extract_request(self, *args):
        """Extract the request object from the arguments passed to a view.

        The position of the request in the list of arguments is different
        depending on the nature of the view: if the view is a UI view it's
        the first argument and if the view is a piston-based API view, it's
        the second argument.
        """
        if len(args) < 1:
            assert False, (
                "Couldn't find request in arguments (no argument).")
        elif isinstance(args[0], http.HttpRequest):
            # This is a UI view, the request is the first argument.
            return args[0]
        if len(args) < 2:
            assert False, (
                "Couldn't find request in arguments (no second argument).")
        elif isinstance(args[1], http.HttpRequest):
            # This is an API view, the request is the second argument (the
            # handler is the first argument).
            return args[1]
        assert False, "Couldn't find request in arguments."

    def __call__(self, *args, **kwargs):
        """Invoke the wrapped view with retry logic.

        :returns: The response from `self.atomic_view`, or, if the number of
            retries is exceeded, a serialization error.
        """
        for attempt in xrange(1, self.retries + 1):
            try:
                return self.atomic_view(*args, **kwargs)
            except Exception as e:
                if is_serialization_failure(e):
                    request = self.extract_request(*args)
                    log_retry(request, attempt)
                    reset_request(request)
                    continue
                else:
                    raise
        else:
            # Last chance, unadorned by retry logic.
            return self.atomic_view(*args, **kwargs)


def retry_url(regex, view, kwargs=None, name=None, prefix=''):
    """Return a :py:func:`url` with a callback prepared for retries."""
    # Resources with handlers descended from OperationsHandlerMixin have a
    # `decorate` method expressly designed for decorating the exported
    # handlers within. Try to use that before wrapping the entire view.
    try:
        decorate = view.handler.decorate
    except AttributeError:
        view = RetryView.make(view)
    else:
        decorate(RetryView.make)

    return url(regex, view, kwargs=kwargs, name=name, prefix=prefix)
