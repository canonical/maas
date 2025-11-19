# Copyright 2015-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Signals coming off models."""

__all__ = [
    "blockdevices",
    "bmc",
    "bootsources",
    "controllerinfo",
    "dhcpsnippet",
    "dnsdata",
    "dnsresource",
    "domain",
    "events",
    "interfaces",
    "iprange",
    "nodes",
    "regionrackrpcconnection",
    "partitions",
    "podhints",
    "power",
    "scriptresult",
    "services",
    "staticipaddress",
    "subnet",
]

from maasserver.models.signals import (
    blockdevices,
    bmc,
    bootsources,
    controllerinfo,
    dhcpsnippet,
    dnsdata,
    dnsresource,
    domain,
    events,
    interfaces,
    iprange,
    nodes,
    partitions,
    podhints,
    power,
    regionrackrpcconnection,
    scriptresult,
    services,
    staticipaddress,
    subnet,
)
