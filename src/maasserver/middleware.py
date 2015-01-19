# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

"""Access middleware."""

str = None

__metaclass__ = type
__all__ = [
    "AccessMiddleware",
    "APIErrorsMiddleware",
    "ErrorsMiddleware",
    "ExceptionMiddleware",
    ]

from abc import (
    ABCMeta,
    abstractproperty,
    )
import httplib
import json
import logging
import re
import sys
import traceback

from crochet import TimeoutError
from django.conf import settings
from django.contrib import messages
from django.core.exceptions import (
    PermissionDenied,
    ValidationError,
    )
from django.core.urlresolvers import reverse
from django.http import (
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseForbidden,
    HttpResponseRedirect,
    )
from django.utils.http import urlquote_plus
from maasserver import logger
from maasserver.bootresources import SIMPLESTREAMS_URL_REGEXP
from maasserver.clusterrpc.utils import get_error_message_for_exception
from maasserver.components import (
    discard_persistent_error,
    register_persistent_error,
    )
from maasserver.enum import (
    COMPONENT,
    NODEGROUP_STATUS,
    )
from maasserver.exceptions import (
    ExternalComponentException,
    MAASAPIException,
    )
from maasserver.models.nodegroup import NodeGroup
from maasserver.rpc import getAllClients
from maasserver.utils.orm import is_serialization_failure
from provisioningserver.rpc.exceptions import (
    MultipleFailures,
    NoConnectionsAvailable,
    PowerActionAlreadyInProgress,
    )
from provisioningserver.utils.shell import ExternalProcessError


try:
    from django.http.request import build_request_repr
except ImportError:
    # build_request_repr is only used for debugging: use
    # a degraded version if build_request_repr is not
    # available (i.e. if Django version < 1.5).
    build_request_repr = repr


class AccessMiddleware:
    """Protect access to views.

    Most UI views are visible only to logged-in users, but there are pages
    that are accessible to anonymous users (e.g. the login page!) or that
    use other authentication (e.g. the MAAS API, which is managed through
    piston).
    """

    def __init__(self):
        # URL prefixes that do not require authentication by Django.
        public_url_roots = [
            # Login page: must be visible to anonymous users.
            reverse('login'),
            # The combo loaders are publicly accessible.
            reverse('combo-yui'),
            reverse('combo-maas'),
            reverse('combo-raphael'),
            # Static resources are publicly visible.
            settings.STATIC_URL_PATTERN,
            reverse('robots'),
            reverse('api-doc'),
            # Metadata service is for use by nodes; no login.
            reverse('metadata'),
            # RPC information is for use by clusters; no login.
            reverse('rpc-info'),
            # Boot resources simple streams endpoint; no login.
            SIMPLESTREAMS_URL_REGEXP,
            # API calls are protected by piston.
            settings.API_URL_REGEXP,
            ]
        self.public_urls = re.compile("|".join(public_url_roots))
        self.login_url = reverse('login')

    def process_request(self, request):
        # Public urls.
        if self.public_urls.match(request.path_info):
            return None
        else:
            if request.user.is_anonymous():
                return HttpResponseRedirect("%s?next=%s" % (
                    reverse('login'), urlquote_plus(request.path)))
            else:
                return None


class ExternalComponentsMiddleware:
    """Middleware to check external components at regular intervals."""

    def _check_cluster_connectivity(self):
        """Check each accepted cluster to see if it's connected.

        If any clusters are disconnected, add a persistent error.
        """
        clusters = NodeGroup.objects.filter(status=NODEGROUP_STATUS.ACCEPTED)
        connected_cluster_uuids = {client.ident for client in getAllClients()}
        disconnected_clusters = {
            cluster for cluster in clusters
            if cluster.uuid not in connected_cluster_uuids
        }
        if len(disconnected_clusters) == 0:
            discard_persistent_error(COMPONENT.CLUSTERS)
        else:
            if len(disconnected_clusters) == 1:
                message = (
                    "One cluster is not yet connected to the region")
            else:
                message = (
                    "%d clusters are not yet connected to the region"
                    % len(disconnected_clusters))
            message = (
                "%s. Visit the <a href=\"%s\">clusters page</a> for more "
                "information." % (message, reverse('cluster-list')))
            register_persistent_error(COMPONENT.CLUSTERS, message)

    def process_request(self, request):
        # This middleware hijacks the request to perform checks.  Any
        # error raised during these checks should be caught to avoid
        # disturbing the handling of the request.  Proper error reporting
        # should be handled in the check method itself.
        self._check_cluster_connectivity()
        return None


