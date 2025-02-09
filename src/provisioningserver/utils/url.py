# Copyright 2014-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Utilities for URL handling."""

import re
import urllib.error
import urllib.parse
from urllib.parse import urlparse, urlunparse
import urllib.request


def compose_URL(base_url, host):
    """Compose (or recompose) a URL, based on an existing URL and given host.

    This is straightforward if the IP address is a hostname or an IPv4
    address; but if it's an IPv6 address, the URL must contain the IP address
    in square brackets as per RFC 3986.

    :param base_url: URL with or without the host part; for example:
        `http:///path`, `http://foo:5240/path`, or `http://:5240/path`.
    :param host: Host name or IP address to insert in the host part of the URL.
    :return: A URL string with the host part taken from `host`, and all others
        from `base_url`.
    """
    if re.match("[:.0-9a-fA-F]+(?:%.+)?$", host) and host.count(":") > 0:
        # IPv6 address, without the brackets.  Add square brackets.
        # In case there's a zone index (introduced by a % sign), escape it.
        netloc_host = "[%s]" % urllib.parse.quote(host, safe=":")
    else:
        # IPv4 address, hostname, or IPv6 with brackets.  Keep as-is.
        netloc_host = host
    parsed_url = urlparse(base_url)
    if parsed_url.port is None:
        netloc = netloc_host
    else:
        netloc = "%s:%d" % (netloc_host, parsed_url.port)
    return urlunparse(parsed_url._replace(netloc=netloc))


def splithost(host):
    """Split `host` into hostname and port.

    If no :port is in `host` the port with return as None.
    """
    parsed = urlparse("//" + host)
    hostname = parsed.hostname
    if hostname is None:
        # This only occurs when the `host` is an IPv6 address without brakets.
        # Lets try again but add the brackets.
        parsed = urlparse("//[%s]" % host)
        hostname = parsed.hostname
    if ":" in hostname:
        # IPv6 hostname, place back into brackets.
        hostname = "[%s]" % hostname
    return hostname, parsed.port


def get_domain(url):
    """Get just the domain name from a URL."""
    parsed_uri = urlparse(url)
    domain, _ = splithost(parsed_uri.netloc)
    return domain
