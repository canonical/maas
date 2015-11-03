.. -*- mode: rst -*-

.. _storage:

=========================
Storage
=========================

.. note::

  This feature is available in MAAS versions 1.9 and above on Ubuntu
  deployments.  If you're writing a client application, you can check
  if MAAS supports this feature via the web API; see the documentation
  for the ``storage-deployment-ubuntu`` capability
  :ref:`here<cap-storage-deployment-ubuntu>`.

MAAS has the ability to configure any storage layout during node deployment.
MAAS doesn't just do simple partitioning it supports complex storage layouts,
including setting up and configuring Bcache, RAID, and LVM. This gives users
unlimited possibilities on the storage configurations they want to deploy.

Layouts
-------

When a node is acquired by a user it gets a default storage layout. This layout
provides the basic storage configuration to allow a node to deploy
successfully. The default storage layout can also be adjusted allowing an
administrator to make the decision on which layout will be the default.

The users deploying nodes are not limited by the default. They can set an
explicit storage layout when they acquire a node or after they have acquried a
node with the set-storage-layout API. The user acquiring a node or performing
the set-storage-layout API calls can also customize the layout generation. Each
layout has a set of options that can be set to adjust the generated layout.

Below list all the available storage layouts and the available options for
each.

LVM Layout
^^^^^^^^^^

Creates a volume group `vgroot` on a partition that spans the entire boot disk.
A logical volume `lvroot` is created for the full size of the volume group. The
`lvroot` is formatted with `ext4` and set as the `/` mount point.
::

    NAME        SIZE        TYPE    FSTYPE         MOUNTPOINT
    sda         100G        disk
      sda1      512M        part    fat32          /boot/efi
      sda2      99.5G       part    lvm-pv(vgroot)
    vgroot      99.5G       lvm
      lvroot    99.5G       lvm     ext4           /

The following options are supported for this layout.
::

    boot_size: Size of the boot partition on the boot disk. Default is 0,
        meaning not to create the boot partition. The '/boot' will be placed
        on the root filesystem.
    root_device: The block device to place the root partition on. Default is
        the boot disk.
    root_size: Size of the root partition. Default is 100%, meaning the
        entire size of the root device.
    vg_name: Name of the created volume group. Default is `vgroot`.
    lv_name: Name of the created logical volume. Default is `lvroot`.
    lv_size: Size of the created logical volume. Default is 100%, meaning
        the entire size of the volume group.

Flat Layout
^^^^^^^^^^^

Creates a partition that spans the entire boot disk. The partition is formatted
with `ext4` and set as the `/` mount point.
::

  NAME        SIZE        TYPE    FSTYPE         MOUNTPOINT
  sda         100G        disk
    sda1      512M        part    fat32          /boot/efi
    sda2      99.5G       part    ext4           /

The following options are supported for this layout.
::

  boot_size: Size of the boot partition on the boot disk. Default is 0,
      meaning not to create the boot partition. The '/boot' will be placed
      on the root filesystem.
  root_device: The block device to place the root partition on. Default is
      the boot disk.
  root_size: Size of the root partition. Default is 100%, meaning the
      entire size of the root device.

Bcache Layout
^^^^^^^^^^^^^

Creates a Bcache using a partition that spans the entire boot disk as the
backing device. Uses the smallest block device tagged with `ssd` as the cache
device. The Bcache device is formatted with `ext4` and set as the `/` mount
point. If no block devices exists on the node that are tagged with `ssd` then
the Bcache device will not be created and the `flat` layout will be used.
::

  NAME        SIZE        TYPE    FSTYPE         MOUNTPOINT
  sda         100G        disk
    sda1      512M        part    fat32          /boot/efi
    sda2      99.5G       part    bc-backing
  sdb         50G         disk
    sdb1      50G         part    bc-cache
  bcache0     99.5G       disk    ext4           /

