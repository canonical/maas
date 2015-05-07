# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Not found API handler."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )


str = None

__metaclass__ = type
__all__ = [
    'not_found_handler',
    ]


from maasserver.exceptions import MAASAPINotFound


def not_found_handler(request):
    """An API handler that returns API 404 responses."""
    raise MAASAPINotFound("Unknown API endpoint: %s." % request.path)
