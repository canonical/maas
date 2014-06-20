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
]

import json
import zlib

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
