# This software is licensed under the MIT license.
#
# Copyright (c) Twisted Matrix Laboratories.
#               2011-2012 Oregon State University Open Source Lab
#               2011-2012 Corbin Simpson
#               2015-2018 Canonical Ltd.
#
# http://twistedmatrix.com/trac/ticket/4173

"""
The WebSockets protocol (RFC 6455), provided as a resource which wraps a
factory.
"""

__all__ = [
    "WebSocketsResource",
    "IWebSocketsFrameReceiver",
    "lookupProtocolForFactory",
    "WebSocketsProtocol",
    "WebSocketsProtocolWrapper",
    "CONTROLS",
    "STATUSES",
]


import base64
from hashlib import sha1
from itertools import cycle
from struct import pack, unpack
from typing import List, Sequence

from twisted.internet.protocol import Protocol
from twisted.protocols.tls import TLSMemoryBIOProtocol
from twisted.python.constants import ValueConstant, Values
from twisted.web.resource import IResource
from twisted.web.server import NOT_DONE_YET
from zope.interface import directlyProvides, implementer, Interface, providedBy

from provisioningserver.logger import LegacyLogger

log = LegacyLogger()


class _WSException(Exception):
    """
    Internal exception for control flow inside the WebSockets frame parser.
    """


class CONTROLS(Values):
    """
    Control frame specifiers.

    @since: 13.2
    """

    CONTINUE = ValueConstant(0)
    TEXT = ValueConstant(1)
    BINARY = ValueConstant(2)
    CLOSE = ValueConstant(8)
    PING = ValueConstant(9)
    PONG = ValueConstant(10)


class STATUSES(Values):
    """
    Closing status codes.

    @since: 13.2
    """

    NORMAL = ValueConstant(1000)
    GOING_AWAY = ValueConstant(1001)
    PROTOCOL_ERROR = ValueConstant(1002)
    UNSUPPORTED_DATA = ValueConstant(1003)
    NONE = ValueConstant(1005)
    ABNORMAL_CLOSE = ValueConstant(1006)
    INVALID_PAYLOAD = ValueConstant(1007)
    POLICY_VIOLATION = ValueConstant(1008)
    MESSAGE_TOO_BIG = ValueConstant(1009)
    MISSING_EXTENSIONS = ValueConstant(1010)
    INTERNAL_ERROR = ValueConstant(1011)
    TLS_HANDSHAKE_FAILED = ValueConstant(1056)


# The GUID for WebSockets, from RFC 6455.
_WS_GUID = b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


def _makeAccept(key: bytes) -> bytes:
    """
    Create an B{accept} response for a given key.

    @type key: C{bytes}
    @param key: The key to respond to.

    @rtype: C{bytes}
    @return: An encoded response.
    """
    digest = sha1(b"%s%s" % (key, _WS_GUID)).digest()
    return base64.encodebytes(digest).strip()


def _mask(buf: bytes, key: bytes) -> bytes:
    """
    Mask or unmask a buffer of bytes with a masking key.

    @type buf: C{bytes}
    @param buf: A buffer of bytes.

    @type key: C{bytes}
    @param key: The masking key. Must be exactly four bytes.

    @rtype: C{str}
    @return: A masked buffer of bytes.
    """
    return bytes((b ^ k) for b, k in zip(buf, cycle(key)))


def _makeFrame(buf: bytes, opcode, fin: bool, mask: bytes = None) -> bytes:
    """
    Make a frame.

    This function always creates unmasked frames, and attempts to use the
    smallest possible lengths.

    @type buf: C{bytes}
    @param buf: A buffer of bytes.

    @type opcode: C{CONTROLS}
    @param opcode: Which type of frame to create.

    @type fin: C{bool}
    @param fin: Whether or not we're creating a final frame.

    @type mask: C{bytes} or C{NoneType}
    @param mask: If specified, the masking key to apply on the created frame.

    @rtype: C{bytes}
    @return: A packed frame.
    """
    bufferLength = len(buf)
    if mask is not None:
        lengthMask = 0x80
    else:
        lengthMask = 0

    if bufferLength > 0xFFFF:
        length = b"%s%s" % (
            bytes([lengthMask | 0x7F]),
            pack(">Q", bufferLength),
        )
    elif bufferLength > 0x7D:
        length = b"%s%s" % (
            bytes([lengthMask | 0x7E]),
            pack(">H", bufferLength),
        )
    else:
        length = bytes([lengthMask | bufferLength])

    if fin:
        header = 0x80
    else:
        header = 0x01

    header = bytes([header | opcode.value])
    if mask is not None:
        buf = b"%s%s" % (mask, _mask(buf, mask))
    frame = b"%s%s%s" % (header, length, buf)
    return frame


