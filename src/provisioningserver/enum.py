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
    'get_power_types',
    ]


# We specifically declare this here so that a node not knowing its own
# powertype won't fail to enlist. However, we don't want it in the list
# of power types since setting a node's power type to "I don't know"
# from another type doens't make any sense.
UNKNOWN_POWER_TYPE = ''


def get_power_types():
    """Return the choice of mechanism to control a node's power.

    :return: Dictionary mapping power type to its description.
    """
    return {
        "virsh": "virsh (virtual systems)",
        "ether_wake": "Wake-on-LAN",
        "fence_cdu": "Sentry Switch CDU",
        "ipmi": "IPMI",
        "moonshot": "iLO4 Moonshot Chassis",
        "sm15k": "SeaMicro 15000",
        "amt": "Intel AMT",
        "dli": "Digital Loggers, Inc. PDU",
        }


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
