# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Access middleware."""


from dataclasses import dataclass
import http.client
import json
import logging
from pprint import pformat
import sys
import traceback

from crochet import TimeoutError
from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.handlers.exception import get_exception_response
from django.http import (
    Http404,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseForbidden,
    HttpResponseRedirect,
)
from django.urls import get_resolver, get_urlconf, reverse
from django.utils.encoding import force_str
from django.utils.http import urlquote_plus

from maasserver import logger
from maasserver.clusterrpc.utils import get_error_message_for_exception
from maasserver.exceptions import MAASAPIException
from maasserver.rbac import rbac
from maasserver.secrets import SecretManager
from maasserver.utils.orm import is_retryable_failure
from provisioningserver.rpc.exceptions import (
    NoConnectionsAvailable,
    PowerActionAlreadyInProgress,
)
from provisioningserver.utils.shell import ExternalProcessError

# 'Retry-After' header sent for httplib.SERVICE_UNAVAILABLE
# responses.
RETRY_AFTER_SERVICE_UNAVAILABLE = 10

PUBLIC_URL_PREFIXES = [
    # Login page: must be visible to anonymous users.
    reverse("login"),
    # Authentication: must be visible to anonymous users.
    reverse("authenticate"),
    reverse("discharge-request"),
    # CSRF: only usable by logged in users, but returns FORBIDDEN instead of
    # a redirect to the login page on request of an unauthenticated user.
    reverse("csrf"),
    # The combo loaders are publicly accessible.
    reverse("robots"),
    # Metadata service is for use by nodes; no login.
    reverse("metadata"),
    # RPC information is for use by rack controllers; no login.
    reverse("rpc-info"),
    # Script to run commissioning scripts manually on a machine
    reverse("maas-run-scripts"),
    # Prometheus metrics with usage stats
    reverse("metrics"),
    # VM host certificates are publicly accessible
    "/MAAS/vmhost-certificate",
    # API meta-information is publicly visible.
    reverse("api_version"),
    reverse("api_v1_error"),
    # API calls are protected by piston.
    settings.API_URL_PREFIX,
    # Boot resources simple streams endpoint; no login.
    settings.SIMPLESTREAMS_URL_PREFIX,
]


def is_public_path(path):
    """Whether a request.path is publicly accessible."""
    return any(path.startswith(prefix) for prefix in PUBLIC_URL_PREFIXES)


class AccessMiddleware:
    """Protect access to views.

    Most UI views are visible only to logged-in users, but there are pages
    that are accessible to anonymous users (e.g. the login page!) or that
    use other authentication (e.g. the MAAS API, which is managed through
    piston).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if is_public_path(request.path):
            return self.get_response(request)

        if request.user.is_anonymous:
            return HttpResponseRedirect(
                "/MAAS/?next=%s" % urlquote_plus(request.path)
            )

        return self.get_response(request)


class ExceptionMiddleware:
    """Convert exceptions into appropriate HttpResponse responses.

    For example, a MAASAPINotFound exception processed by a middleware
    based on this class will result in an http 404 response to the client.
    Validation errors become "bad request" responses.

    .. middleware: https://docs.djangoproject.com
       /en/dev/topics/http/middleware/
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            return self.get_response(request)
        except Exception as exception:
            response = self.process_exception(request, exception)
            if response:
                return response
            else:
                raise

    def process_exception(self, request, exception):
        encoding = "utf-8"
        if isinstance(exception, MAASAPIException):
            # Print a traceback if this is a 500 error.
            if (
                settings.DEBUG
                or exception.api_error == http.client.INTERNAL_SERVER_ERROR
            ):
                self.log_exception(exception)
            # This type of exception knows how to translate itself into
            # an http response.
            return exception.make_http_response()
        elif isinstance(exception, ValidationError):
            if settings.DEBUG:
                self.log_exception(exception)
            if hasattr(exception, "message_dict"):
                # Complex validation error with multiple fields:
                # return a json version of the message_dict.
                return HttpResponseBadRequest(
                    json.dumps(exception.message_dict),
                    content_type="application/json",
                )
            else:
                # Simple validation error: return the error message.
                return HttpResponseBadRequest(
                    str("".join(exception.messages)).encode(encoding),
                    content_type="text/plain; charset=%s" % encoding,
                )
        elif isinstance(exception, PermissionDenied):
            if settings.DEBUG:
                self.log_exception(exception)
            return HttpResponseForbidden(
                content=str(exception).encode(encoding),
                content_type="text/plain; charset=%s" % encoding,
            )
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
                content_type="text/plain; charset=%s" % encoding,
            )
            response["Retry-After"] = RETRY_AFTER_SERVICE_UNAVAILABLE
            return response
        elif isinstance(exception, Http404):
            if settings.DEBUG:
                self.log_exception(exception)
            return get_exception_response(
                request, get_resolver(get_urlconf()), 404, exception
            )
        elif is_retryable_failure(exception):
            # We never handle retryable failures.
            return None
        elif isinstance(exception, SystemExit):
            return None
        else:
            # Print a traceback.
            self.log_exception(exception)
            # Return an API-readable "Internal Server Error" response.
            return HttpResponse(
                content=str(exception).encode(encoding),
                status=int(http.client.INTERNAL_SERVER_ERROR),
                content_type="text/plain; charset=%s" % encoding,
            )

    def log_exception(self, exception):
        exc_info = sys.exc_info()
        logger.error(" Exception: %s ".center(79, "#") % str(exception))
        logger.error("".join(traceback.format_exception(*exc_info)))