The following options are supported for this layout.
::

  boot_size: Size of the boot partition on the boot disk. Default is 0,
      meaning not to create the boot partition. The '/boot' will be placed
      on the root filesystem.
  root_device: The block device to place the root partition on. Default is
      the boot disk.
  root_size: Size of the root partition. Default is 100%, meaning the
      entire size of the root device.
  cache_device: The block device to use as the cache device. Default
      is the smallest block device tagged ssd.
  cache_mode: The cache mode to set the created Bcache device to. Default
      is `writethrough`.
  cache_size: The size of the partition on the cache device. Default is
      100%, meaning the entire size of the cache device.
  cache_no_part: Whether or not to create a partition on the cache device.
      Default is false, meaning to create a partition using the given
      `cache_size`. If set to true no partition will be created and the raw
      cache device will be used as the cache.

.. note::

  The `/boot/efi` partition on all layouts will only be created on nodes that
  deploy with UEFI.


Setting the Layout
------------------

The following are a couple of was the storage layout can be changed either
globally, on acquire, or after acquire.

Globally
^^^^^^^^

The global default storage layout can be set using the API and the UI. This
will change the default storage layout for when a node is acquired. `It will
not adjust the layout of any node that is already passed the acquire stage.`::

  $ maas my-maas-session maas set_config name=default_storage_layout value=flat

Set Storage Layout
^^^^^^^^^^^^^^^^^^

If a node is already acquired and you want to adjust the storage layout the
set_storage_layout API call can be used. The options for this API call do not
require the `storage_layout_` prefix.::

  $ maas my-maas-session node set-storage-layout <system-id> storage_layout=lvm lv_size=50%

.. note::

  This will completely remove any previous storage configuration on all block
  devices.

Block Devices
-------------

Once the initial storage layout has been configure on a node you can perform
many operations to view and adjust the entire storage layout for the node. In
MAAS there are two different types of block devices.

**Physical**

A physical block device is a physically attached block device. This being true
storage on a machine. E.g. A 100G hard drive in a server.

**Virtual**

A virtual block device is a block device that is exposed by the Linux kernel
when an operation is performed. Almost all the operations on a physical block
device can be performed on a virtual block device. E.g. A RAID device exposed
as `md0`.

List Block Devices
^^^^^^^^^^^^^^^^^^
To view all block devices on a node use the `read` operation. This list both
physical and virtual block devices.::

  $ maas my-maas-session block-devices read node-f4e2281c-d19a-11e4-a5ac-00163edde41f
  [
      {
          "size": 21474836480,
          "resource_uri": "/MAAS/api/1.0/nodes/node-f4e2281c-d19a-11e4-a5ac-00163edde41f/blockdevices/6/",
          "uuid": null,
          "tags": [
              "ssd",
              "rotary"
          ],
          "name": "sda",
          "partition_table_type": "MBR",
          "id_path": "/dev/disk/by-id/ata-QEMU_HARDDISK_QM00001",
          "path": "/dev/disk/by-dname/sda",
          "model": "QEMU HARDDISK",
          "block_size": 4096,
          "type": "physical",
          "id": 6,
          "serial": "QM00001",
          "partitions": [
              {
                  "uuid": "e94ca09a-d83e-4521-8bac-833da2ed0b3e",
                  "bootable": false,
                  "filesystem": {
                      "label": null,
                      "mount_point": null,
                      "uuid": "61d447c2-387d-4fb1-885a-65eeef91e92a",
                      "fstype": "lvm-pv"
                  },
                  "path": "/dev/disk/by-dname/sda-part1",
                  "resource_uri": "/MAAS/api/1.0/nodes/node-f4e2281c-d19a-11e4-a5ac-00163edde41f/blockdevices/6/partition/1",
                  "type": "partition",
                  "id": 1,
                  "size": 21471690752
              }
          ]
      },
      {
          "resource_uri": "/MAAS/api/1.0/nodes/node-f4e2281c-d19a-11e4-a5ac-00163edde41f/blockdevices/11/",
          "uuid": "f58b8fb2-dcf2-4ba9-a01c-60409829a64e",
          "tags": [],
          "partitions": [],
          "name": "vgroot-lvroot",
          "partition_table_type": null,
          "filesystem": {
              "label": "root",
              "mount_point": "/",
              "uuid": "9f09e3fd-2484-4da5-bb56-a72a0c478d06",
              "fstype": "ext4"
          },
          "id_path": null,
          "path": "/dev/disk/by-dname/lvroot",
          "model": null,
          "block_size": 4096,
          "type": "virtual",
          "id": 11,
          "serial": null,
          "size": 21470642176
      }
  ]

