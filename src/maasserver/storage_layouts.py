# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Storage layouts."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    ]

from django import forms
from django.core.exceptions import ValidationError
from django.forms import Form
from maasserver.enum import (
    CACHE_MODE_TYPE,
    CACHE_MODE_TYPE_CHOICES,
    FILESYSTEM_TYPE,
    PARTITION_TABLE_TYPE,
)
from maasserver.exceptions import MAASAPIValidationError
from maasserver.fields_storage import (
    BytesOrPrecentageField,
    calculate_size_from_precentage,
    is_precentage,
)
from maasserver.utils.forms import (
    compose_invalid_choice_text,
    set_form_error,
)


EFI_PARTITION_SIZE = 512 * 1024 * 1024  # 512 MiB
MIN_BOOT_PARTITION_SIZE = 512 * 1024 * 1024  # 512 GiB
MIN_ROOT_PARTITION_SIZE = 3 * 1024 * 1024 * 1024  # 3 GiB


class StorageLayoutError(Exception):
    """Error raised when layout cannot be used on node."""


class StorageLayoutMissingBootDiskError(StorageLayoutError):
    """Error raised when a node is missing a boot disk to configure."""


class StorageLayoutFieldsError(MAASAPIValidationError):
    """Error raised when fields from a storage layout are invalid."""


class StorageLayoutBase(Form):
    """Base class all storage layouts extend from."""

    boot_size = BytesOrPrecentageField(required=False)
    root_size = BytesOrPrecentageField(required=False)

    def __init__(self, node, params={}):
        super(StorageLayoutBase, self).__init__(data=params)
        self.node = node
        self.block_devices = self._load_physical_block_devices()
        self.boot_disk = node.get_boot_disk()
        self.setup_root_device_field()

    def _load_physical_block_devices(self):
        """Load all the `PhysicalBlockDevice`'s for node."""
        return list(self.node.physicalblockdevice_set.order_by('id').all())

    def setup_root_device_field(self):
        """Setup the possible root devices."""
        choices = [
            (block_device.id, block_device.id)
            for block_device in self.block_devices
        ]
        invalid_choice_message = compose_invalid_choice_text(
            'root_device', choices)
        self.fields['root_device'] = forms.ChoiceField(
            choices=choices, required=False,
            error_messages={'invalid_choice': invalid_choice_message})

    def _clean_size(self, field, min_size=None, max_size=None):
        """Clean a size field."""
        size = self.cleaned_data[field]
        if size is None:
            return None
        if is_precentage(size):
            # Calculate the precentage not counting the EFI partition.
            size = calculate_size_from_precentage(
                self.boot_disk.size - EFI_PARTITION_SIZE, size)
        if min_size is not None and size < min_size:
            raise ValidationError(
                "Size is too small. Minimum size is %s." % min_size)
        if max_size is not None and size > max_size:
            raise ValidationError(
                "Size is too large. Maximum size is %s." % max_size)
        return size

    def clean_boot_size(self):
        """Clean the boot_size field."""
        if self.boot_disk is not None:
            return self._clean_size(
                'boot_size', MIN_BOOT_PARTITION_SIZE, (
                    self.boot_disk.size - EFI_PARTITION_SIZE -
                    MIN_ROOT_PARTITION_SIZE))
        else:
            return None

    def clean_root_size(self):
        """Clean the root_size field."""
        if self.boot_disk is not None:
            return self._clean_size(
                'root_size', MIN_ROOT_PARTITION_SIZE, (
                    self.boot_disk.size - EFI_PARTITION_SIZE -
                    MIN_BOOT_PARTITION_SIZE))
        else:
            return None

    def clean(self):
        """Validate the data."""
        cleaned_data = super(StorageLayoutBase, self).clean()
        if len(self.block_devices) == 0:
            raise StorageLayoutMissingBootDiskError(
                "Node doesn't have any storage devices to configure.")
        disk_size = self.boot_disk.size
        total_size = (
            EFI_PARTITION_SIZE + self.get_boot_size())
        root_size = self.get_root_size()
        if root_size is not None and total_size + root_size > disk_size:
            raise ValidationError(
                "Size of the boot partition and root partition are larger "
                "than the available space on the boot disk.")
        return cleaned_data

    def get_root_device(self):
        """Get the device that should be the root partition.

        Return of None means to use the boot disk.
        """
        if self.cleaned_data.get('root_device'):
            root_id = self.cleaned_data['root_device']
            return self.node.physicalblockdevice_set.get(id=root_id)
        else:
            return None

    def get_boot_size(self):
        """Get the size of the boot partition."""
        if self.cleaned_data.get('boot_size'):
            return self.cleaned_data['boot_size']
        else:
            return 0

    def get_root_size(self):
        """Get the size of the root partition.

        Return of None means to expand the remaining of the disk.
        """
        if self.cleaned_data.get('root_size'):
            return self.cleaned_data['root_size']
        else:
            return None

    def create_basic_layout(self):
        """Create the basic layout that is similar for all layout types.

        :return: The created root partition.
        """
        # Circular imports.
        from maasserver.models.filesystem import Filesystem
        from maasserver.models.partitiontable import PartitionTable
        boot_partition_table = PartitionTable.objects.create(
            block_device=self.boot_disk)
        if boot_partition_table.table_type == PARTITION_TABLE_TYPE.GPT:
            efi_partition = boot_partition_table.add_partition(
                size=EFI_PARTITION_SIZE, bootable=True)
            Filesystem.objects.create(
                partition=efi_partition,
                fstype=FILESYSTEM_TYPE.FAT32,
                label="efi",
                mount_point="/boot/efi")
        boot_size = self.get_boot_size()
        if boot_size > 0:
            boot_partition = boot_partition_table.add_partition(
                size=self.get_boot_size(), bootable=True)
            Filesystem.objects.create(
                partition=boot_partition,
                fstype=FILESYSTEM_TYPE.EXT4,
                label="boot",
                mount_point="/boot")
        root_device = self.get_root_device()
        if root_device is None or root_device == self.boot_disk:
            root_partition = boot_partition_table.add_partition(
                size=self.get_root_size())
        else:
            root_partition_table = PartitionTable.objects.create(
                block_device=root_device)
            root_partition = root_partition_table.add_partition(
                size=self.get_root_size())
        return root_partition

    def configure(self, allow_fallback=True):
        """Configure the storage for the node."""
        if not self.is_valid():
            raise StorageLayoutFieldsError(self.errors)
        self.node._clear_storage_configuration()
        return self.configure_storage(allow_fallback)

    def configure_storage(self, allow_fallback):
        """Configure the storage of the node.

        Sub-classes should override this method not `configure`.
        """
        raise NotImplementedError()


