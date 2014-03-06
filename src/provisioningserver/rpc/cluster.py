# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""RPC declarations for clusters.

These are commands that a cluster controller ought to respond to.
"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "DescribePowerTypes",
    "Identify",
    "ListBootImages",
    "ListSupportedArchitectures",
]

from twisted.protocols import amp


class Identify(amp.Command):
    """Request the identity of the cluster, i.e. its UUID."""

    response = [(b"uuid", amp.Unicode())]


class ListBootImages(amp.Command):
    """List the boot images available on this cluster controller."""

    arguments = []
    response = [
        (b"images", amp.AmpList(
            [(b"architecture", amp.Unicode()),
             (b"subarchitecture", amp.Unicode()),
             (b"release", amp.Unicode()),
             (b"purpose", amp.Unicode())]))
    ]
    errors = []


class DescribePowerTypes(amp.Command):
    """Get a JSON Schema describing this cluster's power types."""

    arguments = []
    response = [
        (b"power_types", amp.Unicode())
    ]
    errors = []


class ListSupportedArchitectures(amp.Command):
    arguments = []
    response = [
        (b"architectures", amp.AmpList([
            (b"name", amp.Unicode()),
            (b"description", amp.Unicode()),
            ])),
    ]
    errors = []
