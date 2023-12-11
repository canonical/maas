# Copyright 2015-2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import random
import uuid

from django.core.exceptions import ValidationError

from maasserver.enum import FILESYSTEM_TYPE
from maasserver.forms import (
    CreatePhysicalBlockDeviceForm,
    FormatBlockDeviceForm,
    UpdateDeployedPhysicalBlockDeviceForm,
    UpdatePhysicalBlockDeviceForm,
    UpdateVirtualBlockDeviceForm,
)
from maasserver.models import Filesystem
from maasserver.models.blockdevice import MIN_BLOCK_DEVICE_SIZE
from maasserver.models.partition import PARTITION_ALIGNMENT_SIZE
from maasserver.models.partitiontable import PARTITION_TABLE_TYPE
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.converters import round_size_to_nearest_block
from maasserver.utils.orm import get_one, reload_object


class TestFormatBlockDeviceForm(MAASServerTestCase):
    def test_requires_fields(self):
        form = FormatBlockDeviceForm(
            block_device=factory.make_BlockDevice(), data={}
        )
        self.assertFalse(form.is_valid(), form.errors)
        self.assertEqual({"fstype"}, form.errors.keys())

    def test_is_not_valid_if_block_device_has_partition_table(self):
        fstype = factory.pick_filesystem_type()
        block_device = factory.make_PhysicalBlockDevice()
        factory.make_PartitionTable(block_device=block_device)
        data = {"fstype": fstype}
        form = FormatBlockDeviceForm(block_device, data=data)
        self.assertFalse(
            form.is_valid(),
            "Should be invalid because block device has a partition table.",
        )
        self.assertEqual(
            {
                "__all__": [
                    "Cannot format block device with a partition table."
                ]
            },
            form._errors,
        )

    def test_is_not_valid_if_invalid_format_fstype(self):
        block_device = factory.make_PhysicalBlockDevice()
        data = {"fstype": FILESYSTEM_TYPE.LVM_PV}
        form = FormatBlockDeviceForm(block_device, data=data)
        self.assertFalse(
            form.is_valid(), "Should be invalid because of an invalid fstype."
        )
        self.assertEqual(
            {
                "fstype": [
                    "Select a valid choice. lvm-pv is not one of the "
                    "available choices."
                ]
            },
            form._errors,
        )

    def test_is_not_valid_if_invalid_uuid(self):
        fstype = factory.pick_filesystem_type()
        block_device = factory.make_PhysicalBlockDevice()
        data = {"fstype": fstype, "uuid": factory.make_string(size=32)}
        form = FormatBlockDeviceForm(block_device, data=data)
        self.assertFalse(
            form.is_valid(), "Should be invalid because of an invalid uuid."
        )
        self.assertEqual({"uuid": ["Enter a valid value."]}, form._errors)

    def test_is_not_valid_if_invalid_uuid_append_XYZ(self):
        fstype = factory.pick_filesystem_type()
        block_device = factory.make_PhysicalBlockDevice()
        data = {
            "fstype": fstype,
            "uuid": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaXYZ",
        }
        form = FormatBlockDeviceForm(block_device, data=data)
        self.assertFalse(
            form.is_valid(), "Should be invalid because of an invalid uuid."
        )
        self.assertEqual({"uuid": ["Enter a valid value."]}, form._errors)

    def test_is_not_valid_if_invalid_uuid_prepend_XYZ(self):
        fstype = factory.pick_filesystem_type()
        block_device = factory.make_PhysicalBlockDevice()
        data = {
            "fstype": fstype,
            "uuid": "XYZaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        }
        form = FormatBlockDeviceForm(block_device, data=data)
        self.assertFalse(
            form.is_valid(), "Should be invalid because of an invalid uuid."
        )
        self.assertEqual({"uuid": ["Enter a valid value."]}, form._errors)

    def test_is_not_valid_if_non_user_format_fstype(self):
        block_device = factory.make_PhysicalBlockDevice()
        factory.make_Filesystem(
            fstype="bcache-backing", block_device=block_device
        )
        data = {"fstype": FILESYSTEM_TYPE.EXT4}
        form = FormatBlockDeviceForm(block_device, data=data)
        self.assertRaises(ValidationError, form.save)

    def test_creates_filesystem(self):
        fsuuid = "%s" % uuid.uuid4()
        fstype = factory.pick_filesystem_type()
        block_device = factory.make_PhysicalBlockDevice()
        data = {"uuid": fsuuid, "fstype": fstype}
        form = FormatBlockDeviceForm(block_device, data=data)
        self.assertTrue(form.is_valid(), form._errors)
        form.save()
        filesystem = get_one(
            Filesystem.objects.filter(block_device=block_device)
        )
        self.assertIsNotNone(filesystem)
        self.assertEqual(fstype, filesystem.fstype)
        self.assertEqual(fsuuid, filesystem.uuid)

    def test_deletes_old_filesystem_and_creates_new_one(self):
        fstype = factory.pick_filesystem_type()
        block_device = factory.make_PhysicalBlockDevice()
        prev_filesystem = factory.make_Filesystem(block_device=block_device)
        data = {"fstype": fstype}
        form = FormatBlockDeviceForm(block_device, data=data)
        self.assertTrue(form.is_valid(), form._errors)
        form.save()
        self.assertEqual(
            1,
            Filesystem.objects.filter(block_device=block_device).count(),
            "Should only be one filesystem that exists for block device.",
        )
        self.assertIsNone(reload_object(prev_filesystem))
        filesystem = get_one(
            Filesystem.objects.filter(block_device=block_device)
        )
        self.assertIsNotNone(filesystem)
        self.assertEqual(fstype, filesystem.fstype)


class TestCreatePhysicalBlockDeviceForm(MAASServerTestCase):
    def test_requires_fields(self):
        node = factory.make_Node()
        form = CreatePhysicalBlockDeviceForm(node, data={})
        self.assertFalse(form.is_valid(), form.errors)
        self.assertEqual(
            {
                "name": ["This field is required."],
                "size": ["This field is required."],
                "block_size": ["This field is required."],
                "__all__": [
                    "serial/model are required if id_path is not provided."
                ],
            },
            form.errors,
        )

    def test_creates_physical_block_device_with_model_serial(self):
        node = factory.make_Node()
        name = factory.make_name("sd")
        model = factory.make_name("model")
        serial = factory.make_name("serial")
        size = random.randint(
            MIN_BLOCK_DEVICE_SIZE, MIN_BLOCK_DEVICE_SIZE * 10
        )
        block_size = 4096
        form = CreatePhysicalBlockDeviceForm(
            node,
            data={
                "name": name,
                "model": model,
                "serial": serial,
                "size": size,
                "block_size": block_size,
            },
        )
        self.assertTrue(form.is_valid(), form.errors)
        block_device = form.save()
        self.assertEqual(block_device.name, name)
        self.assertEqual(block_device.model, model)
        self.assertEqual(block_device.serial, serial)
        self.assertEqual(block_device.size, size)
        self.assertEqual(block_device.block_size, block_size)
        self.assertEqual(block_device.numa_node, node.default_numanode)

    def test_creates_physical_block_device_with_id_path(self):
        node = factory.make_Node()
        name = factory.make_name("sd")
        id_path = factory.make_absolute_path()
        size = random.randint(
            MIN_BLOCK_DEVICE_SIZE, MIN_BLOCK_DEVICE_SIZE * 10
        )
        block_size = 4096
        form = CreatePhysicalBlockDeviceForm(
            node,
            data={
                "name": name,
                "id_path": id_path,
                "size": size,
                "block_size": block_size,
            },
        )
        self.assertTrue(form.is_valid(), form.errors)
        block_device = form.save()
        self.assertEqual(block_device.name, name)
        self.assertEqual(block_device.id_path, id_path)
        self.assertEqual(block_device.size, size)
        self.assertEqual(block_device.block_size, block_size)
        self.assertEqual(block_device.numa_node, node.default_numanode)

    def test_creates_physical_block_device_with_numa_node(self):
        node = factory.make_Node()
        numa_node = factory.make_NUMANode(node=node)
        name = factory.make_name("sd")
        id_path = factory.make_absolute_path()
        size = random.randint(
            MIN_BLOCK_DEVICE_SIZE, MIN_BLOCK_DEVICE_SIZE * 10
        )
        block_size = 4096
        form = CreatePhysicalBlockDeviceForm(
            node,
            data={
                "name": name,
                "id_path": id_path,
                "size": size,
                "block_size": block_size,
                "numa_node": numa_node.index,
            },
        )
        self.assertTrue(form.is_valid(), form.errors)
        block_device = form.save()
        self.assertEqual(block_device.name, name)
        self.assertEqual(block_device.id_path, id_path)
        self.assertEqual(block_device.size, size)
        self.assertEqual(block_device.block_size, block_size)
        self.assertEqual(block_device.numa_node, numa_node)

    def test_creates_physical_block_device_invalid_numa_node(self):
        node = factory.make_Node()
        name = factory.make_name("sd")
        id_path = factory.make_absolute_path()
        size = random.randint(
            MIN_BLOCK_DEVICE_SIZE, MIN_BLOCK_DEVICE_SIZE * 10
        )
        block_size = 4096
        form = CreatePhysicalBlockDeviceForm(
            node,
            data={
                "name": name,
                "id_path": id_path,
                "size": size,
                "block_size": block_size,
                "numa_node": 4,
            },
        )
        self.assertFalse(form.is_valid(), form.errors)
        self.assertEqual({"numa_node": ["Invalid NUMA node"]}, form.errors)


class TestUpdatePhysicalBlockDeviceForm(MAASServerTestCase):
    def test_requires_no_fields(self):
        block_device = factory.make_PhysicalBlockDevice()
        form = UpdatePhysicalBlockDeviceForm(instance=block_device, data={})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(set(), form.errors.keys())

    def test_updates_physical_block_device(self):
        block_device = factory.make_PhysicalBlockDevice()
        node = block_device.node_config.node
        numa_node = factory.make_NUMANode(node=node)
        name = factory.make_name("sd")
        model = factory.make_name("model")
        serial = factory.make_name("serial")
        id_path = factory.make_absolute_path()
        size = random.randint(
            MIN_BLOCK_DEVICE_SIZE, MIN_BLOCK_DEVICE_SIZE * 10
        )
        block_size = 4096
        form = UpdatePhysicalBlockDeviceForm(
            instance=block_device,
            data={
                "name": name,
                "model": model,
                "serial": serial,
                "id_path": id_path,
                "size": size,
                "block_size": block_size,
                "numa_node": numa_node.index,
            },
        )
        self.assertTrue(form.is_valid(), form.errors)
        block_device = form.save()
        self.assertEqual(block_device.name, name)
        self.assertEqual(block_device.model, model)
        self.assertEqual(block_device.serial, serial)
        self.assertEqual(block_device.id_path, id_path)
        self.assertEqual(block_device.size, size)
        self.assertEqual(block_device.block_size, block_size)
        self.assertEqual(block_device.numa_node, numa_node)

    def test_update_invalid_numa_node(self):
        block_device = factory.make_PhysicalBlockDevice()
        form = UpdatePhysicalBlockDeviceForm(
            instance=block_device, data={"numa_node": 3}
        )
        self.assertFalse(form.is_valid())
        self.assertEqual({"numa_node": ["Invalid NUMA node"]}, form.errors)

    def test_update_no_numa_node_change(self):
        node = factory.make_Node()
        numa_node = factory.make_NUMANode(node=node)
        # associate with a node different from the default one
        block_device = factory.make_PhysicalBlockDevice(numa_node=numa_node)
        form = UpdatePhysicalBlockDeviceForm(instance=block_device, data={})
        self.assertTrue(form.is_valid(), form.errors)
        block_device = form.save()
        self.assertEqual(block_device.numa_node, numa_node)

    def test_udpate_partitiontable_type(self):
        block_device = factory.make_PhysicalBlockDevice()
        factory.make_PartitionTable(
            table_type=PARTITION_TABLE_TYPE.GPT, block_device=block_device
        )
        form = UpdatePhysicalBlockDeviceForm(
            instance=block_device,
            data={"partition_table_type": PARTITION_TABLE_TYPE.MBR},
        )
        self.assertTrue(form.is_valid(), form.errors)
        block_device = form.save()
        self.assertEqual(
            block_device.get_partitiontable().table_type,
            PARTITION_TABLE_TYPE.MBR,
        )

    def test_udpate_partitiontable_type_no_table(self):
        block_device = factory.make_PhysicalBlockDevice()
        self.assertIsNone(block_device.get_partitiontable())
        form = UpdatePhysicalBlockDeviceForm(
            instance=block_device,
            data={"partition_table_type": PARTITION_TABLE_TYPE.MBR},
        )
        self.assertFalse(form.is_valid())
        self.assertEqual(
            form.errors["partition_table_type"],
            ["Block device has no partition table"],
        )


class TestUpdateDeployedPhysicalBlockDeviceForm(MAASServerTestCase):
    def test_requires_no_fields(self):
        block_device = factory.make_PhysicalBlockDevice()
        form = UpdateDeployedPhysicalBlockDeviceForm(
            instance=block_device, data={}
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(set(), form.errors.keys())

    def test_updates_deployed_physical_block_device(self):
        block_device = factory.make_PhysicalBlockDevice()
        name = factory.make_name("sd")
        model = factory.make_name("model")
        serial = factory.make_name("serial")
        id_path = factory.make_absolute_path()
        form = UpdateDeployedPhysicalBlockDeviceForm(
            instance=block_device,
            data={
                "name": name,
                "model": model,
                "serial": serial,
                "id_path": id_path,
            },
        )
        self.assertTrue(form.is_valid(), form.errors)
        block_device = form.save()
        self.assertEqual(block_device.name, name)
        self.assertEqual(block_device.model, model)
        self.assertEqual(block_device.serial, serial)
        self.assertEqual(block_device.id_path, id_path)
        self.assertEqual(block_device.size, block_device.size)
        self.assertEqual(block_device.block_size, block_device.block_size)


class TestUpdateVirtualBlockDeviceForm(MAASServerTestCase):
    def test_requires_no_fields(self):
        block_device = factory.make_VirtualBlockDevice()
        form = UpdateVirtualBlockDeviceForm(instance=block_device, data={})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(set(), form.errors.keys())

    def test_updates_virtual_block_device(self):
        block_device = factory.make_VirtualBlockDevice()
        name = factory.make_name("lv")
        vguuid = "%s" % uuid.uuid4()
        size = random.randint(
            MIN_BLOCK_DEVICE_SIZE, block_device.filesystem_group.get_size()
        )
        form = UpdateVirtualBlockDeviceForm(
            instance=block_device,
            data={"name": name, "uuid": vguuid, "size": size},
        )
        self.assertTrue(form.is_valid(), form.errors)
        block_device = form.save()
        expected_size = round_size_to_nearest_block(
            size, PARTITION_ALIGNMENT_SIZE, False
        )
        self.assertEqual(block_device.name, name)
        self.assertEqual(block_device.uuid, vguuid)
        self.assertEqual(block_device.size, expected_size)
