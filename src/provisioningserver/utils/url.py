# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Utilities for URL handling."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'compose_URL',
    ]

import re
import urllib
from urlparse import (
    urlparse,
    urlunparse,
)


def compose_URL(base_url, host):
    """Produce a URL on a given hostname or IP address.

    This is straightforward if the IP address is a hostname or an IPv4
    address; but if it's an IPv6 address, the URL must contain the IP address
    in square brackets as per RFC 3986.

    :param base_url: URL without the host part, e.g. `http:///path'.
    :param host: Host name or IP address to insert in the host part of the URL.
    :return: A URL string with the host part taken from `host`, and all others
        from `base_url`.
    """
    if re.match('[:.0-9a-fA-F]+(?:%.+)?$', host) and host.count(':') > 0:
        # IPv6 address, without the brackets.  Add square brackets.
        # In case there's a zone index (introduced by a % sign), escape it.
        netloc_host = '[%s]' % urllib.quote(host, safe=':')
    else:
        # IPv4 address, hostname, or IPv6 with brackets.  Keep as-is.
        netloc_host = host
    parsed_url = urlparse(base_url)
    if parsed_url.port is None:
        netloc = netloc_host
    else:
        netloc = '%s:%d' % (netloc_host, parsed_url.port)
    return urlunparse(parsed_url._replace(netloc=netloc))
