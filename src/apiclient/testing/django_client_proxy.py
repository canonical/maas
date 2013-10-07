# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""A proxy that looks like MAASClient.

This actually passes the requests on to a django.test.client.Client, to avoid
having to go via a real HTTP server.
"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'MAASDjangoTestClient',
    ]

import httplib
import io
import urllib2


def to_addinfourl(response):
    """Convert a `django.http.HttpResponse` to a `urllib2.addinfourl`."""
    headers_raw = response.serialize_headers()
    headers = httplib.HTTPMessage(io.BytesIO(headers_raw))
    return urllib2.addinfourl(
        fp=io.BytesIO(response.content), headers=headers,
        url=None, code=response.status_code)


class MAASDjangoTestClient:
    """Wrap the Django testing Client to look like a MAASClient."""

    def __init__(self, django_client):
        self.django_client = django_client

    def get(self, path, op=None, **kwargs):
        kwargs['op'] = op
        return to_addinfourl(self.django_client.get(path, kwargs))

    def post(self, path, op=None, **kwargs):
        kwargs['op'] = op
        return to_addinfourl(self.django_client.post(path, kwargs))

    def put(self, path, **kwargs):
        return to_addinfourl(self.django_client.put(path, kwargs))

    def delete(self, path):
        return to_addinfourl(self.django_client.delete(path))
