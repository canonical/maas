# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""RPC declarations for clusters."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "Identify",
    "ListBootImages",
]

from twisted.protocols import amp


class Identify(amp.Command):
    """Request the identity of the cluster, i.e. its UUID."""

    response = [(b"uuid", amp.Unicode())]


class ListBootImages(amp.Command):
    arguments = []
    response = [
        (b"images", amp.AmpList(
            [(b"architecture", amp.Unicode()),
             (b"subarchitecture", amp.Unicode()),
             (b"release", amp.Unicode()),
             (b"purpose", amp.Unicode())]))
    ]
    errors = []