def _parseFrames(frameBuffer: List[bytes], needMask: bool = True):
    """
    Parse frames in a highly compliant manner. It modifies C{frameBuffer}
    removing the parsed content from it.

    @param frameBuffer: A buffer of bytes.
    @type frameBuffer: C{list}

    @param needMask: If C{True}, refuse any frame which is not masked.
    @type needMask: C{bool}
    """
    start = 0
    payload = b"".join(frameBuffer)

    while True:
        # If there's not at least two bytes in the buffer, bail.
        if len(payload) - start < 2:
            break

        # Grab the header. This single byte holds some flags and an opcode
        header = payload[start]
        if header & 0x70:
            # At least one of the reserved flags is set. Pork chop sandwiches!
            raise _WSException("Reserved flag in frame (%d)" % (header,))

        fin = header & 0x80

        # Get the opcode, and translate it to a local enum which we actually
        # care about.
        opcode = header & 0xF
        try:
            opcode = CONTROLS.lookupByValue(opcode)
        except ValueError:
            raise _WSException("Unknown opcode %d in frame" % opcode)  # noqa: B904

        # Get the payload length and determine whether we need to look for an
        # extra length.
        length = payload[start + 1]
        masked = length & 0x80

        if not masked and needMask:
            # The client must mask the data sent
            raise _WSException("Received data not masked")

        length &= 0x7F

        # The offset we'll be using to walk through the frame. We use this
        # because the offset is variable depending on the length and mask.
        offset = 2

        # Extra length fields.
        if length == 0x7E:
            if len(payload) - start < 4:
                break

            length = payload[start + 2 : start + 4]
            length = unpack(">H", length)[0]
            offset += 2
        elif length == 0x7F:
            if len(payload) - start < 10:
                break

            # Protocol bug: The top bit of this long long *must* be cleared;
            # that is, it is expected to be interpreted as signed.
            length = payload[start + 2 : start + 10]
            length = unpack(">Q", length)[0]
            offset += 8

        if masked:
            if len(payload) - (start + offset) < 4:
                # This is not strictly necessary, but it's more explicit so
                # that we don't create an invalid key.
                break

            key = payload[start + offset : start + offset + 4]
            offset += 4

        if len(payload) - (start + offset) < length:
            break

        data = payload[start + offset : start + offset + length]

        if masked:
            data = _mask(data, key)

        if opcode == CONTROLS.CLOSE:
            if len(data) >= 2:
                # Gotta unpack the opcode and return usable data here.
                code = STATUSES.lookupByValue(unpack(">H", data[:2])[0])
                data = code, data[2:]
            else:
                # No reason given; use generic data.
                data = STATUSES.NONE, b""

        yield opcode, data, bool(fin)
        start += offset + length

    if len(payload) > start:
        frameBuffer[:] = [payload[start:]]
    else:
        frameBuffer[:] = []


class IWebSocketsFrameReceiver(Interface):
    """
    An interface for receiving WebSockets frames.

    @since: 13.2
    """

    def makeConnection(transport):
        """
        Notification about the connection.

        @param transport: A L{WebSocketsTransport} instance wrapping an
            underlying transport.
        @type transport: L{WebSocketsTransport}.
        """

    def frameReceived(opcode, data, fin):
        """
        Callback when a frame is received.

        @type opcode: C{CONTROLS}
        @param opcode: The type of frame received.

        @type data: C{bytes}
        @param data: The content of the frame received.

        @type fin: C{bool}
        @param fin: Whether or not the frame is final.
        """


class WebSocketsTransport:
    """
    A frame transport for WebSockets.

    @ivar _transport: A reference to the real transport.

    @since: 13.2
    """

    _disconnecting = False

    def __init__(self, transport):
        self._transport = transport

    def sendFrame(self, opcode, data: bytes, fin: bool):
        """
        Build a frame packet and send it over the wire.

        @type opcode: C{CONTROLS}
        @param opcode: The type of frame to send.

        @type data: C{bytes}
        @param data: The content of the frame to send.

        @type fin: C{bool}
        @param fin: Whether or not we're sending a final frame.
        """
        packet = _makeFrame(data, opcode, fin)
        self._transport.write(packet)

    def loseConnection(self, code=STATUSES.NORMAL, reason: bytes = b""):
        """
        Close the connection.

        This includes telling the other side we're closing the connection.

        If the other side didn't signal that the connection is being closed,
        then we might not see their last message, but since their last message
        should, according to the spec, be a simple acknowledgement, it
        shouldn't be a problem.

        @param code: The closing frame status code.
        @type code: L{STATUSES}

        @param reason: Optionally, a utf-8 encoded text explaining why the
            connection was closed.
        @param reason: C{bytes}
        """
        # Send a closing frame. It's only polite. (And might keep the browser
        # from hanging.)
        if not self._disconnecting:
            data = b"%s%s" % (pack(">H", code.value), reason)
            frame = _makeFrame(data, CONTROLS.CLOSE, True)
            self._transport.write(frame)
            self._disconnecting = True
            self._transport.loseConnection()


