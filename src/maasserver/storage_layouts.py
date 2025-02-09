# Copyright 2015-2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Storage layouts."""

from operator import attrgetter

from django import forms
from django.core.exceptions import ValidationError
from django.forms import Form
from django.utils import timezone

from maasserver.enum import (
    CACHE_MODE_TYPE,
    CACHE_MODE_TYPE_CHOICES,
    FILESYSTEM_TYPE,
    PARTITION_TABLE_TYPE,
)
from maasserver.exceptions import MAASAPIValidationError
from maasserver.fields_storage import (
    BytesOrPercentageField,
    calculate_size_from_percentage,
    is_percentage,
)
from maasserver.models.cacheset import CacheSet
from maasserver.models.partition import (
    get_max_mbr_partition_size,
    MIN_PARTITION_SIZE,
)
from maasserver.utils.forms import compose_invalid_choice_text, set_form_error

EFI_PARTITION_SIZE = 512 * 1024 * 1024  # 512 MiB
MIN_BOOT_PARTITION_SIZE = 512 * 1024 * 1024  # 512 MiB
MIN_ROOT_PARTITION_SIZE = 3 * 1024 * 1024 * 1024  # 3 GiB


class StorageLayoutError(Exception):
    """Error raised when layout cannot be used on node."""


class StorageLayoutMissingBootDiskError(StorageLayoutError):
    """Error raised when a node is missing a boot disk to configure."""


class StorageLayoutFieldsError(MAASAPIValidationError):
    """Error raised when fields from a storage layout are invalid."""


