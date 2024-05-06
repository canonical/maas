# Copyright 2015-2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Handlers for the WebSocket connections."""

# Note: please keep this array in a consistent order with the imports below,
# so that it's easy to sanity-check.
__all__ = [
    "BootResourceHandler",
    "ConfigHandler",
    "ControllerHandler",
    "DHCPSnippetHandler",
    "DeviceHandler",
    "DiscoveryHandler",
    "DomainHandler",
    "EventHandler",
    "FabricHandler",
    "GeneralHandler",
    "IPRangeHandler",
    "MachineHandler",
    "MAASSiteManagerHandler",
    "NodeDeviceHandler",
    "NodeResultHandler",
    "NotificationHandler",
    "PackageRepositoryHandler",
    "PodHandler",
    "ResourcePoolHandler",
    "SSHKeyHandler",
    "SSLKeyHandler",
    "ScriptHandler",
    "ServiceHandler",
    "SpaceHandler",
    "StaticRouteHandler",
    "SubnetHandler",
    "TagHandler",
    "TokenHandler",
    "UserHandler",
    "VLANHandler",
    "VMClusterHandler",
    "ZoneHandler",
]

from maasserver.websockets.handlers.bootresource import BootResourceHandler
from maasserver.websockets.handlers.config import ConfigHandler
from maasserver.websockets.handlers.controller import ControllerHandler
from maasserver.websockets.handlers.device import DeviceHandler
from maasserver.websockets.handlers.dhcpsnippet import DHCPSnippetHandler
from maasserver.websockets.handlers.discovery import DiscoveryHandler
from maasserver.websockets.handlers.domain import DomainHandler
from maasserver.websockets.handlers.event import EventHandler
from maasserver.websockets.handlers.fabric import FabricHandler
from maasserver.websockets.handlers.general import GeneralHandler
from maasserver.websockets.handlers.iprange import IPRangeHandler
from maasserver.websockets.handlers.machine import MachineHandler
from maasserver.websockets.handlers.msm import MAASSiteManagerHandler
from maasserver.websockets.handlers.node_device import NodeDeviceHandler
from maasserver.websockets.handlers.node_result import NodeResultHandler
from maasserver.websockets.handlers.notification import NotificationHandler
from maasserver.websockets.handlers.packagerepository import (
    PackageRepositoryHandler,
)
from maasserver.websockets.handlers.pod import PodHandler
from maasserver.websockets.handlers.resourcepool import ResourcePoolHandler
from maasserver.websockets.handlers.script import ScriptHandler
from maasserver.websockets.handlers.service import ServiceHandler
from maasserver.websockets.handlers.space import SpaceHandler
from maasserver.websockets.handlers.sshkey import SSHKeyHandler
from maasserver.websockets.handlers.sslkey import SSLKeyHandler
from maasserver.websockets.handlers.staticroute import StaticRouteHandler
from maasserver.websockets.handlers.subnet import SubnetHandler
from maasserver.websockets.handlers.tag import TagHandler
from maasserver.websockets.handlers.token import TokenHandler
from maasserver.websockets.handlers.user import UserHandler
from maasserver.websockets.handlers.vlan import VLANHandler
from maasserver.websockets.handlers.vmcluster import VMClusterHandler
from maasserver.websockets.handlers.zone import ZoneHandler