class FlatStorageLayout(StorageLayoutBase):
    """Flat layout.

    NAME        SIZE        TYPE    FSTYPE         MOUNTPOINT
    sda         100G        disk
      sda15     512M        part    fat32          /boot/efi
      sda1      1G          part    ext4           /boot
      sda2      98.5G       part    ext4           /
    """

    def configure_storage(self, allow_fallback):
        """Create the flat configuration."""
        # Circular imports.
        from maasserver.models.filesystem import Filesystem
        root_partition = self.create_basic_layout()
        Filesystem.objects.create(
            partition=root_partition,
            fstype=FILESYSTEM_TYPE.EXT4,
            label="root",
            mount_point="/")
        return "flat"


class LVMStorageLayout(StorageLayoutBase):
    """LVM layout.

    NAME        SIZE        TYPE    FSTYPE         MOUNTPOINT
    sda         100G        disk
      sda15     512M        part    fat32          /boot/efi
      sda1      1G          part    ext4           /boot
      sda2      98.5G       part    lvm-pv(vgroot)
    vgroot      98.5G       lvm
      lvroot    98.5G       lvm     ext4           /
    """

    DEFAULT_VG_NAME = "vgroot"
    DEFAULT_LV_NAME = "lvroot"

    vg_name = forms.CharField(required=False)
    lv_name = forms.CharField(required=False)
    lv_size = BytesOrPrecentageField(required=False)

    def get_vg_name(self):
        """Get the name of the volume group."""
        if self.cleaned_data.get('vg_name'):
            return self.cleaned_data['vg_name']
        else:
            return self.DEFAULT_VG_NAME

    def get_lv_name(self):
        """Get the name of the logical volume."""
        if self.cleaned_data.get('lv_name'):
            return self.cleaned_data['lv_name']
        else:
            return self.DEFAULT_LV_NAME

    def get_lv_size(self):
        """Get the size of the logical volume.

        Return of None means to expand the entire volume group.
        """
        if self.cleaned_data.get('lv_size'):
            return self.cleaned_data['lv_size']
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
        cleaned_data = super(LVMStorageLayout, self).clean()
        lv_size = self.get_lv_size()
        if lv_size is not None:
            root_size = self.get_root_size()
            if root_size is None:
                root_size = (
                    self.boot_disk.size - EFI_PARTITION_SIZE -
                    self.get_boot_size())
            if is_precentage(lv_size):
                lv_size = calculate_size_from_precentage(
                    root_size, lv_size)
            if lv_size < MIN_ROOT_PARTITION_SIZE:
                set_form_error(
                    self, "lv_size",
                    "Size is too small. Minimum size is %s." % (
                        MIN_ROOT_PARTITION_SIZE))
            if lv_size > root_size:
                set_form_error(
                    self, "lv_size",
                    "Size is too large. Maximum size is %s." % root_size)
            cleaned_data['lv_size'] = lv_size
        return cleaned_data

    def configure_storage(self, allow_fallback):
        """Create the LVM configuration."""
        # Circular imports.
        from maasserver.models.filesystem import Filesystem
        from maasserver.models.filesystemgroup import VolumeGroup
        root_partition = self.create_basic_layout()
        volume_group = VolumeGroup.objects.create_volume_group(
            self.get_vg_name(), block_devices=[], partitions=[root_partition])
        logical_volume = volume_group.create_logical_volume(
            self.get_lv_name(), self.get_calculated_lv_size(volume_group))
        Filesystem.objects.create(
            block_device=logical_volume,
            fstype=FILESYSTEM_TYPE.EXT4,
            label="root",
            mount_point="/")
        return "lvm"


