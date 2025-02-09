# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Utilities for working with TFTP and ``python-tx-tftp``."""

from twisted.python.context import get

# Paths in TFTP are always byte strings.
TFTPPath = bytes


def get_local_address():
    """Return the ``(host, port)`` for the local side of a TFTP transfer.

    This is important on a cluster controller that manages multiple networks.

    This is populated by ``python-tx-tftp``, and is only available in
    ``IBackend.get_reader()`` and ``IBackend.get_writer()``

    :return: A 2-tuple containing the address and port for the local side of
        the transfer.
    """
    return extract_address(get("local"))


def get_remote_address():
    """Return the ``(host, port)`` for the remote side of a TFTP transfer.

    This is important on a cluster controller that manages multiple networks.

    This is populated by ``python-tx-tftp``, and is only available in
    ``IBackend.get_reader()`` and ``IBackend.get_writer()``

    :return: A 2-tuple containing the address and port for the remote side of
        the transfer.
    """
    return extract_address(get("remote"))


def extract_address(addr):
    if addr is None:
        return None, None
    elif len(addr) >= 2:
        # Some versions of Twisted have the scope and flow info in the remote
        # address tuple; see https://twistedmatrix.com/trac/ticket/6826 (the
        # address is captured by tftp.protocol.TFTP.dataReceived). We want
        # only the first two elements of the addr tuple: host and port.
        return addr[0], addr[1]
    else:
        raise AssertionError(
            "The address tuple must contain at least 2 "
            "elements, got: %r" % (addr,)
        )