Read Block Device
^^^^^^^^^^^^^^^^^

If you want to read just one block device instead of listing all block devices
the `read` operation on the `block-device` endpoint provides that information.
::

  $ maas my-maas-session block-device read node-f4e2281c-d19a-11e4-a5ac-00163edde41f 12
  {
      "size": 21474836480,
      "resource_uri": "/MAAS/api/1.0/nodes/node-f4e2281c-d19a-11e4-a5ac-00163edde41f/blockdevices/12/",
      "uuid": null,
      "tags": [],
      "name": "sdb",
      "partition_table_type": null,
      "id_path": "",
      "path": "/dev/disk/by-dname/sdb",
      "model": "QEMU HARDDISK",
      "block_size": 4096,
      "type": "physical",
      "id": 12,
      "serial": "QM00001",
      "partitions": []
  }

It is also possible to use the name of the block device instead of its ID.::

  $ maas my-maas-session block-device read node-f4e2281c-d19a-11e4-a5ac-00163edde41f sdb
  {
      "size": 21474836480,
      "resource_uri": "/MAAS/api/1.0/nodes/node-f4e2281c-d19a-11e4-a5ac-00163edde41f/blockdevices/12/",
      "uuid": null,
      "tags": [],
      "name": "sdb",
      "partition_table_type": null,
      "id_path": "",
      "path": "/dev/disk/by-dname/sdb",
      "model": "QEMU HARDDISK",
      "block_size": 4096,
      "type": "physical",
      "id": 12,
      "serial": "QM00001",
      "partitions": []
  }

.. note::

  MAAS allows the name of a block device to be changed. If the block device
  name has changed then the API call needs to use the new name. Using the ID
  is safer as it never changes.

Create Block Device
^^^^^^^^^^^^^^^^^^^

This operation only allows an administrator to add a physical block device to
a node. It is not recommended to create a block device as you need very
specific information for each block device. It is recommended to
re-commissioning the machine for MAAS to gather the required information. If
MAAS does not provide the required information this API exists only as a
fallback.::

  $ maas my-maas-session block-devices create node-f4e2281c-d19a-11e4-a5ac-00163edde41f name=sdb model="QEMU HARDDISK" serial="QM00001" size=21474836480 block_size=4096
  {
      "size": 21474836480,
      "resource_uri": "/MAAS/api/1.0/nodes/node-f4e2281c-d19a-11e4-a5ac-00163edde41f/blockdevices/12/",
      "uuid": null,
      "tags": [],
      "name": "sdb",
      "partition_table_type": null,
      "id_path": "",
      "path": "/dev/disk/by-dname/sdb",
      "model": "QEMU HARDDISK",
      "block_size": 4096,
      "type": "physical",
      "id": 12,
      "serial": "QM00001",
      "partitions": []
  }

.. note::

  The serial number is what MAAS will use when a node is deployed to find the
  specific block device. Its very important that this be absolutely correct.
  In a rare chance that your block device does not provide a model or serial
  number you can provide an id_path. The id_path should be a path that is
  always the same, no matter the kernel version.

Update Block Device
^^^^^^^^^^^^^^^^^^^