class BcacheStorageLayoutBase(StorageLayoutBase):
    """Base that provides the logic for bcache layout types.

    This class is shared by `BcacheStorageLayout` and `BcacheLVMStorageLayout`.
    """

    DEFAULT_CACHE_MODE = CACHE_MODE_TYPE.WRITETHROUGH

    cache_mode = forms.ChoiceField(
        choices=CACHE_MODE_TYPE_CHOICES, required=False)
    cache_size = BytesOrPrecentageField(required=False)
    cache_no_part = forms.BooleanField(required=False)

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
            'cache_device', choices)
        self.fields['cache_device'] = forms.ChoiceField(
            choices=choices, required=False,
            error_messages={'invalid_choice': invalid_choice_message})

    def _find_best_cache_device(self):
        """Return the best possible cache device on the node."""
        if self.boot_disk is None:
            return None
        block_devices = self.node.physicalblockdevice_set.exclude(
            id__in=[self.boot_disk.id]).order_by('size')
        for block_device in block_devices:
            if "ssd" in block_device.tags:
                return block_device
        return None

    def get_cache_device(self):
        """Return the device to use for cache."""
        # Return the requested cache device.
        if self.cleaned_data.get('cache_device'):
            for block_device in self.block_devices:
                if block_device.id == self.cleaned_data['cache_device']:
                    return block_device
        # Return the best bcache device.
        return self._find_best_cache_device()

    def get_cache_mode(self):
        """Get the cache mode.

        Return of None means to expand the entire cache device.
        """
        if self.cleaned_data.get('cache_mode'):
            return self.cleaned_data['cache_mode']
        else:
            return self.DEFAULT_CACHE_MODE

    def get_cache_size(self):
        """Get the size of the cache partition.

        Return of None means to expand the entire cache device.
        """
        if self.cleaned_data.get('cache_size'):
            return self.cleaned_data['cache_size']
        else:
            return None

    def get_cache_no_part(self):
        """Return true if use full cache device without partition."""
        return self.cleaned_data['cache_no_part']

    def create_cache_device(self):
        """Create the cache device based on the provided options."""
        # Circular imports.
        from maasserver.models.partitiontable import PartitionTable
        cache_block_device = self.get_cache_device()
        cache_no_part = self.get_cache_no_part()
        if cache_no_part:
            cache_device = cache_block_device
        else:
            cache_partition_table = PartitionTable.objects.create(
                block_device=cache_block_device)
            cache_device = cache_partition_table.add_partition(
                size=self.get_cache_size())
        return cache_device

    def clean(self):
        # Circular imports.
        from maasserver.models.blockdevice import MIN_BLOCK_DEVICE_SIZE
        cleaned_data = super(BcacheStorageLayoutBase, self).clean()
        cache_device = self.get_cache_device()
        cache_size = self.get_cache_size()
        cache_no_part = self.get_cache_no_part()
        if cache_size is not None and cache_no_part:
            error_msg = (
                "Cannot use cache_size and cache_no_part at the same time.")
            set_form_error(self, "cache_size", error_msg)
            set_form_error(self, "cache_no_part", error_msg)
        elif cache_device is not None and cache_size is not None:
            if is_precentage(cache_size):
                cache_size = calculate_size_from_precentage(
                    cache_device.size, cache_size)
            if cache_size < MIN_BLOCK_DEVICE_SIZE:
                set_form_error(
                    self, "cache_size",
                    "Size is too small. Minimum size is %s." % (
                        MIN_BLOCK_DEVICE_SIZE))
            if cache_size > cache_device.size:
                set_form_error(
                    self, "cache_size",
                    "Size is too large. Maximum size is %s." % (
                        cache_device.size))
            cleaned_data['cache_size'] = cache_size
        return cleaned_data


