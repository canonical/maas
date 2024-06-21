> *Errors or typos? Topics missing? Hard to read? <a href="https://docs.google.com/forms/d/e/1FAIpQLScIt3ffetkaKW3gDv6FDk7CfUTNYP_HGmqQotSTtj2htKkVBw/viewform?usp=pp_url&entry.1739714854=https://maas.io/docs/using-controller-tags" target = "_blank">Let us know.</a>*

If you have a large MAAS network, with multiple region and rack controllers, controller tags can help you classify, search, and organise them.

## Discover the ID of your region controller(s) (CLI)

You can discover the ID of your region controller(s) with the following command:

```nohighlight
maas $PROFILE region-controllers read \
| jq -r '(["name","id"]
|(.,map(length*"-"))),(.[]|[.hostname,.system_id])
| @tsv' | column -t
```

For example:

```nohighlight
maas admin region-controllers read \
| jq -r '(["name","id"]
|(.,map(length*"-"))),(.[]|[.hostname,.system_id])
| @tsv' | column -t
```

Typical output would look something like this:

```nohighlight
name                         id
----                         --
bill-Lenovo-Yoga-C740-15IML  86xya8
```

## Assign tags to a region controller (CLI)

To add tags to a region controller, you can use a command of this form:

```nohighlight
maas $PROFILE tag update-nodes $TAG_NAME add=$SYSTEM_ID
```