class ExceptionMiddleware:
    """Convert exceptions into appropriate HttpResponse responses.

    For example, a MAASAPINotFound exception processed by a middleware
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
        if not self.path_matcher.match(request.path_info):
            # Not a path we're handling exceptions for.
            return None

        if is_serialization_failure(exception):
            # We never handle serialization failures.
            return None

        encoding = b'utf-8'
        if isinstance(exception, MAASAPIException):
            # Print a traceback if this is a 500 error.
            if exception.api_error == httplib.INTERNAL_SERVER_ERROR:
                self.log_exception(exception)
            # This type of exception knows how to translate itself into
            # an http response.
            return exception.make_http_response()
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
        elif isinstance(exception, PermissionDenied):
            return HttpResponseForbidden(
                content=unicode(exception).encode(encoding),
                mimetype=b"text/plain; charset=%s" % encoding)
        elif isinstance(exception, ExternalProcessError):
            # Catch problems interacting with processes that the
            # appserver spawns, e.g. rndc.
            #
            # While this is a serious error, it should be a temporary
            # one as the admin should be checking and fixing, or it
            # could be spurious.  There's no way of knowing, so the best
            # course of action is to ask the caller to repeat.
            response = HttpResponse(
                content=unicode(exception).encode(encoding),
                status=httplib.SERVICE_UNAVAILABLE,
                mimetype=b"text/plain; charset=%s" % encoding)
            response['Retry-After'] = (
                self.RETRY_AFTER_SERVICE_UNAVAILABLE)
            return response
        else:
            # Print a traceback.
            self.log_exception(exception)
            # Return an API-readable "Internal Server Error" response.
            return HttpResponse(
                content=unicode(exception).encode(encoding),
                status=httplib.INTERNAL_SERVER_ERROR,
                mimetype=b"text/plain; charset=%s" % encoding)

    def log_exception(self, exception):
        exc_info = sys.exc_info()
        logger.error(" Exception: %s ".center(79, "#") % unicode(exception))
        logger.error(''.join(traceback.format_exception(*exc_info)))


class APIErrorsMiddleware(ExceptionMiddleware):
    """Report exceptions from API requests as HTTP error responses."""

    path_regex = settings.API_URL_REGEXP


class ErrorsMiddleware:
    """Handle ExternalComponentException exceptions in POST requests: add a
    message with the error string and redirect to the same page (using GET).
    """

    def process_exception(self, request, exception):
        should_process_exception = (
            request.method == 'POST' and
            isinstance(exception, ExternalComponentException))
        if should_process_exception:
            messages.error(request, unicode(exception))
            return HttpResponseRedirect(request.path)
        else:
            # Not an ExternalComponentException or not a POST request: do not
            # handle it.
            return None


class DebuggingLoggerMiddleware:

    log_level = logging.DEBUG

    def process_request(self, request):
        if logger.isEnabledFor(self.log_level):
            header = " Request dump ".center(79, "#")
            logger.log(
                self.log_level,
                "%s\n%s", header, build_request_repr(request))
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
        MultipleFailures,
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
        path_matcher = re.compile(settings.API_URL_REGEXP)
        if path_matcher.match(request.path_info):
            # Not a path we're handling exceptions for.
            # APIRPCErrorsMiddleware handles all the API request RPC
            # errors.
            return None

        if not isinstance(exception, self.handled_exceptions):
            # Nothing to do, since we don't care about anything other
            # than MultipleFailures and handled_exceptions.
            return None

        if isinstance(exception, MultipleFailures):
            exceptions = [
                failure.value for failure in exception.args]
            for exception in exceptions:
                self._handle_exception(request, exception)
        else:
            self._handle_exception(request, exception)
        return HttpResponseRedirect(request.path)


class APIRPCErrorsMiddleware(RPCErrorsMiddleware):
    """A middleware for handling RPC errors in API requests."""

    handled_exceptions = {
        NoConnectionsAvailable: httplib.SERVICE_UNAVAILABLE,
        PowerActionAlreadyInProgress: httplib.SERVICE_UNAVAILABLE,
        MultipleFailures: httplib.INTERNAL_SERVER_ERROR,
        TimeoutError: httplib.GATEWAY_TIMEOUT,
        }

    # Default 'Retry-After' header sent for httplib.SERVICE_UNAVAILABLE
    # responses.
    RETRY_AFTER_SERVICE_UNAVAILABLE = 10

    def process_exception(self, request, exception):
        path_matcher = re.compile(settings.API_URL_REGEXP)
        if not path_matcher.match(request.path_info):
            # Not a path we're handling exceptions for.
            # RPCErrorsMiddleware handles non-API requests.
            return None

        handled_exceptions = self.handled_exceptions.viewkeys()
        if exception.__class__ not in handled_exceptions:
            # This isn't something we handle; allow processing to
            # continue.
            return None

        status = self.handled_exceptions[exception.__class__]
        if isinstance(exception, MultipleFailures):
            # If only one exception has been raised, process this exception:
            # this allows MAAS to convert this exception into the proper
            # type of response (e.g. 503) instead of the 500 response that
            # MultipleFailures is transformed into.
            if len(exception.args) == 1:
                return self.process_exception(request, exception.args[0].value)
            for failure in exception.args:
                logging.exception(exception)
            error_message = "\n".join(
                get_error_message_for_exception(failure.value)
                for failure in exception.args)
        else:
            logging.exception(exception)
            error_message = get_error_message_for_exception(exception)

        encoding = b'utf-8'
        response = HttpResponse(
            content=error_message.encode(encoding), status=status,
            mimetype=b"text/plain; charset=%s" % encoding)
        if status == httplib.SERVICE_UNAVAILABLE:
            response['Retry-After'] = (
                self.RETRY_AFTER_SERVICE_UNAVAILABLE)
        return response
