# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Access middleware."""

__all__ = [
    "AccessMiddleware",
    "APIErrorsMiddleware",
    "ExceptionMiddleware",
    ]

from abc import (
    ABCMeta,
    abstractproperty,
)
import http.client
import json
import logging
from pprint import pformat
import sys
import traceback

from crochet import TimeoutError
from django.conf import settings
from django.contrib import messages
from django.core.exceptions import (
    PermissionDenied,
    ValidationError,
)
from django.http import (
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseForbidden,
    HttpResponseRedirect,
)
from django.utils import six
from django.utils.encoding import force_str
from django.utils.http import urlquote_plus
from maasserver import logger
from maasserver.clusterrpc.utils import get_error_message_for_exception
from maasserver.components import (
    discard_persistent_error,
    register_persistent_error,
)
from maasserver.enum import COMPONENT
from maasserver.exceptions import MAASAPIException
from maasserver.models.config import Config
from maasserver.models.node import RackController
from maasserver.rpc import getAllClients
from maasserver.utils.django_urls import reverse
from maasserver.utils.orm import is_retryable_failure
from maasserver.views.combo import MERGE_VIEWS
from provisioningserver.rpc.exceptions import (
    NoConnectionsAvailable,
    PowerActionAlreadyInProgress,
)
from provisioningserver.utils.shell import ExternalProcessError

# 'Retry-After' header sent for httplib.SERVICE_UNAVAILABLE
# responses.
RETRY_AFTER_SERVICE_UNAVAILABLE = 10

SIMPLESTREAMS_URL_PREFIX = '/images-stream/'

PUBLIC_URL_PREFIXES = [
    # Login page: must be visible to anonymous users.
    reverse('login'),
    # Authentication: must be visible to anonymous users.
    reverse('authenticate'),
    # The combo loaders are publicly accessible.
    reverse('combo-yui'),
    reverse('robots'),
    reverse('api-doc'),
    # Metadata service is for use by nodes; no login.
    reverse('metadata'),
    # RPC information is for use by rack controllers; no login.
    reverse('rpc-info'),
    # API meta-information is publicly visible.
    reverse('api_version'),
    reverse('api_v1_error'),
    # API calls are protected by piston.
    settings.API_URL_PREFIX,
    # Static resources are publicly visible.
    settings.STATIC_URL_PREFIX,
    # Boot resources simple streams endpoint; no login.
    SIMPLESTREAMS_URL_PREFIX,
] + [reverse('merge', args=[filename]) for filename in MERGE_VIEWS]


def is_public_path(path_info):
    """Whether a request.path_info is publicly accessible."""
    return any(path_info.startswith(prefix) for prefix in PUBLIC_URL_PREFIXES)


class AccessMiddleware:
    """Protect access to views.

    Most UI views are visible only to logged-in users, but there are pages
    that are accessible to anonymous users (e.g. the login page!) or that
    use other authentication (e.g. the MAAS API, which is managed through
    piston).
    """

    def process_request(self, request):
        if is_public_path(request.path_info):
            return None

        if request.user.is_anonymous:
            return HttpResponseRedirect("%s?next=%s" % (
                reverse('login'), urlquote_plus(request.path)))

        if (not Config.objects.get_config('completed_intro') or
                not request.user.userprofile.completed_intro):
            index_path = reverse('index')
            if (request.path != index_path and
                    request.path != reverse('logout')):
                return HttpResponseRedirect(index_path)


class ExternalComponentsMiddleware:
    """Middleware to check external components at regular intervals."""

    def _check_rack_controller_connectivity(self):
        """Check each rack controller to see if it's connected.

        If any rack controllers are disconnected, add a persistent error.
        """
        controllers = RackController.objects.all()
        connected_ids = {client.ident for client in getAllClients()}
        disconnected_controllers = {
            controller
            for controller in controllers
            if controller.system_id not in connected_ids
        }
        if len(disconnected_controllers) == 0:
            discard_persistent_error(COMPONENT.RACK_CONTROLLERS)
        else:
            if len(disconnected_controllers) == 1:
                message = (
                    "One rack controller is not yet connected to the region")
            else:
                message = (
                    "%d rack controllers are not yet connected to the region"
                    % len(disconnected_controllers))
            message = (
                "%s. Visit the <a href=\"%s#/nodes?tab=controllers\">"
                "rack controllers page</a> for "
                "more information." % (message, reverse('index')))
            register_persistent_error(COMPONENT.RACK_CONTROLLERS, message)

    def process_request(self, request):
        # This middleware hijacks the request to perform checks.  Any
        # error raised during these checks should be caught to avoid
        # disturbing the handling of the request.  Proper error reporting
        # should be handled in the check method itself.
        self._check_rack_controller_connectivity()
        return None


