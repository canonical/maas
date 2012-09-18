# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Remote API library."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    "ascii_url",
    ]


from urlparse import urlparse


def ascii_url(url):
    """Encode `url` as ASCII if it isn't already."""
    if isinstance(url, unicode):
        urlparts = urlparse(url)
        urlparts = urlparts._replace(
            netloc=urlparts.netloc.encode("idna"))
        url = urlparts.geturl()
    return url.encode("ascii")
