This page explains how to configure custom storage layouts for MAAS-deployed machines.  Note that custom storage is only available for MAAS versions 3.1 and higher.

MAAS version 3.1 and higher allow you to define a custom storage layout for a machine, via a custom commissioning script. You must upload a script which conforms to the following rules:

- it must run after the `40-maas-01-machine-resources` script and before the `50-maas-01-commissioning` one, so it should have a name that starts with anything between `41-` and `49-`. This ensures the script can access the JSON file created by the former which provides info about the machine hardware and network resources. In addition, the custom script can directly inspect the machine it's running on to determine how to configure storage.
- it can read machine hardware/network information from the JSON file at the path specified by `$MAAS_RESOURCES_FILE`
- it must output a JSON file at the path specified by `$MAAS_STORAGE_CONFIG_FILE` with the desired storage layout
- names of disks provided in the custom layout must match the ones detected by MAAS and provided in the resources file.

## Config format

The configuration contains two main sections:
- `layout`, which lists the desired storage layout in terms of disks and volumes, along with their setup (partitions, volumes, ...).
  This consists of a dictionary of device names and their configuration. Each device must have a `type` property (see below for supported types).
- `mounts`, which lists the desired filesystem mount points.
  As an example:

```nohighlight
"mounts": {
  "/": {
    "device": "sda2",
    "options": "noatime"
  },
  "/boot/efi": {
    "device": "sda1"
  },
  "/data": {
    "device": "raid0"
  }     
}
```

A complete `$MAAS_STORAGE_CONFIG_FILE` would look like this:

```nohighlight
{
    "layouts": {
        "sda": {
           ...
        },
        "raid0": {
           ...
        },
        ...
    },
    "mounts": {
       "/": {
           ...
       },
       ...
    }
}
```



The following device types are supported in the `"layout"` section:

## Disk

```nohighlight
"sda": {
  "type": "disk",
  "ptable": "gpt",
  "boot": true,
  "partitions": [
    {
      "name": "sda1",
      "fs": "vfat",
      "size": "100M"
      "bootable": true,
    }
  ]
}
```
A `disk` entry defines a physical disk.
The following details can be specified:
- the partition table type (`ptable`), which can be `gpt` or `mbr`
- whether it should be selected as `boot` disk
- optionally, a list of partitions to create, with their `size` and filesystem type (`fs`)

## LVM

```nohighlight
"lvm0": {
  "type": "lvm",
  "members": [
    "sda1",
    "sdb1",
  ],
  "volumes": [
    {
      "name": "data1",
      "size": "5G",
      "fs": "ext4"
    },
    {
      "name": "data2",
      "size": "7G",
      "fs": "btrfs"
    }
  ]
}
```

An `lvm` entry defines a VG (volume group) composed by a set of disks or partitions (listed as `members`). Optionally it's possible to specify the the LVs (logical volumes) to create.
Those are defined similarly to partitions, with a name and size (and optionally the filesystem).

## Bcache

```nohighlight
"bcache0": {
  "type": "bcache",
  "cache-device": "sda",
  "backing-device": "sdf3",
  "cache-mode": "writeback",
  "fs": "ext4"
}
```

A `bcache`  entry must specify a device to use as cache and one to use as storage. Both can be either a partition or a disk.
Optionally the `cache-mode` for the Bcache can be specified.

## RAID

```nohighlight
"myraid": {
  "type": "raid",
  "level": 5,
  "members": [
    "sda",
    "sdb",
    "sdc",
  ],
  "spares": [
    "sdd",
    "sde"
  ],
  "fs": "btrfs"
```

A `raid` entry defines a RAID with a set of member devices.
Spare devices can also be specified.



## Config examples

Here's a few examples of custom storage layout configurations that a script could output to the `$MAAS_STORAGE_CONFIG_FILE`. The examples assumes that the machine has 5 disks (named `sda` to `sde`).

Note that there's no need to add entries for those devices in the `layout` section if the disks are not explicitly partitioned, but just used by other devices (e.g. RAID or LVM).

