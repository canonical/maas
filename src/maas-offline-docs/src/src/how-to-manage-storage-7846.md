> *Errors or typos? Topics missing? Hard to read? <a href="https://docs.google.com/forms/d/e/1FAIpQLScIt3ffetkaKW3gDv6FDk7CfUTNYP_HGmqQotSTtj2htKkVBw/viewform?usp=pp_url&entry.1739714854=https://maas.io/docs/how-to-manage-machine-storage" target = "_blank">Let us know.</a>

This page describes machine storage operations that are common to all layouts and storage types.

## Set default layout

All machines will have a default layout applied when commissioned. If you change the default layout, that new default will only apply to newly-commissioned machines. To set the default storage layout for all machines:

* In the MAAS UI, choose *Settings* > *Storage* > choose default layout. A default erasure configuration can be also set by selecting *Storage* > *Settings*. If option *Erase machines' disks prior to releasing* is chosen, then users will be compelled to use disk erasure. That option will be pre-filled in the machine's view and the user will be unable to remove the option.

* Via the MAAS UI, use the following commands:

```nohighlight
    maas $PROFILE maas set-config name=default_storage_layout value=$LAYOUT_TYPE
```
    
    For example, to set the default layout to Flat:
    
```nohighlight
    maas $PROFILE maas set-config name=default_storage_layout value=flat
```

## Set per-machine layout (CLI)

An administrator can set a storage layout for a 'Ready' machine:

```nohighlight
maas $PROFILE machine set-storage-layout $SYSTEM_ID storage_layout=$LAYOUT_TYPE [$OPTIONS]
```

For example, to set an LVM layout where the logical volume has a size of 5 GB:

```nohighlight
maas $PROFILE machine set-storage-layout $SYSTEM_ID storage_layout=lvm lv_size=5368709120
```

You must specify all storage sizes in bytes. This action will remove the configuration that may exist on any block device.

## Erase disks (CLI)

When using the [MAAS CLI](/t/tutorial-try-the-maas-cli/5236), you can erase a disk when releasing an individual machine. Note that this option is not available when releasing multiple machines, so you'll want to make sure you're using:

```nohighlight
maas $PROFILE machine release...
```

and not:

```nohighlight
maas $PROFILE machines release...
```

Note the difference in singular and plural "machine/machines" in the commands. Releasing a machine requires that you have the `system_id` of the machine to be released, which you can obtain with a command like this one:

```nohighlight
maas admin machines read | jq -r '(["HOSTNAME","SYSID","POWER","STATUS",
"OWNER", "TAGS", "POOL", "VLAN","FABRIC","SUBNET"] | (., map(length*"-"))),
(.[] | [.hostname, .system_id, .power_state, .status_name, .owner // "-", 
.tag_names[0] // "-", .pool.name,
.boot_interface.vlan.name, .boot_interface.vlan.fabric,
.boot_interface.links[0].subnet.name]) | @tsv' | column -t
```

<a href="https://discourse-maas-io-uploads.s3.us-east-1.amazonaws.com/original/1X/a496ac76977909f3403160ca96a1bb7224e785f5.jpeg" target = "_blank"><img src="https://discourse-maas-io-uploads.s3.us-east-1.amazonaws.com/original/1X/a496ac76977909f3403160ca96a1bb7224e785f5.jpeg">
</a>

The basic form of the release command, when erasing disks on releasing, is:

```nohighlight
maas $PROFILE machine release $SYSTEM_ID comment="some comment" erase=true [secure_erase=true ||/&& quick_erase=true]
```

Parameters `secure_erase` and `quick_erase` are both optional, although if you don't specify either of them, the entire disk will be overwritten with null bytes. Note that this overwrite process is very slow.

Secure erasure uses the drive's secure erase feature, if it has one. In some cases, this can be much faster than overwriting the entire drive. Be aware, though, that some drives implement secure erasure as a complete drive overwrite, so this method may still be very slow. Additionally, if you specify secure erasure and the drive doesn't have this feature, you'll get a complete overwrite anyway -- again, possibly very slow.

Quick erasure wipes 2MB at the start and end of the drive to make recovery both inconvenient and unlikely to happen by accident. Note, though, that quick erasure is not secure.

## Set conditional erasure (CLI)

If you specify both erasure types, like this:

```nohighlight
maas $PROFILE machine release $SYSTEM_ID comment="some comment" erase=true secure_erase=true quick_erase=true
```

then MAAS will perform a secure erasure if the drive has that feature; if not, it will perform a quick erasure. Of course, if you're concerned about completely erasing the drive, and you're not sure whether the disk has secure erase features, the best way to handle that is to specify nothing, and allow the full disk to be overwritten by null bytes:

```nohighlight
maas $PROFILE machine release $SYSTEM_ID comment="some comment" erase=true
```

You can manipulate machine block storage devices with the MAAS CLI.  Note that block devices cannot be managed through the MAAS UI.

## Manage block devices

You can directly manage block devices associated with MAAS.

### List block devices

To view all block devices on a machine use the read operation. This list both physical and virtual block devices, as you can see in the output from the following command:

```nohighlight
maas admin block-devices read <node-id>
```

### Read block device

If you want to read just one block device instead of listing all block devices the read operation on the block device endpoint provides that information. To display the details on device '11' from the previous output, for example, we could enter:

```nohighlight
maas admin block-device read <node-id> 11
```

It is also possible to use the name of the block device, such as 'sda' or 'vda', instead of its 'id':

```nohighlight
s admin block-device read <node-id> vda
```

> MAAS allows the name of a block device to be changed. If the block device name has changed then the API call needs to use the new name. Using the ID is safer as it never changes.

### Create block device

