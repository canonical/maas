# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""RPC declarations for the region."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "Identify",
    "ReportBootImages",
]

from twisted.protocols import amp


class Identify(amp.Command):
    """Request the identity of the region, i.e. the event-loop name."""

    response = [(b"name", amp.Unicode())]


class ReportBootImages(amp.Command):
    arguments = [
        # The cluster UUID.
        (b"uuid", amp.Unicode()),
        (b"images", amp.AmpList(
            [(b"architecture", amp.Unicode()),
             (b"subarchitecture", amp.Unicode()),
             (b"release", amp.Unicode()),
             (b"purpose", amp.Unicode())])),
    ]
    response = []
    errors = []
