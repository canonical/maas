# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Remote API library."""

__all__ = ["ascii_url", "urlencode"]

from urllib.parse import quote_plus, urlparse


def ascii_url(url):
    """Encode `url` as ASCII if it isn't already."""
    if isinstance(url, str):
        urlparts = urlparse(url)
        urlparts = urlparts._replace(
            # Encode IDNA and decode back to bytes-in-unicode string.
            netloc=urlparts.netloc.encode("idna").decode("ascii")
        )
        return urlparts.geturl().encode("ascii")
    else:
        # Round-trip via ASCII so we at least crash if it's not.
        return url.decode("ascii").encode("ascii")


def urlencode(data):
    """A version of `urllib.urlencode` that isn't insane.

    This only cares that `data` is an iterable of iterables. Each sub-iterable
    must be of overall length 2, i.e. a name/value pair.

    Unicode strings will be encoded to UTF-8. This is what Django expects; see
    `smart_text` in the Django documentation.
    """
    return "&".join(
        f"{quote_plus(name)}={quote_plus(value)}" for name, value in data
    )