class StorageLayoutBase(Form):
    """Base class all storage layouts extend from."""

    boot_size = BytesOrPercentageField(required=False)
    root_size = BytesOrPercentageField(required=False)

    # subclasses should override these
    name = ""
    title = ""

    def __init__(self, node, params: dict = None):
        super().__init__(data=({} if params is None else params))
        self.node = node
        self.block_devices = self._load_physical_block_devices()
        self.boot_disk = node.get_boot_disk()
        self.setup_root_device_field()

    def _load_physical_block_devices(self):
        """Load all the `PhysicalBlockDevice`'s for node."""
        # The websocket prefetches blockdevice_set, creating a queryset
        # on node.physicalblockdevice_set adds additional queries.
        physical_bds = []
        for bd in self.node.current_config.blockdevice_set.all():
            try:
                physical_bds.append(bd.physicalblockdevice)
            except Exception:
                pass
        return sorted(physical_bds, key=attrgetter("id"))

    def setup_root_device_field(self):
        """Setup the possible root devices."""
        choices = [
            (block_device.id, block_device.id)
            for block_device in self.block_devices
        ]
        invalid_choice_message = compose_invalid_choice_text(
            "root_device", choices
        )
        self.fields["root_device"] = forms.ChoiceField(
            choices=choices,
            required=False,
            error_messages={"invalid_choice": invalid_choice_message},
        )

    def _clean_size(self, field, min_size=None, max_size=None):
        """Clean a size field."""
        size = self.cleaned_data[field]
        if size is None:
            return None
        if is_percentage(size):
            # Calculate the percentage not counting the EFI partition.
            size = calculate_size_from_percentage(
                self.boot_disk.size - EFI_PARTITION_SIZE, size
            )
        if min_size is not None and size < min_size:
            raise ValidationError(
                "Size is too small. Minimum size is %s." % min_size
            )
        if max_size is not None and size > max_size:
            raise ValidationError(
                "Size is too large. Maximum size is %s." % max_size
            )
        return size

    def clean_boot_size(self):
        """Clean the boot_size field."""
        if self.boot_disk is not None:
            return self._clean_size(
                "boot_size",
                MIN_BOOT_PARTITION_SIZE,
                (
                    self.boot_disk.size
                    - EFI_PARTITION_SIZE
                    - MIN_ROOT_PARTITION_SIZE
                ),
            )
        else:
            return None

    def clean_root_size(self):
        """Clean the root_size field."""
        if self.boot_disk is not None:
            return self._clean_size(
                "root_size",
                MIN_ROOT_PARTITION_SIZE,
                (
                    self.boot_disk.size
                    - EFI_PARTITION_SIZE
                    - MIN_BOOT_PARTITION_SIZE
                ),
            )
        else:
            return None

    def clean(self):
        """Validate the data."""
        cleaned_data = super().clean()
        if len(self.block_devices) == 0:
            raise StorageLayoutMissingBootDiskError(
                "Node doesn't have any storage devices to configure."
            )
        if self.boot_disk is None:
            raise StorageLayoutMissingBootDiskError(
                "Node doesn't have a boot partition defined."
            )
        disk_size = self.boot_disk.size
        total_size = EFI_PARTITION_SIZE + self.get_boot_size()
        root_size = self.get_root_size()
        if root_size is not None and total_size + root_size > disk_size:
            raise ValidationError(
                "Size of the boot partition and root partition are larger "
                "than the available space on the boot disk."
            )
        return cleaned_data

    def get_root_device(self):
        """Get the device that should be the root partition.

        Return the boot_disk if no root_device was defined.
        """
        if self.cleaned_data.get("root_device"):
            root_id = self.cleaned_data["root_device"]
            return self.node.physicalblockdevice_set.get(id=root_id)
        else:
            # User didn't specify a root disk so use the currently defined
            # boot disk.
            return self.boot_disk

    def get_boot_size(self):
        """Get the size of the boot partition."""
        if self.cleaned_data.get("boot_size"):
            return self.cleaned_data["boot_size"]
        else:
            return 0

    def get_root_size(self):
        """Get the size of the root partition.

        Return of None means to expand the remaining of the disk.
        """
        if self.cleaned_data.get("root_size"):
            return self.cleaned_data["root_size"]
        else:
            return None

    def create_basic_layout(self, boot_size=None):
        """Create the basic layout that is similar for all layout types.

        :return: The created root partition.
        """
        from maasserver.models.filesystem import Filesystem
        from maasserver.models.partitiontable import PartitionTable

        boot_partition_table = PartitionTable.objects.create(
            block_device=self.boot_disk
        )
        bios_boot_method = self.node.get_bios_boot_method()
        node_arch, _ = self.node.split_arch()
        if (
            boot_partition_table.table_type == PARTITION_TABLE_TYPE.GPT
            and bios_boot_method == "uefi"
            and node_arch != "ppc64el"
        ):
            # Add EFI partition only if booting UEFI and not a ppc64el
            # architecture.
            efi_partition = boot_partition_table.add_partition(
                size=EFI_PARTITION_SIZE, bootable=True
            )
            Filesystem.objects.create(
                node_config_id=self.node.current_config_id,
                partition=efi_partition,
                fstype=FILESYSTEM_TYPE.FAT32,
                label="efi",
                mount_point="/boot/efi",
            )
        elif (
            bios_boot_method != "uefi"
            and node_arch == "arm64"
            and boot_size is None
        ):
            # Add boot partition only if booting an arm64 architecture and
            # not UEFI and boot_size is None.
            boot_partition = boot_partition_table.add_partition(
                size=MIN_BOOT_PARTITION_SIZE, bootable=True
            )
            Filesystem.objects.create(
                node_config_id=self.node.current_config_id,
                partition=boot_partition,
                fstype=FILESYSTEM_TYPE.EXT4,
                label="boot",
                mount_point="/boot",
            )
        if boot_size is None:
            boot_size = self.get_boot_size()
        if boot_size > 0:
            boot_partition = boot_partition_table.add_partition(
                size=boot_size, bootable=True
            )
            Filesystem.objects.create(
                node_config_id=self.node.current_config_id,
                partition=boot_partition,
                fstype=FILESYSTEM_TYPE.EXT4,
                label="boot",
                mount_point="/boot",
            )
        root_device = self.get_root_device()
        root_size = self.get_root_size()
        if root_device == self.boot_disk:
            partition_table = boot_partition_table
            root_device = self.boot_disk
        else:
            partition_table = PartitionTable.objects.create(
                block_device=root_device
            )

        # Fix the maximum root_size for MBR.
        max_mbr_size = get_max_mbr_partition_size()
        if (
            partition_table.table_type == PARTITION_TABLE_TYPE.MBR
            and root_size is not None
            and root_size > max_mbr_size
        ):
            root_size = max_mbr_size
        root_partition = partition_table.add_partition(size=root_size)
        return root_partition, boot_partition_table

    def configure(self, allow_fallback=True):
        """Configure the storage for the node."""
        if not self.is_valid():
            raise StorageLayoutFieldsError(self.errors)
        self.node._clear_full_storage_configuration()
        return self.configure_storage(allow_fallback)

    def configure_storage(self, allow_fallback):
        """Configure the storage of the node.

        Sub-classes should override this method not `configure`.
        """
        raise NotImplementedError()

    def is_uefi_partition(self, partition):
        """Returns whether or not the given partition is a UEFI partition."""
        if partition.partition_table.table_type != PARTITION_TABLE_TYPE.GPT:
            return False
        if partition.size != EFI_PARTITION_SIZE:
            return False
        if not partition.bootable:
            return False
        fs = partition.get_effective_filesystem()
        if fs is None:
            return False
        if fs.fstype != FILESYSTEM_TYPE.FAT32:
            return False
        if fs.label != "efi":
            return False
        if fs.mount_point != "/boot/efi":
            return False
        return True

    def is_boot_partition(self, partition):
        """Returns whether or not the given partition is a boot partition."""
        if not partition.bootable:
            return False
        fs = partition.get_effective_filesystem()
        if fs is None:
            return False
        if fs.fstype != FILESYSTEM_TYPE.EXT4:
            return False
        if fs.label != "boot":
            return False
        if fs.mount_point != "/boot":
            return False
        return True

    def is_layout(self):
        """Returns the block device the layout was applied on."""
        raise NotImplementedError()