## Simple single-disk layout with GPT partitioning
```nohighlight
{
  "layout": {
    "sda": {
      "type": "disk",
      "ptable": "gpt",
      "boot": true,
      "partitions": [
        {
          "name": "sda1",
          "fs": "vfat",
          "size": "500M",
          "bootable": true
        },
        {
          "name": "sda2",
          "size": "5G",
          "fs": "ext4"
        },
        {
          "name": "sda3",
          "size": "2G",
          "fs": "swap"
        },
        {
          "name": "sda4",
          "size": "120G",
          "fS": "ext4"
        }
      ]
    }
  },
  "mounts": {
    "/": {
      "device": "sda2",
      "options": "noatime"
    },
    "/boot/efi": {
      "device": "sda1"
    },
    "/data": {
      "device": "sda4"
    },
    "none": {
      "device": "sda3"
    }
  }
}
```
In the `mounts` section, options for mount points can be specified. For swap, an entry must be present (with any unique name that doesn't start with a `/`), otherwise the swap will be created but not activated.

## RAID 5 setup (with spare devices)
```nohighlight
{
  "layout": {
    "storage": {
      "type": "raid",
      "level": 5,
      "members": [
        "sda",
        "sdb",
        "sdc"
      ],
      "spares": [
        "sdd",
        "sde"
      ],
      "fs": "btrfs"
    }
  },
  "mounts": {
    "/data": {
      "device": "storage"
    }
  }
}
```
Both full disks and partitions can be used as RAID members.

## LVM with pre-defined volumes
```nohighlight
{
  "layout": {
    "storage": {
      "type": "lvm",
      "members": [
        "sda",
        "sdb",
        "sdc",
        "sdd"
      ],
      "volumes": [
        {
          "name": "data1",
          "size": "1T",
          "fs": "ext4"
        },
        {
          "name": "data2",
          "size": "2.5T",
          "fs": "btrfs"
        }
      ]
    }
  },
  "mounts": {
    "/data1": {
      "device": "data1"
    },
    "/data2": {
      "device": "data2"
    }
  }
}
```
If no volumes are specified, the volume group is still created.

## Bcache
```nohighlight
{
  "layout": {
     "data1": {
      "type": "bcache",
      "cache-device": "sda",
      "backing-device": "sdb",
      "cache-mode": "writeback",
      "fs": "ext4"
    },
    "data2": {
      "type": "bcache",
      "cache-device": "sda",
      "backing-device": "sdc",
      "fs": "btrfs"
    }
  },
  "mounts": {
    "/data1": {
      "device": "data1"
    },
    "/data2": {
      "device": "data2"
    }
  }
}
```
The same cache set can be used by different bcaches by specifying the same `backing-device` for them.

## LVM on top of RAID with Bcache
```nohighlight
{
  "layout": {
    "bcache0": {
      "type": "bcache",
      "backing-device": "sda",
      "cache-device": "sdf"
    },
    "bcache1": {
      "type": "bcache",
      "backing-device": "sdb",
      "cache-device": "sdf"
    },
    "bcache2": {
      "type": "bcache",
      "backing-device": "sdc",
      "cache-device": "sdf"
    },
    "bcache3": {
      "type": "bcache",
      "backing-device": "sdd",
      "cache-device": "sdf"
    },
    "bcache4": {
      "type": "bcache",
      "backing-device": "sde",
      "cache-device": "sdf"
    },
    "raid": {
      "type": "raid",
      "level": 5,
      "members": [
        "bcache0",
        "bcache1",
        "bcache2"
      ],
      "spares": [
        "bcache3",
        "bcache4"
      ]
    },
    "lvm": {
      "type": "lvm",
      "members": [
        "raid"
      ],
      "volumes": [
        {
          "name": "root",
          "size": "10G",
          "fs": "ext4"
        },
        {
          "name": "data",
          "size": "3T",
          "fs": "btrfs"
        }
      ]
    }
  },
  "mounts": {
   "/": {
      "device": "root"
    },
    "/data": {
      "device": "data"
    }
  }
}
```
The RAID is created by using 5 bcache devices, each one using a different disk and the same SSD cache device. LVM is created on top of the RAID device and volumes are then created in it, to provide partitions.