Provides the ability for an administrator needs to update the information of a
physical block device and a standard user to update information of a virtual
block device. A standard user cannot update the information of a physical
block device.::

  $ maas my-maas-session block-device update node-f4e2281c-d19a-11e4-a5ac-00163edde41f 11 name=newroot
  {
      "size": 21470642176,
      "resource_uri": "/MAAS/api/1.0/nodes/node-f4e2281c-d19a-11e4-a5ac-00163edde41f/blockdevices/11/",
      "uuid": "f58b8fb2-dcf2-4ba9-a01c-60409829a64e",
      "tags": [],
      "name": "vgroot-newroot",
      "partition_table_type": null,
      "filesystem": {
          "label": "root",
          "mount_point": "/",
          "uuid": "9f09e3fd-2484-4da5-bb56-a72a0c478d06",
          "fstype": "ext4"
      },
      "path": "/dev/disk/by-dname/vgroot-newroot",
      "model": null,
      "block_size": 4096,
      "type": "virtual",
      "id": 11,
      "serial": null,
      "partitions": []
  }

Delete Block Device
^^^^^^^^^^^^^^^^^^^

Allows an adminstrator to delete a physical block device and a standard user
to delete a virtual block device.::

  $ maas my-maas-session block-device delete node-f4e2281c-d19a-11e4-a5ac-00163edde41f 12

Format Block Device
^^^^^^^^^^^^^^^^^^^

Format the entire block device with a file system.::

  $ maas my-maas-session block-device format node-f4e2281c-d19a-11e4-a5ac-00163edde41f 11 fstype=ext4
  {
      "size": 21470642176,
      "resource_uri": "/MAAS/api/1.0/nodes/node-f4e2281c-d19a-11e4-a5ac-00163edde41f/blockdevices/11/",
      "uuid": "f58b8fb2-dcf2-4ba9-a01c-60409829a64e",
      "tags": [],
      "name": "vgroot-newroot",
      "partition_table_type": null,
      "filesystem": {
          "label": null,
          "mount_point": null,
          "uuid": "b713af05-3f1c-4ddc-b4dd-a7878e6af14f",
          "fstype": "ext4"
      },
      "path": "/dev/disk/by-dname/vgroot-newroot",
      "model": null,
      "block_size": 4096,
      "type": "virtual",
      "id": 11,
      "serial": null,
      "partitions": []
  }

.. note::

  You cannot format a block device that contains partitions or is used to make
  another virtual block device.

Unformat Block Device
^^^^^^^^^^^^^^^^^^^^^

Remove the file system from the block device.::

  $ maas my-maas-session block-device unformat node-f4e2281c-d19a-11e4-a5ac-00163edde41f 11
  {
      "size": 21470642176,
      "resource_uri": "/MAAS/api/1.0/nodes/node-f4e2281c-d19a-11e4-a5ac-00163edde41f/blockdevices/11/",
      "uuid": "f58b8fb2-dcf2-4ba9-a01c-60409829a64e",
      "tags": [],
      "name": "vgroot-newroot",
      "partition_table_type": null,
      "path": "/dev/disk/by-dname/vgroot-newroot",
      "model": null,
      "block_size": 4096,
      "type": "virtual",
      "id": 11,
      "serial": null,
      "partitions": []
  }

Mount Block Device
^^^^^^^^^^^^^^^^^^

Mount the block device at the given mount point. Block device is required to
have a filesystem.::

  $ maas my-maas-session block-device mount node-f4e2281c-d19a-11e4-a5ac-00163edde41f 11 mount_point=/srv
  {
      "size": 21470642176,
      "resource_uri": "/MAAS/api/1.0/nodes/node-f4e2281c-d19a-11e4-a5ac-00163edde41f/blockdevices/11/",
      "uuid": "f58b8fb2-dcf2-4ba9-a01c-60409829a64e",
      "tags": [],
      "name": "vgroot-newroot",
      "partition_table_type": null,
      "filesystem": {
          "label": null,
          "mount_point": "/srv",
          "uuid": "b892e5c3-8bea-4371-a456-bde11df3df40",
          "fstype": "ext4"
      },
      "path": "/dev/disk/by-dname/vgroot-newroot",
      "model": null,
      "block_size": 4096,
      "type": "virtual",
      "id": 11,
      "serial": null,
      "partitions": []
  }

