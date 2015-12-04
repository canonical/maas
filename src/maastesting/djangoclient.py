# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Django client with sensible handling of data."""

__all__ = [
    'SensibleClient',
    ]

from functools import wraps

from django.test import client


def transparent_encode_multipart(func):
    """Wrap an HTTP client method, transparently encoding multipart data.

    This wraps Django's `Client` HTTP verb methods -- put, get, etc. -- in a
    way that's both convenient and compatible across Django versions. It
    augments those methods to accept a dict of data to be sent as part of the
    request body, in MIME multipart encoding.

    Since Django 1.5, these HTTP verb methods require data in the form of a
    byte string. The application (that's us) need to take care of MIME
    encoding.
    """
    @wraps(func)
    def maybe_encode_multipart(
            self, path, data=b"", content_type=None, **extra):

        if isinstance(data, bytes):
            if content_type is None:
                content_type = 'application/octet-stream'
        elif content_type is None:
            content_type = client.MULTIPART_CONTENT
            data = client.encode_multipart(client.BOUNDARY, data)
        else:
            raise TypeError(
                "Cannot combine data (%r) with content-type (%r)."
                % (data, content_type))

        return func(self, path, data, content_type, **extra)

    return maybe_encode_multipart


class SensibleClient(client.Client):
    """A Django test client that transparently encodes multipart data."""

    # get(), post(), and head() handle their own payload-encoding and accept
    # dicts as `data`, so they're not wrapped. The following all accept
    # byte-strings as `data` so they are transparently wrapped.
    delete = transparent_encode_multipart(client.Client.delete)
    options = transparent_encode_multipart(client.Client.options)
    patch = transparent_encode_multipart(client.Client.patch)
    put = transparent_encode_multipart(client.Client.put)
