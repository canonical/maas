# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Enumerations meaningful to the provisioning server."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    'POWER_TYPE',
    'POWER_TYPE_CHOICES',
    'PSERV_FAULT',
    ]


class PSERV_FAULT:
    """Fault codes for errors raised by the provisioning server."""

    # Could not communicate with Cobbler.
    NO_COBBLER = 2

    # Failed to authenticate with Cobbler.
    COBBLER_AUTH_FAILED = 3

    # Cobbler no longer accepts the provisioning server's login token.
    COBBLER_AUTH_ERROR = 4

    # Profile does not exist.
    NO_SUCH_PROFILE = 5

    # Error looking up cobbler server.
    COBBLER_DNS_LOOKUP_ERROR = 6

    # Non-specific error inside Cobbler.
    GENERIC_COBBLER_ERROR = 99


class POWER_TYPE:
    """Choice of mechanism to control a node's power."""

    # The null value.  Set this to indicate that the value should be
    # taken from the configured default.
    # Django doesn't deal well with null strings, so we're forced to use
    # the empty string instead.  Hopefully this will be replaced with
    # None at some point.
    DEFAULT = ''

    # Use virsh (for virtual machines).
    VIRSH = 'virsh'

    # Network wake-up.
    WAKE_ON_LAN = 'ether_wake'

    # IPMI (Intelligent Platform Management Interface).
    IPMI = 'ipmi'

    # IPMI over LAN.
    IPMI_LAN = 'ipmi_lan'


POWER_TYPE_CHOICES = (
    (POWER_TYPE.VIRSH, "virsh (virtual systems)"),
    (POWER_TYPE.WAKE_ON_LAN, "Wake-on-LAN"),
    )