class FlatStorageLayout(StorageLayoutBase):
    """Flat layout.

    NAME        SIZE        TYPE    FSTYPE         MOUNTPOINT
    sda         100G        disk
      sda1      512M        part    fat32          /boot/efi
      sda2      99.5G       part    ext4           /
    """

    name = "flat"
    title = "Flat layout"

    def configure_storage(self, allow_fallback):
        """Create the flat configuration."""
        # Circular imports.
        from maasserver.models.filesystem import Filesystem

        root_partition, _ = self.create_basic_layout()
        Filesystem.objects.create(
            node_config_id=self.node.current_config_id,
            partition=root_partition,
            fstype=FILESYSTEM_TYPE.EXT4,
            label="root",
            mount_point="/",
        )
        return self.name

    def is_layout(self):
        """Checks if the node is using a flat layout."""
        for bd in self.block_devices:
            pt = bd.get_partitiontable()
            if pt is None:
                continue
            for partition in pt.partitions.all():
                # On UEFI systems the first partition is for the bootloader. If
                # found check the next partition.
                if partition.index == 1 and self.is_uefi_partition(partition):
                    continue
                # Most layouts allow you to define a boot partition, skip it
                # if its defined.
                if self.is_boot_partition(partition):
                    continue
                # Check if the partition is an EXT4 partition. If it isn't
                # move onto the next block device.
                fs = partition.get_effective_filesystem()
                if fs is None:
                    break
                if fs.fstype != FILESYSTEM_TYPE.EXT4:
                    break
                if fs.label != "root":
                    break
                if fs.mount_point != "/":
                    break
                return bd
        return None


