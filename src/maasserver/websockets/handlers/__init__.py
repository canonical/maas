# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Handlers for the WebSocket connections."""

__all__ = [
    "NodeHandler",
    "DeviceHandler",
    "GeneralHandler"
    "ClusterHandler",
    "UserHandler",
    "ZoneHandler",
    "FabricHandler",
    "SpaceHandler",
    "SubnetHandler",
    "VLANHandler",
    ]

from maasserver.utils import ignore_unused
from maasserver.websockets.handlers.controller import ControllerHandler
from maasserver.websockets.handlers.device import DeviceHandler
from maasserver.websockets.handlers.event import EventHandler
from maasserver.websockets.handlers.fabric import FabricHandler
from maasserver.websockets.handlers.general import GeneralHandler
from maasserver.websockets.handlers.machine import MachineHandler
from maasserver.websockets.handlers.space import SpaceHandler
from maasserver.websockets.handlers.subnet import SubnetHandler
from maasserver.websockets.handlers.tag import TagHandler
from maasserver.websockets.handlers.user import UserHandler
from maasserver.websockets.handlers.vlan import VLANHandler
from maasserver.websockets.handlers.zone import ZoneHandler


ignore_unused(ControllerHandler)
ignore_unused(DeviceHandler)
ignore_unused(EventHandler)
ignore_unused(FabricHandler)
ignore_unused(GeneralHandler)
ignore_unused(MachineHandler)
ignore_unused(SpaceHandler)
ignore_unused(SubnetHandler)
ignore_unused(TagHandler)
ignore_unused(UserHandler)
ignore_unused(VLANHandler)
ignore_unused(ZoneHandler)
