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