# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Enumerations meaningful to the provisioning server."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'ARP_HTYPE',
    'IPMI_DRIVER',
    'IPMI_DRIVER_CHOICES',
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

    # Sentry Switch CDU's.
    CDU = 'fence_cdu'

    # IPMI (Intelligent Platform Management Interface).
    IPMI = 'ipmi'

    # ILO4/bridging/IPMI
    MOONSHOT = 'moonshot'

    # The SeaMicro SM15000.
    # http://www.seamicro.com/sites/default/files/SM15000_Datasheet.pdf
    SEAMICRO15K = 'sm15k'


POWER_TYPE_CHOICES = (
    (POWER_TYPE.VIRSH, "virsh (virtual systems)"),
    (POWER_TYPE.WAKE_ON_LAN, "Wake-on-LAN"),
    (POWER_TYPE.CDU, "Sentry Switch CDU"),
    (POWER_TYPE.IPMI, "IPMI"),
    (POWER_TYPE.MOONSHOT, "iLO4 Moonshot Chassis"),
    (POWER_TYPE.SEAMICRO15K, "SeaMicro 15000"),
    )


class IPMI_DRIVER:
    DEFAULT = ''
    LAN = 'LAN'
    LAN_2_0 = 'LAN_2_0'


IPMI_DRIVER_CHOICES = (
    (IPMI_DRIVER.DEFAULT, "Auto-detect"),
    (IPMI_DRIVER.LAN, "LAN (IPMI 1.5)"),
    (IPMI_DRIVER.LAN_2_0, "LAN_2_0 (IPMI 2.0)"),
    )


class ARP_HTYPE:
    """ARP Hardware Type codes."""

    ETHERNET = 0x01
