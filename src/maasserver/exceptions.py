# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Exceptions."""

from __future__ import (
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    "MAASException",
    "MAASAPIBadRequest",
    "MAASAPIException",
    "MAASAPINotFound",
    "NodeStateViolation",
    ]


import httplib


class MAASException(Exception):
    """Base class for MAAS' exceptions."""


class CannotDeleteUserException(Exception):
    """User can't be deleted."""


class NoRabbit(MAASException):
    """Could not reach RabbitMQ."""


class MAASAPIException(Exception):
    """Base class for MAAS' API exceptions.

    :ivar api_error: The HTTP code that should be returned when this error
        is raised in the API (defaults to 500: "Internal Server Error").

    """
    api_error = httplib.INTERNAL_SERVER_ERROR


class MAASAPIBadRequest(MAASAPIException):
    api_error = httplib.BAD_REQUEST


class MAASAPINotFound(MAASAPIException):
    api_error = httplib.NOT_FOUND


class Unauthorized(MAASAPIException):
    """HTTP error 401: Unauthorized.  Login required."""
    api_error = httplib.UNAUTHORIZED


class NodeStateViolation(MAASAPIException):
    """Operation on node not possible given node's current state."""
    api_error = httplib.CONFLICT


class NodesNotAvailable(NodeStateViolation):
    """Requested node(s) are not available to be acquired."""
    api_error = httplib.CONFLICT
