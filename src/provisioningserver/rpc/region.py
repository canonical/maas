# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""RPC declarations for the region.

These are commands that a region controller ought to respond to.
"""

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

from provisioningserver.rpc.arguments import Bytes
from provisioningserver.rpc.common import Identify
from twisted.protocols import amp


class ReportBootImages(amp.Command):
    """Report boot images available on the invoking cluster controller."""

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


class GetBootSources(amp.Command):
    """Report boot sources and selections for the given cluster."""

    arguments = [
        # The cluster UUID.
        (b"uuid", amp.Unicode()),
    ]
    response = [
        (b"sources", amp.AmpList(
            [(b"url", amp.Unicode()),
             (b"keyring", Bytes()),
             (b"selections", amp.AmpList(
                 [(b"release", amp.Unicode()),
                  (b"arches", amp.ListOf(amp.Unicode())),
                  (b"subarches", amp.ListOf(amp.Unicode())),
                  (b"labels", amp.ListOf(amp.Unicode()))]))])),
    ]
    errors = []