class WebSocketsProtocol(Protocol):
    """
    A protocol parsing WebSockets frames and interacting with a
    L{IWebSocketsFrameReceiver} instance.

    @ivar _receiver: The L{IWebSocketsFrameReceiver} provider handling the
        frames.
    @type _receiver: L{IWebSocketsFrameReceiver} provider

    @ivar _buffer: The pending list of frames not processed yet.
    @type _buffer: C{list}

    @since: 13.2
    """

    _buffer = None

    def __init__(self, receiver):
        self._receiver = receiver

    def connectionMade(self):
        """
        Log the new connection and initialize the buffer list.
        """
        peer = self.transport.getPeer()
        log.debug("Opening connection with {peer}", peer=peer)
        self._buffer = []
        self._receiver.makeConnection(WebSocketsTransport(self.transport))

    def _parseFrames(self):
        """
        Find frames in incoming data and pass them to the underlying protocol.
        """
        for opcode, data, fin in _parseFrames(self._buffer):
            self._receiver.frameReceived(opcode, data, fin)
            if opcode == CONTROLS.CLOSE:
                # The other side wants us to close.
                code, reason = data
                msgFormat = "Closing connection: {code!r}"
                if reason:
                    msgFormat += " ({reason!r})"
                log.debug(msgFormat, reason=reason, code=code)

                # Close the connection.
                self.transport.loseConnection()
                return
            elif opcode == CONTROLS.PING:
                # 5.5.2 PINGs must be responded to with PONGs.
                # 5.5.3 PONGs must contain the data that was sent with the
                # provoking PING.
                self.transport.write(_makeFrame(data, CONTROLS.PONG, True))

    def dataReceived(self, data: bytes):
        """
        Append the data to the buffer list and parse the whole.

        @type data: C{bytes}
        @param data: The buffer received.
        """
        self._buffer.append(data)
        try:
            self._parseFrames()
        except _WSException:
            # Couldn't parse all the frames, something went wrong, let's bail.
            log.err()
            self.transport.loseConnection()


@implementer(IWebSocketsFrameReceiver)
class _WebSocketsProtocolWrapperReceiver:
    """
    A L{IWebSocketsFrameReceiver} which accumulates data frames and forwards
    the payload to its C{wrappedProtocol}.

    @ivar _wrappedProtocol: The connected protocol
    @type _wrappedProtocol: C{IProtocol} provider.

    @ivar _transport: A reference to the L{WebSocketsTransport}
    @type _transport: L{WebSocketsTransport}

    @ivar _messages: The pending list of payloads received.
    @types _messages: C{list}
    """

    def __init__(self, wrappedProtocol):
        self._wrappedProtocol = wrappedProtocol

    def makeConnection(self, transport):
        """
        Keep a reference to the given C{transport} and instantiate the list of
        messages.
        """
        self._transport = transport
        self._messages = []

    def frameReceived(self, opcode, data, fin: bool):
        """
        For each frame received, accumulate the data (ignoring the opcode), and
        forwarding the messages if C{fin} is set.

        @type opcode: C{CONTROLS}
        @param opcode: The type of frame received.

        @type data: C{bytes}
        @param data: The content of the frame received.

        @type fin: C{bool}
        @param fin: Whether or not the frame is final.
        """
        if opcode not in (CONTROLS.BINARY, CONTROLS.TEXT, CONTROLS.CONTINUE):
            return
        self._messages.append(data)
        if fin:
            content = b"".join(self._messages)
            self._messages[:] = []
            self._wrappedProtocol.dataReceived(content)


