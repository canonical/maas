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

from provisioningserver.rpc.arguments import StructureAsJSON
from provisioningserver.rpc.common import Identify
from twisted.protocols import amp


class ListBootImages(amp.Command):
    """List the boot images available on this cluster controller.

    :since: 1.5
    """

    arguments = []
    response = [
        (b"images", amp.AmpList(
            [(b"osystem", amp.Unicode()),
             (b"architecture", amp.Unicode()),
             (b"subarchitecture", amp.Unicode()),
             (b"release", amp.Unicode()),
             (b"label", amp.Unicode()),
             (b"purpose", amp.Unicode())]))
    ]
    errors = []


class DescribePowerTypes(amp.Command):
    """Get a JSON Schema describing this cluster's power types.

    :since: 1.5
    """

    arguments = []
    response = [
        (b"power_types", StructureAsJSON()),
    ]
    errors = []


class ListSupportedArchitectures(amp.Command):
    """Report the cluster's supported architectures.

    :since: 1.5
    """

    arguments = []
    response = [
        (b"architectures", amp.AmpList([
            (b"name", amp.Unicode()),
            (b"description", amp.Unicode()),
            ])),
    ]
    errors = []