Unmount Block Device
^^^^^^^^^^^^^^^^^^^^

Remove the mount point from the block device.::

  $ maas my-maas-session block-device unmount node-f4e2281c-d19a-11e4-a5ac-00163edde41f 11
  {
      "size": 21470642176,
      "resource_uri": "/MAAS/api/1.0/nodes/node-f4e2281c-d19a-11e4-a5ac-00163edde41f/blockdevices/11/",
      "uuid": "f58b8fb2-dcf2-4ba9-a01c-60409829a64e",
      "tags": [],
      "name": "vgroot-newroot",
      "partition_table_type": null,
      "filesystem": {
          "label": null,
          "mount_point": null,
          "uuid": "b892e5c3-8bea-4371-a456-bde11df3df40",
          "fstype": "ext4"
      },
      "path": "/dev/disk/by-dname/vgroot-newroot",
      "model": null,
      "block_size": 4096,
      "type": "virtual",
      "id": 11,
      "serial": null,
      "partitions": []
  }

Set as Boot Disk
^^^^^^^^^^^^^^^^

MAAS by default picks the first added block device to the node as the boot
disk. In most cases this works as expected as the BIOS enumerates the boot disk
as the first block device. There are cases where this fails and the boot disk
needs to be set to another disk. This API allow setting which block device on
a node MAAS should use as the boot disk.::

  $ maas my-maas-session block-device set-boot-disk node-f4e2281c-d19a-11e4-a5ac-00163edde41f 6
  OK

.. note::

  Only an administrator can set which block device should be used as the boot
  disk and only a physical block device can be set as a the boot disk. This
  operation should be done before a node is acquired or the storage layout will
  be applied to the previous boot disk.

Partitions
----------

List Partitions
^^^^^^^^^^^^^^^
View all the partitions on a block device.::

  $ maas my-maas-session partitions read node-f4e2281c-d19a-11e4-a5ac-00163edde41f 6
  [
      {
          "uuid": "e94ca09a-d83e-4521-8bac-833da2ed0b3e",
          "bootable": false,
          "filesystem": {
              "label": null,
              "mount_point": null,
              "uuid": "61d447c2-387d-4fb1-885a-65eeef91e92a",
              "fstype": "lvm-pv"
          },
          "path": "/dev/disk/by-dname/sda-part1",
          "resource_uri": "/MAAS/api/1.0/nodes/node-f4e2281c-d19a-11e4-a5ac-00163edde41f/blockdevices/6/partition/1",
          "type": "partition",
          "id": 1,
          "size": 21471690752
      }
  ]

Read Partition
^^^^^^^^^^^^^^

If you want to read just one partition on a block device instead of listing all
partitions `read` operation on the `partition` endpoint provides that
information.
::

  $ maas my-maas-session partition read node-f4e2281c-d19a-11e4-a5ac-00163edde41f 6 1
  {
      "uuid": "e94ca09a-d83e-4521-8bac-833da2ed0b3e",
      "bootable": false,
      "filesystem": {
          "label": null,
          "mount_point": null,
          "uuid": "61d447c2-387d-4fb1-885a-65eeef91e92a",
          "fstype": "lvm-pv"
      },
      "path": "/dev/disk/by-dname/sda-part1",
      "resource_uri": "/MAAS/api/1.0/nodes/node-f4e2281c-d19a-11e4-a5ac-00163edde41f/blockdevices/6/partition/1",
      "type": "partition",
      "id": 1,
      "size": 21471690752
  }

Create Partition
^^^^^^^^^^^^^^^^

Creates a partition on a block device.::

  $ maas my-maas-session partitions create node-f4e2281c-d19a-11e4-a5ac-00163edde41f 6 size=2G
  {
      "uuid": "fc06be78-1665-4fd2-95d3-f588aaad3575",
      "bootable": false,
      "path": "/dev/disk/by-dname/sda-part1",
      "resource_uri": "/MAAS/api/1.0/nodes/node-f4e2281c-d19a-11e4-a5ac-00163edde41f/blockdevices/6/partition/2",
      "type": "partition",
      "id": 2,
      "size": 2000003072
  }

