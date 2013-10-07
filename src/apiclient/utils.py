# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Remote API library."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "ascii_url",
    "urlencode",
    ]


from urllib import quote_plus
from urlparse import urlparse


def ascii_url(url):
    """Encode `url` as ASCII if it isn't already."""
    if isinstance(url, unicode):
        urlparts = urlparse(url)
        urlparts = urlparts._replace(
            netloc=urlparts.netloc.encode("idna"))
        url = urlparts.geturl()
    return url.encode("ascii")


def urlencode(data):
    """A version of `urllib.urlencode` that isn't insane.

    This only cares that `data` is an iterable of iterables. Each sub-iterable
    must be of overall length 2, i.e. a name/value pair.

    Unicode strings will be encoded to UTF-8. This is what Django expects; see
    `smart_text` in the Django documentation.
    """
    enc = lambda string: quote_plus(
        string.encode("utf-8") if isinstance(string, unicode) else string)
    return b"&".join(
        b"%s=%s" % (enc(name), enc(value))
        for name, value in data)
