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

__metaclass__ = type
__all__ = [
    'MAASDjangoTestClient',
    ]


class FileLikeWrapper:
    """Wrap a Django response object to look like a urllib2.addinfourl object.

    Django returns something that has a 'status_code' and a 'content'
    attributes. urllib2 returns something that has a 'code' and a 'read()'
    method.
    """

    def __init__(self, response):
        self.response = response

    def read(self):
        return self.response.content

    @property
    def code(self):
        return self.response.status_code


class MAASDjangoTestClient:
    """Wrap the Django testing Client to look like a MAASClient."""

    def __init__(self, django_client):
        self.django_client = django_client

    def get(self, path, op=None, **kwargs):
        kwargs['op'] = op
        return FileLikeWrapper(self.django_client.get(path, kwargs))

    def post(self, path, op=None, **kwargs):
        kwargs['op'] = op
        return FileLikeWrapper(self.django_client.post(path, kwargs))

    def put(self, path, **kwargs):
        return FileLikeWrapper(self.django_client.put(path, kwargs))

    def delete(self, path):
        return FileLikeWrapper(self.django_client.delete(path))
