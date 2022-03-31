from maasserver.enum import FILESYSTEM_GROUP_TYPE, INTERFACE_TYPE
from maasserver.models import PhysicalBlockDevice, VirtualBlockDevice
from maasserver.models.nodeconfig import NODE_CONFIG_TYPE
from maasserver.nodeconfig import duplicate_nodeconfig
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestDuplicateNodeConfig(MAASServerTestCase):
    def test_interfaces(self):
        src_config = factory.make_NodeConfig()
        if1 = factory.make_Interface(node_config=src_config)
        bridge = factory.make_Interface(
            iftype=INTERFACE_TYPE.BRIDGE, node_config=src_config, parents=[if1]
        )
        if2 = factory.make_Interface(node_config=src_config)
        vlan = factory.make_Interface(
            iftype=INTERFACE_TYPE.VLAN, node_config=src_config, parents=[if1]
        )

        new_config = duplicate_nodeconfig(
            src_config, NODE_CONFIG_TYPE.DEPLOYMENT
        )
        (
            new_if1,
            new_bridge,
            new_if2,
            new_vlan,
        ) = new_config.interface_set.order_by("id")
        self.assertEqual(new_if1.type, INTERFACE_TYPE.PHYSICAL)
        self.assertEqual(new_if1.name, if1.name)
        self.assertNotEqual(new_if1.id, if1.id)

        self.assertEqual(new_if2.type, INTERFACE_TYPE.PHYSICAL)
        self.assertEqual(new_if2.name, if2.name)
        self.assertNotEqual(new_if2.id, if2.id)

        self.assertEqual(new_bridge.type, INTERFACE_TYPE.BRIDGE)
        self.assertEqual(new_bridge.name, bridge.name)
        self.assertNotEqual(new_bridge.id, bridge.id)
        self.assertCountEqual(
            new_bridge.parent_relationships.values_list(
                "parent_id", flat=True
            ),
            [new_if1.id],
        )

        self.assertEqual(new_vlan.type, INTERFACE_TYPE.VLAN)
        self.assertEqual(new_vlan.name, vlan.name)
        self.assertNotEqual(new_vlan.id, vlan.id)
        self.assertCountEqual(
            new_vlan.parent_relationships.values_list("parent_id", flat=True),
            [new_if1.id],
        )

    def test_physicalblockdevices(self):
        node = factory.make_Node(with_boot_disk=False)
        src_config = node.current_config
        disk1 = factory.make_PhysicalBlockDevice(node_config=src_config)
        ptable1 = factory.make_PartitionTable(block_device=disk1)
        disk2 = factory.make_PhysicalBlockDevice(node_config=src_config)
        ptable2 = factory.make_PartitionTable(block_device=disk2)
        new_config = duplicate_nodeconfig(
            src_config, NODE_CONFIG_TYPE.DEPLOYMENT
        )
        new_disk1, new_disk2 = PhysicalBlockDevice.objects.filter(
            node_config=new_config
        ).order_by("id")
        self.assertEqual(new_disk1.name, disk1.name)
        self.assertEqual(new_disk1.model, disk1.model)
        self.assertNotEqual(new_disk1.id, disk1.id)
        self.assertEqual(
            new_disk1.get_partitiontable().table_type,
            ptable1.table_type,
        )
        self.assertEqual(new_disk2.name, disk2.name)
        self.assertEqual(new_disk2.model, disk2.model)
        self.assertNotEqual(new_disk2.id, disk2.id)
        self.assertEqual(
            new_disk2.get_partitiontable().table_type,
            ptable2.table_type,
        )

    def test_virtualblockdevice(self):
        node = factory.make_Node(with_boot_disk=False)
        src_config = node.current_config
        fsgroup1 = factory.make_FilesystemGroup(
            node=node,
            group_type=FILESYSTEM_GROUP_TYPE.LVM_VG,
            num_lvm_devices=1,
        )
        fsgroup2 = factory.make_FilesystemGroup(
            node=node,
            group_type=FILESYSTEM_GROUP_TYPE.LVM_VG,
            num_lvm_devices=1,
        )
        vbdev1 = factory.make_VirtualBlockDevice(filesystem_group=fsgroup1)
        vbdev2 = factory.make_VirtualBlockDevice(filesystem_group=fsgroup2)

        new_config = duplicate_nodeconfig(
            src_config, NODE_CONFIG_TYPE.DEPLOYMENT
        )
        new_vbdev1, new_vbdev2 = VirtualBlockDevice.objects.filter(
            node_config=new_config
        ).order_by("id")
        self.assertNotEqual(new_vbdev1.id, vbdev1.id)
        self.assertEqual(new_vbdev1.uuid, vbdev1.uuid)
        self.assertEqual(
            new_vbdev1.filesystem_group.uuid, vbdev1.filesystem_group.uuid
        )
        self.assertEqual(
            new_vbdev1.filesystem_group.name, vbdev1.filesystem_group.name
        )
        self.assertNotEqual(new_vbdev2.id, vbdev2.id)
        self.assertEqual(new_vbdev2.uuid, vbdev2.uuid)
        self.assertEqual(
            new_vbdev2.filesystem_group.uuid, vbdev2.filesystem_group.uuid
        )
        self.assertEqual(
            new_vbdev2.filesystem_group.name, vbdev2.filesystem_group.name
        )

    def test_partitions_filesystems(self):
        node = factory.make_Node(with_boot_disk=False)
        src_config = node.current_config
        bdev1 = factory.make_PhysicalBlockDevice(node=node)
        ptable1 = factory.make_PartitionTable(block_device=bdev1)
        part1 = ptable1.add_partition()
        fs1 = factory.make_Filesystem(partition=part1)
        bdev2 = factory.make_PhysicalBlockDevice(node=node)
        fs2 = factory.make_Filesystem(block_device=bdev2)

        new_config = duplicate_nodeconfig(
            src_config, NODE_CONFIG_TYPE.DEPLOYMENT
        )
        new_fs1, new_fs2 = new_config.filesystem_set.order_by("id")
        self.assertNotEqual(new_fs1.id, fs1.id)
        self.assertEqual(new_fs1.fstype, fs1.fstype)
        self.assertEqual(new_fs1.partition.uuid, fs1.partition.uuid)
        self.assertIsNone(new_fs1.block_device)
        self.assertNotEqual(new_fs2.id, fs2.id)
        self.assertEqual(new_fs2.fstype, fs2.fstype)
        self.assertEqual(new_fs2.block_device.name, fs2.block_device.name)

    def test_nodedevices(self):
        node = factory.make_Node(with_boot_disk=False)
        src_config = node.current_config
        factory.make_PhysicalBlockDevice(node_config=src_config, pcie=True)
        factory.make_Interface(node_config=src_config)
        nodedev1, nodedev2 = src_config.nodedevice_set.prefetch_related(
            "physical_blockdevice", "physical_interface"
        ).order_by("id")
        new_config = duplicate_nodeconfig(
            src_config, NODE_CONFIG_TYPE.DEPLOYMENT
        )
        [new_disk] = new_config.blockdevice_set.all()
        [new_iface] = new_config.interface_set.all()
        new_nodedev1, new_nodedev2 = new_config.nodedevice_set.order_by("id")
        self.assertEqual(new_nodedev1.physical_blockdevice_id, new_disk.id)
        self.assertEqual(new_nodedev1.bus, nodedev1.bus)
        self.assertEqual(new_nodedev1.hardware_type, nodedev1.hardware_type)
        self.assertEqual(new_nodedev2.physical_interface_id, new_iface.id)
        self.assertEqual(new_nodedev2.bus, nodedev2.bus)
        self.assertEqual(new_nodedev2.hardware_type, nodedev2.hardware_type)
