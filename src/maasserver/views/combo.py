# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Combo view."""

__all__ = ["merge_view"]

import os

from convoy.combo import combine_files
from django.conf import settings
from django.http import HttpResponse, HttpResponseNotFound


MERGE_VIEWS = {
    "jquery.js": {
        "location": settings.JQUERY_LOCATION,
        "content_type": "text/javascript; charset=UTF-8",
        "files": ["jquery.min.js"],
    },
    "angular.js": {
        "location": settings.ANGULARJS_LOCATION,
        "content_type": "text/javascript; charset=UTF-8",
        "files": [
            "angular.min.js",
            "angular-route.min.js",
            "angular-cookies.min.js",
            "angular-sanitize.min.js",
        ],
    },
}


def get_absolute_location(location=""):
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
        [
            content.decode("utf-8")
            for content in combine_files(
                merge_info["files"],
                location,
                resource_prefix="/",
                rewrite_urls=True,
            )
        ]
    )
    return HttpResponse(
        content_type=merge_info["content_type"], status=200, content=content
    )