class LVMStorageLayout(StorageLayoutBase):
    """LVM layout.

    NAME        SIZE        TYPE    FSTYPE         MOUNTPOINT
    sda         100G        disk
      sda1      512M        part    fat32          /boot/efi
      sda2      99.5G       part    lvm-pv(vgroot)
    vgroot      99.5G       lvm
      lvroot    99.5G       lvm     ext4           /
    """

    name = "lvm"
    title = "LVM layout"

    DEFAULT_VG_NAME = "vgroot"
    DEFAULT_LV_NAME = "lvroot"

    vg_name = forms.CharField(required=False)
    lv_name = forms.CharField(required=False)
    lv_size = BytesOrPercentageField(required=False)

    def get_vg_name(self):
        """Get the name of the volume group."""
        if self.cleaned_data.get("vg_name"):
            return self.cleaned_data["vg_name"]
        else:
            return self.DEFAULT_VG_NAME

    def get_lv_name(self):
        """Get the name of the logical volume."""
        if self.cleaned_data.get("lv_name"):
            return self.cleaned_data["lv_name"]
        else:
            return self.DEFAULT_LV_NAME

    def get_lv_size(self):
        """Get the size of the logical volume.

        Return of None means to expand the entire volume group.
        """
        if self.cleaned_data.get("lv_size"):
            return self.cleaned_data["lv_size"]
        else:
            return None

    def get_calculated_lv_size(self, volume_group):
        """Return the size of the logical volume based on `lv_size` or the
        available size in the `volume_group`."""
        lv_size = self.get_lv_size()
        if lv_size is None:
            lv_size = volume_group.get_size()
        return lv_size

    def clean(self):
        """Validate the lv_size."""
        cleaned_data = super().clean()
        lv_size = self.get_lv_size()
        if lv_size is not None:
            root_size = self.get_root_size()
            if root_size is None:
                root_size = (
                    self.boot_disk.size
                    - EFI_PARTITION_SIZE
                    - self.get_boot_size()
                )
            if is_percentage(lv_size):
                lv_size = calculate_size_from_percentage(root_size, lv_size)
            if lv_size < MIN_ROOT_PARTITION_SIZE:
                set_form_error(
                    self,
                    "lv_size",
                    "Size is too small. Minimum size is %s."
                    % MIN_ROOT_PARTITION_SIZE,
                )
            if lv_size > root_size:
                set_form_error(
                    self,
                    "lv_size",
                    "Size is too large. Maximum size is %s." % root_size,
                )
            cleaned_data["lv_size"] = lv_size
        return cleaned_data

    def configure_storage(self, allow_fallback):
        """Create the LVM configuration."""
        from maasserver.models.filesystem import Filesystem
        from maasserver.models.filesystemgroup import VolumeGroup

        root_partition, root_partition_table = self.create_basic_layout()

        # Add extra partitions if MBR and extra space.
        partitions = [root_partition]
        if root_partition_table.table_type == PARTITION_TABLE_TYPE.MBR:
            available_size = root_partition_table.get_available_size()
            while available_size > MIN_PARTITION_SIZE:
                part = root_partition_table.add_partition()
                partitions.append(part)
                available_size -= part.size

        # Create the volume group and logical volume.
        volume_group = VolumeGroup.objects.create_volume_group(
            self.get_vg_name(), block_devices=[], partitions=partitions
        )
        logical_volume = volume_group.create_logical_volume(
            self.get_lv_name(), self.get_calculated_lv_size(volume_group)
        )
        Filesystem.objects.create(
            node_config_id=self.node.current_config_id,
            block_device=logical_volume,
            fstype=FILESYSTEM_TYPE.EXT4,
            label="root",
            mount_point="/",
        )
        return self.name

    def is_layout(self):
        """Checks if the node is using an LVM layout."""
        for bd in self.block_devices:
            pt = bd.get_partitiontable()
            if pt is None:
                continue
            for partition in pt.partitions.all():
                # On UEFI systems the first partition is for the bootloader. If
                # found check the next partition.
                if partition.index == 1 and self.is_uefi_partition(partition):
                    continue
                # Most layouts allow you to define a boot partition, skip it
                # if its defined.
                if self.is_boot_partition(partition):
                    continue
                # Check if the partition is an LVM PV.
                fs = partition.get_effective_filesystem()
                if fs is None:
                    break
                if fs.fstype != FILESYSTEM_TYPE.LVM_PV:
                    break
                fsg = fs.filesystem_group
                if fsg is None:
                    break
                # Don't use querysets here incase the given data has already
                # been cached.
                if len(fsg.virtual_devices.all()) == 0:
                    break
                # self.configure() always puts the LV as the first device.
                vbd = fsg.virtual_devices.all()[0]
                vfs = vbd.get_effective_filesystem()
                if vfs is None:
                    break
                if vfs.fstype != FILESYSTEM_TYPE.EXT4:
                    break
                if vfs.label != "root":
                    break
                if vfs.mount_point != "/":
                    break
                return bd
        return None


