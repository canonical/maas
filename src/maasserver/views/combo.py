# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Combo view."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    'combo_view',
    ]

import os

from convoy.combo import (
    combine_files,
    parse_qs,
    )
from django.conf import settings as django_settings
from django.http import (
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseNotFound,
    )


def get_yui_location():
    if django_settings.STATIC_ROOT:
        return os.path.join(
            django_settings.STATIC_ROOT, 'jslibs', 'yui')
    else:
        return os.path.join(
            os.path.dirname(os.path.dirname(__file__)), 'static',
            'jslibs', 'yui')


def combo_view(request):
    """Handle a request for combining a set of files."""
    fnames = parse_qs(request.META.get("QUERY_STRING", ""))
    YUI_LOCATION = get_yui_location()

    if fnames:
        if fnames[0].endswith('.js'):
            content_type = 'text/javascript; charset=UTF-8'
        elif fnames[0].endswith('.css'):
            content_type = 'text/css'
        else:
            return HttpResponseBadRequest("Invalid file type requested.")
        content = b"".join(
            combine_files(
               fnames, YUI_LOCATION, resource_prefix='/',
               rewrite_urls=True))

        return HttpResponse(
            content_type=content_type, status=200, content=content)

    return HttpResponseNotFound()