class DebuggingLoggerMiddleware:
    log_level = logging.DEBUG

    def __init__(self, get_response):
        self.get_response = get_response

    # Taken straight out of Django 1.8 django.http.request module to improve
    # our debug output on requests (dropped in Django 1.9).
    @classmethod
    def _build_request_repr(
        self,
        request,
        path_override=None,
        GET_override=None,
        POST_override=None,
        COOKIES_override=None,
        META_override=None,
    ):
        """
        Builds and returns the request's representation string. The request's
        attributes may be overridden by pre-processed values.
        """
        # Since this is called as part of error handling, we need to be very
        # robust against potentially malformed input.
        try:
            get = (
                pformat(GET_override)
                if GET_override is not None
                else pformat(request.GET)
            )
        except Exception:
            get = "<could not parse>"
        try:
            post = (
                pformat(POST_override)
                if POST_override is not None
                else pformat(request.POST)
            )
        except Exception:
            post = "<could not parse>"
        try:
            cookies = (
                pformat(COOKIES_override)
                if COOKIES_override is not None
                else pformat(request.COOKIES)
            )
        except Exception:
            cookies = "<could not parse>"
        try:
            meta = (
                pformat(META_override)
                if META_override is not None
                else pformat(request.META)
            )
        except Exception:
            meta = "<could not parse>"
        path = path_override if path_override is not None else request.path
        name = request.__class__.__name__
        return force_str(
            f"<{name}\npath:{path},\nGET:{get},\nPOST:{post},\nCOOKIES:{cookies},\nMETA:{meta}>"
        )

    def __call__(self, request):
        if settings.DEBUG_HTTP and logger.isEnabledFor(self.log_level):
            header = " Request dump ".center(79, "#")
            logger.log(
                self.log_level,
                "%s\n%s",
                header,
                self._build_request_repr(request),
            )
        response = self.get_response(request)
        if settings.DEBUG_HTTP and logger.isEnabledFor(self.log_level):
            header = " Response dump ".center(79, "#")
            content = getattr(response, "content", b"{no content}")
            try:
                decoded_content = content.decode("utf-8")
            except UnicodeDecodeError:
                logger.log(
                    self.log_level,
                    "%s\n%s",
                    header,
                    "** non-utf-8 (binary?) content **",
                )
            else:
                logger.log(self.log_level, "%s\n%s", header, decoded_content)
        return response


