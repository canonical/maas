# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Handlers for the WebSocket connections."""

# Note: please keep this array in a consistent order with the imports below,
# so that it's easy to sanity-check.
__all__ = [
    "ControllerHandler",
    "DHCPSnippetHandler",
    "DeviceHandler",
    "DomainHandler",
    "EventHandler",
    "FabricHandler",
    "GeneralHandler"
    "IPRangeHandler",
    "MachineHandler",
    "ServiceHandler",
    "SpaceHandler",
    "SubnetHandler",
    "TagHandler",
    "UserHandler",
    "VLANHandler",
    "ZoneHandler",
    ]

from maasserver.utils import ignore_unused
from maasserver.websockets.handlers.controller import ControllerHandler
from maasserver.websockets.handlers.device import DeviceHandler
from maasserver.websockets.handlers.dhcpsnippet import DHCPSnippetHandler
from maasserver.websockets.handlers.domain import DomainHandler
from maasserver.websockets.handlers.event import EventHandler
from maasserver.websockets.handlers.fabric import FabricHandler
from maasserver.websockets.handlers.general import GeneralHandler
from maasserver.websockets.handlers.iprange import IPRangeHandler
from maasserver.websockets.handlers.machine import MachineHandler
from maasserver.websockets.handlers.service import ServiceHandler
from maasserver.websockets.handlers.space import SpaceHandler
from maasserver.websockets.handlers.subnet import SubnetHandler
from maasserver.websockets.handlers.tag import TagHandler
from maasserver.websockets.handlers.user import UserHandler
from maasserver.websockets.handlers.vlan import VLANHandler
from maasserver.websockets.handlers.zone import ZoneHandler


ignore_unused(ControllerHandler)
ignore_unused(DHCPSnippetHandler)
ignore_unused(DeviceHandler)
ignore_unused(DomainHandler)
ignore_unused(EventHandler)
ignore_unused(FabricHandler)
ignore_unused(GeneralHandler)
ignore_unused(IPRangeHandler)
ignore_unused(MachineHandler)
ignore_unused(ServiceHandler)
ignore_unused(SpaceHandler)
ignore_unused(SubnetHandler)
ignore_unused(TagHandler)
ignore_unused(UserHandler)
ignore_unused(VLANHandler)
ignore_unused(ZoneHandler)
