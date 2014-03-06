# Copyright 2012-2014 Canonical Ltd.  This software is licensed under the
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
    'UNKNOWN_POWER_TYPE',
    ]


# We specifically declare this here so that a node not knowing its own
# powertype won't fail to enlist. However, we don't want it in the list
# of power types since setting a node's power type to "I don't know"
# from another type doens't make any sense.
UNKNOWN_POWER_TYPE = ''


class IPMI_DRIVER:
    DEFAULT = ''
    LAN = 'LAN'
    LAN_2_0 = 'LAN_2_0'


IPMI_DRIVER_CHOICES = [
    [IPMI_DRIVER.LAN, "LAN [IPMI 1.5]"],
    [IPMI_DRIVER.LAN_2_0, "LAN_2_0 [IPMI 2.0]"],
    ]


class ARP_HTYPE:
    """ARP Hardware Type codes."""

    ETHERNET = 0x01
