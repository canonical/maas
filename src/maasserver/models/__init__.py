# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Model export and helpers for maasserver."""

__all__ = [
    'Bcache',
    'BlockDevice',
    'BMC',
    'BMCRoutableRackControllerRelationship',
    'BondInterface',
    'BootResource',
    'BootResourceFile',
    'BootResourceSet',
    'BootSource',
    'BootSourceCache',
    'BootSourceSelection',
    'BridgeInterface',
    'CacheSet',
    'Config',
    'Controller',
    'ControllerInfo',
    'Device',
    'DHCPSnippet',
    'Discovery',
    'DNSData',
    'DNSPublication',
    'DNSResource',
    'Domain',
    'Event',
    'EventType',
    'Fabric',
    'FanNetwork',
    'FileStorage',
    'Filesystem',
    'FilesystemGroup',
    'Interface',
    'IPRange',
    'ISCSIBlockDevice',
    'KeySource',
    'LargeFile',
    'LicenseKey',
    'logger',
    'Machine',
    'MDNS',
    'Neighbour',
    'Node',
    'NodeMetadata',
    'NodeGroupToRackController',
    'Notification',
    'OwnerData',
    'PackageRepository',
    'Partition',
    'PartitionTable',
    'PhysicalBlockDevice',
    'PhysicalInterface',
    'Pod',
    'PodHints',
    'RackController',
    'RAID',
    'RDNS',
    'RegionController',
    'RegionControllerProcess',
    'RegionControllerProcessEndpoint',
    'RegionRackRPCConnection',
    'ResourcePool',
    'Role',
    'Service',
    'signals',
    'Space',
    'SSHKey',
    'SSLKey',
    'StaticIPAddress',
    'StaticRoute',
    'Subnet',
    'Switch',
    'Tag',
    'Template',
    'UnknownInterface',
    'UserGroup',
    'UserGroupMembership',
    'UserProfile',
    'VersionedTextFile',
    'VirtualBlockDevice',
    'VLAN',
    'VLANInterface',
    'VolumeGroup',
    'Zone',
]

from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User
from django.core.exceptions import ViewDoesNotExist
from django.db.models.signals import post_save
from maasserver import logger
from maasserver.enum import (
    NODE_PERMISSION,
    NODE_TYPE,
)
from maasserver.models.blockdevice import BlockDevice
from maasserver.models.bmc import (
    BMC,
    BMCRoutableRackControllerRelationship,
    Pod,
)
from maasserver.models.bootresource import BootResource
from maasserver.models.bootresourcefile import BootResourceFile
from maasserver.models.bootresourceset import BootResourceSet
from maasserver.models.bootsource import BootSource
from maasserver.models.bootsourcecache import BootSourceCache
from maasserver.models.bootsourceselection import BootSourceSelection
from maasserver.models.cacheset import CacheSet
from maasserver.models.config import Config
from maasserver.models.controllerinfo import ControllerInfo
from maasserver.models.dhcpsnippet import DHCPSnippet
from maasserver.models.discovery import Discovery
from maasserver.models.dnsdata import DNSData
from maasserver.models.dnspublication import DNSPublication
from maasserver.models.dnsresource import DNSResource
from maasserver.models.domain import Domain
from maasserver.models.event import Event
from maasserver.models.eventtype import EventType
from maasserver.models.fabric import Fabric
from maasserver.models.fannetwork import FanNetwork
from maasserver.models.filestorage import FileStorage
from maasserver.models.filesystem import Filesystem
from maasserver.models.filesystemgroup import (
    Bcache,
    FilesystemGroup,
    RAID,
    VolumeGroup,
)
from maasserver.models.interface import (
    BondInterface,
    BridgeInterface,
    Interface,
    PhysicalInterface,
    UnknownInterface,
    VLANInterface,
)
from maasserver.models.iprange import IPRange
from maasserver.models.iscsiblockdevice import ISCSIBlockDevice
from maasserver.models.keysource import KeySource
from maasserver.models.largefile import LargeFile
from maasserver.models.licensekey import LicenseKey
from maasserver.models.mdns import MDNS
from maasserver.models.neighbour import Neighbour
from maasserver.models.node import (
    Controller,
    Device,
    Machine,
    Node,
    NodeGroupToRackController,
    RackController,
    RegionController,
)
from maasserver.models.nodemetadata import NodeMetadata
from maasserver.models.notification import Notification
from maasserver.models.ownerdata import OwnerData
from maasserver.models.packagerepository import PackageRepository
from maasserver.models.partition import Partition
from maasserver.models.partitiontable import PartitionTable
from maasserver.models.physicalblockdevice import PhysicalBlockDevice
from maasserver.models.podhints import PodHints
from maasserver.models.rdns import RDNS
from maasserver.models.regioncontrollerprocess import RegionControllerProcess
from maasserver.models.regioncontrollerprocessendpoint import (
    RegionControllerProcessEndpoint,
)
from maasserver.models.regionrackrpcconnection import RegionRackRPCConnection
from maasserver.models.resourcepool import (
    create_resource_pool,
    ResourcePool,
)
from maasserver.models.role import Role
from maasserver.models.service import Service
from maasserver.models.space import Space
from maasserver.models.sshkey import SSHKey
from maasserver.models.sslkey import SSLKey
from maasserver.models.staticipaddress import StaticIPAddress
from maasserver.models.staticroute import StaticRoute
from maasserver.models.subnet import Subnet
from maasserver.models.switch import Switch
from maasserver.models.tag import Tag
from maasserver.models.template import Template
from maasserver.models.user import create_user
from maasserver.models.usergroup import (
    UserGroup,
    UserGroupMembership,
)
from maasserver.models.userprofile import UserProfile
from maasserver.models.versionedtextfile import VersionedTextFile
from maasserver.models.virtualblockdevice import VirtualBlockDevice
from maasserver.models.vlan import VLAN
from maasserver.models.zone import Zone
from maasserver.utils.django_urls import (
    get_callable,
    get_resolver,
    get_script_prefix,
)
from piston3.doc import HandlerDocumentation
from provisioningserver.utils import is_instance_or_subclass

