You can manipulate storage partitions via the MAAS CLI.  Note that partitions cannot be managed through the MAAS UI.

## List partitions

To view all the partitions on a block device, use the 'partitions read' API call:

```nohighlight
maas admin partitions read <node-id> 10
```

```nohighlight
Success.
Machine-readable output follows:
[
    {
        "bootable": false,
        "id": 9,
        "resource_uri":
"/MAAS/api/2.0/nodes/4y3h8a/blockdevices/10/partition/9",
        "path": "/dev/disk/by-dname/vda-part1",
        "uuid": "aae082cd-8be0-4a64-ab49-e998abd6ea43",
        "used_for": "LVM volume for vgroot",
        "size": 5360320512,
        "type": "partition",
        "filesystem": {
            "uuid": "a56ebfa6-8ef4-48b5-b6bc-9f9d27065d24",
            "mount_options": null,
            "label": null,
            "fstype": "lvm-pv",
            "mount_point": null
        }
    }
]
```

To view the metadata for a specific partition on a block device, rather than all partitions, use the singular 'partition' API call with an endpoint:

```nohighlight
maas admin partition read <node-id> 10 9
```

## Create partition

To create a new partition on a block device, use the 'create' API call:

```nohighlight
maas admin partitions create <node-id> 10 size=5360320512
```

In addition to bytes, as shown above, the 'size' of a partition can also be defined with a 'G' for gigabytes or 'M' for megabytes. The output from the previous command will look like this:

```nohighlight
Success.
Machine-readable output follows:
{
    "bootable": false,
    "path": "/dev/disk/by-dname/vda-part1",
    "filesystem": null,
    "used_for": "Unused",
    "type": "partition",
    "id": 10,
    "size": 5360320512,
    "resource_uri": "/MAAS/api/2.0/nodes/4y3h8a/blockdevices/10/partition/10",
    "uuid": "3d32adbf-9943-4785-ab38-963758338c6c"
}
```

## Delete partition

Partitions can be deleted from a block device with the 'delete' API call. Make sure you double check the partition details as the partition is deleted immediately, with no further confirmation:

```nohighlight
maas admin partition delete <node-id> 10 9
```

Successful output from the 'delete' command will look like this:

```nohighlight
Success.
Machine-readable output follows:
```

## Format partition

Partitions can be formatted in a similar way to block devices:

```nohighlight
maas admin partition format <node-id> 10 9 fstype=ext4
```

The output from the 'format' command will be similar to the following:

```nohighlight
Success.
Machine-readable output follows:
{
    "id": 9,
    "used_for": "Unmounted ext4 formatted filesystem",
    "resource_uri": "/MAAS/api/2.0/nodes/4y3h8a/blockdevices/10/partition/9",
    "path": "/dev/disk/by-dname/vda-part1",
    "uuid": "aae082cd-8be0-4a64-ab49-e998abd6ea43",
    "size": 5360320512,
    "bootable": false,
    "type": "partition",
    "filesystem": {
        "uuid": "ea593366-be43-4ea3-b2d5-0adf82085a62",
        "mount_point": null,
        "mount_options": null,
        "fstype": "ext4",
        "label": "
    }
}
```

> You cannot format partitions that are used to make another virtual block device.

## Unformat partition

You can also remove the filesystem from a partition with the 'unformat' API call:

```nohighlight
maas admin partition unformat <node-id> 10 10 fstype=ext4
```

```nohighlight
Success.
Machine-readable output follows:
{
    "bootable": false,
    "path": "/dev/disk/by-dname/vda-part1",
    "filesystem": null,
    "used_for": "Unused",
    "type": "partition",
    "id": 10,
    "size": 5360320512,
    "resource_uri": "/MAAS/api/2.0/nodes/4y3h8a/blockdevices/10/partition/10",
    "uuid": "3d32adbf-9943-4785-ab38-963758338c6c"
}
```

## Mount partition

A formatted partition can be mounted at a given mount point with the 'mount' command.

```nohighlight
maas admin partition mount <node-id> 10 10 mount_point=/srv
```

The mount point and the filesystem is visible in the output from the command:

```nohighlight
Success.
Machine-readable output follows:
{
    "bootable": false,
    "id": 10,
    "resource_uri": "/MAAS/api/2.0/nodes/4y3h8a/blockdevices/10/partition/10",
    "path": "/dev/disk/by-dname/vda-part1",
    "uuid": "3d32adbf-9943-4785-ab38-963758338c6c",
    "used_for": "ext4 formatted filesystem mounted at /srv",
    "size": 5360320512,
    "type": "partition",
    "filesystem": {
        "uuid": "1949a5fb-f7bd-4ada-8ba5-d06d3f5857a8",
        "mount_options": ",
        "label": ",
        "fstype": "ext4",
        "mount_point": "/srv"
    }
}
```

## Unmount partition

A previous mounted partition can be unmounted with the 'unmount' command:

```nohighlight
maas admin partition unmount 4y3h8a 10 10
```

After successfully running this command, the mount point will show as 'null' in the output:

```nohighlight
Success.
Machine-readable output follows:
{
    "bootable": false,
    "id": 10,
    "resource_uri": "/MAAS/api/2.0/nodes/4y3h8a/blockdevices/10/partition/10",
    "path": "/dev/disk/by-dname/vda-part1",
    "uuid": "3d32adbf-9943-4785-ab38-963758338c6c",
    "used_for": "Unmounted ext4 formatted filesystem",
    "size": 5360320512,
    "type": "partition",
    "filesystem": {
        "uuid": "1949a5fb-f7bd-4ada-8ba5-d06d3f5857a8",
        "mount_options": null,
        "label": ",
        "fstype": "ext4",
        "mount_point": null
    }
    "type": "partition",
    "id": 3,
    "size": 2000003072
}
```
