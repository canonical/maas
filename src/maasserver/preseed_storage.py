# Copyright 2015-2019 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Preseed generation for curtin storage."""


from operator import attrgetter

from django.db.models import F, Q, Sum
import yaml

from maasserver.enum import (
    FILESYSTEM_GROUP_TYPE,
    FILESYSTEM_TYPE,
    PARTITION_TABLE_TYPE,
)
from maasserver.models import FilesystemGroup, Partition, PhysicalBlockDevice
from maasserver.models.partitiontable import (
    BIOS_GRUB_PARTITION_SIZE,
    INITIAL_PARTITION_OFFSET,
    PARTITION_TABLE_EXTRA_SPACE,
    PREP_PARTITION_SIZE,
)
from maasserver.models.virtualblockdevice import VirtualBlockDevice


class CurtinStorageGenerator:
    """Generates the YAML storage configuration for curtin."""

    def __init__(self, node):
        self.node = node
        self.node_config = node.current_config
        self.boot_disk = node.get_boot_disk()
        self.grub_device_ids = []
        self.boot_first_partitions = []
        self.operations = {
            "disk": [],
            "partition": [],
            "format": [],
            "mount": [],
            "lvm_volgroup": [],
            "lvm_partition": [],
            "raid": [],
            "bcache": [],
            "vmfs": [],
        }

    def generate(self):
        """Create the YAML storage configuration for curtin."""
        self.storage_config = []

        # Add all the items to operations.
        self._add_disk_and_filesystem_group_operations()
        self._find_grub_devices()
        self._add_partition_operations()
        self._add_format_and_mount_operations()

        # Generate each YAML operation in the storage_config.
        self._generate_disk_operations()
        self._generate_volume_group_operations()
        self._generate_logical_volume_operations()
        self._generate_raid_operations()
        self._generate_bcache_operations()
        self._generate_vmfs_operations()
        self._generate_partition_operations()
        self._generate_format_operations()

        # Order the storage_config where dependencies come first.
        self._order_config_dependency()

        # Generate the mount operations that go at the end of the
        # storage_config.
        self._generate_mount_operations()

        # Render the resulting YAML.
        storage_config = {
            "partitioning_commands": {
                "builtin": ["curtin", "block-meta", "custom"]
            },
            "storage": {"version": 1, "config": self.storage_config},
        }
        return yaml.safe_dump(storage_config)

    def _add_disk_and_filesystem_group_operations(self):
        """Add all disk and filesystem group (lvm, raid, bcache) operations.

        These operations come from all of the physical block devices attached
        to the node.
        """
        filesystem_group_ids = set()
        for block_device in self.node_config.blockdevice_set.order_by("id"):
            block_device = block_device.actual_instance
            if isinstance(block_device, PhysicalBlockDevice):
                self.operations["disk"].append(block_device)
            elif isinstance(block_device, VirtualBlockDevice):
                filesystem_group_ids.add(block_device.filesystem_group.id)
                self._add_filesystem_group_operation(
                    block_device.filesystem_group, block_device
                )
            else:
                raise ValueError(
                    "Unknown block device instance: %s"
                    % (block_device.__class__.__name__)
                )

        # also add operations for filesystem groups that are not backed by a
        # virtual block device. In that case there's no direct link from the
        # disk to the group, but it goes through a filesystem
        filesystem_groups = (
            FilesystemGroup.objects.filter(
                filesystems__block_device__node_config=self.node_config,
            )
            .exclude(id__in=filesystem_group_ids)
            .annotate(block_device_id=F("filesystems__block_device_id"))
        )
        for filesystem_group in filesystem_groups:
            self._add_filesystem_group_operation(filesystem_group)

    def _add_filesystem_group_operation(
        self, filesystem_group, block_device=None
    ):
        operations_map = (
            (filesystem_group.is_lvm, "lvm_volgroup"),
            (filesystem_group.is_raid, "raid"),
            (filesystem_group.is_bcache, "bcache"),
            (filesystem_group.is_vmfs, "vmfs"),
        )
        for check, key in operations_map:
            if check():
                if filesystem_group not in self.operations[key]:
                    self.operations[key].append(filesystem_group)
                break
        else:
            raise ValueError(
                f"Unknown filesystem group type: {filesystem_group.group_type}"
            )

        if (
            filesystem_group.is_lvm()
            and block_device
            and block_device not in self.operations["lvm_partition"]
        ):
            self.operations["lvm_partition"].append(block_device)

    def _requires_prep_partition(self, block_device):
        """Return True if block device requires the prep partition."""
        arch, _ = self.node.split_arch()
        return arch == "ppc64el" and block_device.id in self.grub_device_ids

    def _requires_bios_grub_partition(self, block_device):
        """Return True if block device requires the bios_grub partition."""
        arch, _ = self.node.split_arch()
        bios_boot_method = self.node.get_bios_boot_method()
        return arch == "amd64" and bios_boot_method != "uefi"

    def _add_partition_operations(self):
        """Add all the partition operations.

        These operations come from all the partitions on all block devices
        attached to the node.
        """
        for block_device in self.node_config.blockdevice_set.order_by("id"):
            requires_prep = self._requires_prep_partition(block_device)
            requires_bios_grub = self._requires_bios_grub_partition(
                block_device
            )
            partition_table = block_device.get_partitiontable()
            if partition_table is not None:
                partitions = list(partition_table.partitions.order_by("id"))
                for idx, partition in enumerate(partitions):
                    # If this is the first partition and prep or bios_grub
                    # partition is required then track this as a first
                    # partition for boot
                    is_boot_partition = (
                        (requires_prep or requires_bios_grub)
                        and block_device.id in self.grub_device_ids
                        and idx == 0
                    )
                    if is_boot_partition:
                        self.boot_first_partitions.append(partition)
                    self.operations["partition"].append(partition)

    def _add_format_and_mount_operations(self):
        """Add all the format and mount operations.

        These operations come from all the block devices and partitions
        attached to the node.
        """
        for block_device in self.node_config.blockdevice_set.order_by("id"):
            filesystem = block_device.get_effective_filesystem()
            if self._requires_format_operation(filesystem):
                self.operations["format"].append(filesystem)
                if filesystem.is_mounted:
                    self.operations["mount"].append(filesystem)
            else:
                partition_table = block_device.get_partitiontable()
                if partition_table is not None:
                    for partition in partition_table.partitions.order_by("id"):
                        partition_filesystem = (
                            partition.get_effective_filesystem()
                        )
                        if self._requires_format_operation(
                            partition_filesystem
                        ):
                            self.operations["format"].append(
                                partition_filesystem
                            )
                            if partition_filesystem.is_mounted:
                                self.operations["mount"].append(
                                    partition_filesystem
                                )

        for filesystem in self.node_config.special_filesystems.filter(
            acquired=True
        ):
            self.operations["mount"].append(filesystem)

    def _requires_format_operation(self, filesystem):
        """Return True if the filesystem requires a format operation."""
        return (
            filesystem is not None
            and filesystem.filesystem_group_id is None
            and filesystem.cache_set is None
        )

    def _find_grub_devices(self):
        """Save which devices should have grub installed."""
        for raid in self.operations["raid"]:
            partition_ids, block_devices_ids = zip(
                *raid.filesystems.values_list("partition", "block_device")
            )
            partition_ids = set(partition_ids)
            partition_ids.discard(None)
            block_devices_ids = set(block_devices_ids)
            block_devices_ids.discard(None)
            devices = PhysicalBlockDevice.objects.filter(
                Q(id__in=block_devices_ids)
                | Q(partitiontable__partitions__in=partition_ids)
            )
            devices = list(devices.values_list("id", flat=True))
            if self.boot_disk.id in devices:
                self.grub_device_ids = devices

        if not self.grub_device_ids:
            self.grub_device_ids = [self.boot_disk.id]

    def _generate_disk_operations(self):
        """Generate all disk operations."""
        for block_device in self.operations["disk"]:
            self._generate_disk_operation(block_device)

    def _generate_disk_operation(self, block_device):
        """Generate disk operation for `block_device` and place in
        `storage_config`."""
        disk_operation = {
            "id": block_device.get_name(),
            "name": block_device.get_name(),
            "type": "disk",
            "wipe": "superblock",
        }
        # Set model and serial unless not set, then curtin will use a
        # device path to match.
        if block_device.model and block_device.serial:
            disk_operation["model"] = block_device.model
            disk_operation["serial"] = block_device.serial
        else:
            disk_operation["path"] = block_device.id_path

        # Set the partition table type if a partition table exists or if this
        # is the boot disk.
        add_prep_partition = False
        add_bios_grub_partition = False
        partition_table = block_device.get_partitiontable()
        bios_boot_method = self.node.get_bios_boot_method()
        node_arch, _ = self.node.split_arch()
        should_install_grub = block_device.id in self.grub_device_ids

        if partition_table is not None:
            disk_operation["ptable"] = self._get_ptable_type(partition_table)
        elif should_install_grub:
            gpt_table = bios_boot_method in [
                "uefi",
                "powernv",
                "powerkvm",
            ] or (bios_boot_method != "uefi" and node_arch == "amd64")
            disk_operation["ptable"] = "gpt" if gpt_table else "msdos"
            add_prep_partition = (
                node_arch == "ppc64el"
                and bios_boot_method in ("uefi", "powernv", "powerkvm")
            )

        # always add a boot partition for GPT without UEFI. ESXi doesn't
        # need a partition added as one is already in the DD format.
        add_bios_grub_partition = (
            disk_operation.get("ptable") == "gpt"
            and node_arch == "amd64"
            and bios_boot_method != "uefi"
            and self.node.osystem != "esxi"
        )

        # Set this disk to be the grub device if it's the boot disk and doesn't
        # require a prep partition. When a prep partition is required grub
        # must be installed on that partition and not in the partition header
        # of that disk.
        requires_prep = self._requires_prep_partition(block_device)
        if should_install_grub and not requires_prep:
            disk_operation["grub_device"] = True
        self.storage_config.append(disk_operation)

        # Add the prep partition at the beginning of the disk
        # when it is required.
        if add_prep_partition:
            self._generate_prep_partition(block_device.get_name())

        # Add the bios_grub partition at the beginning of the disk
        # when it is required.
        if add_bios_grub_partition:
            self._generate_bios_grub_partition(block_device.get_name())

    def _get_ptable_type(self, partition_table):
        """Return the value for the "ptable" entry in the physical operation."""
        if partition_table.table_type == PARTITION_TABLE_TYPE.MBR:
            return "msdos"
        elif partition_table.table_type == PARTITION_TABLE_TYPE.GPT:
            return "gpt"
        else:
            raise ValueError(
                "Unknown partition table type: %s"
                % (partition_table.table_type)
            )

    def _generate_prep_partition(self, device_name):
        """Generate the prep partition at the beginning of the block device."""
        prep_part_name = "%s-part1" % device_name
        partition_operation = {
            "id": prep_part_name,
            "name": prep_part_name,
            "type": "partition",
            "number": 1,
            "offset": "%dB" % INITIAL_PARTITION_OFFSET,
            "size": "%dB" % PREP_PARTITION_SIZE,
            "device": device_name,
            "wipe": "zero",
            "flag": "prep",
            "grub_device": True,
        }
        self.storage_config.append(partition_operation)

    def _generate_bios_grub_partition(self, device_name):
        """Generate the bios_grub partition at the beginning of the device."""
        partition_operation = {
            "id": "%s-part1" % device_name,
            "type": "partition",
            "number": 1,
            "offset": "%dB" % INITIAL_PARTITION_OFFSET,
            "size": "%dB" % BIOS_GRUB_PARTITION_SIZE,
            "device": device_name,
            "wipe": "zero",
            "flag": "bios_grub",
        }
        self.storage_config.append(partition_operation)

    def _generate_partition_operations(self):
        """Generate all partition operations."""
        for partition in self.operations["partition"]:
            if partition in self.boot_first_partitions:
                # This is the first partition in the boot disk and add prep
                # partition at the beginning of the partition table.
                device_name = partition.partition_table.block_device.get_name()
                if self._requires_prep_partition(
                    partition.partition_table.block_device
                ):
                    self._generate_prep_partition(device_name)
                self._generate_partition_operation(
                    partition, include_initial=False
                )
            else:
                self._generate_partition_operation(
                    partition, include_initial=True
                )

    def _generate_partition_operation(self, partition, include_initial):
        """Generate partition operation for `partition` and place in
        `storage_config`."""
        partition_table = partition.partition_table
        block_device = partition_table.block_device
        partition_operation = {
            "id": partition.get_name(),
            "name": partition.get_name(),
            "type": "partition",
            "number": partition.index,
            "uuid": partition.uuid,
            "size": "%sB" % partition.size,
            "device": block_device.get_name(),
            "wipe": "superblock",
        }
        # First partition always sets the initial offset.
        if partition.index == 1 and include_initial:
            partition_operation["offset"] = "%sB" % INITIAL_PARTITION_OFFSET
        if partition.bootable:
            partition_operation["flag"] = "boot"
        if partition_table.table_type == PARTITION_TABLE_TYPE.MBR:
            # Fifth partition on an MBR partition, must add the extend
            # partition operation. So the remaining partitions can be added.
            if partition.index == 5:
                # Calculate the remaining size of the disk available for the
                # extended partition.
                extended_size = block_device.size - PARTITION_TABLE_EXTRA_SPACE
                previous_partitions = Partition.objects.filter(
                    id__lt=partition.id, partition_table=partition_table
                )
                extended_size = extended_size - (
                    previous_partitions.aggregate(Sum("size"))["size__sum"]
                )
                # Curtin adds 1MiB between each logical partition inside the
                # extended partition. It incorrectly adds onto the size
                # automatically so we have to extract that size from the
                # overall size of the extended partition.
                following_partitions = Partition.objects.filter(
                    id__gte=partition.id, partition_table=partition_table
                )
                logical_extra_space = following_partitions.count() * (1 << 20)
                extended_size = extended_size - logical_extra_space
                self.storage_config.append(
                    {
                        "id": "%s-part4" % block_device.get_name(),
                        "type": "partition",
                        "number": 4,
                        "device": block_device.get_name(),
                        "flag": "extended",
                        "size": "%sB" % extended_size,
                    }
                )
                partition_operation["flag"] = "logical"
                partition_operation["size"] = "%sB" % (
                    partition.size - (1 << 20)
                )
            elif partition.index > 5:
                # Curtin adds 1MiB between each logical partition. We subtract
                # the 1MiB from the size of the partition so all the partitions
                # fit within the extended partition.
                partition_operation["flag"] = "logical"
                partition_operation["size"] = "%sB" % (
                    partition.size - (1 << 20)
                )
        self.storage_config.append(partition_operation)

    def _generate_format_operations(self):
        """Generate all format operations."""
        for filesystem in self.operations["format"]:
            self._generate_format_operation(filesystem)

    def _ext4_has_metadata_csum(self):
        """Older distros don't have Metadata Checksum, and enabling it when
        it's not supported prevents Linux from mounting this partition
        for writing"""
        if self.node.osystem == "suse":
            return not self.node.distro_series.startswith("sles12")
        return True

    def _generate_format_operation(self, filesystem):
        """Generate format operation for `filesystem` and place in
        `storage_config`."""
        device_or_partition = filesystem.get_device()
        extra = {}

        if (
            filesystem.fstype == FILESYSTEM_TYPE.EXT4
            and not self._ext4_has_metadata_csum()
        ):
            extra["extra_options"] = ["-O", "^metadata_csum"]

        self.storage_config.append(
            {
                "id": "%s_format" % device_or_partition.get_name(),
                "type": "format",
                "fstype": filesystem.fstype,
                "uuid": filesystem.uuid,
                "label": filesystem.label,
                "volume": device_or_partition.get_name(),
                **extra,
            }
        )

    def _generate_volume_group_operations(self):
        """Generate all volume group operations."""
        for filesystem_group in self.operations["lvm_volgroup"]:
            self._generate_volume_group_operation(filesystem_group)

    def _generate_volume_group_operation(self, filesystem_group):
        """Generate volume group operation for `filesystem_group` and place in
        `storage_config`."""
        volume_group_operation = {
            "id": filesystem_group.name,
            "name": filesystem_group.name,
            "type": "lvm_volgroup",
            "uuid": filesystem_group.uuid,
            "devices": [],
        }
        for filesystem in filesystem_group.filesystems.all():
            block_or_partition = filesystem.get_device()
            volume_group_operation["devices"].append(
                block_or_partition.get_name()
            )
        volume_group_operation["devices"] = sorted(
            volume_group_operation["devices"]
        )
        self.storage_config.append(volume_group_operation)

    def _generate_logical_volume_operations(self):
        """Generate all logical volume operations."""
        for block_device in self.operations["lvm_partition"]:
            self._generate_logical_volume_operation(block_device)

    def _generate_logical_volume_operation(self, block_device):
        """Generate logical volume operation for `block_device` and place in
        `storage_config`."""

        filesystem_group = getattr(block_device, "filesystem_group", None)
        if not filesystem_group:
            # physical block devices are not directly linked to a filesystem
            # group, but through a filesystem. This is the case for instance
            # for LVM VGs created directly on a physical disk
            filesystem_group = (
                block_device.get_effective_filesystem().filesystem_group
            )
        self.storage_config.append(
            {
                "id": block_device.get_name(),
                "name": block_device.name,  # Use name of logical volume only.
                "type": "lvm_partition",
                "volgroup": filesystem_group.name,
                "size": f"{block_device.size}B",
            }
        )

    def _generate_raid_operations(self):
        """Generate all raid operations."""
        for filesystem_group in self.operations["raid"]:
            self._generate_raid_operation(filesystem_group)

    def _generate_raid_operation(self, filesystem_group):
        """Generate raid operation for `filesystem_group` and place in
        `storage_config`."""
        raid_operation = {
            "id": filesystem_group.name,
            "name": filesystem_group.name,
            "type": "raid",
            "raidlevel": self._get_raid_level(filesystem_group),
            "devices": [],
            "spare_devices": [],
        }
        for filesystem in filesystem_group.filesystems.all():
            block_or_partition = filesystem.get_device()
            name = block_or_partition.get_name()
            if filesystem.fstype == FILESYSTEM_TYPE.RAID:
                raid_operation["devices"].append(name)
            elif filesystem.fstype == FILESYSTEM_TYPE.RAID_SPARE:
                raid_operation["spare_devices"].append(name)
        raid_operation["devices"] = sorted(raid_operation["devices"])
        raid_operation["spare_devices"] = sorted(
            raid_operation["spare_devices"]
        )
        block_device = filesystem_group.virtual_device
        partition_table = block_device.get_partitiontable()
        if partition_table is not None:
            raid_operation["ptable"] = self._get_ptable_type(partition_table)
        self.storage_config.append(raid_operation)

    def _get_raid_level(self, filesystem_group):
        """Return the raid level for the filesystem group type."""
        raid_levels = {
            FILESYSTEM_GROUP_TYPE.RAID_0: 0,
            FILESYSTEM_GROUP_TYPE.RAID_1: 1,
            FILESYSTEM_GROUP_TYPE.RAID_5: 5,
            FILESYSTEM_GROUP_TYPE.RAID_6: 6,
            FILESYSTEM_GROUP_TYPE.RAID_10: 10,
        }
        return raid_levels[filesystem_group.group_type]

    def _generate_bcache_operations(self):
        """Generate all bcache operations."""
        for filesystem_group in self.operations["bcache"]:
            self._generate_bcache_operation(filesystem_group)

    def _generate_bcache_operation(self, filesystem_group):
        """Generate bcache operation for `filesystem_group` and place in
        `storage_config`."""
        bcache_operation = {
            "id": filesystem_group.name,
            "name": filesystem_group.name,
            "type": "bcache",
            "backing_device": filesystem_group.get_bcache_backing_filesystem()
            .get_device()
            .get_name(),
            "cache_device": filesystem_group.cache_set.get_device().get_name(),
            "cache_mode": filesystem_group.cache_mode,
        }
        block_device = filesystem_group.virtual_device
        partition_table = block_device.get_partitiontable()
        if partition_table is not None:
            bcache_operation["ptable"] = self._get_ptable_type(partition_table)
        self.storage_config.append(bcache_operation)

    def _generate_vmfs_operations(self):
        """Generate all vmfs operations."""
        for vmfs in self.operations["vmfs"]:
            self.storage_config.append(
                {
                    "id": vmfs.name,
                    "name": vmfs.name,
                    "type": "vmfs6",
                    "devices": sorted(
                        fs.get_device().name for fs in vmfs.filesystems.all()
                    ),
                }
            )

    def _reorder_devices(self, ids_above, operation):
        for device in operation["devices"]:
            if device not in ids_above:
                self._reorder_operation(operation, device)
                return True
        return False

    def _order_config_dependency(self):
        """Re-order the storage config so dependencies appear before
        dependents."""
        # Continuously loop through the storage configuration until a complete
        # pass is made without having to reorder dependencies.
        while True:
            ids_above = []
            for operation in list(self.storage_config):
                operation_type = operation["type"]
                if operation_type == "disk":
                    # Doesn't depend on anything.
                    pass
                elif operation_type == "partition":
                    device = operation["device"]
                    if device not in ids_above:
                        self._reorder_operation(operation, device)
                        break
                elif operation_type == "format":
                    volume = operation["volume"]
                    if volume not in ids_above:
                        self._reorder_operation(operation, volume)
                        break
                elif operation_type == "lvm_volgroup":
                    if self._reorder_devices(ids_above, operation):
                        break
                elif operation_type == "lvm_partition":
                    volgroup = operation["volgroup"]
                    if volgroup not in ids_above:
                        self._reorder_operation(operation, volgroup)
                        break
                elif operation_type == "raid":
                    if self._reorder_devices(ids_above, operation):
                        break
                    exit_early = False
                    for device in operation["spare_devices"]:
                        if device not in ids_above:
                            self._reorder_operation(operation, device)
                            exit_early = True
                            break
                    if exit_early:
                        break
                elif operation_type == "bcache":
                    backing_device = operation["backing_device"]
                    if backing_device not in ids_above:
                        self._reorder_operation(operation, backing_device)
                        break
                    cache_device = operation["cache_device"]
                    if cache_device not in ids_above:
                        self._reorder_operation(operation, cache_device)
                        break
                elif operation_type == "vmfs6":
                    if self._reorder_devices(ids_above, operation):
                        break
                else:
                    raise ValueError(
                        "Unknown operation type: %s" % operation_type
                    )
                ids_above.append(operation["id"])

            # If parsed the entire storage config without breaking out of the
            # loop then all dependencies are in order.
            if len(ids_above) == len(self.storage_config):
                break

    def _reorder_operation(self, operation, dependent_id):
        """Reorder the `operation` to be after `dependent_id` in the
        `storage_config`."""
        # Remove the operation from the storage_config.
        self.storage_config.remove(operation)

        # Place the operation after the dependent in the storage_config.
        dependent_idx = [
            idx
            for idx, op in enumerate(self.storage_config)
            if op["id"] == dependent_id
        ][0]
        self.storage_config.insert(dependent_idx + 1, operation)

    def _generate_mount_operations(self):
        """Generate all mount operations."""
        # Sort the mounts lexically. This will ensure that the mount
        # operations are performed in a sane order. Without this curtin will
        # mount the filesystems out of order preventing installation from
        # working correctly.
        mount_operations = sorted(
            self.operations["mount"], key=attrgetter("mount_point")
        )
        for filesystem in mount_operations:
            self._generate_mount_operation(filesystem)

    def _generate_mount_operation(self, filesystem):
        """Generate mount operation for `filesystem` and place in
        `storage_config`."""
        device = filesystem.get_device()
        stanza = {"type": "mount"}
        if device:
            name = device.get_name()
            stanza.update(
                {
                    "id": f"{name}_mount",
                    "device": f"{name}_format",
                }
            )
        else:
            # this is a special filesystem
            mount_id = filesystem.mount_point.lstrip("/").replace("/", "-")
            mount_id += "_mount"
            stanza.update(
                {
                    "id": mount_id,
                    "fstype": filesystem.fstype,
                    "spec": filesystem.fstype,
                }
            )
        if filesystem.uses_mount_point:
            stanza["path"] = filesystem.mount_point
        if filesystem.mount_options is not None:
            stanza["options"] = filesystem.mount_options
        self.storage_config.append(stanza)


def compose_curtin_storage_config(node):
    """Compose the storage configuration for curtin."""
    generator = CurtinStorageGenerator(node)
    return [generator.generate()]