MAAS gathers the required information itself on block devices when re- commissioning a machine. If this doesn't provide the required information, it is also possible - though not recommended - for an administrator to use the API to manually add a physical block device to a machine.

```nohighlight
maas admin block-devices create <node-id> name=vdb model="QEMU" serial="QM00001" size=21474836480 block_size=4096
```

> The serial number is what MAAS will use when a machine is deployed to find the specific block device. It's important that this be correct. In a rare chance that your block device does not provide a model or serial number you can provide an id_path. The id_path should be a path that is always the same, no matter the kernel version.

### Update block device

An administrator can also update the details held on a physical block device, such as its name, from the API:

```nohighlight
maas admin block-device update <node-id> 12 name=newroot
```

### Delete block device

Physical and virtual block devices can be deleted by an administrator, while ordinary users can only delete virtual block devices:

```nohighlight
maas admin block-device delete <node-id> 12
```

### Format block device

An entire block device can be formatted by defining a filesystem with the 'format' API call:

```nohighlight
maas admin block-device format <node-id> 11 fstype=ext4
```

> You cannot format a block device that contains partitions or is used to make another virtual block device.

### Unformat block device

You can remove the filesystem from a block device with the 'unformat' API call:

```nohighlight
maas admin block-device unformat <node-id> 11
```

### Mount block device

If a block device has a filesystem, you can use the 'maas' command to mount a block devices at a given mount point:

```nohighlight
maas admin block-device mount <node-id> 11 mount_point=/srv
```

### Unmount block device

To remove the mount point from the block device, use the 'unmount' call:

```nohighlight
maas admin block-device unmount <node-id> 11 mount_point=/srv
```

### Boot from block device

By default, MAAS picks the first added block device to the machine as the boot disk. In most cases this works as expected as the BIOS usually enumerates the boot disk as the first block device. There are cases where this fails and the boot disk needs to be set to another disk. This API allow setting which block device on a machine MAAS should use as the boot disk.:

```nohighlight
maas admin block-device set-boot-disk <node-id> 10
```

> Only an administrator can set which block device should be used as the boot disk and only a physical block device can be set as as the boot disk. This operation should be done before a machine is allocated or the storage layout will be applied to the previous boot disk.

## Manage partitions

You can manipulate storage partitions via the MAAS CLI.  Note that partitions cannot be managed through the MAAS UI.

### List partitions

To view all the partitions on a block device, use the 'partitions read' API call:

```nohighlight
maas admin partitions read <node-id> 10
```

To view the metadata for a specific partition on a block device, rather than all partitions, use the singular 'partition' API call with an endpoint:

```nohighlight
maas admin partition read <node-id> 10 9
```

### Create partition

To create a new partition on a block device, use the 'create' API call:

```nohighlight
maas admin partitions create <node-id> 10 size=5360320512
```

In addition to bytes, as shown above, the 'size' of a partition can also be defined with a 'G' for gigabytes or 'M' for megabytes.

### Delete partition

Partitions can be deleted from a block device with the 'delete' API call. Make sure you double check the partition details as the partition is deleted immediately, with no further confirmation:

```nohighlight
maas admin partition delete <node-id> 10 9
```

### Format partition

Partitions can be formatted in a similar way to block devices:

```nohighlight
maas admin partition format <node-id> 10 9 fstype=ext4
```

> You cannot format partitions that are used to make another virtual block device.

### Unformat partition

You can also remove the filesystem from a partition with the 'unformat' API call:

```nohighlight
maas admin partition unformat <node-id> 10 10 fstype=ext4
```

### Mount partition

A formatted partition can be mounted at a given mount point with the 'mount' command.

```nohighlight
maas admin partition mount <node-id> 10 10 mount_point=/srv
```

### Unmount partition

A previous mounted partition can be unmounted with the 'unmount' command:

```nohighlight
maas admin partition unmount 4y3h8a 10 10
```

## Manage VMFS datastores
You can manipulate VMFS datastores with the MAAS CLI.  Note that VMFS datastores cannot be managed via the MAAS UI.

### Create VMFS datastore

A VMware VMFS datastore is created on one or more block devices or partitions.

To create a VMFS Datastores on a machine use the 'vmfs-datastores create' API call:

```nohighlight
maas $PROFILE vmfs-datastores create $SYSTEM_ID name=$VMFS_NAME block_devices=$BLOCK_ID_1,$BLOCK_ID_2 partitions=$PARTITION_ID_1,$PARTITION_ID_2
```

### Edit VMFS datastore

To edit an existing VMFS Datastores on a machine use the 'vmfs-datastore update' API call:

```nohighlight
maas $PROFILE vmfs-datastore update $SYSTEM_ID $VMFS_ID name=$NEW_VMFS_NAME add_block_devices=$NEW_BLOCK_ID_1,$NEW_BLOCK_ID_2 add_partitions=$NEW_PARTITION_ID_1,$NEW_PARTITION_ID_2 remove_partitions=$EXISTING_PARTITION_ID1,$EXISTING_PARTITION_ID2
```

### Delete VMFS datastore

To delete a VMFS Datastores on a machine use the 'vmfs-datastore delete' API call:

```nohighlight
maas $PROFILE vmfs-datastore delete $SYSTEM_ID $VMFS_ID
```

### List VMFS datastores

To view all VMFS Datastores on a machine, use the 'vmfs-datastores read' API call:

```nohighlight
maas $PROFILE vmfs-datastores read $SYSTEM_ID
```

### View VMFS datastore

To view a specific VMFS Datastores on a machine, use the 'vmfs-datastore read' API call:

```nohighlight
maas $PROFILE vmfs-datastore read $SYSTEM_ID $VMFS_DATASTORE_ID
```
