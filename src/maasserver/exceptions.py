# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Exceptions."""

from __future__ import (
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    "MaaSException",
    "MaaSAPIBadRequest",
    "MaaSAPIException",
    "MaaSAPINotFound",
    "PermissionDenied",
    ]


import httplib


class MaaSException(Exception):
    """Base class for MaaS' exceptions."""


class CannotDeleteUserException(Exception):
    """User can't be deleted."""


class MaaSAPIException(Exception):
    """Base class for MaaS' API exceptions.

    :ivar api_error: The HTTP code that should be returned when this error
        is raised in the API (defaults to 500: "Internal Server Error").

    """
    api_error = httplib.INTERNAL_SERVER_ERROR


class MaaSAPIBadRequest(MaaSAPIException):
    api_error = httplib.BAD_REQUEST


class MaaSAPINotFound(MaaSAPIException):
    api_error = httplib.NOT_FOUND


class PermissionDenied(MaaSAPIException):
    """HTTP error 403: Forbidden.  User is logged in, but lacks permission.

    Do not confuse this with 401: Unauthorized ("you need to be logged in
    for this, so please authenticate").  The Piston error codes do confuse
    the two.
    """
    api_error = httplib.FORBIDDEN


class Unauthorized(MaaSAPIException):
    """HTTP error 401: Unauthorized.  Login required."""
    api_error = httplib.UNAUTHORIZED


class NodesNotAvailable(MaaSAPIException):
    """Requested node(s) are not available to be acquired."""
    api_error = httplib.CONFLICT