class BcacheStorageLayout(FlatStorageLayout):
    """Bcache layout.

    NAME        SIZE        TYPE    FSTYPE         MOUNTPOINT
    sda         100G        disk
      sda1      512M        part    fat32          /boot/efi
      sda2      99.5G       part    bc-backing
    sdb         50G         disk
      sdb1      50G         part    bc-cache
    bcache0     99.5G       disk    ext4           /
    """

    name = "bcache"
    title = "Bcache layout"

    DEFAULT_CACHE_MODE = CACHE_MODE_TYPE.WRITETHROUGH

    cache_mode = forms.ChoiceField(
        choices=CACHE_MODE_TYPE_CHOICES, required=False
    )
    cache_size = BytesOrPercentageField(required=False)
    cache_no_part = forms.BooleanField(required=False)

    def __init__(self, node, params: dict = None):
        super().__init__(node, params=({} if params is None else params))
        self.setup_cache_device_field()

    def setup_cache_device_field(self):
        """Setup the possible cache devices."""
        if self.boot_disk is None:
            return
        choices = [
            (block_device.id, block_device.id)
            for block_device in self.block_devices
            if block_device != self.boot_disk
        ]
        invalid_choice_message = compose_invalid_choice_text(
            "cache_device", choices
        )
        self.fields["cache_device"] = forms.ChoiceField(
            choices=choices,
            required=False,
            error_messages={"invalid_choice": invalid_choice_message},
        )

    def _find_best_cache_device(self):
        """Return the best possible cache device on the node."""
        if self.boot_disk is None:
            return None
        block_devices = self.node.physicalblockdevice_set.exclude(
            id__in=[self.boot_disk.id]
        ).order_by("size")
        for block_device in block_devices:
            if "ssd" in block_device.tags:
                return block_device
        return None

    def get_cache_device(self):
        """Return the device to use for cache."""
        # Return the requested cache device.
        if self.cleaned_data.get("cache_device"):
            for block_device in self.block_devices:
                if block_device.id == self.cleaned_data["cache_device"]:
                    return block_device
        # Return the best bcache device.
        return self._find_best_cache_device()

    def get_cache_mode(self):
        """Get the cache mode.

        Return of None means to expand the entire cache device.
        """
        if self.cleaned_data.get("cache_mode"):
            return self.cleaned_data["cache_mode"]
        else:
            return self.DEFAULT_CACHE_MODE

    def get_cache_size(self):
        """Get the size of the cache partition.

        Return of None means to expand the entire cache device.
        """
        if self.cleaned_data.get("cache_size"):
            return self.cleaned_data["cache_size"]
        else:
            return None

    def get_cache_no_part(self):
        """Return true if use full cache device without partition."""
        return self.cleaned_data["cache_no_part"]

    def create_cache_set(self):
        """Create the cache set based on the provided options."""
        # Circular imports.
        from maasserver.models.partitiontable import PartitionTable

        cache_block_device = self.get_cache_device()
        cache_no_part = self.get_cache_no_part()
        if cache_no_part:
            return CacheSet.objects.get_or_create_cache_set_for_block_device(
                cache_block_device
            )
        else:
            cache_partition_table = PartitionTable.objects.create(
                block_device=cache_block_device
            )
            cache_partition = cache_partition_table.add_partition(
                size=self.get_cache_size()
            )
            return CacheSet.objects.get_or_create_cache_set_for_partition(
                cache_partition
            )

    def clean(self):
        # Circular imports.
        from maasserver.models.blockdevice import MIN_BLOCK_DEVICE_SIZE

        cleaned_data = super().clean()
        cache_device = self.get_cache_device()
        cache_size = self.get_cache_size()
        cache_no_part = self.get_cache_no_part()
        if cache_size is not None and cache_no_part:
            error_msg = (
                "Cannot use cache_size and cache_no_part at the same time."
            )
            set_form_error(self, "cache_size", error_msg)
            set_form_error(self, "cache_no_part", error_msg)
        elif cache_device is not None and cache_size is not None:
            if is_percentage(cache_size):
                cache_size = calculate_size_from_percentage(
                    cache_device.size, cache_size
                )
            if cache_size < MIN_BLOCK_DEVICE_SIZE:
                set_form_error(
                    self,
                    "cache_size",
                    "Size is too small. Minimum size is %s."
                    % MIN_BLOCK_DEVICE_SIZE,
                )
            if cache_size > cache_device.size:
                set_form_error(
                    self,
                    "cache_size",
                    "Size is too large. Maximum size is %s."
                    % (cache_device.size),
                )
            cleaned_data["cache_size"] = cache_size
        return cleaned_data

    def configure_storage(self, allow_fallback):
        """Create the Bcache configuration."""
        # Circular imports.
        from maasserver.models.filesystem import Filesystem
        from maasserver.models.filesystemgroup import Bcache

        cache_block_device = self.get_cache_device()
        if cache_block_device is None:
            if allow_fallback:
                # No cache device so just configure using the flat layout.
                return super().configure_storage(allow_fallback)
            else:
                raise StorageLayoutError(
                    "Node doesn't have an available cache device to "
                    "setup bcache."
                )

        boot_size = self.get_boot_size()
        if boot_size == 0:
            boot_size = 1 * 1024**3
        root_partition, _ = self.create_basic_layout(boot_size=boot_size)
        cache_set = self.create_cache_set()
        bcache = Bcache.objects.create_bcache(
            cache_mode=self.get_cache_mode(),
            cache_set=cache_set,
            backing_partition=root_partition,
        )
        Filesystem.objects.create(
            node_config_id=self.node.current_config_id,
            block_device=bcache.virtual_device,
            fstype=FILESYSTEM_TYPE.EXT4,
            label="root",
            mount_point="/",
        )
        return self.name

    def is_layout(self):
        """Checks if the node is using a Bcache layout."""
        for bd in self.block_devices:
            pt = bd.get_partitiontable()
            if pt is None:
                continue
            found_boot = False
            ordered_partitions = sorted(
                pt.partitions.all(), key=lambda part: part.id
            )
            for partition in ordered_partitions:
                # On UEFI systems the first partition is for the bootloader. If
                # found check the next partition.
                if partition.index == 1 and self.is_uefi_partition(partition):
                    continue
                # Bcache always has a boot partition. Keep searching until its
                # found.
                if self.is_boot_partition(partition):
                    found_boot = True
                    continue
                elif not found_boot:
                    continue
                # Check if the partition is Bcache backing
                fs = partition.get_effective_filesystem()
                if fs is None:
                    break
                if fs.fstype != FILESYSTEM_TYPE.BCACHE_BACKING:
                    break
                fsg = fs.filesystem_group
                if fsg is None:
                    break
                # Don't use querysets here incase the given data has already
                # been cached.
                if len(fsg.virtual_devices.all()) == 0:
                    break
                # self.configure() always uses the first virtual device for
                # the EXT4 filesystem.
                vbd = fsg.virtual_devices.all()[0]
                vfs = vbd.get_effective_filesystem()
                if vfs is None:
                    break
                if vfs.fstype != FILESYSTEM_TYPE.EXT4:
                    break
                if vfs.label != "root":
                    break
                if vfs.mount_point != "/":
                    break
                return bd
        return None


