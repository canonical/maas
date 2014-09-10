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
    "ConfigureDHCPv4",
    "ConfigureDHCPv6",
    "CreateHostMaps",
    "DescribePowerTypes",
    "GetPreseedData",
    "Identify",
    "ListBootImages",
    "ListOperatingSystems",
    "ListSupportedArchitectures",
    "PowerOff",
    "PowerOn",
    "PowerQuery",
    "ValidateLicenseKey",
]

from provisioningserver.power.poweraction import (
    PowerActionFail,
    UnknownPowerType,
    )
from provisioningserver.rpc import exceptions
from provisioningserver.rpc.arguments import (
    Bytes,
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
             (b"purpose", amp.Unicode()),
             (b"xinstall_type", amp.Unicode()),
             (b"xinstall_path", amp.Unicode())]))
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


class PowerQuery(_Power):
    """Query a node's power state.

    :since: 1.7
    """
    response = [
        (b"state", amp.Unicode()),
    ]


class _ConfigureDHCP(amp.Command):
    """Configure a DHCP server.

    :since: 1.7
    """
    arguments = [
        (b"omapi_key", amp.Unicode()),
        (b"subnet_configs", amp.AmpList([
            (b"subnet", amp.Unicode()),
            (b"subnet_mask", amp.Unicode()),
            (b"subnet_cidr", amp.Unicode()),
            (b"broadcast_ip", amp.Unicode()),
            (b"interface", amp.Unicode()),
            (b"router_ip", amp.Unicode()),
            (b"dns_servers", amp.Unicode()),
            (b"ntp_server", amp.Unicode()),
            (b"domain_name", amp.Unicode()),
            (b"ip_range_low", amp.Unicode()),
            (b"ip_range_high", amp.Unicode()),
            ])),
        ]
    response = []
    errors = {exceptions.CannotConfigureDHCP: b"CannotConfigureDHCP"}


class ConfigureDHCPv4(_ConfigureDHCP):
    """Configure the DHCPv4 server.

    :since: 1.7
    """


class ConfigureDHCPv6(_ConfigureDHCP):
    """Configure the DHCPv6 server.

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


class ImportBootImages(amp.Command):
    """Import boot images and report the final
    boot images that exist on the cluster.

    :since: 1.7
    """

    arguments = [
        (b"sources", amp.AmpList(
            [(b"url", amp.Unicode()),
             (b"keyring_data", Bytes()),
             (b"selections", amp.AmpList(
                 [(b"os", amp.Unicode()),
                  (b"release", amp.Unicode()),
                  (b"arches", amp.ListOf(amp.Unicode())),
                  (b"subarches", amp.ListOf(amp.Unicode())),
                  (b"labels", amp.ListOf(amp.Unicode()))]))])),
    ]
    response = []
    errors = []


class StartTimers(amp.Command):
    """Starts timer(s) on the cluster.

    The region controller invokes this on a cluster controller and the
    cluster will call the region back with TimerExpired if the deadline
    is reached before the region calls CancelTimer.  It is the region's
    responsibility to provide an ID for the timers.

    :since: 1.7
    """

    arguments = [
        (b"timers", amp.AmpList(
            [(b"deadline", amp.DateTime()),
             (b"context", StructureAsJSON()),
             (b"id", amp.Unicode()),
             ]))
    ]
    response = []
    errors = []


class CancelTimer(amp.Command):
    """Cancels an existing timer on the cluster.

    :since: 1.7
    """

    arguments = [
        (b"id", amp.Unicode()),
        ]
    response = []
    error = []


class AddVirsh(amp.Command):
    """Probe for and enlist virsh VMs attached to the cluster.

    :since: 1.7
    """

    arguments = [
        (b"poweraddr", amp.Unicode()),
        (b"password", amp.Unicode(optional=True)),
    ]
    response = []
    errors = []


class AddSeaMicro15k(amp.Command):
    """Probe for and enlist seamicro15k machines attached to the cluster.

    :since: 1.7
    """
    arguments = [
        (b"mac", amp.Unicode()),
        (b"username", amp.Unicode()),
        (b"password", amp.Unicode()),
        (b"power_control", amp.Unicode(optional=True)),
    ]
    response = []
    errors = {
        exceptions.NoIPFoundForMACAddress: b"NoIPFoundForMACAddress",
    }
