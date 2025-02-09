# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""
Monkey patch for the MAAS provisioning server, with code for rack and region
server patching.
"""


def fix_tftp_requests():
    """Use intelligence in determining IPv4 vs IPv6 when creatinging a session.

    Specifically, look at addr[0] and pass iface to listenUDP based on that.

    See https://bugs.launchpad.net/ubuntu/+source/python-tx-tftp/+bug/1614581
    """
    from netaddr import IPAddress
    from tftp.bootstrap import (
        RemoteOriginReadSession,
        RemoteOriginWriteSession,
    )
    from tftp.datagram import (
        ERR_ACCESS_VIOLATION,
        ERR_FILE_EXISTS,
        ERR_FILE_NOT_FOUND,
        ERR_ILLEGAL_OP,
        ERR_NOT_DEFINED,
        ERRORDatagram,
        OP_RRQ,
        OP_WRQ,
    )
    from tftp.errors import (
        AccessViolation,
        BackendError,
        FileExists,
        FileNotFound,
        Unsupported,
    )
    from tftp.netascii import NetasciiReceiverProxy, NetasciiSenderProxy
    import tftp.protocol
    from twisted.internet import reactor
    from twisted.internet.defer import inlineCallbacks, returnValue
    from twisted.python.context import call

    @inlineCallbacks
    def new_startSession(self, datagram, addr, mode):
        # Set up a call context so that we can pass extra arbitrary
        # information to interested backends without adding extra call
        # arguments, or switching to using a request object, for example.
        context = {}
        if self.transport is not None:
            # Add the local and remote addresses to the call context.
            local = self.transport.getHost()
            context["local"] = local.host, local.port
            context["remote"] = addr
        try:
            if datagram.opcode == OP_WRQ:
                fs_interface = yield call(
                    context, self.backend.get_writer, datagram.filename
                )
            elif datagram.opcode == OP_RRQ:
                fs_interface = yield call(
                    context, self.backend.get_reader, datagram.filename
                )
        except Unsupported as e:
            self.transport.write(
                ERRORDatagram.from_code(
                    ERR_ILLEGAL_OP, f"{e}".encode("ascii", "replace")
                ).to_wire(),
                addr,
            )
        except AccessViolation:
            self.transport.write(
                ERRORDatagram.from_code(ERR_ACCESS_VIOLATION).to_wire(), addr
            )
        except FileExists:
            self.transport.write(
                ERRORDatagram.from_code(ERR_FILE_EXISTS).to_wire(), addr
            )
        except FileNotFound:
            self.transport.write(
                ERRORDatagram.from_code(ERR_FILE_NOT_FOUND).to_wire(), addr
            )
        except BackendError as e:
            self.transport.write(
                ERRORDatagram.from_code(
                    ERR_NOT_DEFINED, f"{e}".encode("ascii", "replace")
                ).to_wire(),
                addr,
            )
        else:
            if IPAddress(addr[0]).version == 6:
                iface = "::"
            else:
                iface = ""
            if datagram.opcode == OP_WRQ:
                if mode == b"netascii":
                    fs_interface = NetasciiReceiverProxy(fs_interface)
                session = RemoteOriginWriteSession(
                    addr, fs_interface, datagram.options, _clock=self._clock
                )
                reactor.listenUDP(0, session, iface)
                returnValue(session)
            elif datagram.opcode == OP_RRQ:
                if mode == b"netascii":
                    fs_interface = NetasciiSenderProxy(fs_interface)
                session = RemoteOriginReadSession(
                    addr, fs_interface, datagram.options, _clock=self._clock
                )
                reactor.listenUDP(0, session, iface)
                returnValue(session)

    tftp.protocol.TFTP._startSession = new_startSession


def get_patched_URI():
    """Create the patched `twisted.web.client.URI` to handle IPv6."""
    import re

    from twisted.web import http
    from twisted.web.client import URI

    class PatchedURI(URI):
        @classmethod
        def fromBytes(cls, uri, defaultPort=None):
            """Patched replacement for `twisted.web.client._URI.fromBytes`.

            The Twisted version of this function breaks when you give it a URL
            whose netloc is based on an IPv6 address.
            """
            uri = uri.strip()
            scheme, netloc, path, params, query, fragment = http.urlparse(uri)

            if defaultPort is None:
                scheme_ports = {b"https": 443, b"http": 80}
                defaultPort = scheme_ports.get(scheme, 80)

            if b"[" in netloc:
                # IPv6 address.  This is complicated.
                parsed_netloc = re.match(
                    b"\\[(?P<host>[0-9A-Fa-f:.]+)\\]([:](?P<port>[0-9]+))?$",
                    netloc,
                )
                host, port = parsed_netloc.group("host", "port")
            elif b":" in netloc:
                # IPv4 address or hostname, with port spec.  This is easy.
                host, port = netloc.split(b":")
            else:
                # IPv4 address or hostname, without port spec.
                # This is trivial.
                host = netloc
                port = None

            if port is None:
                port = defaultPort
            try:
                port = int(port)
            except ValueError:
                port = defaultPort

            return cls(
                scheme, netloc, host, port, path, params, query, fragment
            )

    return PatchedURI


def fix_twisted_web_client_URI():
    """Patch the `twisted.web.client.URI` to handle IPv6."""
    import twisted.web.client

    PatchedURI = get_patched_URI()

    if hasattr(twisted.web.client, "_URI"):
        twisted.web.client._URI = PatchedURI
    else:
        twisted.web.client.URI = PatchedURI


def fix_twisted_web_http_Request():
    """Fix broken IPv6 handling in twisted.web.http.request.Request."""
    from netaddr import IPAddress
    from netaddr.core import AddrFormatError
    from twisted.internet import address
    from twisted.python.compat import networkString
    import twisted.web.http
    from twisted.web.server import Request
    from twisted.web.test.requesthelper import DummyChannel

    def new_getRequestHostname(self):
        # Unlike upstream, support/require IPv6 addresses to be
        # [ip:v6:add:ress]:port, with :port being optional.
        # IPv6 IP addresses are wrapped in [], to disambigate port numbers.
        host = self.getHeader(b"host")
        if host:
            if host.startswith(b"[") and b"]" in host:
                if host.find(b"]") < host.rfind(b":"):
                    # The format is: [ip:add:ress]:port.
                    return host[: host.rfind(b":")]
                else:
                    # no :port after [...]
                    return host
            # No brackets, so it must be host:port or IPv4:port.
            return host.split(b":", 1)[0]
        host = self.getHost().host
        try:
            if isinstance(host, str):
                ip = IPAddress(host)
            else:
                ip = IPAddress(host.decode("idna"))
        except AddrFormatError:
            # If we could not convert the hostname to an IPAddress, assume that
            # it is a hostname.
            return networkString(host)
        if ip.version == 4:
            return networkString(host)
        else:
            return networkString("[" + host + "]")

    def new_setHost(self, host, port, ssl=0):
        try:
            ip = IPAddress(host.decode("idna"))
        except AddrFormatError:
            ip = None  # `host` is a host or domain name.
        self._forceSSL = ssl  # set first so isSecure will work
        if self.isSecure():
            default = 443
        else:
            default = 80
        if ip is None or ip.version == 4:
            hostHeader = host
        else:
            hostHeader = networkString(f"[{host}]")
        if port != default:
            hostHeader += networkString(f":{port}")
        self.requestHeaders.setRawHeaders(b"host", [hostHeader])
        if ip is None:
            # Pretend that a host or domain name is an IPv4 address.
            self.host = address.IPv4Address("TCP", host, port)
        elif ip.version == 4:
            self.host = address.IPv4Address("TCP", host, port)
        else:
            self.host = address.IPv6Address("TCP", host, port)

    request = Request(DummyChannel(), False)
    request.client = address.IPv6Address("TCP", "fe80::1", "80")
    request.setHost(b"fe80::1", 1234)
    if isinstance(request.host, address.IPv4Address):
        # Buggy code calls fe80::1 an IPv4Address.
        twisted.web.http.Request.setHost = new_setHost
    if request.getRequestHostname() == b"fe80":
        # The fe80::1 test address above was incorrectly interpreted as
        # address='fe80', port = ':1', because it does host.split(':', 1)[0].
        twisted.web.http.Request.getRequestHostname = new_getRequestHostname

    def new_getHost(self):
        """See https://twistedmatrix.com/trac/ticket/5406"""
        if type(self.host) is address.UNIXAddress:
            return address.IPv4Address("TCP", "127.0.0.1", "80")

        return self.host

    twisted.web.http.Request.getHost = new_getHost

    def new_getClientAddress(self):
        """See https://twistedmatrix.com/trac/ticket/5406"""
        if type(self.client) is address.UNIXAddress:
            return address.IPv4Address("TCP", "127.0.0.1", "80")

        return self.client

    twisted.web.http.Request.getClientAddress = new_getClientAddress