class RPCErrorsMiddleware:
    """A middleware for handling RPC errors."""

    handled_exceptions = (
        NoConnectionsAvailable,
        PowerActionAlreadyInProgress,
        TimeoutError,
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            return self.get_response(request)
        except Exception as exception:
            response = self.process_exception(request, exception)
            if response:
                return response
            else:
                raise

    def process_exception(self, request, exception):
        if request.path.startswith(settings.API_URL_PREFIX):
            # Not a path we're handling exceptions for.
            # APIRPCErrorsMiddleware handles all the API request RPC
            # errors.
            return None

        if not isinstance(exception, self.handled_exceptions):
            # Nothing to do, since we don't care about anything other
            # than handled_exceptions.
            return None

        logging.exception(exception)
        return HttpResponseRedirect(request.path)


class APIRPCErrorsMiddleware(RPCErrorsMiddleware):
    """A middleware for handling RPC errors in API requests."""

    handled_exceptions = {
        NoConnectionsAvailable: int(http.client.SERVICE_UNAVAILABLE),
        PowerActionAlreadyInProgress: int(http.client.SERVICE_UNAVAILABLE),
        TimeoutError: int(http.client.GATEWAY_TIMEOUT),
    }

    def process_exception(self, request, exception):
        if not request.path.startswith(settings.API_URL_PREFIX):
            # Not a path we're handling exceptions for.
            # RPCErrorsMiddleware handles non-API requests.
            return None

        if exception.__class__ not in self.handled_exceptions:
            # This isn't something we handle; allow processing to
            # continue.
            return None

        status = self.handled_exceptions[exception.__class__]
        logging.exception(exception)
        error_message = get_error_message_for_exception(exception)

        encoding = "utf-8"
        response = HttpResponse(
            content=error_message.encode(encoding),
            status=status,
            content_type="text/plain; charset=%s" % encoding,
        )
        if status == http.client.SERVICE_UNAVAILABLE:
            response["Retry-After"] = RETRY_AFTER_SERVICE_UNAVAILABLE
        return response


class CSRFHelperMiddleware:
    """A Middleware to decide whether a request needs to be protected against
    CSRF attacks.

    Requests with a session cookie (i.e. requests for which the basic
    session-based Django authentification is used) will be CSRF protected.
    Requests without this cookie are pure 0-legged API requests and thus don't
    need to use the CSRF protection machinery because each request is signed.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        session_cookie = request.COOKIES.get(
            settings.SESSION_COOKIE_NAME, None
        )
        if session_cookie is None:
            # csrf_processing_done is a field used by Django.  We use it here
            # to bypass the CSRF protection when it's not needed (i.e. when the
            # request is OAuth-authenticated).
            request.csrf_processing_done = True
        return self.get_response(request)


@dataclass
class ExternalAuthInfo:
    """Hold information about external authentication."""

    type: str
    url: str
    domain: str = ""
    admin_group: str = ""


class ExternalAuthInfoMiddleware:
    """A Middleware adding information about the external authentication.

    This adds an `external_auth_info` attribute to the request, which is an
    ExternalAuthInfo instance if external authentication is enabled, None
    otherwise.

    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.external_auth_info = self._get_external_auth_info(request)
        return self.get_response(request)

    def _get_external_auth_info(self, request):
        config = SecretManager().get_composite_secret(
            "external-auth", default={}
        )
        candid_endpoint = config.get("url", "")
        rbac_endpoint = config.get("rbac-url", "")
        auth_domain = config.get("domain", "")
        auth_admin_group = config.get("admin-group", "")
        if rbac_endpoint:
            auth_type = "rbac"
            auth_endpoint = rbac_endpoint.rstrip("/") + "/auth"
            # not used, ensure they're unset
            auth_domain = ""
            auth_admin_group = ""
        elif candid_endpoint:
            auth_type = "candid"
            auth_endpoint = candid_endpoint
        else:
            return None

        # strip trailing slashes as otherwise js-bakery ends up using double
        # slashes in the URL
        return ExternalAuthInfo(
            type=auth_type,
            url=auth_endpoint.rstrip("/"),
            domain=auth_domain,
            admin_group=auth_admin_group,
        )


class RBACMiddleware:
    """Middleware that cleans the RBAC thread-local cache.


    At the end of each request the RBAC client that is held in the thread-local
    needs to be cleaned up. That way the next request on the same thread will
    use a new RBAC client.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        result = self.get_response(request)
        # Now that the response has been handled, clear the thread-local
        # state of the RBAC connection.
        rbac.clear()
        return result