class BcacheStorageLayout(FlatStorageLayout, BcacheStorageLayoutBase):
    """Bcache layout.

    NAME        SIZE        TYPE    FSTYPE         MOUNTPOINT
    sda         100G        disk
      sda15     512M        part    fat32          /boot/efi
      sda1      1G          part    ext4           /boot
      sda2      98.5G       part    bc-backing
    sdb         50G         disk
      sdb1      50G         part    bc-cache
    bcache0     98.5G       disk    ext4           /
    """

    def __init__(self, node, params={}):
        super(BcacheStorageLayout, self).__init__(node, params=params)
        self.setup_cache_device_field()

    def configure_storage(self, allow_fallback):
        """Create the Bcache configuration."""
        # Circular imports.
        from maasserver.models.filesystem import Filesystem
        from maasserver.models.filesystemgroup import Bcache
        cache_block_device = self.get_cache_device()
        if cache_block_device is None:
            if allow_fallback:
                # No cache device so just configure using the flat layout.
                return super(BcacheStorageLayout, self).configure_storage(
                    allow_fallback)
            else:
                raise StorageLayoutError(
                    "Node doesn't have an available cache device to "
                    "setup bcache.")

        root_partition = self.create_basic_layout()
        cache_device = self.create_cache_device()
        create_kwargs = {
            "backing_partition": root_partition,
            "cache_mode": self.get_cache_mode(),
        }
        if cache_device.type == "partition":
            create_kwargs['cache_partition'] = cache_device
        else:
            create_kwargs['cache_device'] = cache_device
        bcache = Bcache.objects.create_bcache(**create_kwargs)
        Filesystem.objects.create(
            block_device=bcache.virtual_device,
            fstype=FILESYSTEM_TYPE.EXT4,
            label="root",
            mount_point="/")
        return "bcache"


# Holds all the storage layouts that can be used.
STORAGE_LAYOUTS = {
    "flat": ("Flat layout", FlatStorageLayout),
    "lvm": ("LVM layout", LVMStorageLayout),
    "bcache": ("Bcache layout", BcacheStorageLayout),
    }


def get_storage_layout_choices():
    """Return the storage layout choices.

    Formatted to work with Django form.
    """
    return [
        (name, title)
        for name, (title, klass) in STORAGE_LAYOUTS.items()
    ]


def get_storage_layout_for_node(name, node, params={}):
    """Get the storage layout object from its name."""
    if name in STORAGE_LAYOUTS:
        return STORAGE_LAYOUTS[name][1](node, params=params)
    else:
        return None


class StorageLayoutForm(Form):
    """Form to validate the `storage_layout` parameter."""

    def __init__(self, *args, **kwargs):
        required = kwargs.pop('required', False)
        super(StorageLayoutForm, self).__init__(*args, **kwargs)
        self.setup_field(required=required)

    def setup_field(self, required=False):
        choices = get_storage_layout_choices()
        invalid_choice_message = compose_invalid_choice_text(
            'storage_layout', choices)
        self.fields['storage_layout'] = forms.ChoiceField(
            choices=choices, required=required,
            error_messages={'invalid_choice': invalid_choice_message})
