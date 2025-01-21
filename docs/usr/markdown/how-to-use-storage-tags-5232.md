> *Errors or typos? Topics missing? Hard to read? <a href="https://docs.google.com/forms/d/e/1FAIpQLScIt3ffetkaKW3gDv6FDk7CfUTNYP_HGmqQotSTtj2htKkVBw/viewform?usp=pp_url&entry.1739714854=https://maas.io/docs/using-storage-tags" target = "_blank">Let us know.</a>*

This page explains how to use MAAS storage tags. In order to create or modify block device tags, the device has to be in an "available" state, with no active partitions.

## Create block device tags (UI)

To create and assign tags to block devices, select *Machines* > machine > *Storage* > *Available disks and partitions* > *Edit...*. Add *Tags* as desired, and *Save*.

## Delete block device tags (UI)

To create and assign tags to block devices, select *Machines* > machine > *Storage* > *Available disks and partitions* > *Edit...*. Remove tags by selecting the *X* on the tag name, and *Save* your changes.

## List storage tags (UI)

To see block device and partition tags in the UI, you can list all storage links by using the filter tool on the machine list. Select *Machines* > *Filters* > *Storage tags*. Select tag(s) to filter against; the screen will immediately narrow to match your selections. Uncheck tags to return to the previous view.

## View block device tags (UI)

To view all tags associated with block devices on a given machine, select *Machines* > machine > *Storage* > *Available disks and partitions*.

## View partition tags (UI)

To view all tags associated with partitions on a given machine, select *Machines* > machine > *Storage* > *Available disks and partitions*.

## Find block device ID (CLI)

Block devices do not exist apart from the physical or virtual machines to which they are attached. Finding the ID of the block device that interests you requires starting with a particular machine, in a command form that looks like this:

```nohighlight
maas $PROFILE block-devices read $SYSTEM_ID \
| jq -r '(["system_id","block_device_id","path","avail_size"]
|(.,map(length*"-"))),(.[]|[.system_id,.id,.path,.available_size])
| @tsv' | column -t
```

For example:

```nohighlight
maas admin block-devices read qk4b3g \
| jq -r '(["system_id","block_device_id","path","avail_size"]
|(.,map(length*"-"))),(.[]|[.system_id,.id,.path,.available_size])
| @tsv' | column -t
```

This example would produce output that looks something like this:

```nohighlight
system_id  block_device_id  path                    avail_size
---------  ---------------  ----                    ----------
qk4b3g     10               /dev/disk/by-dname/sda  0
```

The `path` component is printed to help you confirm that you are choosing the right block device when there are several present. The `avail-size` column will tell you whether you can operate on that block device at all. If the available size is "0," for example, you can't set a block device tag on any part of that drive. Instead, you'd want to see something like this:

```nohighlight
system_id  block_device_id  path                    avail_size
---------  ---------------  ----                    ----------
xn8taa     8                /dev/disk/by-dname/sda  1996488704
```

## Assign block device tags (CLI)

