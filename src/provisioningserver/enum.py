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
    'ARP_HTYPE',
    'POWER_TYPE',
    'POWER_TYPE_CHOICES',
    ]


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
    IPMI = 'ipmitool'

    # IPMI over LAN.
    IPMI_LAN = 'ipmilan'


POWER_TYPE_CHOICES = (
    (POWER_TYPE.VIRSH, "virsh (virtual systems)"),
    (POWER_TYPE.WAKE_ON_LAN, "Wake-on-LAN"),
    (POWER_TYPE.IPMI, "IPMI v1.5 (LAN Interface)"),
    (POWER_TYPE.IPMI_LAN, "IPMI v2.0 (RMCP+ LAN Interface)"),
    )


class ARP_HTYPE:
    """ARP Hardware Type codes."""

    ETHERNET = 0x01