class VMFS6StorageLayout(StorageLayoutBase):
    """VMFS6 layout.

    The VMware ESXi 6+ image is a DD. The image has 8 partitions which are
    *not* in order. Users may only change the last partition which is partition
    3 and stored at the end of the disk.

    NAME                PARTITION   SIZE      START BLOCK   END BLOCK
    EFI System          1           3MB       0             3
    Basic Data          5           249MB     4             253
    Basic Data          6           249MB     254           503
    VMware Diagnostic   7           109MB     504           613
    Basic Data          8           285MB     614           899
    VMware Diagnostic   9           2.5GB     900           3459
    Basic Data          2           4GB       3460          7554
    VMFS                3           Remaining 7555          End of disk
    """

    name = "vmfs6"
    title = "VMFS6 layout"

    _default_layout = "default"

    base_partitions = {
        "default": [
            # EFI System
            {"index": 1, "size": 3 * 1024**2, "bootable": True},
            # Basic Data
            {"index": 2, "size": 4 * 1024**3},
            # VMFS Datastore, size is 0 so the partition order is correct, its
            # fixed after everything is applied.
            {"index": 3, "size": 0},
            # Basic Data
            {"index": 5, "size": 249 * 1024**2},
            # Basic Data
            {"index": 6, "size": 249 * 1024**2},
            # VMKCore Diagnostic
            {"index": 7, "size": 109 * 1024**2},
            # Basic Data
            {"index": 8, "size": 285 * 1024**2},
            # VMKCore Diagnostic
            {"index": 9, "size": 2560 * 1024**2},
        ],
    }

    def _clean_boot_disk(self):
        if self.boot_disk.size < (10 * 1024**3):
            set_form_error(
                self, "boot_size", "Boot disk must be at least 10Gb."
            )

    def clean(self):
        cleaned_data = super().clean()
        self._clean_boot_disk()
        return cleaned_data

    def configure_storage(self, allow_fallback):
        # Circular imports.
        from maasserver.models import VMFS
        from maasserver.models.partition import Partition
        from maasserver.models.partitiontable import PartitionTable

        boot_partition_table = PartitionTable.objects.create(
            block_device=self.get_root_device(),
            table_type=PARTITION_TABLE_TYPE.GPT,
        )
        now = timezone.now()
        # The model rounds partition sizes for performance and has a min size
        # of 4MB. VMware ESXi does not conform to these constraints so add each
        # partition directly to get around the model. VMware ESXi always uses
        # the same UUIDs which is a constraint set at database level we can't
        # get around so leave them unset.
        # See https://kb.vmware.com/s/article/1036609
        Partition.objects.bulk_create(
            [
                Partition(
                    partition_table=boot_partition_table,
                    created=now,
                    updated=now,
                    **partition,
                )
                for partition in self.base_partitions[self._default_layout]
            ]
        )
        vmfs_part = boot_partition_table.partitions.get(size=0)
        root_size = self.get_root_size()
        if root_size is not None:
            vmfs_part.size = root_size
        else:
            vmfs_part.size = boot_partition_table.get_available_size()
        vmfs_part.save()
        # datastore1 is the default name VMware uses.
        VMFS.objects.create_vmfs(name="datastore1", partitions=[vmfs_part])
        return self.name

    def is_layout(self):
        """Checks if the node is using a VMFS6 layout."""
        for bd in self.block_devices:
            pt = bd.get_partitiontable()
            if pt is None:
                continue
            if pt.table_type != PARTITION_TABLE_TYPE.GPT:
                continue
            partitions = sorted(pt.partitions.all(), key=attrgetter("id"))
            for layout in self.base_partitions.values():
                if len(partitions) < len(layout):
                    continue
                for i, (partition, base_partition) in enumerate(
                    zip(partitions, layout)
                ):
                    if (i + 1) == len(layout):
                        return bd
                    if partition.bootable != base_partition.get(
                        "bootable", False
                    ):
                        break
                    # Skip checking the size of the Datastore partition as that
                    # changes based on available disk size/user input.
                    if base_partition["size"] == 0:
                        continue
                    if partition.size != base_partition["size"]:
                        break
        return None

    @property
    def last_base_partition_index(self):
        return self.base_partitions[self._default_layout][-1]["index"]


