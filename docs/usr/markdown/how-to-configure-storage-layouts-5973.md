> *Errors or typos? Topics missing? Hard to read? <a href="https://docs.google.com/forms/d/e/1FAIpQLScIt3ffetkaKW3gDv6FDk7CfUTNYP_HGmqQotSTtj2htKkVBw/viewform?usp=pp_url&entry.1739714854=https://maas.io/docs/configuring-storage-layouts" target = "_blank">Let us know.</a>*

MAAS supports multiple storage layouts, including options for non-UEFI-compatible systems.

## Flat layout

The Flat layout means one partition takes up the whole boot disk, formatted with ext4 and mounted at the root (`/`).

| Name  | Size       | Type | Filesystem | Mount point |
|-------|------------|------|------------|-------------|
| sda   | -          | disk | -          | -           |
| sda1  | 512 MB     | part | FAT32      | /boot/efi   |
| sda2  | rest of sda| part | ext4       | /           |

**Options:**

- **boot_size**: Sets the size of the boot partition. Default is zero, putting `/boot` on the root filesystem.
- **root_device**: The block device for the root partition. Usually the boot disk.
- **root_size**: Root partition size, 100% by default.

## LVM layout

LVM (Logical Volume Management) offers flexibility. A volume group `vgroot` covers a partition on the boot disk, wrapping logical volume `lvroot`.

| Name  | Size        | Type  | Filesystem     | Mount point |
|-------|-------------|-------|----------------|-------------|
| sda   | -           | disk  | -              | -           |
| sda1  | 512 MB      | part  | FAT32          | /boot/efi   |
| sda2  | rest of sda | part  | lvm-pv(vgroot) | -           |
| lvroot| rest of sda | lvm   | ext4           | /           |

**Options:**

- **vg_name**: Customise volume group's name.
- **lv_name**: Personalise logical volume's name.
- **lv_size**: Set the size, defaulting to the entire volume group.

## bcache layout

For better disk performance, the bcache layout uses the boot disk as the backing device and an SSD as the cache.

| Name   | Size        | Type      | Filesystem | Mount point |
|--------|-------------|-----------|------------|-------------|
| sda    | -           | disk      | -          | -           |
| sda1   | 512 MB      | part      | FAT32      | /boot/efi   |
| sda2   | rest of sda | part      | bc-backing | -           |
| sdb(ssd)| -          | disk      | -          | -           |
| sdb1   | 100% of sdb | part      | bc-cache   | -           |
| bcache0| per sda2    | disk      | ext4       | /           |

**Options:**

- **cache_device**: Opt for cache device, defaulting to the smallest SSD.
- **cache_mode**: Adjust the cache mode; `writethrough` is standard.
- **cache_size**: Define cache partition size.
- **cache_no_part**: Decide on partition creation for the cache device.

## VMFS6 layout

For VMware ESXi deployments, VMFS6 is the required layout, automating both OS and datastore configurations.

| Name  | Size        | Type       | Use                |
|-------|-------------|------------|--------------------|
| sda   | -           | disk       | -                  |
| sda1  | 3 MB        | part       | EFI                |
| sda2  | 4 GB        | part       | Basic Data         |
| sda3  | Remaining   | part       | VMFS Datastore 1   |

**Options:**

- **root_size**: Sets the default VMFS Datastore size, generally the remaining disk space.

## Blank layout

The Blank layout clears all, making way for custom configurations. It leaves the system un-deployable until you manually configure storage.

> Machines with this layout need manual storage configuration before deployment.

