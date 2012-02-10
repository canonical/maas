# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Metadata API."""

from __future__ import (
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    'metadata_index',
    'meta_data',
    'version_index',
    'user_data',
    ]

from django.http import HttpResponse


class UnknownMetadataVersion(RuntimeError):
    """Not a known metadata version."""


def make_text_response(contents):
    """Create a response containing `contents` as plain text."""
    return HttpResponse(contents, mimetype='text/plain')


def make_list_response(items):
    """Create an `HttpResponse` listing `items`, one per line."""
    return make_text_response('\n'.join(items))


def check_version(version):
    """Check that `version` is a supported metadata version."""
    if version != 'latest':
        raise UnknownMetadataVersion("Unknown metadata version: %s" % version)


def metadata_index(request):
    """View: top-level metadata listing."""
    return make_list_response(['latest'])


def version_index(request, version):
    """View: listing for a given metadata version."""
    check_version(version)
    return make_list_response(['meta-data', 'user-data'])


def meta_data(request, version):
    """View: meta-data listing for a given version."""
    check_version(version)
    items = [
        'kernel-id',
        ]
    return make_list_response(items)


def user_data(request, version):
    """View: user-data blob for a given version."""
    check_version(version)
    data = b"User data here."
    return HttpResponse(data, mimetype='application/octet-stream')
