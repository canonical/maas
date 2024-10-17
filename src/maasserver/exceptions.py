# Copyright 2012-2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Exceptions."""

__all__ = [
    "ClusterUnavailable",
    "MAASException",
    "MAASAPIBadRequest",
    "MAASAPIException",
    "MAASAPINotFound",
    "NodeStateViolation",
    "NodeGroupMisconfiguration",
    "NoScriptsFound",
    "IteratorReusedError",
    "PowerProblem",
    "StaticIPAddressExhaustion",
    "StaticIPAddressTypeClash",
    "UnresolvableHost",
]

import http.client
import json

from django.core.exceptions import ValidationError
from django.http import HttpResponse, HttpResponseRedirect


class MAASException(Exception):
    """Base class for MAAS' exceptions."""


class CannotDeleteUserException(Exception):
    """User can't be deleted."""


class MAASAPIException(Exception):
    """Base class for MAAS' API exceptions.

    :ivar api_error: The HTTP code that should be returned when this error
        is raised in the API (defaults to 500: "Internal Server Error").

    """

    api_error = int(http.client.INTERNAL_SERVER_ERROR)

    def make_http_response(self):
        """Create an :class:`HttpResponse` representing this exception."""
        encoding = "utf-8"
        return HttpResponse(
            status=self.api_error,
            content=str(self).encode(encoding),
            content_type="text/plain; charset=%s" % encoding,
        )


class MAASAPIBadRequest(MAASAPIException):
    api_error = int(http.client.BAD_REQUEST)


class MAASAPINotFound(MAASAPIException):
    api_error = int(http.client.NOT_FOUND)


class MAASAPIForbidden(MAASAPIException):
    api_error = int(http.client.FORBIDDEN)


class MAASAPIValidationError(MAASAPIBadRequest, ValidationError):
    """A validation error raised during a MAAS API request."""

    def make_http_response(self):
        """Create an :class:`HttpResponse` representing this exception."""
        content_type = b"application/json"
        if hasattr(self, "error_dict"):
            messages = json.dumps(self.message_dict)
        elif len(self.messages) == 1:
            messages = self.messages[0]
            content_type = b"text/plain"
        else:
            messages = json.dumps(self.messages)

        encoding = b"utf-8"
        return HttpResponse(
            status=self.api_error,
            content=messages,
            content_type=b"%s; charset=%s" % (content_type, encoding),
        )


class Unauthorized(MAASAPIException):
    """HTTP error 401: Unauthorized.  Login required."""

    api_error = int(http.client.UNAUTHORIZED)


class NodeStateViolation(MAASAPIException):
    """Operation on node not possible given node's current state."""

    api_error = int(http.client.CONFLICT)


class NodesNotAvailable(NodeStateViolation):
    """Requested node(s) are not available to be acquired."""

    api_error = int(http.client.CONFLICT)


class Redirect(MAASAPIException):
    """Redirect.  The exception message is the target URL."""

    api_error = int(http.client.FOUND)

    def make_http_response(self):
        return HttpResponseRedirect(str(self))


class NodeGroupMisconfiguration(MAASAPIException):
    """Node Groups (aka Cluster Controllers) are misconfigured.

    This might mean that more than one controller is marked as managing the
    same network
    """

    api_error = int(http.client.CONFLICT)


class ClusterUnavailable(MAASAPIException):
    """A Cluster Controller is not available for RPC queries."""

    api_error = int(http.client.SERVICE_UNAVAILABLE)


class IteratorReusedError(Exception):
    """Raise when a :class:`UseOnceIterator` gets reused."""


class StaticIPAddressExhaustion(MAASAPIException):
    """Raised when no more static IPs are available during allocation."""

    api_error = int(http.client.SERVICE_UNAVAILABLE)


class IPAddressCheckFailed(MAASAPIException):
    """IP address allocation checks failed."""

    api_error = int(http.client.SERVICE_UNAVAILABLE)


class StaticIPAddressUnavailable(MAASAPIException):
    """Raised when a requested IP is not available."""

    api_error = int(http.client.NOT_FOUND)


class StaticIPAddressOutOfRange(MAASAPIException):
    """Raised when a requested IP is not in an acceptable range."""

    api_error = int(http.client.FORBIDDEN)


class StaticIPAddressTypeClash(MAASAPIException):
    """Raised when trying to allocate an IP for a MAC where one of another
    type already exists."""

    api_error = int(http.client.CONFLICT)


class StaticIPAlreadyExistsForMACAddress(MAASAPIException):
    """Raised when trying to allocate a static IP for a non-node MAC
    where a node with that MAC already exists."""

    api_error = int(http.client.CONFLICT)


class StaticIPAddressConflict(MAASAPIException):
    """Raised when trying to allocate a static IP that doesn't belong to
    the network the MAC address is connected to."""

    api_error = int(http.client.CONFLICT)


class StaticIPAddressForbidden(MAASAPIException):
    """Raised when trying to allocate a static IP that belongs to a
    dynamic range."""

    api_error = int(http.client.CONFLICT)


class StaticIPAddressReservedIPConflict(MAASAPIException):
    """Raised when there is already a reserved IP for a specific MAC address and the static IP does not match it."""

    api_error = int(http.client.CONFLICT)


class NodeActionError(MAASException):
    """Raised when there is an error performing a NodeAction."""

    def __init__(self, error):
        # Avoid circular imports.
        from maasserver.clusterrpc.utils import get_error_message_for_exception

        if isinstance(error, Exception):
            super().__init__(get_error_message_for_exception(error))
        else:
            super().__init__(error)


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

    api_error = int(http.client.SERVICE_UNAVAILABLE)


class PodProblem(MAASAPIException):
    """Raised when there's a problem with a pod operation.

    This could be a problem with parameters, a problem with the pod's
    controller, or something else.  The exception text will contain more
    information.
    """

    api_error = int(http.client.SERVICE_UNAVAILABLE)


class NoScriptsFound(MAASException):
    """Raised when no Scripts are found based on user input."""


class StorageClearProblem(MAASAPIException):
    """Raised when an issue occurs that prevents the clearing of a machine's
    storage configuration."""


class NetworkingResetProblem(MAASException):
    """Raised when an issue occurs that prevents resetting networking configuration."""


class MAASBadDeprecation(MAASException):
    """Raised when an API endpoint or operation has it's deprecation incorrectly assigned."""
