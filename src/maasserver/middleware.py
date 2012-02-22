# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from __future__ import (
    print_function,
    unicode_literals,
    )

"""Access middleware."""

__metaclass__ = type
__all__ = [
    "AccessMiddleware",
    "APIErrorsMiddleware",
    "ExceptionMiddleware",
    ]

from abc import (
    ABCMeta,
    abstractproperty,
    )
import json
import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.urlresolvers import reverse
from django.http import (
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseRedirect,
    )
from django.utils.http import urlquote_plus
from maasserver.exceptions import MaasAPIException


class AccessMiddleware:
    """Protect access to views.

    Most UI views are visible only to logged-in users, but there are pages
    that are accessible to anonymous users (e.g. the login page!) or that
    use other authentication (e.g. the MaaS API, which is managed through
    piston).
    """

    def __init__(self):
        # URL prefixes that do not require authentication by Django.
        public_url_roots = [
            # Login/logout pages: must be visible to anonymous users.
            reverse('login'),
            reverse('logout'),
            # Static resources are publicly visible.
            settings.STATIC_URL,
            reverse('favicon'),
            reverse('robots'),
            reverse('api-doc'),
            # Metadata service is for use by nodes; no login.
            reverse('metadata'),
            # API calls are protected by piston.
            settings.API_URL_REGEXP,
            ]
        self.public_urls = re.compile("|".join(public_url_roots))
        self.login_url = reverse('login')

    def process_request(self, request):
        # Public urls.
        if self.public_urls.match(request.path):
            return None
        else:
            if request.user.is_anonymous():
                return HttpResponseRedirect("%s?next=%s" % (
                    self.login_url, urlquote_plus(request.path)))
            else:
                return None


class ExceptionMiddleware:
    """Convert exceptions into appropriate HttpResponse responses.

    For example, a MaasAPINotFound exception processed by a middleware
    based on this class will result in an http 404 response to the client.
    Validation errors become "bad request" responses.

    Use this as a base class for middleware_ classes that apply to
    sub-trees of the http path tree.  Subclass this class, provide a
    `path_regex`, and register your concrete class in
    settings.MIDDLEWARE_CLASSES.  Exceptions in that sub-tree will then
    come out as HttpResponses, insofar as they map neatly.

    .. middleware: https://docs.djangoproject.com
       /en/dev/topics/http/middleware/
    """

    __metaclass__ = ABCMeta

    path_regex = abstractproperty(
        "Regular expression for the paths that this should apply to.")

    def __init__(self):
        self.path_matcher = re.compile(self.path_regex)

    def process_exception(self, request, exception):
        """Django middleware callback."""
        if not self.path_matcher.match(request.path):
            # Not a path we're handling exceptions for.
            return None

        encoding = b'utf-8'
        if isinstance(exception, MaasAPIException):
            # The exception is a MaasAPIException: exception.api_error
            # will give us the proper error type.
            return HttpResponse(
                content=unicode(exception).encode(encoding),
                status=exception.api_error,
                mimetype=b"text/plain; charset=%s" % encoding)
        elif isinstance(exception, ValidationError):
            if hasattr(exception, 'message_dict'):
                # Complex validation error with multiple fields:
                # return a json version of the message_dict.
                return HttpResponseBadRequest(
                    json.dumps(exception.message_dict),
                    content_type='application/json')
            else:
                # Simple validation error: return the error message.
                return HttpResponseBadRequest(
                    unicode(''.join(exception.messages)).encode(encoding),
                    mimetype=b"text/plain; charset=%s" % encoding)
        else:
            # Do not handle the exception, this will result in a
            # "Internal Server Error" response.
            return None


class APIErrorsMiddleware(ExceptionMiddleware):
    """Report exceptions from API requests as HTTP error responses."""

    path_regex = settings.API_URL_REGEXP


class ConsoleExceptionMiddleware:
    def process_exception(self, request, exception):
        import traceback
        import sys
        exc_info = sys.exc_info()
        print(" Exception ".center(79, "#"))
        print(''.join(traceback.format_exception(*exc_info)))
        print("#" * 79)