# Connect post-creation methods for models.
post_save.connect(create_user, sender=User)
post_save.connect(create_resource_pool, sender=ResourcePool)


# Monkey patch django.contrib.auth.models.User to force email to be unique.
User._meta.get_field('email')._unique = True


# Monkey patch piston's usage of Django's get_resolver to be compatible
# with Django 1.4.
# XXX: rvb 2012-09-21 bug=1054040
# See https://bitbucket.org/jespern/django-piston/issue/218 for details.
def get_resource_uri_template(self):
    """
    URI template processor.
    See http://bitworking.org/projects/URI-Templates/
    """
    def _convert(template, params=[]):
        """URI template converter"""
        paths = template % dict([p, "{%s}" % p] for p in params)
        return '%s%s' % (get_script_prefix(), paths)
    try:
        resource_uri = self.handler.resource_uri()
        components = [None, [], {}]

        for i, value in enumerate(resource_uri):
            components[i] = value
        lookup_view, args, kwargs = components
        try:
            lookup_view = get_callable(lookup_view)
        except (ImportError, ViewDoesNotExist):
            # Emulate can_fail=True from earlier django versions.
            pass

        possibilities = get_resolver(None).reverse_dict.getlist(lookup_view)
        # The monkey patch is right here: we need to cope with 'possibilities'
        # being a list of tuples with 2 or 3 elements.
        for possibility_data in possibilities:
            possibility = possibility_data[0]
            for result, params in possibility:
                if args:
                    if len(args) != len(params):
                        continue
                    return _convert(result, params)
                else:
                    if set(kwargs.keys()) != set(params):
                        continue
                    return _convert(result, params)
    except:
        return None

HandlerDocumentation.get_resource_uri_template = get_resource_uri_template

# Monkey patch the property resource_uri_template: it hold a reference to
# get_resource_uri_template.
HandlerDocumentation.resource_uri_template = (
    property(get_resource_uri_template))

# Some actions are applied to model object types global to MAAS; not
# necessarily a particular object. The following objects cannot be created or
# changed by non-administrative users, but superusers can always create, read
# write, or delete them.
UNRESTRICTED_READ_MODELS = (
    DNSData,
    DNSResource,
    Domain,
    Fabric,
    FanNetwork,
    Space,
    Subnet,
    StaticRoute,
    VLAN
)

