# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Additional AMP argument classes."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "Bytes",
    "StructureAsJSON",
    "ParsedURL",
]

import json
import urlparse
import zlib

from apiclient.utils import ascii_url
from twisted.protocols import amp


class Bytes(amp.Argument):
    """Encode a structure on the wire as bytes.

    In truth, this does nothing more than assert that the inputs are
    always bytes.
    """

    def toString(self, inObject):
        if not isinstance(inObject, bytes):
            raise TypeError("Not a byte string: %r" % (inObject,))
        return inObject

    def fromString(self, inString):
        # inString is always a byte string, as defined by amp.Argument.
        return inString


class ParsedURL(amp.Argument):
    """Encode a URL on the wire.

    The URL should be an instance of :py:class:`~urlparse.ParseResult`
    or :py:class:`~urlparse.SplitResult` for encoding. When decoding,
    :py:class:`~urlparse.ParseResult` is always returned.
    """

    def toString(self, inObject):
        """Encode a URL-like object into an ASCII URL.

        :raise TypeError: If `inObject` is not a URL-like object
            (meaning it doesn't have a `geturl` method).
        """
        try:
            geturl = inObject.geturl
        except AttributeError:
            raise TypeError("Not a URL-like object: %r" % (inObject,))
        else:
            return ascii_url(geturl())

    def fromString(self, inString):
        """Decode an ASCII URL into a URL-like object.

        :return: :py:class:`~urlparse.ParseResult`
        """
        return urlparse.urlparse(inString)


class StructureAsJSON(amp.Argument):
    """Encode a structure on the wire as JSON, compressed with zlib.

    The compressed size of the structure should not exceed
    :py:data:`~twisted.protocols.amp.MAX_VALUE_LENGTH`, or ``0xffff``
    bytes. This is pretty hard to be sure of ahead of time, so only use
    this for small structures that won't go near the limit.
    """

    def toString(self, inObject):
        return zlib.compress(json.dumps(inObject))

    def fromString(self, inString):
        return json.loads(zlib.decompress(inString))
