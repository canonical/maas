# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""
Monkey patch for the MAAS provisioning server, with code for rack and region
server patching.
"""

__all__ = [
    "add_term_error_code_to_tftp",
    "add_patches_to_twisted",
]


def add_term_error_code_to_tftp():
    """Add error code 8 to TFT server as introduced by RFC 2347.

    Manually apply the fix to python-tx-tftp landed in
    https://github.com/shylent/python-tx-tftp/pull/20
    """
    import tftp.datagram
    if tftp.datagram.errors.get(8) is None:
        tftp.datagram.errors[8] = (
            "Terminate transfer due to option negotiation")


def fix_twisted_web_http_Request():
    """Add ipv6 support to Request.getClientIP()

       See https://bugs.launchpad.net/ubuntu/+source/twisted/+bug/1604608
    """
    from netaddr import IPAddress
    from netaddr.core import AddrFormatError
    from twisted.internet import address
    from twisted.python.compat import intToBytes
    import twisted.web.http
    from twisted.web.server import Request
    from twisted.web.test.requesthelper import DummyChannel

    def new_getClientIP(self):
        from twisted.internet import address
        if isinstance(self.client, address.IPv4Address):
            return self.client.host
        elif isinstance(self.client, address.IPv6Address):
            return self.client.host
        else:
            return None

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
        if ip is None:
            hostHeader = host
        elif ip.version == 4:
            hostHeader = host
        else:
            hostHeader = b"[" + host + b"]"
        if port != default:
            hostHeader += b":" + intToBytes(port)
        self.requestHeaders.setRawHeaders(b"host", [hostHeader])
        if ip is None:
            # Pretend that a host or domain name is an IPv4 address.
            self.host = address.IPv4Address("TCP", host, port)
        if ip.version == 4:
            self.host = address.IPv4Address("TCP", host, port)
        else:
            self.host = address.IPv6Address("TCP", host, port)

    request = Request(DummyChannel(), False)
    request.client = address.IPv6Address('TCP', 'fe80::1', '80')
    request.setHost(b"fe80::1", 1234)
    if request.getClientIP() is None:
        twisted.web.http.Request.getClientIP = new_getClientIP
    if isinstance(request.host, address.IPv4Address):
        twisted.web.http.Request.setHost = new_setHost


def fix_twisted_web_server_addressToTuple():
    """Add ipv6 support to t.w.server._addressToTuple()

       See https://bugs.launchpad.net/ubuntu/+source/twisted/+bug/1604608
    """
    import twisted.web.server
    from twisted.internet import address

    def new_addressToTuple(addr):
        if isinstance(addr, address.IPv4Address):
            return ('INET', addr.host, addr.port)
        elif isinstance(addr, address.IPv6Address):
            return ('INET6', addr.host, addr.port)
        elif isinstance(addr, address.UNIXAddress):
            return ('UNIX', addr.name)
        else:
            return tuple(addr)

    test = address.IPv6Address("TCP", "fe80::1", '80')
    try:
        twisted.web.server._addressToTuple(test)
    except TypeError:
        twisted.web.server._addressToTuple = new_addressToTuple


def add_patches_to_twisted():
    fix_twisted_web_http_Request()
    fix_twisted_web_server_addressToTuple()