class WebSocketsProtocolWrapper(WebSocketsProtocol):
    """
    A L{WebSocketsProtocol} which wraps a regular C{IProtocol} provider,
    ignoring the frame mechanism.

    @ivar _wrappedProtocol: The connected protocol
    @type _wrappedProtocol: C{IProtocol} provider.

    @ivar defaultOpcode: The opcode used when C{transport.write} is called.
        Defaults to L{CONTROLS.TEXT}, can be L{CONTROLS.BINARY}.
    @type defaultOpcode: L{CONTROLS}

    @since: 13.2
    """

    def __init__(self, wrappedProtocol, defaultOpcode=CONTROLS.TEXT):
        self.wrappedProtocol = wrappedProtocol
        self.defaultOpcode = defaultOpcode
        WebSocketsProtocol.__init__(
            self, _WebSocketsProtocolWrapperReceiver(wrappedProtocol)
        )

    def makeConnection(self, transport):
        """
        Upon connection, provides the transport interface, and forwards ourself
        as the transport to C{self.wrappedProtocol}.

        @type transport: L{twisted.internet.interfaces.ITransport} provider.
        @param transport: The transport to use for the protocol.
        """
        directlyProvides(self, providedBy(transport))
        WebSocketsProtocol.makeConnection(self, transport)
        self.wrappedProtocol.makeConnection(self)

    def write(self, data: bytes):
        """
        Write to the websocket protocol, transforming C{data} in a frame.

        @type data: C{bytes}
        @param data: Data buffer used for the frame content.
        """
        self._receiver._transport.sendFrame(self.defaultOpcode, data, True)

    def writeSequence(self, data: Sequence):
        """
        Send all chunks from C{data} using C{write}.

        @type data: C{list} of C{bytes}
        @param data: Data buffers used for the frames content.
        """
        for chunk in data:
            self.write(chunk)

    def loseConnection(self, *args, **kwargs):
        """
        Try to lose the connection gracefully when closing by sending a close
        frame.
        """
        self._receiver._transport.loseConnection(*args, **kwargs)

    def __getattr__(self, name):
        """
        Forward all non-local attributes and methods to C{self.transport}.
        """
        return getattr(self.transport, name)

    def connectionLost(self, reason):
        """
        Forward C{connectionLost} to C{self.wrappedProtocol}.

        @type reason: L{twisted.python.failure.Failure}
        @param reason: A failure instance indicating the reason why the
            connection was lost.
        """
        self.wrappedProtocol.connectionLost(reason)