If you need to find the ID of your region controller(s), you can [look it up](#heading--discover-the-id-of-your-region-controllers).

For example:

```nohighlight
maas admin tag update-nodes virtual add=86xya8
```

This command produces output similar to the following:

```nohighlight
Success.
Machine-readable output follows:
{
    "added": 1,
    "removed": 0
}
```

You can check your work by [listing all tags for your region controllers](#heading--list-tags-for-all-region-controllers).
## Remove tags from a region controller (CLI)

To remove tags from a region controller, you can use a command like this:

```nohighlight
maas $PROFILE tag update-nodes $TAG_NAME remove=$SYSTEM_ID
```

If you need to find the ID of your region controller(s), you can [look it up](#heading--discover-the-id-of-your-region-controllers).

For example:

```nohighlight
maas admin tag update-nodes virtual remove=86xya8
```

This command produces output similar to the following:

```nohighlight
Success.
Machine-readable output follows:
{
    "added": 0,
    "removed": 1
}
```

You can check your work by [listing all tags for your region controllers](#heading--list-tags-for-all-region-controllers).

## List tags for all region controllers (CLI)

To list tags for all region controllers, you can use a command similar to this:

```nohighlight
maas $PROFILE region-controllers read | jq -r '(["hostname","sysid","tags"]|(.,map(length*"-"))),(.[]|[.hostname,.system_id,.tag_names[]]) | @tsv' | column -t
```

For example:

```nohighlight
maas admin region-controllers read | jq -r '(["hostname","sysid","tags"]|(.,map(length*"-"))),(.[]|[.hostname,.system_id,.tag_names[]]) | @tsv' | column -t
```

This will produce output something like this:

```nohighlight
hostname                     sysid   tags
--------                     -----   ----
bill-Lenovo-Yoga-C740-15IML  86xya8  virtual  lxd-vm-host
```

## View tags for one region controller (CLI)

To view tags for a specific region controller, you can try a command like this:

```nohighlight
maas $PROFILE region-controller read $SYSTEM_ID | jq -r '(["hostname","sysid","tags"]|(.,map(length*"-"))),([.hostname,.system_id,.tag_names[]]) | @tsv' | column -t
```

If you need to find the ID of your region controller(s), you can [look it up](#heading--discover-the-id-of-your-region-controllers).

For example:

```nohighlight
maas admin region-controller read 86xya8 \
| jq -r '(["hostname","sysid","tags"]
|(.,map(length*"-"))),([.hostname,.system_id,.tag_names[]])
| @tsv' | column -t
```

This should produce output similar to the following:

```nohighlight
hostname                     sysid   tags
--------                     -----   ----
bill-Lenovo-Yoga-C740-15IML  86xya8  virtual  lxd-vm-host
```



## Discover the ID of your rack controller(s) (CLI)

You can discover the ID of your rack controller(s) with the following command:

```nohighlight
maas $PROFILE rack-controllers read \
| jq -r '(["name","id"]
|(.,map(length*"-"))),(.[]|[.hostname,.system_id])
| @tsv' | column -t
```

For example:

```nohighlight
maas admin rack-controllers read \
| jq -r '(["name","id"]
|(.,map(length*"-"))),(.[]|[.hostname,.system_id])
| @tsv' | column -t
```

Typical output would look something like this:

```nohighlight
name                         id
----                         --
bill-Lenovo-Yoga-C740-15IML  86xya8
```

## Assign tags to a rack controller (CLI)

To add tags to a rack controller, you can use a command of this form:

```nohighlight
maas $PROFILE tag update-nodes $TAG_NAME add=$SYSTEM_ID
```

If you need to find the ID of your rack controller(s), you can [look it up](#heading--discover-the-id-of-your-rack-controllers).

For example:

```nohighlight
maas admin tag update-nodes virtual add=86xya8
```

This command produces output similar to the following:

```nohighlight
Success.
Machine-readable output follows:
{
    "added": 1,
    "removed": 0
}
```

You can check your work by [listing all tags for your rack controllers](#heading--list-tags-for-all-rack-controllers).

## Remove tags from a rack controller (CLI)

To remove tags from a rack controller, you can use a command like this:

```nohighlight
maas $PROFILE tag update-nodes $TAG_NAME remove=$SYSTEM_ID
```

If you need to find the ID of your rack controller(s), you can [look it up](#heading--discover-the-id-of-your-rack-controllers).

For example:

```nohighlight
maas admin tag update-nodes virtual remove=86xya8
```

This command produces output similar to the following:

```nohighlight
Success.
Machine-readable output follows:
{
    "added": 0,
    "removed": 1
}
```

You can check your work by [listing all tags for your rack controllers](#heading--list-tags-for-all-rack-controllers).

## List tags for all rack controllers (CLI)

To list tags for all rack controllers, you can use a command similar to this:

```nohighlight
maas $PROFILE rack-controllers read | jq -r '(["hostname","sysid","tags"]|(.,map(length*"-"))),(.[]|[.hostname,.system_id,.tag_names[]]) | @tsv' | column -t
```

For example:

```nohighlight
maas admin rack-controllers read | jq -r '(["hostname","sysid","tags"]|(.,map(length*"-"))),(.[]|[.hostname,.system_id,.tag_names[]]) | @tsv' | column -t
```

This will produce output something like this:

```nohighlight
hostname                     sysid   tags
--------                     -----   ----
bill-Lenovo-Yoga-C740-15IML  86xya8  virtual  lxd-vm-host
```

## View tags for one rack controller (CLI)

To view tags for a specific rack controller, you can try a command like this:

```nohighlight
maas $PROFILE rack-controller read $SYSTEM_ID | jq -r '(["hostname","sysid","tags"]|(.,map(length*"-"))),([.hostname,.system_id,.tag_names[]]) | @tsv' | column -t
'''

If you need to find the ID of your rack controller(s), you can [look it up](#heading--discover-the-id-of-your-rack-controllers).

For example:

```nohighlight
maas admin rack-controller read 86xya8 \
| jq -r '(["hostname","sysid","tags"]
|(.,map(length*"-"))),([.hostname,.system_id,.tag_names[]])
| @tsv' | column -t
```

This should produce output similar to the following:

```nohighlight
hostname                     sysid   tags
--------                     -----   ----
bill-Lenovo-Yoga-C740-15IML  86xya8  virtual  lxd-vm-host
```

## Create controller tags (UI)

To create and assign a controller tag, select *Controllers* > controller > *Configuration* > *Controller configuration* > *Edit* > *Tags*. Enter a new tag and *Save changes* to assign it to the controller.

## Delete controller tags (UI)

To remove (and possibly delete) a controller tag, select *Controllers* > controller > *Configuration* > *Controller configuration* > *Edit* > *Tags*. Click the *X* on the tag name to delete it, then select *Save changes*.

## View controller tags (UI)

To view controller tags, select *Controllers* > controller > *Configuration*. View the tags for this controller under the *Tags* row.