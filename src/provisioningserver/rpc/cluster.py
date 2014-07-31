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
    "CreateHostMaps",
    "DescribePowerTypes",
    "GetPreseedData",
    "Identify",
    "ListBootImages",
    "ListOperatingSystems",
    "ListSupportedArchitectures",
    "PowerOff",
    "PowerOn",
    "ValidateLicenseKey",
]

from provisioningserver.power.poweraction import (
    PowerActionFail,
    UnknownPowerType,
    )
from provisioningserver.rpc import exceptions
from provisioningserver.rpc.arguments import (
    ParsedURL,
    StructureAsJSON,
    )
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


class ListOperatingSystems(amp.Command):
    """Report the cluster's supported operating systems.

    :since: 1.7
    """

    arguments = []
    response = [
        (b"osystems", amp.AmpList([
            (b"name", amp.Unicode()),
            (b"title", amp.Unicode()),
            (b"releases", amp.AmpList([
                (b"name", amp.Unicode()),
                (b"title", amp.Unicode()),
                (b"requires_license_key", amp.Boolean()),
                (b"can_commission", amp.Boolean()),
            ])),
            (b"default_release", amp.Unicode(optional=True)),
            (b"default_commissioning_release", amp.Unicode(optional=True)),
        ])),
    ]
    errors = []


class ValidateLicenseKey(amp.Command):
    """Validate an OS license key.

    :since: 1.7
    """

    arguments = [
        (b"osystem", amp.Unicode()),
        (b"release", amp.Unicode()),
        (b"key", amp.Unicode()),
    ]
    response = [
        (b"is_valid", amp.Boolean()),
    ]
    errors = {
        exceptions.NoSuchOperatingSystem: (
            b"NoSuchOperatingSystem"),
    }


class GetPreseedData(amp.Command):
    """Get OS-specific preseed data.

    :since: 1.7
    """

    arguments = [
        (b"osystem", amp.Unicode()),
        (b"preseed_type", amp.Unicode()),
        (b"node_system_id", amp.Unicode()),
        (b"node_hostname", amp.Unicode()),
        (b"consumer_key", amp.Unicode()),
        (b"token_key", amp.Unicode()),
        (b"token_secret", amp.Unicode()),
        (b"metadata_url", ParsedURL()),
    ]
    response = [
        (b"data", StructureAsJSON()),
    ]
    errors = {
        exceptions.NoSuchOperatingSystem: (
            b"NoSuchOperatingSystem"),
        NotImplementedError: (
            b"NotImplementedError"),
    }


class _Power(amp.Command):
    """Base class for power control commands.

    :since: 1.7
    """

    arguments = [
        (b"system_id", amp.Unicode()),
        (b"hostname", amp.Unicode()),
        (b"power_type", amp.Unicode()),
        # We can't define a tighter schema here because this is a highly
        # variable bag of arguments from a variety of sources.
        (b"context", StructureAsJSON()),
    ]
    response = []
    errors = {
        UnknownPowerType: (
            b"UnknownPowerType"),
        NotImplementedError: (
            b"NotImplementedError"),
        PowerActionFail: (
            b"PowerActionFail"),
    }


class PowerOn(_Power):
    """Turn a node's power on.

    :since: 1.7
    """


class PowerOff(_Power):
    """Turn a node's power off.

    :since: 1.7
    """


class CreateHostMaps(amp.Command):
    """Create host maps in the DHCP server's configuration.

    :since: 1.7
    """

    arguments = [
        (b"mappings", amp.AmpList([
            (b"ip_address", amp.Unicode()),
            (b"mac_address", amp.Unicode()),
        ])),
        (b"shared_key", amp.Unicode()),
    ]
    response = []
    errors = {
        exceptions.CannotCreateHostMap: (
            "CannotCreateHostMap"),
    }


class RemoveHostMaps(amp.Command):
    """Remove host maps from the DHCP server's configuration.

    :since: 1.7
    """

    arguments = [
        (b"ip_addresses", amp.ListOf(amp.Unicode())),
        (b"shared_key", amp.Unicode()),
    ]
    response = []
    errors = {
        exceptions.CannotRemoveHostMap: (
            "CannotRemoveHostMap"),
    }
