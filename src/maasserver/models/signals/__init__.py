# Copyright 2015-2019 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Signals coming off models."""

__all__ = [
    "blockdevices",
    "bmc",
    "bootresourcefiles",
    "bootsources",
    "config",
    "controllerinfo",
    "dhcpsnippet",
    "events",
    "interfaces",
    "iprange",
    "keysource",
    "largefiles",
    "nodes",
    "partitions",
    "power",
    "scriptresult",
    "services",
    "staticipaddress",
    "subnet",
]

from maasserver.models.signals import (
    blockdevices,
    bmc,
    bootresourcefiles,
    bootsources,
    config,
    controllerinfo,
    dhcpsnippet,
    events,
    interfaces,
    iprange,
    keysource,
    largefiles,
    nodes,
    partitions,
    power,
    scriptresult,
    services,
    staticipaddress,
    subnet,
)
