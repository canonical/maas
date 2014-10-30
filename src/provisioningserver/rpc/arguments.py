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
    "Choice",
    "StructureAsJSON",
    "ParsedURL",
]

import collections
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


class Choice(amp.Argument):
    """Encode a choice to a predefined bytestring on the wire."""

    def __init__(self, choices, optional=False):
        """Default constructor.

        :param choices: A :py:class:`~collections.Mapping` of possible
            choices. The keys can be any Python object suitable for use
            as a mapping key, but the values must be byte strings. On
            the wire the Python objects will be represented by those
            byte strings, and mapped back at the receiving end.
        """
        super(Choice, self).__init__(optional=optional)
        if not isinstance(choices, collections.Mapping):
            raise TypeError("Not a mapping: %r" % (choices,))
        not_byte_strings = sorted(
            value for value in choices.itervalues()
            if not isinstance(value, bytes))
        if len(not_byte_strings) != 0:
            raise TypeError("Not byte strings: %s" % ", ".join(
                repr(value) for value in not_byte_strings))
        self._encode = {name: value for name, value in choices.iteritems()}
        self._decode = {value: name for name, value in choices.iteritems()}

    def toString(self, inObject):
        return self._encode[inObject]

    def fromString(self, inString):
        return self._decode[inString]


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


class CompressedAmpList(amp.AmpList):
    """An :py:class:`amp.AmpList` that's compressed on the wire.

    The serialised form is transparently compressed and decompressed with
    zlib. This can be useful when there's a lot of repetition in the list
    being transmitted.
    """

    def toStringProto(self, inObject, proto):
        toStringProto = super(CompressedAmpList, self).toStringProto
        return zlib.compress(toStringProto(inObject, proto))

    def fromStringProto(self, inString, proto):
        fromStringProto = super(CompressedAmpList, self).fromStringProto
        return fromStringProto(zlib.decompress(inString), proto)
