# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Interfaces for the RPC implementation."""

__all__ = []

from zope import interface


class IConnection(interface.Interface):

    ident = interface.Attribute(
        "ident", "An identifier far end of the connection.")

    hostCertificate = interface.Attribute(
        "hostCertificate", "The certificate used locally for TLS.")

    peerCertificate = interface.Attribute(
        "peerCertificate", "The certificate used remotely for TLS.")

    def callRemote(cmd, **arguments):
        """Call a remote method with the given arguments."""
