> *Errors or typos? Topics missing? Hard to read? <a href="https://docs.google.com/forms/d/e/1FAIpQLScIt3ffetkaKW3gDv6FDk7CfUTNYP_HGmqQotSTtj2htKkVBw/viewform?usp=pp_url&entry.1739714854=https://maas.io/docs/tagging-machines-and-controllers" target = "_blank">Let us know.</a>*

This page explains how to work with [tags](/t/how-to-label-machines/6200).

## Naming tags

When working with tags, there are some universal rules you need to follow: 

1. Tag names can include any combination of alphabetic letters (a-zA-Z), numbers (0-9), dashes (-) and underscores (_).
2. Tag names can be a maximum of 256 characters in length.
3. Tag names *cannot* include spaces.

In general, names that do not conform to these rules cannot be created.

## Download H/W info (UI)

To download hardware configuration information in XML format, select *Machines* > machine (allocated or deployed) > *Logs* > *Installation output* > *Download* > *Machine output (XML)*

You can [learn more about the returned information](https://ezix.org/project/wiki/HardwareLiSter)**^** if desired. Note that:

- Size and capacity can have various meanings depending on the device
- The size of a node is always equal to its capacity
- Serial refers to the device’s serial number, but is used to report the MAC address for network devices, GUID for disk partition.

You can also find device classes from the same sources. 

## Adding tags (3.2++/UI)

In the MAAS UI, creating and assigning tags is a combined operation; that is, you create tags as you assign them, rather than creating them first. Creating tags in the UI is a little different user experience: there is a self-loading completion menu that collects all tags of a similar type. This completion menu helps you avoid misspelling tags when entering them more than once; otherwise, you might not be able to group and filter tags properly. It also makes tag entry more efficient.

To create and assign a tag to specific machines, select *Machines* > machine > *Take action* > *Tag*. In the pop-up tag dialogue, enter your proposed tag name in *Search existing or add new tags*, then select *Create tag {tag-name}*. Fill in the form:

- Optionally enter a *Comment*.

- Optionally enter *Kernel options*.

Select *Create and add to tag changes* > *Save*. You can confirm your changes by hovering over the *Tags* list in the *Machines* screen.

## Adding tags (3.1--/UI)

In the MAAS UI, creating and assigning tags is a combined operation; that is, you create tags as you assign them, rather than creating them first. Creating tags in the UI is a little different user experience: there is a self-loading completion menu that collects all tags of a similar type. This completion menu helps you avoid misspelling tags when entering them more than once; otherwise, you might not be able to group and filter tags properly. It also makes tag entry more efficient.

The process for creating and assigning tags in the UI is generally the same for all tag types: Enter the name of the tag in the *Tags box and press the return key. Select the appropriate completion button to register your changes. The tag you just entered will now be added to the tag auto complete list, in alphabetical order, for re-use with other machines.

## Adding tags (CLI)

With the CLI, you can create a tag with the following command:

```nohighlight
maas $PROFILE tags create name=$TAG_NAME comment='$TAG_COMMENT'
```

For example, depending upon your system configuration, you might type a command similar to this one:

```nohighlight
maas admin tags create name="new_tag" comment="a new tag for test purposes"
```

When the command is successful, you should see output similar to this:

```nohighlight
Success.
Machine-readable output follows:
{
    "name": "new_tag",
    "definition": ",
    "comment": "a new tag for test purposes",
    "kernel_opts": ",
    "resource_uri": "/MAAS/api/2.0/tags/new_tag/"
}
```

## Kernel option tags

*This feature is only available via the MAAS CLI.*

You can create tags with embedded kernel boot options. When you apply such tags to a machine, those kernel boot options will be applied to that machine on the next deployment.

To create a tag with embedded kernel boot options, use the following command:

```nohighlight
maas $PROFILE tags create name='$TAG_NAME' \
    comment='$TAG_COMMENT' kernel_opts='$KERNEL_OPTIONS'
```

For example:

```nohighlight
maas admin tags create name='nomodeset_tag' \
    comment='nomodeset_kernel_option' kernel_opts='nomodeset vga'
```

This command yields the following results:

```nohighlight
Success.
Machine-readable output follows:
{
    "name": "nomodeset_tag",
    "definition": ",
    "comment": "nomodeset_kernel_option",
    "kernel_opts": "nomodeset vga",
    "resource_uri": "/MAAS/api/2.0/tags/nomodeset_tag/"
}
```

You can check your work with a modified form of the listing command:

```nohighlight
maas admin tags read | jq -r \
'(["tag_name","tag_comment","kernel_options"]
|(.,map(length*"-"))),(.[]|[.name,.comment,.kernel_opts]) 
| @tsv' | column -t
```

This should give you results something like this:

```nohighlight
tag_name             tag_comment                  kernel_options                     
--------             -----------                  --------------                     
virtual                                                                              
new_tag              a-new-tag-for-test-purposes                                     
pod-console-logging  console=tty1                 console=ttyS0                      
nomodeset_tag        nomodeset_kernel_option      nomodeset       vga
```

## Removing tags (3.2++/UI)

You have two choices when it comes to eliminating tags from machines in your MAAS instance: you can delete them from all machines, or simply remove them from specific machines.

## Deleting tags from all machines at once

To delete tags from all machines, select *Machines* > *Tags* > trash can icon > *Delete*. The tag will be unassigned from all machines and deleted. There is no undo.

## Removing a tag from specific machines

To remove a tag only from specific machines, select *Machines* > machine(s) by checkbox > *Take action* > *Tag*. For each tag you wish to unassign, select *Remove*. When done, select *Save* to finalise your changes.

## Removing tags (3.1--/UI)

With the MAAS UI, you remove tags, rather than explicitly deleting them. Tags are "deleted" when you have removed them from all machines:

1. Find the *Tags* box.

2. Click the *X* next to the tag you wish to remove.

3. When you're done, select the appropriate completion button to register your changes.

Note that the tag you just removed will be deleted from  the tag auto complete list when it is no longer assigned to any  machines.

## Removing tags (CLI)

With the CLI, you can delete a tag with the following command:

```nohighlight
maas $PROFILE tag delete $TAG_NAME
```

For example, depending upon your system configuration, you might type a command similar to this one:

```nohighlight
maas admin tag delete zorko
```

When the command is successful, you should see output similar to this:

```nohighlight
Success.
Machine-readable output follows:
```

Note that there is no actual "Machine-readable output" produced by this command, in most cases. Also note that remove a tag removes it from any nodes where you may have assigned it, but does not affect those nodes in any other way.

## Unassign tags (UI)

To unassign tags from machines:

1. Select *Machines*.

2. Select the checkbox(es) next to the machine(s) you wish to untag.

3. Select *Take action* > *Tag*. A table of tags appears at the top of the screen.

4. For each tag you wish to unassign, select *Remove*. The text will change to *Discard* with an *X* to the right.

5. If you want to undo a choice before saving, click the *X* to right of *Discard* to undo the proposed change.

6. When you're satisfied with your new tag configuration, select *Save* to finalise and register your choice(s).

> Automatic tags cannot be unassigned manually. You can either update or delete automatic tags.

You can also unassign tags individually by going to *Machines >> {machine-name} >> Configuration >> Tags >> Edit*. The *Tags* table functions exactly the same as what's described above.

## List tagged nodes

To see how many nodes (Machines, controllers, devices) are tagged, search for GRUB_CMDLINE_LINUX_DEFAULT in the "Installation output" tab of the machine details page. That log should stay around for the lifetime of the deployment of the machine. The log gets overwritten when you redeploy the machine. For example:

```nohighlight
GRUB_CMDLINE_LINUX_DEFAULT="sysrq_always_enabled dyndbg='file drivers/usb/* +p' console=tty1 console=ttyS0"
```

## Update tags

*This feature is only available via the MAAS CLI.*

You can update a tag (e.g., a tag comment) like this:

```nohighlight
maas $PROFILE tag update $TAG_NAME comment='$TAG_COMMENT'
```

For example:

```nohighlight
maas admin tag update new_tag comment="a-new-tag-for-test-purposes"
```

This should return an output similar to this one:

```nohighlight
Success.
Machine-readable output follows:
{
    "name": "new_tag",
    "definition": ",
    "comment": "a-new-tag-for-test-purposes",
    "kernel_opts": ",
    "resource_uri": "/MAAS/api/2.0/tags/new_tag/"
}
```

## List all tags

*This feature is only available via the MAAS CLI.*

You can list all tags that currently exist in this MAAS with a command of the form:

```nohighlight
maas $PROFILE tags read | jq -r '(["tag_name","tag_comment"]|(.,map(length*"-"))),(.[]|[.name,.comment]) | @tsv' | column -t
```

For example:

```nohighlight
maas admin tags read | jq -r '(["tag_name","tag_comment"]|(.,map(length*"-"))),(.[]|[.name,.comment]) | @tsv' | column -t
```

Your output might look like this:

```nohighlight
tag_name  tag_comment
--------  -----------
virtual   
new_tag   a-new-tag-for-test-purposes
```

## Rebuild a tag

*This feature is only available via the MAAS CLI.*

If you need to update tags for all machines – without having to recommission them – you can accomplish this with the rebuild command:

```nohighlight
maas $PROFILE tag rebuild $TAG
```

This command automatically applies the tag to all machines regardless of state, even machines that are actively deployed. For example:

```nohighlight
maas admin tag rebuild virtual
```

This command would produce output similar to the following:

```nohighlight
Success.
Machine-readable output follows:
{
    "rebuilding": "virtual"
}
```

## Automatic tags

MAAS 3.2 and above provide greatly expanded tagging capability (through the UI only). You can auto-apply tags to machines that match a custom XPath expression. Setting up an automatic tag lets you recognise special hardware characteristics and settings, e.g., the gpu passthrough.

## Creating automatic tags (3.4)

To create automatic tags, select *Organisation > Tags* > *Create new tag* and fill in the form:

- Enter the *Tag name*.

- Optionally enter a *Comment*.

- Optionally enter *Kernel options*.

- Enter an XPath-based *Definition*. A tag is considered automatic when the definition field is filled with an XPath expression. The current version of our UI will only validate if your XPath expression is valid or not, but it will not show you which machines it will apply to before you create the tag.

When done, select *Save* to register your changes. Once an automatic tag is created the screen will initially show that 0 machines are tagged. That is because MAAS is running a background task to auto-apply the tag to matching machines. It can take some time to see that the number of machines tagged is populating. 

>**Pro tip**: Kernel options will be applied at boot time. So by default kernel options will not be applied to any machines until they are deployed. If machines are deployed before they are tagged, the kernel option will be applied when these machines are redeployed.

## Change tag definitions

To change tag definitions: 

1. Select *Organisation > Tags*.

2. Select the pencil icon on the right end of the tag's row.

3. Edit the *Definition*.

4. Select *Save* to register your changes.

Keep in mind that when a new definition is updated, MAAS will re-tag all the machines that match with the new definition. This can take some time, since it is a background process. 

## Creating automatic tags (3.3/3.2)

To create automatic tags, select *Machines* > *Tags* > *Create new tag* and fill in the form:

- Enter the *Tag name*.

- Optionally enter a *Comment*.

- Optionally enter *Kernel options*.

- Enter an XPath-based *Definition*. A tag is considered automatic when the definition field is filled with an XPath expression. The current version of our UI will only validate if your XPath expression is valid or not, but it will not show you which machines it will apply to before you create the tag.

Select *Save* to register your changes. Once an automatic tag is created the screen will initially show that 0 machines are tagged. That is because MAAS is running a background task to auto-apply the tag to matching machines. It can take some time to see that the number of machines tagged is populating. 

Kernel options will be applied at boot time. So, by default, kernel options will not be applied to any machines until they are deployed. If machines are deployed before they are tagged, the kernel option will be applied when these machines are redeployed.

## Update tag definitions (UI)

To update tag definitions: 

1. Select *Machines* > *Tags*.

2. Select the pencil icon on the right end of the tag's row.

3. Edit the *Definition*.

4. Select *Save* to register your changes.

Keep in mind that when a new definition is updated, MAAS will re-tag all the machines that match with the new definition. This can take some time, since it is a background process. 

## Update tag kernel options

*This feature is only available via the MAAS UI.*

To update the kernel options on a tag:

1. Select *Machines* > *Tags*.

2. Select the pencil icon on the right end of the tag's row.

3. Edit the *Kernel options*.

4. Select *Save* to register your changes.

Kernel options can exist for both manual and automatic tags. However, they will be applied during boot time (commissioning and deploying).

If the tagged machines are deployed, the updated kernel option won’t apply until the machines are redeployed. We suggest that you release those machines prior to the update, then redeploy those machines when the kernel options of the tag are updated.