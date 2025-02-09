# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Utilities for working with Netplan."""

import re

from provisioningserver.logger import LegacyLogger

log = LegacyLogger()

# The keys in this dictionary match what is understood by ifupdown, via the
# `ifenslave` package. The values represent their netplan equivalents. The most
# current netplan documentation can be found at:
#     https://git.launchpad.net/netplan/tree/doc/netplan.md
#
# Last updated:
#     ifenslave-2.7ubuntu1 (See README.Debian, ifenslave.if-pre-up)
#     netplan git: e41215b (See doc/netplan.md)
#
# XXX: Some bond options do not seem to have netplan equivalents. See:
#   https://bugs.launchpad.net/netplan/+bug/1671453
ifenslave_to_netplan_bond_params = {
    "bond-ad-select": "ad-select",
    "bond-arp-interval": "arp-interval",
    # Note: this can be a list. (and must be a list in netplan)
    "bond-arp-ip-target": "arp-ip-targets",
    "bond-arp-validate": "arp-validate",
    "bond-downdelay": "down-delay",
    "bond-give-a-chance": "up-delay",
    "bond-lacp-rate": "lacp-rate",
    "bond-miimon": "mii-monitor-interval",
    "bond-mode": "mode",
    # XXX Introduce a mispelling to workaround LP: #1827238
    "bond-num-grat-arp": "gratuitious-arp",
    # This is just an internal alias for bond-num-grat-arp.
    "bond-num-unsol-na": "gratuitious-arp",
    #
    "bond-primary-reselect": "primary-reselect-policy",
    "bond-updelay": "up-delay",
    "bond-xmit-hash-policy": "transmit-hash-policy",
    # The following parameters were found in the docs, but don't
    # appear to be used in the ifenslave package:
    "bond-packets-per-slave": "packets-per-slave",
    # These parameters are available in Netplan, but not documented
    # in `ifenslave`:
    "bond-all-slaves-active": "all-slaves-active",
    "bond-arp-all-targets": "arp-all-targets",
    "bond-fail-over-mac-policy": "fail-over-mac-policy",
    "bond-learn-packet-interval": "learn-packet-interval",
    "bond-min-links": "min-links",
    # The following parameters are not documented or defined in Netplan:
    "bond-active-slave": None,
    "bond-fail-over-mac": None,
    "bond-master": None,
    "bond-primary": None,
    "bond-queue-id": None,
    "bond-slaves": None,
    "bond-use-carrier": None,
}


def _get_netplan_bond_parameter(key: str, value):
    """ "Returns the equivalent Netplan (key, value) for what was specified.

    :param key: The ifupdown/ifenslave bond configuration key.
        The key must be all lowecase, and use dash ('-') for its separator.
    :param value: The ifupdown/ifenslave bond configuration value.
    :return: The resulting (key, value) tuple, or the tuple (None, value) if no
        equivalent could be found.
    """
    key = ifenslave_to_netplan_bond_params.get(key)
    if key is not None:
        # Translate any netplan values which have different formats than
        # ifupdown/ifenslave.
        if key == "arp-ip-targets":
            value = list(filter(lambda x: x, re.split(r"\s+", value)))
        return key, value
    else:
        return None, value


def get_netplan_bond_parameters(ifenslave_params: dict):
    """Builds a Netplan parameters dictionary for the given bond parameters.

    :param ifenslave_params: A dictionary of ifupdown/ifenslave bond
        parameters.
    :return: the equivalent dictionary for Netplan.
    """
    netplan_parameters = dict()
    for key, value in ifenslave_params.items():
        netplan_key, netplan_value = _get_netplan_bond_parameter(key, value)
        if netplan_key is None:
            if key in ifenslave_to_netplan_bond_params:
                log.msg(
                    "Warning: no netplan equivalent for bond option: '%s=%r'."
                    % (key, value)
                )
            else:
                log.msg(f"Warning: unknown bond option: '{key}={value!r}'.")
        else:
            netplan_parameters[netplan_key] = netplan_value
    return netplan_parameters


# The keys in this dictionary match what is understood by ifupdown, via the
# `bridge-utils` package. The values represent their netplan equivalents.
#
# Last updated:
#     bridge-utils_1.5-9ubuntu1 (man 5 bridge-utils-interfaces)
#     netplan git: e41215b (See doc/netplan.md)
#
# XXX: Some bridge options do not seem to have netplan equivalents. See:
#   https://bugs.launchpad.net/netplan/+bug/1671544
bridgeutils_to_netplan_bridge_params = {
    "bridge_ageing": "ageing-time",
    "bridge_bridgeprio": "priority",
    "bridge_fd": "forward-delay",
    "bridge_hello": "hello-time",
    "bridge_maxage": "max-age",
    "bridge_pathcost": "path-cost",
    "bridge_stp": "stp",
    # The following parameters are not documented or defined in Netplan:
    "bridge_gcint": None,  # Bridge garbage collection interval.
    "bridge_hw": None,  # Bridge hardware address.
    "brdige_maxwait": None,  # Maximum time to wait for the bridge to be ready.
    "bridge_portprio": None,  # Bridge port priority.
    "bridge_ports": None,  # Bridge ports. (handled elsewhere)
    "bridge_waitport": None,  # If specified, will wait for the bridge.
}


def _get_netplan_bridge_parameter(key: str, value):
    """ "Returns the equivalent Netplan (key, value) for what was specified.

    :param key: The ifupdown/ifenslave bridge configuration key.
        The key must be all lowecase, and use dash ('-') for its separator.
    :param value: The ifupdown/ifenslave bridge configuration value.
    :return: The resulting (key, value) tuple, or the tuple (None, value) if no
        equivalent could be found.
    """
    key = bridgeutils_to_netplan_bridge_params.get(key)
    if key is not None:
        return key, value
    else:
        return None, value


def get_netplan_bridge_parameters(ifenslave_params: dict):
    """Builds a Netplan parameters dictionary for the given bridge parameters.

    :param ifenslave_params: A dictionary of ifupdown/ifenslave bridge
        parameters.
    :return: the equivalent dictionary for Netplan.
    """
    netplan_parameters = dict()
    for key, value in ifenslave_params.items():
        netplan_key, netplan_value = _get_netplan_bridge_parameter(key, value)
        if netplan_key is None:
            if key in bridgeutils_to_netplan_bridge_params:
                log.msg(
                    "Warning: no netplan equivalent for bridge option: "
                    "'%s=%r'." % (key, value)
                )
            else:
                log.msg(f"Warning: unknown bridge option: '{key}={value!r}'.")
        else:
            netplan_parameters[netplan_key] = netplan_value
    return netplan_parameters
