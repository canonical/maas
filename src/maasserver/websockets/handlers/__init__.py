# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Handlers for the WebSocket connections."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "NodeHandler",
    "DeviceHandler",
    "GeneralHandler"
    "ClusterHandler",
    "UserHandler",
    "ZoneHandler",
    ]

from maasserver.utils import ignore_unused
from maasserver.websockets.handlers.cluster import ClusterHandler
from maasserver.websockets.handlers.device import DeviceHandler
from maasserver.websockets.handlers.event import EventHandler
from maasserver.websockets.handlers.general import GeneralHandler
from maasserver.websockets.handlers.node import NodeHandler
from maasserver.websockets.handlers.tag import TagHandler
from maasserver.websockets.handlers.user import UserHandler
from maasserver.websockets.handlers.zone import ZoneHandler


ignore_unused(ClusterHandler)
ignore_unused(DeviceHandler)
ignore_unused(EventHandler)
ignore_unused(GeneralHandler)
ignore_unused(NodeHandler)
ignore_unused(TagHandler)
ignore_unused(UserHandler)
ignore_unused(ZoneHandler)
