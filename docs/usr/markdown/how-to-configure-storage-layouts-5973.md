
## Cheat sheet
| Layout   | Best for | Key notes |
| Flat | Simple setups, small servers | One root partition, minimal options |
| LVM  | Flexibility & growth | Resize or add volumes later |
| Bcache | Performance boost | Needs SSD for caching, defaults to writethrough |
| VMFS6 | VMware ESXi hosts | Creates OS + VMFS datastore automatically |
| Blank | Custom/manual setups | Wipes disks, must configure storage manually |

MAAS lets you choose different storage layouts when deploying machines.  These layouts affect performance, flexibility, and compatibility (e.g.  UEFI vs. non-UEFI).  Picking the right one ensures deployments succeed and fit your workload.

You can configure layouts when:
- Commissioning a new machine.
- Editing a machine’s storage before deployment.

In the UI: choose *Machines* > *[machine]* > *Storage*.

In the CLI: use `maas $PROFILE machine set-storage-layout`.


## Flat layout

What it is:
A simple setup where the entire disk is one root filesystem.  Good for small or simple systems.

| Name  | Size       | Type | Filesystem | Mount point |
| sda   | -          | disk | -          | -           |
| sda1  | 512 MB     | part | FAT32      | /boot/efi   |
| sda2  | rest of sda| part | ext4       | /           |

How to configure:
- UI: Choose Flat in the storage layout dropdown.
- CLI:
  ```bash
  maas $PROFILE machine set-storage-layout $SYSTEM_ID layout=flat
  ```

Options:
- `boot_size`: Size of `/boot`.  Default is 0 (combined with `/`).
- `root_device`: Device to hold the root partition (default: boot disk).
- `root_size`: Size of root partition (default: 100%).


## LVM layout

What it is:
Logical Volume Manager (LVM) adds flexibility, allowing resizing or adding volumes later.

| Name  | Size        | Type  | Filesystem     | Mount point |
| sda   | -           | disk  | -              | -           |
| sda1  | 512 MB      | part  | FAT32          | /boot/efi   |
| sda2  | rest of sda | part  | lvm-pv(vgroot) | -           |
| lvroot| rest of sda | lvm   | ext4           | /           |

How to configure:
- UI: Select LVM in storage layout.
- CLI:
  ```bash
  maas $PROFILE machine set-storage-layout $SYSTEM_ID layout=lvm
  ```

Options:
- `vg_name`: Name of the volume group (default: `vgroot`).
- `lv_name`: Name of logical volume (default: `lvroot`).
- `lv_size`: Size of LV (default: 100%).


## Bcache layout

What it is:
Uses an SSD as a cache for a slower backing disk to improve performance.

| Name   | Size        | Type      | Filesystem | Mount point |
| sda    | -           | disk      | -          | -           |
| sda1   | 512 MB      | part      | FAT32      | /boot/efi   |
| sda2   | rest of sda | part      | bc-backing | -           |
| sdb(ssd)| -          | disk      | -          | -           |
| sdb1   | 100% of sdb | part      | bc-cache   | -           |
| bcache0| per sda2    | disk      | ext4       | /           |

How to configure:
- UI: Select Bcache in storage layout.
- CLI:
  ```bash
  maas $PROFILE machine set-storage-layout $SYSTEM_ID layout=bcache
  ```

Options:
- `cache_device`: SSD to use as cache (default: smallest SSD).
- `cache_mode`: Cache mode (`writethrough` by default).
- `cache_size`: Partition size for cache.
- `cache_no_part`: Whether to skip partition creation on cache device.

If no SSD is present, bcache layout will fail.


## VMFS6 layout

What it is:
Required for VMware ESXi deployments.  Sets up both the OS and VMFS datastore.

| Name  | Size        | Type       | Use                |
| sda   | -           | disk       | -                  |
| sda1  | 3 MB        | part       | EFI                |
| sda2  | 4 GB        | part       | Basic Data         |
| sda3  | Remaining   | part       | VMFS Datastore 1   |

How to configure:
- UI: Select VMFS6 when editing storage.
- CLI:
  ```bash
  maas $PROFILE machine set-storage-layout $SYSTEM_ID layout=vmfs6
  ```

Options:
- `root_size`: Size of datastore (default: remainder of disk).


## Blank layout

What it is:
Wipes the disk and leaves storage unconfigured.  Use this if you want to manually define partitions, filesystems, or RAIDs before deployment.

How to configure:
- UI: Select Blank in storage layout.
- CLI:
  ```bash
  maas $PROFILE machine set-storage-layout $SYSTEM_ID layout=blank
  ```

A machine with Blank layout cannot deploy until storage is manually configured.


## Safety nets

- Always confirm layout with `maas $PROFILE machine read $SYSTEM_ID | jq .storage`.
- In UI, check the Storage tab before hitting *Deploy*.
- Test deployment of a machine before applying custom layouts widely.


## Next steps
- Peruse the [storage reference catalog](https://canonical.com/maas/docs/reference-maas-storage)
