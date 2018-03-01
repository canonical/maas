# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Combo view."""

__all__ = [
    'get_combo_view',
    ]

from functools import partial
import os

from convoy.combo import (
    combine_files,
    parse_qs,
)
from django.conf import settings
from django.http import (
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseNotFound,
    HttpResponseRedirect,
)


MERGE_VIEWS = {
    "jquery.js": {
        "location": settings.JQUERY_LOCATION,
        "content_type": "text/javascript; charset=UTF-8",
        "files": [
            "jquery.min.js",
        ]
    },
    "angular.js": {
        "location": settings.ANGULARJS_LOCATION,
        "content_type": "text/javascript; charset=UTF-8",
        "files": [
            "angular.min.js",
            "angular-route.min.js",
            "angular-cookies.min.js",
            "angular-sanitize.min.js",
        ]
    },
    "yui.js": {
        "location": settings.YUI_LOCATION,
        "content_type": "text/javascript; charset=UTF-8",
        "files": [
            "yui-base/yui-base-min.js",
        ]
    },
    "macaroons.js": {
        "content_type": "text/javascript; charset=UTF-8",
        "files": [
            "js/macaroon/js-macaroon-min.js",
            "js/macaroon/bakery.js",
            "js/macaroon/web-handler.js",
        ]
    },
}


def get_absolute_location(location=''):
    """Return the absolute location of a static resource.

    This utility exist to deal with the various places where MAAS can find
    static resources.

    If the given location is an absolute location, return it. If not, treat
    the location as a relative location.

    :param location: An optional absolute or relative location.
    :type location: unicode
    :return: The absolute path.
    :rtype: unicode
    """
    if location.startswith(os.path.sep):
        return location
    else:
        return os.path.join(settings.STATIC_ROOT, location)


def get_combo_view(location='', default_redirect=None):
    """Return a Django view to serve static resources using a combo loader.

    :param location: An optional absolute or relative location.
    :type location: unicode
    :param default_redirect: An optional address where requests for one file
        of an unknown file type will be redirected.  If this parameter is
        omitted, such requests will lead to a "Bad request" response.
    :type location: unicode
    :return: A Django view method.
    :rtype: callable
    """
    location = get_absolute_location(location)
    return partial(
        combo_view, location=location, default_redirect=default_redirect)


def combo_view(request, location, default_redirect=None, encoding='utf8'):
    """Handle a request for combining a set of files.

    The files are searched in the absolute location `abs_location` (if
    defined) or in the relative location `rel_location`.
    """
    fnames = parse_qs(request.META.get("QUERY_STRING", ""))

    if fnames:
        if fnames[0].endswith('.js'):
            content_type = 'text/javascript; charset=UTF-8'
        elif fnames[0].endswith('.css'):
            content_type = 'text/css'
        elif default_redirect is not None and len(fnames) == 1:
            return HttpResponseRedirect(
                "%s%s" % (default_redirect, fnames[0]))
        else:
            return HttpResponseBadRequest(
                "Invalid file type requested.",
                content_type="text/plain; charset=UTF-8")
        content = "".join(
            [content.decode(encoding) for content in combine_files(
                fnames, location, resource_prefix='/', rewrite_urls=True)])

        return HttpResponse(
            content_type=content_type, status=200, content=content)

    return HttpResponseNotFound()


def merge_view(request, filename):
    """Merge the `files` from `location` into one file. Return the HTTP
    response with `content_type`.
    """
    merge_info = MERGE_VIEWS.get(filename, None)
    if merge_info is None:
        return HttpResponseNotFound()
    location = merge_info.get("location", None)
    if location is None:
        location = get_absolute_location()
    content = "".join(
        [content.decode('utf-8') for content in combine_files(
            merge_info["files"], location,
            resource_prefix='/', rewrite_urls=True)])
    return HttpResponse(
        content_type=merge_info["content_type"], status=200, content=content)