def fix_twisted_web_server_addressToTuple():
    """Add ipv6 support to t.w.server._addressToTuple()

    Return address.IPv6Address where appropriate.

    See https://bugs.launchpad.net/ubuntu/+source/twisted/+bug/1604608
    """
    from twisted.internet import address
    import twisted.web.server

    def new_addressToTuple(addr):
        if isinstance(addr, address.IPv4Address):
            return ("INET", addr.host, addr.port)
        elif isinstance(addr, address.IPv6Address):
            return ("INET6", addr.host, addr.port)
        elif isinstance(addr, address.UNIXAddress):
            return ("UNIX", addr.name)
        else:
            return tuple(addr)

    test = address.IPv6Address("TCP", "fe80::1", "80")
    try:
        twisted.web.server._addressToTuple(test)
    except TypeError:
        twisted.web.server._addressToTuple = new_addressToTuple


def fix_twisted_internet_tcp():
    """Default client to AF_INET6 sockets.

    Specifically, strip any brackets surrounding the address.

    See https://bugs.launchpad.net/ubuntu/+source/twisted/+bug/1604608
    """
    import socket

    import twisted.internet.tcp
    from twisted.internet.tcp import _NUMERIC_ONLY

    def new_resolveIPv6(ip, port):
        # Remove brackets surrounding the address, if any.
        ip = ip.strip("[]")
        return socket.getaddrinfo(ip, port, 0, 0, 0, _NUMERIC_ONLY)[0][4]

    twisted.internet.tcp._resolveIPv6 = new_resolveIPv6


def augment_twisted_deferToThreadPool():
    """Wrap every function deferred to a thread in `synchronous`."""
    from twisted.internet import threads
    from twisted.internet.threads import deferToThreadPool

    from provisioningserver.utils.twisted import ISynchronous, synchronous

    def new_deferToThreadPool(reactor, threadpool, f, *args, **kwargs):
        """Variant of Twisted's that wraps all functions in `synchronous`."""
        func = f if ISynchronous.providedBy(f) else synchronous(f)
        return deferToThreadPool(reactor, threadpool, func, *args, **kwargs)

    if threads.deferToThreadPool.__module__ != __name__:
        threads.deferToThreadPool = new_deferToThreadPool


def add_patches_to_txtftp():
    fix_tftp_requests()


def add_patches_to_twisted():
    fix_twisted_web_client_URI()
    fix_twisted_web_http_Request()
    fix_twisted_web_server_addressToTuple()
    fix_twisted_internet_tcp()
    augment_twisted_deferToThreadPool()
