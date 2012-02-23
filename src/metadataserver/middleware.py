# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Django "middlewares" for the metadata API."""

from __future__ import (
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    'MetadataErrorsMiddleware',
    ]

from django.conf import settings
from maasserver.middleware import ExceptionMiddleware


class MetadataErrorsMiddleware(ExceptionMiddleware):
    """Report exceptions from the metadata app as HTTP responses."""

    path_regex = settings.METADATA_URL_REGEXP
