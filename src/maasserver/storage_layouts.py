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

from django.core.exceptions import ValidationError
from django.forms import Form
from maasserver.enum import FILESYSTEM_TYPE
from maasserver.exceptions import MAASAPIValidationError
from maasserver.fields_storage import (
    BytesOrPrecentageField,
    calculate_size_from_precentage,
    is_precentage,
)
from maasserver.models.filesystem import Filesystem
from maasserver.models.partitiontable import PartitionTable


EFI_PARTITION_SIZE = 512 * 1024 * 1024  # 512 MiB
MIN_BOOT_PARTITION_SIZE = 512 * 1024 * 1024  # 512 GiB
DEFAULT_BOOT_PARTITION_SIZE = 1 * 1024 * 1024 * 1024  # 1 GiB
MIN_ROOT_PARTITION_SIZE = 3 * 1024 * 1024 * 1024  # 3 GiB


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

    def _load_physical_block_devices(self):
        """Load all the `PhysicalBlockDevice`'s for node."""
        return list(self.node.physicalblockdevice_set.order_by('id').all())

    def get_boot_disk(self):
        """Return the boot disk for the node."""
        if len(self.block_devices) > 0:
            return self.block_devices[0]
        else:
            return None

    def _clean_size(self, field, min_size, max_size):
        """Clean a size field."""
        size = self.cleaned_data[field]
        if size is None:
            return None
        if is_precentage(size):
            # Calculate the precentage not counting the EFI partition.
            size = calculate_size_from_precentage(
                self.get_boot_disk().size - EFI_PARTITION_SIZE, size)
        if size < min_size:
            raise ValidationError(
                "Size is too small. Minimum size is %s." % min_size)
        if size > max_size:
            raise ValidationError(
                "Size is too large. Maximum size is %s." % max_size)
        return size

    def clean_boot_size(self):
        """Clean the boot_size field."""
        boot_disk = self.get_boot_disk()
        if boot_disk is not None:
            return self._clean_size(
                'boot_size', MIN_BOOT_PARTITION_SIZE, (
                    boot_disk.size - EFI_PARTITION_SIZE -
                    MIN_ROOT_PARTITION_SIZE))
        else:
            return None

    def clean_root_size(self):
        """Clean the root_size field."""
        boot_disk = self.get_boot_disk()
        if boot_disk is not None:
            return self._clean_size(
                'root_size', MIN_ROOT_PARTITION_SIZE, (
                    boot_disk.size - EFI_PARTITION_SIZE -
                    MIN_BOOT_PARTITION_SIZE))
        else:
            return None

    def clean(self):
        """Validate the data."""
        cleaned_data = super(StorageLayoutBase, self).clean()
        if len(self.block_devices) == 0:
            raise ValidationError(
                "%s: doesn't have any storage devices to configure." % (
                    self.node.fqdn))
        disk_size = self.get_boot_disk().size
        total_size = (
            EFI_PARTITION_SIZE + self.get_boot_size())
        root_size = self.get_root_size()
        if root_size is not None and total_size + root_size > disk_size:
            raise ValidationError(
                "Size of the boot partition and root partition are larger "
                "than the available space on the boot disk.")
        return cleaned_data

    def get_boot_size(self):
        """Get the size of the boot partition."""
        if self.cleaned_data.get('boot_size'):
            return self.cleaned_data['boot_size']
        else:
            return DEFAULT_BOOT_PARTITION_SIZE

    def get_root_size(self):
        """Get the size of the root partition.

        Return of None means to expand the remaining of the disk.
        """
        if self.cleaned_data.get('root_size'):
            return self.cleaned_data['root_size']
        else:
            return None

    def configure(self):
        """Configure the storage for the node."""
        if not self.is_valid():
            raise StorageLayoutFieldsError(self.errors)
        self.node._clear_storage_configuration()
        self.configure_storage()

    def configure_storage(self):
        """Configure the storage of the node.

        Sub-classes should override this method not `configure`.
        """
        raise NotImplementedError()


class FlatStorageLayout(StorageLayoutBase):
    """Flat layout.

    NAME        SIZE        TYPE    FSTYPE      MOUNTPOINT
    sda         100G        disk
      sda15     512M        part    fat32       /boot/efi
      sda1      1G          part    ext4        /boot
      sda2      98.5G       part    ext4        /
    """

    def configure_storage(self):
        boot_disk = self.get_boot_disk()
        partition_table = PartitionTable.objects.create(
            block_device=boot_disk)
        efi_partition = partition_table.add_partition(
            size=EFI_PARTITION_SIZE, bootable=True, partition_number=15)
        boot_partition = partition_table.add_partition(
            size=self.get_boot_size(), bootable=True, partition_number=1)
        root_partition = partition_table.add_partition(
            size=self.get_root_size(), partition_number=2)
        Filesystem.objects.create(
            partition=efi_partition,
            fstype=FILESYSTEM_TYPE.FAT32,
            label="efi",
            mount_point="/boot/efi")
        Filesystem.objects.create(
            partition=boot_partition,
            fstype=FILESYSTEM_TYPE.EXT4,
            label="boot",
            mount_point="/boot")
        Filesystem.objects.create(
            partition=root_partition,
            fstype=FILESYSTEM_TYPE.EXT4,
            label="root",
            mount_point="/")


# Holds all the storage layouts that can be used.
STORAGE_LAYOUTS = [
    ("flat", "Flat layout", FlatStorageLayout)
    ]


def get_storage_layout_choices():
    """Return the storage layout choices.

    Formatted to work with Django form.
    """
    return [
        (name, title)
        for name, title, klass in STORAGE_LAYOUTS
    ]
