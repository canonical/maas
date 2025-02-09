# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Not found API handler."""

from maasserver.exceptions import MAASAPINotFound


def not_found_handler(request):
    """An API handler that returns API 404 responses."""
    raise MAASAPINotFound("Unknown API endpoint: %s." % request.path)
