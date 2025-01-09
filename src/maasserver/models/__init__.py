# Copyright 2012-2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Model export and helpers for maasserver."""

__all__ = [
    "Bcache",
    "BlockDevice",
    "BMC",
    "BMCRoutableRackControllerRelationship",
    "BondInterface",
    "BootResource",
    "BootResourceFile",
    "BootResourceFileSync",
    "BootResourceSet",
    "BootSource",
    "BootSourceCache",
    "BootSourceSelection",
    "BridgeInterface",
    "CacheSet",
    "Config",
    "Controller",
    "ControllerInfo",
    "DefaultResource",
    "Device",
    "DHCPSnippet",
    "Discovery",
    "DNSData",
    "DNSPublication",
    "DNSResource",
    "Domain",
    "Event",
    "EventType",
    "Fabric",
    "FileStorage",
    "Filesystem",
    "FilesystemGroup",
    "ForwardDNSServer",
    "GlobalDefault",
    "Interface",
    "IPRange",
    "LargeFile",
    "LicenseKey",
    "logger",
    "Machine",
    "MDNS",
    "Neighbour",
    "Node",
    "NodeConfig",
    "NodeDevice",
    "NodeDeviceVPD",
    "NodeKey",
    "NodeMetadata",
    "NodeUserData",
    "NodeGroupToRackController",
    "Notification",
    "NUMANode",
    "NUMANodeHugepages",
    "OwnerData",
    "PackageRepository",
    "Partition",
    "PartitionTable",
    "PhysicalBlockDevice",
    "PhysicalInterface",
    "Pod",
    "PodHints",
    "PodStoragePool",
    "RackController",
    "RAID",
    "RBACLastSync",
    "RBACSync",
    "RDNS",
    "RegionController",
    "RegionControllerProcess",
    "RegionControllerProcessEndpoint",
    "RegionRackRPCConnection",
    "ReservedIP",
    "ResourcePool",
    "RootKey",
    "Script",
    "ScriptResult",
    "ScriptSet",
    "Secret",
    "Service",
    "signals",
    "Space",
    "SSHKey",
    "SSLKey",
    "StaticIPAddress",
    "StaticRoute",
    "Subnet",
    "Tag",
    "Template",
    "UnknownInterface",
    "UserProfile",
    "VaultSecret",
    "VersionedTextFile",
    "VirtualBlockDevice",
    "VirtualMachine",
    "VLAN",
    "VLANInterface",
    "VolumeGroup",
    "VMCluster",
    "VMFS",
    "Zone",
]

from django.contrib.auth.models import _user_has_perm, User, UserManager
from django.core.exceptions import ViewDoesNotExist
from django.db.models.signals import post_save
from django.urls import get_callable, get_resolver, get_script_prefix
from piston3.doc import HandlerDocumentation

