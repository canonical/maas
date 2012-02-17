# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Exceptions."""

from __future__ import (
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    "MaasException",
    "MaasAPIBadRequest",
    "MaasAPIException",
    "MaasAPINotFound",
    "PermissionDenied",
    ]


import httplib


class MaasException(Exception):
    """Base class for Maas' exceptions."""


class CannotDeleteUserException(Exception):
    """User can't be deleted."""


class MaasAPIException(Exception):
    """Base class for Maas' API exceptions.

    :ivar api_error: The HTTP code that should be returned when this error
        is raised in the API (defaults to 500: "Internal Server Error").

    """
    api_error = httplib.INTERNAL_SERVER_ERROR


class MaasAPIBadRequest(MaasAPIException):
    api_error = httplib.BAD_REQUEST


class MaasAPINotFound(MaasAPIException):
    api_error = httplib.NOT_FOUND


class PermissionDenied(MaasAPIException):
    """HTTP error 403: Forbidden.  User is logged in, but lacks permission.

    Do not confuse this with 401: Unauthorized ("you need to be logged in
    for this, so please authenticate").  The Piston error codes do confuse
    the two.
    """
    api_error = httplib.FORBIDDEN


class Unauthorized(MaasAPIException):
    """HTTP error 401: Unauthorized.  Login required."""
    api_error = httplib.UNAUTHORIZED


class NodesNotAvailable(MaasAPIException):
    """Requested node(s) are not available to be acquired."""
    api_error = httplib.CONFLICT