Delete Partition
^^^^^^^^^^^^^^^^

Deletes a partition from a block device.::

  $ maas my-maas-session partition delete node-f4e2281c-d19a-11e4-a5ac-00163edde41f 6 2

Format Partition
^^^^^^^^^^^^^^^^

Format the partition with a file system.::

  $ maas my-maas-session partition format node-f4e2281c-d19a-11e4-a5ac-00163edde41f 6 3 fstype=ext4
  {
      "uuid": "fb468be6-64bd-434a-b95b-b8c932610960",
      "bootable": false,
      "filesystem": {
          "label": "",
          "mount_point": null,
          "uuid": "8fbb4e35-cb65-49f7-8377-f00f48ac9da9",
          "fstype": "ext4"
      },
      "path": "/dev/disk/by-dname/sda-part1",
      "resource_uri": "/MAAS/api/1.0/nodes/node-f4e2281c-d19a-11e4-a5ac-00163edde41f/blockdevices/6/partition/3",
      "type": "partition",
      "id": 3,
      "size": 2000003072
  }

.. note::

  You cannot format partitions that are used to make another virtual block
  device.

Unformat Partition
^^^^^^^^^^^^^^^^^^

Remove the file system from the partition.::

  $ maas my-maas-session partition unformat node-f4e2281c-d19a-11e4-a5ac-00163edde41f 6 3
  {
      "uuid": "fb468be6-64bd-434a-b95b-b8c932610960",
      "bootable": false,
      "path": "/dev/disk/by-dname/sda-part1",
      "resource_uri": "/MAAS/api/1.0/nodes/node-f4e2281c-d19a-11e4-a5ac-00163edde41f/blockdevices/6/partition/3",
      "type": "partition",
      "id": 3,
      "size": 2000003072
  }

Mount Partition
^^^^^^^^^^^^^^^

Mount the partition at the given mount point. Partition is required to
have a filesystem.::

  $ maas my-maas-session partition mount node-f4e2281c-d19a-11e4-a5ac-00163edde41f 6 3 mount_point=/srv
  {
      "uuid": "fb468be6-64bd-434a-b95b-b8c932610960",
      "bootable": false,
      "filesystem": {
          "label": "",
          "mount_point": "/srv",
          "uuid": "b59ad2c3-cffa-4cda-830f-276df4151c1c",
          "fstype": "ext4"
      },
      "path": "/dev/disk/by-dname/sda-part1",
      "resource_uri": "/MAAS/api/1.0/nodes/node-f4e2281c-d19a-11e4-a5ac-00163edde41f/blockdevices/6/partition/3",
      "type": "partition",
      "id": 3,
      "size": 2000003072
  }

Unmount Partition
^^^^^^^^^^^^^^^^^

Remove the mount point from the partition.::

  $ maas my-maas-session partition unmount node-f4e2281c-d19a-11e4-a5ac-00163edde41f 6 3
  {
      "uuid": "fb468be6-64bd-434a-b95b-b8c932610960",
      "bootable": false,
      "filesystem": {
          "label": "",
          "mount_point": null,
          "uuid": "b59ad2c3-cffa-4cda-830f-276df4151c1c",
          "fstype": "ext4"
      },
      "path": "/dev/disk/by-dname/sda-part1",
      "resource_uri": "/MAAS/api/1.0/nodes/node-f4e2281c-d19a-11e4-a5ac-00163edde41f/blockdevices/6/partition/3",
      "type": "partition",
      "id": 3,
      "size": 2000003072
  }

Restrictions
------------

There are only a couple of restrictions that exists in the storage
configuration. These restrictions are only in place because they are known
to not allow a successful deployment.

  * EFI partition is required to be on the boot disk for UEFI.
  * Cannot place partitions on logical volumes.
  * Cannot use a logical volume as a Bcache backing device.
