# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Helper class for all tests using the `PostgresListenerService` under
`maasserver.triggers.tests`."""

__all__ = []

from crochet import wait_for
from django.contrib.auth.models import User
from maasserver.enum import (
    INTERFACE_TYPE,
    NODE_TYPE,
)
from maasserver.listener import PostgresListenerService
from maasserver.models.blockdevice import BlockDevice
from maasserver.models.cacheset import CacheSet
from maasserver.models.event import Event
from maasserver.models.fabric import Fabric
from maasserver.models.filesystem import Filesystem
from maasserver.models.filesystemgroup import FilesystemGroup
from maasserver.models.interface import Interface
from maasserver.models.node import (
    Node,
    RackController,
)
from maasserver.models.partition import Partition
from maasserver.models.partitiontable import PartitionTable
from maasserver.models.physicalblockdevice import PhysicalBlockDevice
from maasserver.models.space import Space
from maasserver.models.sshkey import SSHKey
from maasserver.models.sslkey import SSLKey
from maasserver.models.staticipaddress import StaticIPAddress
from maasserver.models.subnet import Subnet
from maasserver.models.tag import Tag
from maasserver.models.virtualblockdevice import VirtualBlockDevice
from maasserver.models.vlan import VLAN
from maasserver.models.zone import Zone
from maasserver.testing.factory import factory
from maasserver.utils.orm import transactional
from metadataserver.models import NodeResult


wait_for_reactor = wait_for(30)  # 30 seconds.


class TransactionalHelpersMixin:
    """Helpers performing actions in transactions."""

    def make_listener_without_delay(self):
        listener = PostgresListenerService()
        self.patch(listener, "HANDLE_NOTIFY_DELAY", 0)
        return listener

    @transactional
    def get_node(self, system_id):
        node = Node.objects.get(system_id=system_id)
        return node

    @transactional
    def create_node(self, params=None):
        if params is None:
            params = {}
        params['with_boot_disk'] = False
        return factory.make_Node(**params)

    @transactional
    def update_node(self, system_id, params):
        node = Node.objects.get(system_id=system_id)
        for key, value in params.items():
            setattr(node, key, value)
        return node.save()

    @transactional
    def delete_node(self, system_id):
        node = Node.objects.get(system_id=system_id)
        node.delete()

    @transactional
    def create_device_with_parent(self, params=None):
        if params is None:
            params = {}
        parent = factory.make_Node(with_boot_disk=False)
        params["node_type"] = NODE_TYPE.DEVICE
        params["parent"] = parent
        device = factory.make_Node(**params)
        return device, parent

    @transactional
    def get_node_boot_interface(self, system_id):
        node = Node.objects.get(system_id=system_id)
        return node.get_boot_interface()

    @transactional
    def create_fabric(self, params=None):
        if params is None:
            params = {}
        return factory.make_Fabric(**params)

    @transactional
    def update_fabric(self, id, params):
        fabric = Fabric.objects.get(id=id)
        for key, value in params.items():
            setattr(fabric, key, value)
        return fabric.save()

    @transactional
    def delete_fabric(self, id):
        fabric = Fabric.objects.get(id=id)
        fabric.delete()

    @transactional
    def create_space(self, params=None):
        if params is None:
            params = {}
        return factory.make_Space(**params)

    @transactional
    def update_space(self, id, params):
        space = Space.objects.get(id=id)
        for key, value in params.items():
            setattr(space, key, value)
        return space.save()

    @transactional
    def delete_space(self, id):
        space = Space.objects.get(id=id)
        space.delete()

    @transactional
    def create_subnet(self, params=None):
        if params is None:
            params = {}
        return factory.make_Subnet(**params)

    @transactional
    def update_subnet(self, id, params):
        subnet = Subnet.objects.get(id=id)
        for key, value in params.items():
            setattr(subnet, key, value)
        return subnet.save()

    @transactional
    def delete_subnet(self, id):
        subnet = Subnet.objects.get(id=id)
        subnet.delete()

    @transactional
    def create_vlan(self, params=None):
        if params is None:
            params = {}
        return factory.make_VLAN(**params)

    @transactional
    def update_vlan(self, id, params):
        vlan = VLAN.objects.get(id=id)
        for key, value in params.items():
            setattr(vlan, key, value)
        return vlan.save()

    @transactional
    def delete_vlan(self, id):
        vlan = VLAN.objects.get(id=id)
        vlan.delete()

    @transactional
    def create_zone(self, params=None):
        if params is None:
            params = {}
        return factory.make_Zone(**params)

    @transactional
    def update_zone(self, id, params):
        zone = Zone.objects.get(id=id)
        for key, value in params.items():
            setattr(zone, key, value)
        return zone.save()

    @transactional
    def delete_zone(self, id):
        zone = Zone.objects.get(id=id)
        zone.delete()

    @transactional
    def create_tag(self, params=None):
        if params is None:
            params = {}
        return factory.make_Tag(**params)

    @transactional
    def add_node_to_tag(self, node, tag):
        node.tags.add(tag)
        node.save()

    @transactional
    def remove_node_from_tag(self, node, tag):
        node.tags.remove(tag)
        node.save()

    @transactional
    def update_tag(self, id, params):
        tag = Tag.objects.get(id=id)
        for key, value in params.items():
            setattr(tag, key, value)
        return tag.save()

    @transactional
    def delete_tag(self, id):
        tag = Tag.objects.get(id=id)
        tag.delete()

    @transactional
    def create_user(self, params=None):
        if params is None:
            params = {}
        return factory.make_User(**params)

    @transactional
    def update_user(self, id, params):
        user = User.objects.get(id=id)
        for key, value in params.items():
            setattr(user, key, value)
        return user.save()

    @transactional
    def delete_user(self, id):
        user = User.objects.get(id=id)
        user.consumers.all().delete()
        user.delete()

    @transactional
    def create_event(self, params=None):
        if params is None:
            params = {}
        return factory.make_Event(**params)

    @transactional
    def update_event(self, id, params):
        event = Event.objects.get(id=id)
        for key, value in params.items():
            setattr(event, key, value)
        return event.save()

    @transactional
    def delete_event(self, id):
        event = Event.objects.get(id=id)
        event.delete()

    @transactional
    def create_staticipaddress(self, params=None):
        if params is None:
            params = {}
        return factory.make_StaticIPAddress(**params)

    @transactional
    def update_staticipaddress(self, id, params):
        ip = StaticIPAddress.objects.get(id=id)
        for key, value in params.items():
            setattr(ip, key, value)
        return ip.save()

    @transactional
    def delete_staticipaddress(self, id):
        sip = StaticIPAddress.objects.get(id=id)
        sip.delete()

    @transactional
    def get_ipaddress_subnet(self, id):
        ipaddress = StaticIPAddress.objects.get(id=id)
        return ipaddress.subnet

    @transactional
    def get_ipaddress_vlan(self, id):
        ipaddress = StaticIPAddress.objects.get(id=id)
        return ipaddress.subnet.vlan

    @transactional
    def get_ipaddress_fabric(self, id):
        ipaddress = StaticIPAddress.objects.get(id=id)
        return ipaddress.subnet.vlan.fabric

    @transactional
    def get_ipaddress_space(self, id):
        ipaddress = StaticIPAddress.objects.get(id=id)
        return ipaddress.subnet.space

    @transactional
    def create_noderesult(self, params=None):
        if params is None:
            params = {}
        return factory.make_NodeResult_for_commissioning(**params)

    @transactional
    def delete_noderesult(self, id):
        result = NodeResult.objects.get(id=id)
        result.delete()

    @transactional
    def create_interface(self, params=None):
        if params is None:
            params = {}
        return factory.make_Interface(INTERFACE_TYPE.PHYSICAL, **params)

    @transactional
    def delete_interface(self, id):
        interface = Interface.objects.get(id=id)
        interface.delete()

    @transactional
    def update_interface(self, id, params):
        interface = Interface.objects.get(id=id)
        for key, value in params.items():
            setattr(interface, key, value)
        return interface.save()

    @transactional
    def get_interface_vlan(self, id):
        interface = Interface.objects.get(id=id)
        return interface.vlan

    @transactional
    def get_interface_fabric(self, id):
        interface = Interface.objects.get(id=id)
        return interface.vlan.fabric

    @transactional
    def create_blockdevice(self, params=None):
        if params is None:
            params = {}
        return factory.make_BlockDevice(**params)

    @transactional
    def create_physicalblockdevice(self, params=None):
        if params is None:
            params = {}
        return factory.make_PhysicalBlockDevice(**params)

    @transactional
    def create_virtualblockdevice(self, params=None):
        if params is None:
            params = {}
        return factory.make_VirtualBlockDevice(**params)

    @transactional
    def delete_blockdevice(self, id):
        blockdevice = BlockDevice.objects.get(id=id)
        blockdevice.delete()

    @transactional
    def update_blockdevice(self, id, params):
        blockdevice = BlockDevice.objects.get(id=id)
        for key, value in params.items():
            setattr(blockdevice, key, value)
        return blockdevice.save()

    @transactional
    def update_physicalblockdevice(self, id, params):
        blockdevice = PhysicalBlockDevice.objects.get(id=id)
        for key, value in params.items():
            setattr(blockdevice, key, value)
        return blockdevice.save()

    @transactional
    def update_virtualblockdevice(self, id, params):
        blockdevice = VirtualBlockDevice.objects.get(id=id)
        for key, value in params.items():
            setattr(blockdevice, key, value)
        return blockdevice.save()

    @transactional
    def create_partitiontable(self, params=None):
        if params is None:
            params = {}
        return factory.make_PartitionTable(**params)

    @transactional
    def delete_partitiontable(self, id):
        partitiontable = PartitionTable.objects.get(id=id)
        partitiontable.delete()

    @transactional
    def update_partitiontable(self, id, params):
        partitiontable = PartitionTable.objects.get(id=id)
        for key, value in params.items():
            setattr(partitiontable, key, value)
        return partitiontable.save()

    @transactional
    def create_partition(self, params=None):
        if params is None:
            params = {}
        return factory.make_Partition(**params)

    @transactional
    def delete_partition(self, id):
        partition = Partition.objects.get(id=id)
        partition.delete()

    @transactional
    def update_partition(self, id, params):
        partition = Partition.objects.get(id=id)
        for key, value in params.items():
            setattr(partition, key, value)
        return partition.save()

    @transactional
    def create_filesystem(self, params=None):
        if params is None:
            params = {}
        return factory.make_Filesystem(**params)

    @transactional
    def delete_filesystem(self, id):
        filesystem = Filesystem.objects.get(id=id)
        filesystem.delete()

    @transactional
    def update_filesystem(self, id, params):
        filesystem = Filesystem.objects.get(id=id)
        for key, value in params.items():
            setattr(filesystem, key, value)
        return filesystem.save()

    @transactional
    def create_filesystemgroup(self, params=None):
        if params is None:
            params = {}
        return factory.make_FilesystemGroup(**params)

    @transactional
    def delete_filesystemgroup(self, id):
        filesystemgroup = FilesystemGroup.objects.get(id=id)
        filesystemgroup.delete()

    @transactional
    def update_filesystemgroup(self, id, params):
        filesystemgroup = FilesystemGroup.objects.get(id=id)
        for key, value in params.items():
            setattr(filesystemgroup, key, value)
        return filesystemgroup.save()

    @transactional
    def create_cacheset(self, params=None):
        if params is None:
            params = {}
        return factory.make_CacheSet(**params)

    @transactional
    def delete_cacheset(self, id):
        cacheset = CacheSet.objects.get(id=id)
        cacheset.delete()

    @transactional
    def update_cacheset(self, id, params):
        cacheset = CacheSet.objects.get(id=id)
        for key, value in params.items():
            setattr(cacheset, key, value)
        return cacheset.save()

    @transactional
    def create_sshkey(self, params=None):
        if params is None:
            params = {}
        return factory.make_SSHKey(**params)

    @transactional
    def delete_sshkey(self, id):
        key = SSHKey.objects.get(id=id)
        key.delete()

    @transactional
    def create_sslkey(self, params=None):
        if params is None:
            params = {}
        return factory.make_SSLKey(**params)

    @transactional
    def delete_sslkey(self, id):
        key = SSLKey.objects.get(id=id)
        key.delete()

    @transactional
    def create_rack_controller(self, params=None):
        if params is None:
            params = {}
        return factory.make_RackController(**params)

    @transactional
    def update_rack_controller(self, id, params):
        rack = RackController.objects.get(id=id)
        for key, value in params.items():
            setattr(rack, key, value)
        return rack.save()

    @transactional
    def delete_rack_controller(self, id):
        rack = RackController.objects.get(id=id)
        rack.delete()