from maasserver import logger
from maasserver.models.blockdevice import BlockDevice
from maasserver.models.bmc import (
    BMC,
    BMCRoutableRackControllerRelationship,
    Pod,
)
from maasserver.models.bootresource import BootResource
from maasserver.models.bootresourcefile import (
    BootResourceFile,
    BootResourceFileSync,
)
from maasserver.models.bootresourceset import BootResourceSet
from maasserver.models.bootsource import BootSource
from maasserver.models.bootsourcecache import BootSourceCache
from maasserver.models.bootsourceselection import BootSourceSelection
from maasserver.models.cacheset import CacheSet
from maasserver.models.config import Config
from maasserver.models.controllerinfo import ControllerInfo
from maasserver.models.defaultresource import DefaultResource
from maasserver.models.dhcpsnippet import DHCPSnippet
from maasserver.models.discovery import Discovery
from maasserver.models.dnsdata import DNSData
from maasserver.models.dnspublication import DNSPublication
from maasserver.models.dnsresource import DNSResource
from maasserver.models.domain import Domain
from maasserver.models.event import Event
from maasserver.models.eventtype import EventType
from maasserver.models.fabric import Fabric
from maasserver.models.filestorage import FileStorage
from maasserver.models.filesystem import Filesystem
from maasserver.models.filesystemgroup import (
    Bcache,
    FilesystemGroup,
    RAID,
    VMFS,
    VolumeGroup,
)
from maasserver.models.forwarddnsserver import ForwardDNSServer
from maasserver.models.globaldefault import GlobalDefault
from maasserver.models.interface import (
    BondInterface,
    BridgeInterface,
    Interface,
    PhysicalInterface,
    UnknownInterface,
    VLANInterface,
)
from maasserver.models.iprange import IPRange
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
from maasserver.models.nodeconfig import NodeConfig
from maasserver.models.nodedevice import NodeDevice
from maasserver.models.nodedevicevpd import NodeDeviceVPD
from maasserver.models.nodekey import NodeKey
from maasserver.models.nodemetadata import NodeMetadata
from maasserver.models.nodeuserdata import NodeUserData
from maasserver.models.notification import Notification
from maasserver.models.numa import NUMANode, NUMANodeHugepages
from maasserver.models.ownerdata import OwnerData
from maasserver.models.packagerepository import PackageRepository
from maasserver.models.partition import Partition
from maasserver.models.partitiontable import PartitionTable
from maasserver.models.physicalblockdevice import PhysicalBlockDevice
from maasserver.models.podhints import PodHints
from maasserver.models.podstoragepool import PodStoragePool
from maasserver.models.rbacsync import RBACLastSync, RBACSync
from maasserver.models.rdns import RDNS
from maasserver.models.regioncontrollerprocess import RegionControllerProcess
from maasserver.models.regioncontrollerprocessendpoint import (
    RegionControllerProcessEndpoint,
)
from maasserver.models.regionrackrpcconnection import RegionRackRPCConnection
from maasserver.models.reservedip import ReservedIP
from maasserver.models.resourcepool import ResourcePool
from maasserver.models.rootkey import RootKey
from maasserver.models.script import Script
from maasserver.models.scriptresult import ScriptResult
from maasserver.models.scriptset import ScriptSet
from maasserver.models.secret import Secret, VaultSecret
from maasserver.models.service import Service
from maasserver.models.space import Space
from maasserver.models.sshkey import SSHKey
from maasserver.models.sslkey import SSLKey
from maasserver.models.staticipaddress import StaticIPAddress
from maasserver.models.staticroute import StaticRoute
from maasserver.models.subnet import Subnet
from maasserver.models.tag import Tag
from maasserver.models.template import Template
from maasserver.models.user import create_user
from maasserver.models.userprofile import UserProfile
from maasserver.models.versionedtextfile import VersionedTextFile
from maasserver.models.virtualblockdevice import VirtualBlockDevice
from maasserver.models.virtualmachine import VirtualMachine
from maasserver.models.vlan import VLAN
from maasserver.models.vmcluster import VMCluster
from maasserver.models.zone import Zone

# Connect post-creation methods for models.
post_save.connect(create_user, sender=User)


# Monkey patch django.contrib.auth.models.User to force email to be unique and
# allow null.
User._meta.get_field("email")._unique = True
User._meta.get_field("email").blank = False
User._meta.get_field("email").null = True

_normalize_email = UserManager.normalize_email


def normalize_email(cls, email):
    if not email:
        return None
    return _normalize_email(email)


UserManager.normalize_email = classmethod(normalize_email)


# Monkey patch django.contrib.auth.models.User to skip the `is_superuser`
# bypass. We want the `MAASAuthorizationBackend` to always be called.
def has_perm(self, perm, obj=None):
    return _user_has_perm(self, perm, obj)


User.has_perm = has_perm


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
        paths = template % {p: "{%s}" % p for p in params}
        return f"{get_script_prefix()}{paths}"

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
    except Exception:
        return None


HandlerDocumentation.get_resource_uri_template = get_resource_uri_template

# Monkey patch the property resource_uri_template: it hold a reference to
# get_resource_uri_template.
HandlerDocumentation.resource_uri_template = property(
    get_resource_uri_template
)


# Ensure that all signals modules are loaded.
from maasserver.models import signals  # noqa:E402 isort:skip