class ExceptionMiddleware(metaclass=ABCMeta):
    """Convert exceptions into appropriate HttpResponse responses.

    For example, a MAASAPINotFound exception processed by a middleware
    based on this class will result in an http 404 response to the client.
    Validation errors become "bad request" responses.

    Use this as a base class for middleware_ classes that apply to
    sub-trees of the http path tree.  Subclass this class, provide a
    `path_prefix`, and register your concrete class in
    settings.MIDDLEWARE_CLASSES.  Exceptions in that sub-tree will then
    come out as HttpResponses, insofar as they map neatly.

    .. middleware: https://docs.djangoproject.com
       /en/dev/topics/http/middleware/
    """

    path_prefix = abstractproperty(
        "Prefix for the paths that this should apply to.")

    def process_exception(self, request, exception):
        """Django middleware callback."""
        if not request.path_info.startswith(self.path_prefix):
            # Not a path we're handling exceptions for.
            return None

        if is_retryable_failure(exception):
            # We never handle retryable failures.
            return None

        encoding = 'utf-8'
        if isinstance(exception, MAASAPIException):
            # Print a traceback if this is a 500 error.
            if (settings.DEBUG or
                    exception.api_error == http.client.INTERNAL_SERVER_ERROR):
                self.log_exception(exception)
            # This type of exception knows how to translate itself into
            # an http response.
            return exception.make_http_response()
        elif isinstance(exception, ValidationError):
            if settings.DEBUG:
                self.log_exception(exception)
            if hasattr(exception, 'message_dict'):
                # Complex validation error with multiple fields:
                # return a json version of the message_dict.
                return HttpResponseBadRequest(
                    json.dumps(exception.message_dict),
                    content_type='application/json')
            else:
                # Simple validation error: return the error message.
                return HttpResponseBadRequest(
                    str(''.join(exception.messages)).encode(encoding),
                    content_type="text/plain; charset=%s" % encoding)
        elif isinstance(exception, PermissionDenied):
            if settings.DEBUG:
                self.log_exception(exception)
            return HttpResponseForbidden(
                content=str(exception).encode(encoding),
                content_type="text/plain; charset=%s" % encoding)
        elif isinstance(exception, ExternalProcessError):
            # Catch problems interacting with processes that the
            # appserver spawns, e.g. rndc.
            #
            # While this is a serious error, it should be a temporary
            # one as the admin should be checking and fixing, or it
            # could be spurious.  There's no way of knowing, so the best
            # course of action is to ask the caller to repeat.
            if settings.DEBUG:
                self.log_exception(exception)
            response = HttpResponse(
                content=str(exception).encode(encoding),
                status=int(http.client.SERVICE_UNAVAILABLE),
                content_type="text/plain; charset=%s" % encoding)
            response['Retry-After'] = (
                RETRY_AFTER_SERVICE_UNAVAILABLE)
            return response
        else:
            # Print a traceback.
            self.log_exception(exception)
            # Return an API-readable "Internal Server Error" response.
            return HttpResponse(
                content=str(exception).encode(encoding),
                status=int(http.client.INTERNAL_SERVER_ERROR),
                content_type="text/plain; charset=%s" % encoding)

    def log_exception(self, exception):
        exc_info = sys.exc_info()
        logger.error(" Exception: %s ".center(79, "#") % str(exception))
        logger.error(''.join(traceback.format_exception(*exc_info)))


class APIErrorsMiddleware(ExceptionMiddleware):
    """Report exceptions from API requests as HTTP error responses."""

    path_prefix = settings.API_URL_PREFIX