class VMFS7StorageLayout(VMFS6StorageLayout):
    """VMFS7 layout.

    The VMware ESXi 7+ image is a DD. The image has 5 partitions which are
    in order but not linear. Users may only change the last partition which
    is partition 8 and stored at the end of the disk. In recent ESXi 7 ISOs
    and version 8 onwards, the 32GB minimum disk size is being enforced,
    so the Packer template has been updated.

    NAME                PARTITION   SIZE
    EFI System          1           100MB
    Basic Data          5           4GB
    Basic Data          6           4GB
    VMFSL               7           23.9GB
    VMFS                8           Remaining
    """

    name = "vmfs7"
    title = "VMFS7 layout"

    base_partitions = {
        "default": [
            # EFI System
            {"index": 1, "size": 100 * 1024**2, "bootable": True},
            # Basic Data
            {"index": 5, "size": 4095 * 1024**2},
            # Basic Data
            {"index": 6, "size": 4095 * 1024**2},
            # VMFSL
            {"index": 7, "size": 25662832128},
            # VMFS
            {"index": 8, "size": 0},
        ],
        "legacy": [
            # EFI System
            {"index": 1, "size": 105 * 1024**2, "bootable": True},
            # Basic Data
            {"index": 5, "size": 1074 * 1024**2},
            # Basic Data
            {"index": 6, "size": 1074 * 1024**2},
            # VMFSL
            {"index": 7, "size": 8704 * 1024**2},
            # VMFS
            {"index": 8, "size": 0},
        ],
    }

    def _clean_boot_disk(self):
        """https://docs.vmware.com/en/VMware-vSphere/7.0/com.vmware.esxi.install.doc/GUID-DEB8086A-306B-4239-BF76-E354679202FC.html

        ESXi 7.0 requires a boot disk of at least 32 GB of persistent
        storage such as HDD, SSD, or NVMe. Use USB, SD and non-USB
        flash media devices only for ESXi boot bank partitions. A boot
        device must not be shared between ESXi hosts.
        """
        if self.boot_disk.size < (32 * 1024**3):
            set_form_error(
                self, "boot_size", "Boot disk must be at least 32Gb."
            )

    @property
    def last_base_partition_index(self):
        # VMFS partition can be modified by the user
        return self.base_partitions[self._default_layout][-2]["index"]