You can only assign tags to a block device that is available. You can find out whether the block device is available at all when you [discover its ID](#heading--discover-the-id-of-your-block-device).

To assign an existing tag to a block device, you would type a command formulated like this:

```nohighlight
maas $PROFILE block-device add-tag $SYSTEM_ID $BLOCK_DEVICE_ID tag=$TAG_NAME
```

If you're not sure about the ID of your block device, you can [look it up](#heading--discover-the-id-of-your-block-device).

For example:

```nohighlight
maas admin block-device add-tag xn8taa 8 tag=farquar
```

If this command succeeds, it will display `Success`, followed by a JSON sequence describing the new state of the block device.

Note that if you try to add a tag to a block device that is not available, that is, to a block device that is in use, you will get a result like this:

```nohighlight
Not Found
```

## Remove block device tags (CLI)

You can only remove tags from a block device that is available. You can find out whether the block device is available at all when you [discover its ID](#heading--discover-the-id-of-your-block-device).

To remove an assigned tag from a block device, you would type a command formulated like this:

```nohighlight
maas $PROFILE block-device remove-tag $SYSTEM_ID $BLOCK_DEVICE_ID tag=$TAG_NAME
```

If you're not sure about the ID of your block device, you can [look it up](#heading--discover-the-id-of-your-block-device).

For example:

```nohighlight
maas admin block-device remove-tag xn8taa 8 tag=farquar
```

If this command succeeds, it will display `Success`, followed by a JSON sequence describing the new state of the block device.

Note that if you try to remove a tag from a block device that is not available, that is, from a block device that is in use, you will get a result like this:

```nohighlight
Not Found
```

On the other hand, if you try to remove a tag that is not assigned to the block device you've chosen, MAAS will simply return `Success`, followed by a JSON sequence describing the current state of the block device.

## List tags for all block devices (CLI)

To list tags for all block devices associated with a physical or virtual machine, you can use a command of this form:

```nohighlight
maas $PROFILE block-devices read $SYSTEM_ID | jq -r '(["id","tags"]|(.,map(length*"-"))),(.[]|[.id,.tags[]]) | @tsv' | column -t
```

For example:

```nohighlight
maas admin block-devices read xn8taa | jq -r '(["id","tags"]|(.,map(length*"-"))),(.[]|[.id,.tags[]]) | @tsv' | column -t
```

This command would produce output similar to this:

```nohighlight
id  tags
--  ----
8   hello  ssd  trinkoplinko
```

## View tags for one block device (CLI)

To view tags for one specific block device, you can enter a command like this:

```nohighlight
maas $PROFILE block-device read $SYSTEM_ID $BLOCK_DEVICE_ID | jq -r '(["id","tags"]|(.,map(length*"-"))),([.id,.tags[]]) | @tsv' | column -t
```

If you're not sure about the ID of your block device, you can [look it up](#heading--discover-the-id-of-your-block-device).

For example:

```nohighlight
maas admin block-device read xn8taa 8 | jq -r '(["id","tags"]|(.,map(length*"-"))),([.id,.tags[]]) | @tsv' | column -t
```

This command would produce output similar to this:

```nohighlight
id  tags
--  ----
8   hello  ssd  trinkoplinko
9   20gig  ssd
10  250Gs  ssd
```

## Find partition ID (CLI)

Partitions do not exist apart from the block devices on which they reside. Finding the ID of the partition that interests you requires starting with a particular machine and block device, similar to this command:

```nohighlight
maas $PROFILE partitions read $SYSTEM_ID $BLOCK_DEVICE_ID \
| jq -r '(["system_id","block_dev_id","part_id","path"]
|(.,map(length*"-"))),(.[]|[.system_id,.device_id,.id,.path])
|@tsv' | column -t
```

For example:

```nohighlight
maas admin partitions read xn8taa 8 \
| jq -r '(["system_id","block_dev_id","part_id","path"]
|(.,map(length*"-"))),(.[]|[.system_id,.device_id,.id,.path])
|@tsv' | column -t
```

This example would produce output that looks something like this:

```nohighlight
system_id  block_dev_id  part_id  path
---------  ------------  -------  ----
xn8taa     8             67       /dev/disk/by-dname/sda-part1
```

The `path` component is printed to help you confirm that you are choosing the right partition, when there are several present.

## Assign partition tags (CLI)

You can only assign tags to a partition that is available. To assign an existing tag to a partition, you would type a command formulated like this:

```nohighlight
maas $PROFILE partition add-tag $SYSTEM_ID $BLOCK_DEVICE_ID $PARTITION_ID tag=$TAG_NAME
```

If you're not sure about the ID of your partition, you can [look it up](#heading--discover-the-id-of-your-partition).

For example:

```nohighlight
maas admin partition add-tag xn8taa 8 67 tag=farquar
```

If this command succeeds, it will display `Success`, followed by a JSON sequence describing the new state of the partition.

Note that if you try to add a tag to a partition that is not available, that is, to a partition that is in use, you will get a result like this:

```nohighlight
Not Found
```

## Remove partition tags (CLI)

You can only remove tags from a partition that is available. To remove a existing tag from a partition, you would type a command formulated like this:

```nohighlight
maas $PROFILE partition remove-tag $SYSTEM_ID $BLOCK_DEVICE_ID $PARTITION_ID tag=$TAG_NAME
```

If you're not sure about the ID of your partition, you can [look it up](#heading--discover-the-id-of-your-partition).

For example:

```nohighlight
maas admin partition remove-tag xn8taa 8 67 tag=farquar
```

If this command succeeds, it will display `Success`, followed by a JSON sequence describing the new state of the partition.

Note that if you try to remove a tag from a partition that is not available, that is, from a partition that is in use, you will get a result like this:

```nohighlight
Not Found
```

On the other hand, if you try to remove a tag that is not assigned to the partition you've chosen, MAAS will simply return `Success`, followed by a JSON sequence describing the current state of the partition.

## List tags for all partitions (CLI)

To list tags for all partitions of a particular block device, use a command like this one:

```nohighlight
maas $PROFILE partitions read $SYSTEM_ID $BLOCK_DEVICE_ID \
| jq -r '(["id","tags"]
|(.,map(length*"-"))),(.[]|[.id,.tags[]])
| @tsv' | column -t
```

For example:

```nohighlight
maas admin partitions read xn8taa 8 \
| jq -r '(["id","tags"]
|(.,map(length*"-"))),(.[]|[.id,.tags[]])
| @tsv' | column -t
```

A command like this should return output similar to the following:

```nohighlight
id  tags
--  ----
54  farquar swap opendisk
67  foobar  farquar
97  foobar
```

## View tags for one partition (CLI)

To view tags for one partition, enter

 a command like this:

```nohighlight
maas $PROFILE partition read $SYSTEM_ID $BLOCK_DEVICE_ID $PARTITION_ID | jq -r '(["id","tags"]|(.,map(length*"-"))),([.id,.tags[]]) | @tsv' | column -t
```

If you're not sure about the ID of your partition, you can [look it up](#heading--discover-the-id-of-your-partition).

For example:

```nohighlight
maas admin partition read xn8taa 8 67 | jq -r '(["id","tags"]|(.,map(length*"-"))),([.id,.tags[]]) | @tsv' | column -t
```

This command would produce output similar to this:

```nohighlight
id  tags
--  ----
67  farquar foobar
```