@implementer(IResource)
class WebSocketsResource:
    """
    A resource for serving a protocol through WebSockets.

    This class wraps a factory and connects it to WebSockets clients. Each
    connecting client will be connected to a new protocol of the factory.

    Due to unresolved questions of logistics, this resource cannot have
    children.

    @param lookupProtocol: A callable returning a tuple of
        (protocol instance, matched protocol name or C{None}) when called with
        a valid connection. It's called with a list of asked protocols from the
        client and the connecting client request. If the returned protocol name
        is specified, it is used as I{Sec-WebSocket-Protocol} value. If the
        protocol is a L{WebSocketsProtocol} instance, it will be connected
        directly, otherwise it will be wrapped by L{WebSocketsProtocolWrapper}.
        For simple use cases using a factory, you can use
        L{lookupProtocolForFactory}.
    @type lookupProtocol: C{callable}.

    @since: 13.2
    """

    isLeaf = True

    def __init__(self, lookupProtocol):
        self._lookupProtocol = lookupProtocol

    def getChildWithDefault(self, name, request):
        """
        Reject attempts to retrieve a child resource.  All path segments beyond
        the one which refers to this resource are handled by the WebSocket
        connection.

        @type name: C{bytes}
        @param name: A single path component from a requested URL.

        @type request: L{twisted.web.iweb.IRequest} provider
        @param request: The request received.
        """
        raise RuntimeError(
            "Cannot get IResource children from WebSocketsResource"
        )

    def putChild(self, path, child):
        """
        Reject attempts to add a child resource to this resource.  The
        WebSocket connection handles all path segments beneath this resource,
        so L{IResource} children can never be found.

        @type path: C{bytes}
        @param path: A single path component.

        @type child: L{IResource} provider
        @param child: A resource to put underneat this one.
        """
        raise RuntimeError(
            "Cannot put IResource children under WebSocketsResource"
        )

    def render(self, request):
        """
        Render a request.

        We're not actually rendering a request. We are secretly going to handle
        a WebSockets connection instead.

        @param request: The connecting client request.
        @type request: L{Request<twisted.web.http.Request>}

        @return: a string if the request fails, otherwise C{NOT_DONE_YET}.
        """
        request.defaultContentType = None
        # If we fail at all, we'll fail with 400 and no response.
        failed = False

        if request.method != b"GET":
            # 4.2.1.1 GET is required.
            failed = True

        upgrade = request.getHeader(b"Upgrade")
        if upgrade is None or b"websocket" not in upgrade.lower():
            # 4.2.1.3 Upgrade: WebSocket is required.
            failed = True

        connection = request.getHeader(b"Connection")
        if connection is None or b"upgrade" not in connection.lower():
            # 4.2.1.4 Connection: Upgrade is required.
            failed = True

        key = request.getHeader(b"Sec-WebSocket-Key")
        if key is None:
            # 4.2.1.5 The challenge key is required.
            failed = True

        version = request.getHeader(b"Sec-WebSocket-Version")
        if version != b"13":
            # 4.2.1.6 Only version 13 works.
            failed = True
            # 4.4 Forward-compatible version checking.
            request.setHeader(b"Sec-WebSocket-Version", b"13")

        if failed:
            request.setResponseCode(400)
            return b""

        askedProtocols = request.requestHeaders.getRawHeaders(
            b"Sec-WebSocket-Protocol"
        )
        protocol, protocolName = self._lookupProtocol(askedProtocols, request)

        # If a protocol is not created, we deliver an error status.
        if not protocol:
            request.setResponseCode(502)
            return b""

        # We are going to finish this handshake. We will return a valid status
        # code.
        # 4.2.2.5.1 101 Switching Protocols
        request.setResponseCode(101)
        # 4.2.2.5.2 Upgrade: websocket
        request.setHeader(b"Upgrade", b"WebSocket")
        # 4.2.2.5.3 Connection: Upgrade
        request.setHeader(b"Connection", b"Upgrade")
        # 4.2.2.5.4 Response to the key challenge
        request.setHeader(b"Sec-WebSocket-Accept", _makeAccept(key))
        # 4.2.2.5.5 Optional codec declaration
        if protocolName:
            request.setHeader(b"Sec-WebSocket-Protocol", protocolName)

        # Provoke request into flushing headers and finishing the handshake.
        request.write(b"")

        # And now take matters into our own hands. We shall manage the
        # transport's lifecycle.
        transport, request.transport = request.transport, None

        # Set the cookies on the transport. So the protocol can view the
        # cookies.
        transport.cookies = request.getHeader(b"cookie")

        # Set the uri on the transport. This allows the protocol to view the
        # uri.
        transport.uri = request.uri

        # Set the user-agent on the transport.  This allows the protocol to
        # view the user-agent.
        transport.user_agent = request.requestHeaders.getRawHeaders(
            "user-agent"
        )[0]

        # Set the peer IP on the transport.  This allows the protocol to view
        # the IP address of the client.
        transport.ip_address = getattr(
            request.getClientAddress(), "host", None
        )

        # Set the host.
        transport.host = request.requestHeaders.getRawHeaders("host")[0]

        if not isinstance(protocol, WebSocketsProtocol):
            protocol = WebSocketsProtocolWrapper(protocol)

        # Connect the transport to our factory, and make things go. We need to
        # do some stupid stuff here; see #3204, which could fix it.
        if isinstance(transport.protocol, TLSMemoryBIOProtocol):
            transport.protocol.wrappedProtocol = protocol
        else:
            transport.protocol = protocol
        protocol.makeConnection(transport)

        # Starting with Twisted 16.3+ `_cleanup` must be called on the request
        # so the socket is placed back into the reactor. `_cleanup` has always
        # existed, but was not required to be called until Twisted 16.3+.
        # `_cleanup` in Twisted 16.3+ checks to ensure that if content is None
        # to not call close, in previous versions it does not. To make this
        # code work on both all Twisted versions we must set content to
        # EmptyContent so an `AttributeError` is not raied when the content is
        # None. Only then can `_cleanup` be called safely. `finalize` also
        # exists on the request and is actually the public API, but this
        # method cannot be called because it will write invalid content to the
        # socket which will break the websocket connection.
        if request.content is None:

            class EmptyContent:
                def close(*args, **kwargs):
                    pass

            request.content = EmptyContent()
        request._cleanup()

        return NOT_DONE_YET


def lookupProtocolForFactory(factory):
    """
    Return a suitable C{lookupProtocol} argument for L{WebSocketsResource}
    which ignores the protocol names and just return a protocol instance built
    by C{factory}.

    @since: 13.2
    """

    def lookupProtocol(protocolNames, request):
        protocol = factory.buildProtocol(request.transport.getPeer())
        return protocol, None

    return lookupProtocol