class CustomStorageLayout(StorageLayoutBase):
    """Layout from custom commissioning data."""

    name = "custom"
    title = "Custom layout (from commissioning storage config)"

    def configure_storage(self, allow_fallback):
        from maasserver.storage_custom import (
            apply_layout_to_machine,
            ConfigError,
            get_storage_layout,
            UnappliableLayout,
        )

        data = self.node.get_commissioning_resources()
        if not data or "storage-extra" not in data:
            raise StorageLayoutError(
                "No custom storage layout configuration found"
            )

        try:
            layout = get_storage_layout(data["storage-extra"])
            apply_layout_to_machine(layout, self.node)
        except (ConfigError, UnappliableLayout) as e:
            raise StorageLayoutError(f"Failed to apply storage layout: {e}")  # noqa: B904
        return self.name

    def is_layout(self):
        # XXX we can't really detect if the layout is currently applied as it
        # depends on the provided config. It doesn't really matter though as
        # it's mostly used for the VMFS case. We should eventually get rid of
        # it entirely.
        return None


class BlankStorageLayout(StorageLayoutBase):
    """Blank layout.

    This layout ensures no disk is configured with any partition table or
    filesystem. This helps users who want to have a custom storage layout
    not based on any existing layout.
    """

    name = "blank"
    title = "No storage (blank) layout"

    def configure_storage(self, allow_fallback):
        # StorageLayoutBase has the code to ensure nothing is configured.
        # Once that is done there is nothing left for us to do.
        return self.name

    def is_layout(self):
        """Checks if the node is using a blank layout."""
        for bd in self.block_devices:
            if len(bd.filesystem_set.all()) != 0:
                return None
            if len(bd.partitiontable_set.all()) != 0:
                return None
        # The blank layout is applied to every storage device so return
        # the boot disk.
        return self.boot_disk


# All available layouts
STORAGE_LAYOUTS = frozenset(
    [
        BcacheStorageLayout,
        BlankStorageLayout,
        CustomStorageLayout,
        FlatStorageLayout,
        LVMStorageLayout,
        VMFS6StorageLayout,
        VMFS7StorageLayout,
    ]
)
STORAGE_LAYOUT_CHOICES = [
    (layout.name, layout.title) for layout in STORAGE_LAYOUTS
]


def get_storage_layout_for_node(name, node, params: dict = None):
    """Get the storage layout object from its name."""
    for layout in STORAGE_LAYOUTS:
        if layout.name == name:
            return layout(node, params=params or {})
    return None


def get_applied_storage_layout_for_node(node):
    """Returns the detected storage layout on the node."""
    for layout_class in STORAGE_LAYOUTS:
        layout = layout_class(node)
        bd = layout.is_layout()
        if bd is not None:
            return bd, layout.name
    return None, "unknown"


class StorageLayoutForm(Form):
    """Form to validate the `storage_layout` parameter."""

    def __init__(self, *args, **kwargs):
        required = kwargs.pop("required", False)
        super().__init__(*args, **kwargs)
        self.setup_field(required=required)

    def setup_field(self, required=False):
        invalid_choice_message = compose_invalid_choice_text(
            "storage_layout", STORAGE_LAYOUT_CHOICES
        )
        self.fields["storage_layout"] = forms.ChoiceField(
            choices=STORAGE_LAYOUT_CHOICES,
            required=required,
            error_messages={"invalid_choice": invalid_choice_message},
        )
