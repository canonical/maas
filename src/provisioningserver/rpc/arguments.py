# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Additional AMP argument classes."""

from collections.abc import Mapping
import importlib
from io import BytesIO
from itertools import count
import json
import urllib.parse
import zlib

import attr
import netaddr
from twisted.protocols import amp

from apiclient.utils import ascii_url


class Bytes(amp.Argument):
    """Encode a structure on the wire as bytes.

    In truth, this does nothing more than assert that the inputs are
    always bytes.
    """

    def toString(self, inObject):
        if not isinstance(inObject, bytes):
            raise TypeError(f"Not a byte string: {inObject!r}")
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
        super().__init__(optional=optional)
        if not isinstance(choices, Mapping):
            raise TypeError(f"Not a mapping: {choices!r}")
        not_byte_strings = [
            value for value in choices.values() if not isinstance(value, bytes)
        ]
        if len(not_byte_strings) != 0:
            # For the error message, sort the representations because mixed
            # types are not guaranteed to be comparable in Python 3.
            raise TypeError(
                "Not byte strings: %s"
                % ", ".join(sorted(repr(value) for value in not_byte_strings))
            )
        self._encode = {name: value for name, value in choices.items()}
        self._decode = {value: name for name, value in choices.items()}

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
            raise TypeError(f"Not a URL-like object: {inObject!r}")  # noqa: B904
        else:
            return ascii_url(geturl())

    def fromString(self, inString):
        """Decode an ASCII URL into a URL-like object.

        :return: :py:class:`~urlparse.ParseResult`
        """
        return urllib.parse.urlparse(inString.decode("ascii"))


class StructureAsJSON(amp.Argument):
    """Encode a structure on the wire as JSON, compressed with zlib.

    The compressed size of the structure should not exceed
    :py:data:`~twisted.protocols.amp.MAX_VALUE_LENGTH`, or ``0xffff`` bytes.
    This is pretty hard to be sure of ahead of time, so only use this for
    small structures that won't go near the limit.
    """

    def toString(self, inObject):
        return zlib.compress(json.dumps(inObject).encode("ascii"))

    def fromString(self, inString):
        return json.loads(zlib.decompress(inString).decode("ascii"))


class AttrsClassArgument(StructureAsJSON):
    """Encode and decode an `attr.s` class over the wire.

    The class name to import is specified as a string with full path.
    """

    def __init__(self, class_name, optional=False):
        super().__init__(optional=optional)
        self._class = self._get_class(class_name)

    def _get_class(self, name):
        module_name, cls = name.rsplit(".", 1)
        module = importlib.import_module(module_name)
        return getattr(module, cls)

    def toString(self, obj):
        if not isinstance(obj, self._class):
            raise TypeError(f"{obj!r} is not of type {self._class.__name__}")
        return super().toString(attr.asdict(obj))

    def fromString(self, string):
        data = super().fromString(string)
        return self._class(**data)


def _toByteString(string):
    """Encode `string` as (ASCII) bytes if it's a Unicode string.

    Otherwise return `string` unaltered.
    """
    if isinstance(string, str):
        return string.encode("ascii")
    else:
        return string


class AmpList(amp.AmpList):
    """An :py:class:`amp.AmpList` that works with native string arguments.

    Argument names are serialised transparently to ASCII byte strings and back
    again. This means that arguments can only contain ASCII characters.
    Twisted's ``AmpList`` deals only with byte string argument names.
    """

    def __init__(self, subargs, optional=False):
        """Create an AmpList.

        :param subargs: a sequence of 2-tuples of ('name', argument)
            describing the schema. The names can be byte strings, or Unicode
            strings containing only ASCII characters.
        :param optional: Whether this argument can be omitted in the protocol.
        :type optional: bool
        """
        subargs = tuple((_toByteString(name), arg) for name, arg in subargs)
        super().__init__(subargs, optional)


class CompressedAmpList(AmpList):
    """An :py:class:`amp.AmpList` that's compressed on the wire.

    The serialised form is transparently compressed and decompressed with
    zlib. This can be useful when there's a lot of repetition in the list
    being transmitted.
    """

    CHUNK_MAX = 0xFFFF

    def fromBox(self, name, strings, objects, proto):
        st = self.retrieve(strings, name, proto)
        nk = amp._wireNameToPythonIdentifier(name)
        if self.optional and st is None:
            objects[nk] = None
        else:
            buffer = BytesIO(st)
            for counter in count(2):
                chunk = strings.get(f"{name.decode()}.{counter}".encode())
                if chunk is None:
                    break
                buffer.write(chunk)
            objects[nk] = self.fromStringProto(buffer.getvalue(), proto)

    def toBox(self, name, strings, objects, proto):
        obj = self.retrieve(
            objects, amp._wireNameToPythonIdentifier(name), proto
        )
        if self.optional and obj is None:
            return

        buf = BytesIO(self.toStringProto(obj, proto))
        firstChunk = buf.read(CompressedAmpList.CHUNK_MAX)
        strings[name] = firstChunk
        counter = 2
        while True:
            nextChunk = buf.read(CompressedAmpList.CHUNK_MAX)
            if not nextChunk:
                break
            strings[f"{name.decode()}.{counter}".encode()] = nextChunk
            counter += 1

    def toStringProto(self, inObject, proto):
        toStringProto = super().toStringProto
        return zlib.compress(toStringProto(inObject, proto))

    def fromStringProto(self, inString, proto):
        fromStringProto = super().fromStringProto
        return fromStringProto(zlib.decompress(inString), proto)


class IPAddress(amp.Argument):
    """Encode a `netaddr.IPAddress` object on the wire."""

    def toString(self, inObject):
        length = 4 if inObject.version == 4 else 16
        return inObject.value.to_bytes(length, "big")

    def fromString(self, inString):
        address = int.from_bytes(inString, "big")
        version = 4 if len(inString) == 4 else 6
        return netaddr.IPAddress(address, version)


class IPNetwork(amp.Argument):
    """Encode a `netaddr.IPNetwork` object on the wire."""

    def toString(self, inObject):
        length = 4 if inObject.version == 4 else 16
        return inObject.cidr.value.to_bytes(
            length, "big"
        ) + inObject.prefixlen.to_bytes(1, "big")

    def fromString(self, inString):
        # Compared to sending an IPAddress over the wire, we need to account
        # for one extra byte for the prefix length.
        if len(inString) == 5:
            version = 4
            address_length = 4
        else:
            version = 6
            address_length = 16
        address = int.from_bytes(inString[:address_length], "big")
        prefixlen = int.from_bytes(inString[address_length:], "big")
        network = netaddr.IPNetwork(
            netaddr.IPAddress(address, version=version)
        )
        network.prefixlen = prefixlen
        return network