# The following model objects are restricted from non-administrative users.
# They cannot be seen (or created, or modified, or deleted) by "normal" users.
ADMIN_RESTRICTED_MODELS = (
    Discovery,
)

# ADMIN_PERMISSIONS applies to the model objects in ADMIN_RESTRICTED_MODELS.
# These model objects are restricted to administrators only; permission checks
# will return True for administrators given any of the following permissions:
ADMIN_PERMISSIONS = (
    NODE_PERMISSION.VIEW,
    NODE_PERMISSION.EDIT,
    NODE_PERMISSION.ADMIN,
)


class MAASAuthorizationBackend(ModelBackend):

    supports_object_permissions = True

    def has_perm(self, user, perm, obj=None):
        # Note that a check for a superuser will never reach this code
        # because Django will return True (as an optimization) for every
        # permission check performed on a superuser.
        if not user.is_active:
            # Deactivated users, and in particular the node-init user,
            # are prohibited from accessing maasserver services.
            return False

        if isinstance(obj, Node):
            if perm == NODE_PERMISSION.VIEW:
                # users can see unowned machines if they're in a pool they have
                # access too.  Other types of Node are always visible.
                return (
                    obj.pool is None or
                    ResourcePool.objects.user_can_access_pool(
                        user, obj.pool))
            elif perm == NODE_PERMISSION.EDIT:
                return obj.owner == user and not obj.locked
            elif perm == NODE_PERMISSION.LOCK:
                return obj.owner == user
            elif perm == NODE_PERMISSION.ADMIN:
                # 'admin_node' permission is solely granted to superusers.
                return False
            else:
                raise NotImplementedError(
                    'Invalid permission check (invalid permission name: %s).' %
                    perm)
        elif isinstance(obj, (BlockDevice, FilesystemGroup)):
            if isinstance(obj, BlockDevice):
                node = obj.node
            else:
                node = obj.get_node()
            if perm == NODE_PERMISSION.VIEW:
                # If the node is not ownered or the owner is the user then
                # they can view the information.
                return node.owner is None or node.owner == user
            elif perm == NODE_PERMISSION.EDIT:
                return node.owner == user
            elif perm == NODE_PERMISSION.ADMIN:
                # 'admin_node' permission is solely granted to superusers.
                return False
            else:
                raise NotImplementedError(
                    'Invalid permission check (invalid permission name: %s).' %
                    perm)
        elif isinstance(obj, Interface):
            if perm == NODE_PERMISSION.VIEW:
                # Any registered user can view a interface regardless
                # of its state.
                return True
            elif perm in NODE_PERMISSION.EDIT:
                # A device can be editted by its owner a node must be admin.
                node = obj.get_node()
                if node is None or node.node_type == NODE_TYPE.MACHINE:
                    return user.is_superuser
                else:
                    return node.owner == user
            elif perm in NODE_PERMISSION.ADMIN:
                # Admin permission is solely granted to superusers.
                return user.is_superuser
            else:
                raise NotImplementedError(
                    'Invalid permission check (invalid permission name: %s).' %
                    perm)
        elif is_instance_or_subclass(obj, UNRESTRICTED_READ_MODELS):
            # This model is classified under 'unrestricted read' for any
            # logged-in user; so everyone can view, but only an admin can
            # do anything else.
            if perm == NODE_PERMISSION.VIEW:
                return True
            elif perm in ADMIN_PERMISSIONS:
                # Admin permission is solely granted to superusers.
                return user.is_superuser
            else:
                raise NotImplementedError(
                    'Invalid permission check (invalid permission name: %s).' %
                    perm)
        elif is_instance_or_subclass(obj, ADMIN_RESTRICTED_MODELS):
            # Only administrators are allowed to read/write these objects.
            if perm in ADMIN_PERMISSIONS:
                return user.is_superuser
            else:
                raise NotImplementedError(
                    'Invalid permission check (invalid permission name: %s).' %
                    perm)
        else:
            raise NotImplementedError(
                'Invalid permission check (invalid object type).')


# Ensure that all signals modules are loaded.
from maasserver.models import signals
