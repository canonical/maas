# Copyright 2012-2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Exceptions."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "ClusterUnavailable",
    "ExternalComponentException",
    "MAASException",
    "MAASAPIBadRequest",
    "MAASAPIException",
    "MAASAPINotFound",
    "NodeStateViolation",
    "NodeGroupMisconfiguration",
    "IteratorReusedError",
    "PowerProblem",
    "StaticIPAddressExhaustion",
    "StaticIPAddressTypeClash",
    "UnresolvableHost",
    ]


import httplib

from django.http import (
    HttpResponse,
    HttpResponseRedirect,
    )


class MAASException(Exception):
    """Base class for MAAS' exceptions."""


class CannotDeleteUserException(Exception):
    """User can't be deleted."""


class MAASAPIException(Exception):
    """Base class for MAAS' API exceptions.

    :ivar api_error: The HTTP code that should be returned when this error
        is raised in the API (defaults to 500: "Internal Server Error").

    """
    api_error = httplib.INTERNAL_SERVER_ERROR

    def make_http_response(self):
        """Create an :class:`HttpResponse` representing this exception."""
        encoding = b'utf-8'
        return HttpResponse(
            status=self.api_error, content=unicode(self).encode(encoding),
            mimetype=b"text/plain; charset=%s" % encoding)


class ExternalComponentException(MAASAPIException):
    """An external component failed."""


class MAASAPIBadRequest(MAASAPIException):
    api_error = httplib.BAD_REQUEST


class MAASAPINotFound(MAASAPIException):
    api_error = httplib.NOT_FOUND


class MAASAPIForbidden(MAASAPIException):
    api_error = httplib.FORBIDDEN


class Unauthorized(MAASAPIException):
    """HTTP error 401: Unauthorized.  Login required."""
    api_error = httplib.UNAUTHORIZED


class NodeStateViolation(MAASAPIException):
    """Operation on node not possible given node's current state."""
    api_error = httplib.CONFLICT


class NodesNotAvailable(NodeStateViolation):
    """Requested node(s) are not available to be acquired."""
    api_error = httplib.CONFLICT


class Redirect(MAASAPIException):
    """Redirect.  The exception message is the target URL."""
    api_error = httplib.FOUND

    def make_http_response(self):
        return HttpResponseRedirect(unicode(self))


class NodeGroupMisconfiguration(MAASAPIException):
    """Node Groups (aka Cluster Controllers) are misconfigured.

    This might mean that more than one controller is marked as managing the
    same network
    """
    api_error = httplib.CONFLICT


class ClusterUnavailable(MAASAPIException):
    """A Cluster Controller is not available for RPC queries."""
    api_error = httplib.SERVICE_UNAVAILABLE


class IteratorReusedError(Exception):
    """Raise when a :class:`UseOnceIterator` gets reused."""


class StaticIPAddressExhaustion(MAASAPIException):
    """Raised when no more static IPs are available during allocation."""
    api_error = httplib.SERVICE_UNAVAILABLE


class StaticIPAddressUnavailable(MAASAPIException):
    """Raised when a requested IP is not available."""
    api_error = httplib.NOT_FOUND


class StaticIPAddressOutOfRange(MAASAPIException):
    """Raised when a requested IP is not in an acceptable range."""
    api_error = httplib.FORBIDDEN


class StaticIPAddressTypeClash(MAASAPIException):
    """Raised when trying to allocate an IP for a MAC where one of another
    type already exists."""
    api_error = httplib.CONFLICT


class StaticIPAlreadyExistsForMACAddress(MAASAPIException):
    """Raised when trying to allocate a static IP for a non-node MAC
    where a node with that MAC already exists."""
    api_error = httplib.CONFLICT


class NodeActionError(MAASException):
    """Raised when there is an error performing a NodeAction."""

    def __init__(self, error):
        # Avoid circular imports.
        from maasserver.clusterrpc.utils import (
            get_error_message_for_exception)
        if isinstance(error, Exception):
            super(NodeActionError, self).__init__(
                get_error_message_for_exception(error))
        else:
            super(NodeActionError, self).__init__(error)


class UnresolvableHost(MAASException):
    """Raised when a hostname can't be resolved to an IP address."""


class MissingBootImage(MAASException):
    """Raised when a boot image is expected to exists."""


class PreseedError(MAASException):
    """Raised when issue generating the preseed."""


class PowerProblem(MAASAPIException):
    """Raised when there's a problem with a power operation.

    This could be a problem with parameters, a problem with the power
    controller, or something else.  The exception text will contain more
    information.
    """
    api_error = httplib.SERVICE_UNAVAILABLE
