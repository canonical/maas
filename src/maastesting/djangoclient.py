# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Django client with sensible handling of data."""

from functools import wraps

from django.test import client
from django.utils.http import urlencode


def transparent_encode_multipart(func):
    """Wrap an HTTP client method, transparently encoding multipart data.

    This wraps some of Django's `Client` HTTP verb methods -- delete, options,
    patch, put -- so they accept a dict of data to be sent as part of the
    request body, in MIME multipart encoding.

    This also accepts an optional dict of query parameters (as `query`) to be
    encoded as a query string and appended to the given path.

    Since Django 1.5, these HTTP verb methods require data in the form of a
    byte string. The application (that's us) needs to take care of MIME
    encoding.
    """

    @wraps(func)
    def maybe_encode_multipart(
        self,
        path,
        data=b"",
        content_type=None,
        secure=False,
        query=None,
        **extra,
    ):
        if isinstance(data, bytes):
            if content_type is None:
                content_type = "application/octet-stream"
        elif content_type is None:
            content_type = client.MULTIPART_CONTENT
            data = client.encode_multipart(client.BOUNDARY, data)
        else:
            raise TypeError(
                "Cannot combine data (%r) with content-type (%r)."
                % (data, content_type)
            )

        if query is not None:
            query = urlencode(query, doseq=True)
            path = path + ("&" if "?" in path else "?") + query

        return func(self, path, data, content_type, secure, **extra)

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
