# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Interfaces for the RPC implementation."""


from zope import interface


class IConnection(interface.Interface):
    ident = interface.Attribute(
        "ident", "An identifier for the far end of the connection."
    )

    hostCertificate = interface.Attribute(
        "hostCertificate", "The certificate used locally for TLS."
    )

    peerCertificate = interface.Attribute(
        "peerCertificate", "The certificate used remotely for TLS."
    )

    def callRemote(cmd, **arguments):
        """Call a remote method with the given arguments."""


class IConnectionToRegion(IConnection):
    localIdent = interface.Attribute(
        "ident", "An identifier for this end of the connection."
    )

    address = interface.Attribute(
        "address", "The address of the far end of the connection."
    )