class DebuggingLoggerMiddleware:

    log_level = logging.DEBUG

    # Taken straight out of Django 1.8 django.http.request module to improve
    # our debug output on requests (dropped in Django 1.9).
    @classmethod
    def _build_request_repr(
            self, request, path_override=None, GET_override=None,
            POST_override=None, COOKIES_override=None, META_override=None):
        """
        Builds and returns the request's representation string. The request's
        attributes may be overridden by pre-processed values.
        """
        # Since this is called as part of error handling, we need to be very
        # robust against potentially malformed input.
        try:
            get = (pformat(GET_override)
                   if GET_override is not None
                   else pformat(request.GET))
        except Exception:
            get = '<could not parse>'
        if request._post_parse_error:
            post = '<could not parse>'
        else:
            try:
                post = (pformat(POST_override)
                        if POST_override is not None
                        else pformat(request.POST))
            except Exception:
                post = '<could not parse>'
        try:
            cookies = (pformat(COOKIES_override)
                       if COOKIES_override is not None
                       else pformat(request.COOKIES))
        except Exception:
            cookies = '<could not parse>'
        try:
            meta = (pformat(META_override)
                    if META_override is not None
                    else pformat(request.META))
        except Exception:
            meta = '<could not parse>'
        path = path_override if path_override is not None else request.path
        return force_str(
            '<%s\npath:%s,\nGET:%s,\nPOST:%s,\nCOOKIES:%s,\nMETA:%s>' %
            (request.__class__.__name__,
             path,
             six.text_type(get),
             six.text_type(post),
             six.text_type(cookies),
             six.text_type(meta)))

    def process_request(self, request):
        if logger.isEnabledFor(self.log_level):
            header = " Request dump ".center(79, "#")
            logger.log(
                self.log_level, "%s\n%s", header,
                self._build_request_repr(request))
        return None  # Allow request processing to continue unabated.

    def process_response(self, request, response):
        if logger.isEnabledFor(self.log_level):
            header = " Response dump ".center(79, "#")
            content = getattr(response, "content", "{no content}")
            try:
                decoded_content = content.decode('utf-8')
            except UnicodeDecodeError:
                logger.log(
                    self.log_level,
                    "%s\n%s", header, "** non-utf-8 (binary?) content **")
            else:
                logger.log(
                    self.log_level,
                    "%s\n%s", header, decoded_content)
        return response  # Return response unaltered.


class RPCErrorsMiddleware:
    """A middleware for handling RPC errors."""

    handled_exceptions = (
        NoConnectionsAvailable,
        PowerActionAlreadyInProgress,
        TimeoutError,
        )

    def _handle_exception(self, request, exception):
        logging.exception(exception)
        messages.error(
            request,
            "Error: %s" % get_error_message_for_exception(exception))

    def process_exception(self, request, exception):
        if request.path_info.startswith(settings.API_URL_PREFIX):
            # Not a path we're handling exceptions for.
            # APIRPCErrorsMiddleware handles all the API request RPC
            # errors.
            return None

        if not isinstance(exception, self.handled_exceptions):
            # Nothing to do, since we don't care about anything other
            # than handled_exceptions.
            return None

        self._handle_exception(request, exception)
        return HttpResponseRedirect(request.path)


class APIRPCErrorsMiddleware(RPCErrorsMiddleware):
    """A middleware for handling RPC errors in API requests."""

    handled_exceptions = {
        NoConnectionsAvailable: int(http.client.SERVICE_UNAVAILABLE),
        PowerActionAlreadyInProgress: int(http.client.SERVICE_UNAVAILABLE),
        TimeoutError: int(http.client.GATEWAY_TIMEOUT),
        }

    def process_exception(self, request, exception):
        if not request.path_info.startswith(settings.API_URL_PREFIX):
            # Not a path we're handling exceptions for.
            # RPCErrorsMiddleware handles non-API requests.
            return None

        handled_exceptions = self.handled_exceptions.keys()
        if exception.__class__ not in handled_exceptions:
            # This isn't something we handle; allow processing to
            # continue.
            return None

        status = self.handled_exceptions[exception.__class__]
        logging.exception(exception)
        error_message = get_error_message_for_exception(exception)

        encoding = 'utf-8'
        response = HttpResponse(
            content=error_message.encode(encoding), status=status,
            content_type="text/plain; charset=%s" % encoding)
        if status == http.client.SERVICE_UNAVAILABLE:
            response['Retry-After'] = (
                RETRY_AFTER_SERVICE_UNAVAILABLE)
        return response


class CSRFHelperMiddleware:
    """A Middleware to decide whether a request needs to be protected against
    CSRF attacks.

    Requests with a session cookie (i.e. requests for which the basic
    session-based Django authentification is used) will be CSRF protected.
    Requests without this cookie are pure 0-legged API requests and thus don't
    need to use the CSRF protection machinery because each request is signed.
    """

    def process_request(self, request):
        session_cookie = request.COOKIES.get(
            settings.SESSION_COOKIE_NAME, None)
        if session_cookie is None:
            # csrf_processing_done is a field used by Django.  We use it here
            # to bypass the CSRF protection when it's not needed (i.e. when the
            # request is OAuth-authenticated).
            request.csrf_processing_done = True
        return None
