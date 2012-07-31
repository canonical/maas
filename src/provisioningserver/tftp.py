# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Twisted Application Plugin for the MAAS TFTP server."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    "TFTPBackend",
    ]

from io import BytesIO
from itertools import repeat
import re
from urllib import urlencode
from urlparse import (
    parse_qsl,
    urlparse,
    )

from provisioningserver.enum import ARP_HTYPE
from provisioningserver.utils import deferred
from tftp.backend import (
    FilesystemSynchronousBackend,
    IReader,
    )
from twisted.web.client import getPage
from zope.interface import implementer


@implementer(IReader)
class BytesReader:

    def __init__(self, data):
        super(BytesReader, self).__init__()
        self.buffer = BytesIO(data)
        self.size = len(data)

    def read(self, size):
        return self.buffer.read(size)

    def finish(self):
        self.buffer.close()


class TFTPBackend(FilesystemSynchronousBackend):
    """A partially dynamic read-only TFTP server.

    Requests for PXE configurations are forwarded to a configurable URL. See
    `re_config_file` and `re_mac_address`.

    This must be very selective about which requests to forward, because
    failures cause the boot process to halt. This is why the expression for
    matching the MAC address is so narrowly defined; PXELINUX attempts to
    fetch files at many similar paths, and this must respond to only one
    pattern.
    """

    get_page = staticmethod(getPage)

    # This is how PXELINUX represents a MAC address. See
    # http://www.syslinux.org/wiki/index.php/PXELINUX.
    re_mac_address_octet = r'[0-9a-f]{2}'
    re_mac_address = re.compile(
        "-".join(repeat(re_mac_address_octet, 6)))

    # We assume that the ARP HTYPE (hardware type) that PXELINUX sends is
    # alway Ethernet.
    re_config_file = re.compile(
        r'''
        ^/?
        maas     # Static namespacing.
        /
        (?P<arch>[^/]+)     # Capture arch.
        /
        (?P<subarch>[^/]+)    # Capture subarch.
        /
        pxelinux[.]cfg    # PXELINUX expects this.
        /
        {htype:02x}    # ARP HTYPE.
        -
        (?P<mac>{re_mac_address.pattern})    # Capture MAC.
        $
        '''.format(
            htype=ARP_HTYPE.ETHERNET,
            re_mac_address=re_mac_address),
        re.VERBOSE)

    def __init__(self, base_path, generator_url):
        """
        :param base_path: The root directory for this TFTP server.
        :param generator_url: The URL which can be queried for the PXE
            config. See `get_generator_url` for the types of queries it is
            expected to accept.
        """
        super(TFTPBackend, self).__init__(
            base_path, can_read=True, can_write=False)
        self.generator_url = urlparse(generator_url)

    def get_generator_url(self, params):
        """Calculate the URL, including query, that the PXE config is at.

        :param params: A dict, or iterable suitable for updating a dict, of
            additional query parameters.
        """
        # TODO: update query defaults.
        query = {
            b"title": b"",
            b"kernel": b"",
            b"initrd": b"",
            b"append": b"",
            }
        # Merge parameters from the generator URL.
        query.update(parse_qsl(self.generator_url.query))
        # Merge parameters obtained from the request.
        query.update(params)
        # Merge updated query into the generator URL.
        url = self.generator_url._replace(query=urlencode(query))
        # TODO: do something more intelligent with unicode URLs here; see
        # maas_client._ascii_url() for inspiration.
        return url.geturl().encode("ascii")

    @deferred
    def get_reader(self, file_name):
        """See `IBackend.get_reader()`.

        If `file_name` matches `re_config_file` then the response is obtained
        from a remote server. Otherwise the filesystem is used to service the
        response.
        """
        config_file_match = self.re_config_file.match(file_name)
        if config_file_match is None:
            return super(TFTPBackend, self).get_reader(file_name)
        else:
            params = config_file_match.groupdict()
            url = self.get_generator_url(params)
            d = self.get_page(url)
            d.addCallback(BytesReader)
            return d
