> *Errors or typos? Topics missing? Hard to read? <a href="https://docs.google.com/forms/d/e/1FAIpQLScIt3ffetkaKW3gDv6FDk7CfUTNYP_HGmqQotSTtj2htKkVBw/viewform?usp=pp_url&entry.1739714854=https://maas.io/docs/group-machines" target = "_blank">Let us know.</a>*

This article explains several ways to group machines, including availability zones, resource pools, tags, and annotations.

## Availability zones

Availability zones in MAAS aid in fault tolerance, service performance, and power management. They can represent different physical or network areas, helping to assign resources efficiently and manage system workload and energy consumption.

### List availability zones

To see a list of availability zones: 

* In the MAAS UI, select *AZs* from the top tab bar.

* Via the MAAS CLI, enter the following command:

```nohighlight
    maas $PROFILE zones read \
    | jq -r '(["ZONE","NAME","DESCRIPTION"]
    | (., map(length*"-"))), (.[] | [.id, .name, .description])
    | @tsv' | column -t
```
    
    which produces output similar to:

```nohighlight
    ZONE  NAME         DESCRIPTION
    ----  ----         -----------
    5     BizOffice
    1     default
    4     Inventory
    2     Medications
    3     Payroll
    6     ProServ
```
    
### Add an availability zone

To create an availability zone:

* In the MAAS UI, select *AZs* > *Add AZ* > enter *Name*,*Description* > *Add AZ*.

* Via the CLI, enter the following command:

```nohighlight
    maas $PROFILE zones create name=$ZONE_NAME description=$ZONE_DESCRIPTION
```
    
### Edit an availability zone

To edit an availability zone:

* In the MAAS UI, select *AZs* > <AZ name> > *Edit* > Update *Name*,*Description* > *Update AZ*.

* Via the MAAS CLI, enter a command similar to the following:

```nohighlight
    maas $PROFILE zone update $OLD_ZONE_NAME name=$NEW_ZONE_NAME \
    description=$ZONE_DESCRIPTION
```
    
### Delete an availability zone

To delete an availability zone:

* In the MAAS UI, select *AZs* > <zone name> > *Delete AZ* > *Delete AZ*.

* Via the MAAS CLI, enter a command like this:

```nohighlight
    maas $PROFILE zone delete $ZONE_NAME
```
    
### Assign a machine to an availability zone

To assign a machine to an availability zone:

* In the MAAS 3.4 UI, select *Machines* > choose machines > *Categorise* > *Set zone* > choose *Zone* > *Set zone for machine*.

* With the UI for all other MAAS versions, select *Machines* > choose machines > *Take action* > *Set zone* > choose *Zone* > *Set zone for machine*.

* Via the MAAS CLI, first retrieve the machine's system ID like this:

```nohighlight
    maas PROFILE machines read | jq '.[] | .hostname, .system_id'
```
    
    Then enter the following command, using the system ID you just retrieved:
    
```nohighlight
    maas admin machine update $SYSTEM_ID zone=$ZONE_NAME
```
    
### Deploy a machine in a particular zone (CLI)

To deploy in a particular zone:

1. First acquire the machine, assigning it to the particular zone:

```nohighlight
    maas $PROFILE machines allocate zone=$ZONE_NAME system_id=$SYSTEM_ID 
```
    
2. Then deploy the machine as normal:

```nohighlight
    maas $PROFILE machine deploy system_id=$SYSTEM_ID
```

## Resource pools
 Administrators can manage MAAS resource pools to group machines in sensible ways.  All MAAS installations have a resource pool named "default," to which MAAS automatically adds new machines.

### Add a resource pool 

To add a resource pool to MAAS:

* In the MAAS 3.4 UI, choose *Organisation > Pools > Add pool*; enter *Name* and *Description*; select *Save pool*.

* With the UI in all other versions of MAAS, choose *Resource* > *Add pool*; enter *Name* and *Description*; select *Add pool*.

* Via the MAAS CLI, use the following command:

```nohighlight
    maas $PROFILE resource-pools create name=$NAME description="$DESCRIPTION"
```

### Delete a resource pool

If you delete a resource pool, all machines that belong to that resource pool will return to the default pool.  There is no confirmation dialogue; pools are deleted immediately. To delete a resource pool:

* In the MAAS 3.4 UI, choose *Organisation* > *Pools* > *trash can* > *Delete*.

* With the UI in all other versions of MAAS, choose *Resource* > *(trash can)* > *Delete*.

* Via the MAAS CLI, use the following command:

```nohighlight
    maas $PROFILE resource-pool delete $RESOURCE_POOL_ID
```

### Add a machine to a pool

To add a machine to a resource pool:

* In the MAAS 3.4 UI, choose *Machines* > (machine) > *Categorise* > *Set pool* > *Select pool* > *Resource pool* > *Set pool*.

* With the UI in all other versions of MAAS, choose *Machines* > (machine) > *Configuration* (resource pool) > *Save changes*.

* Via the MAAS CLI, use the following command:

```nohighlight
    maas $PROFILE machine update $SYSTEM_ID pool=$POOL_NAME
```
    
### Remove a machine from a pool

To remove a machine from a resource pool:

* In the MAAS 3.4 UI, choose *Machines* > (machine) > *Categorise* > *Set pool* > *Select pool* > *Resource pool* >"default" > *Set pool*.

* With the UI in all other versions of MAAS, choose *Machines* > (machine) > *Configuration* > "default" > *Save changes*.

* Via the MAAS CLI, use the following command:

```nohighlight
    maas $PROFILE machine update $SYSTEM_ID pool="default"
```

### Add a VM host to a pool

To add a VM host to a resource pool:

* In the MAAS 3.4 UI, choose *KVM* > *LXD* > (VM host) >  *KVM host settings* > *Resource pool* > *Save changes*.

With the UI in all other versions of MAAS, you can add a VM host to a resource pool when you create a new VM host, or you can edit the VM host's configuration:

![image](https://assets.ubuntu.com/v1/84a89952-nodes-resource-pools__2.5_pod_to_pool.png)

* Via the MAAS CLI, use the following command:

```nohighlight
    maas $PROFILE machine update $SYSTEM_ID pool=$POOL_NAME
```

### Remove a VM host from a pool

To remove a VM host from a resource pool:

* In the MAAS 3.4 UI, choose *KVM* > *LXD* > (VM host) > *KVM host settings* > *Resource pool* > "default" > *Save changes*.

* With the UI in all other versions of MAAS, edit the VM host's configuration and assign it to the "default" resource pool:

![image](https://assets.ubuntu.com/v1/84a89952-nodes-resource-pools__2.5_pod_to_pool.png)

* Via the MAAS CLI, use the following command:

```nohighlight
    maas $PROFILE machine update $SYSTEM_ID pool="default"
```

### List resource pools (CLI)

Via the MAAS CLI, use the following command:

```nohighlight
maas $PROFILE resource-pools read
```

### List a single pool

Via the MAAS CLI, use the following command:

```nohighlight
maas $PROFILE resource-pool read $RESOURCE_POOL_ID
```

### Update a pool

Via the MAAS CLI, use the following command:

```nohighlight
maas $PROFILE resource-pool update $RESOURCE_POOL_ID name=newname description="A new description."
```

> The `description` field is optional.

## Tags and annotations

MAAS also offers methods to label machines at all life-cycle stages, including static tags, notes, and dynamic annotations.

### General use of tags

Besides machine tags, there are several speciality tags.  This section explains how to work with any type of tag.

#### Naming tags

When working with tags, there are some universal rules you need to follow: 

1. Tag names can include any combination of alphabetic letters (a-zA-Z), numbers (0-9), dashes (-) and underscores (_).
2. Tag names can be a maximum of 256 characters in length.
3. Tag names *cannot* include spaces.

In general, names that do not conform to these rules cannot be created.

#### Download H/W info (UI)

To download hardware configuration information in XML format, select *Machines* > machine (allocated or deployed) > *Logs* > *Installation output* > *Download* > *Machine output (XML)*

You can [learn more about the returned information](https://ezix.org/project/wiki/HardwareLiSter)**^** if desired. Note that:

- Size and capacity can have various meanings depending on the device
- The size of a node is always equal to its capacity
- Serial refers to the device’s serial number, but is used to report the MAC address for network devices, GUID for disk partition.

You can also find device classes from the same sources. 

#### Adding tags (3.2++/UI)

In the MAAS UI, creating and assigning tags is a combined operation; that is, you create tags as you assign them, rather than creating them first. Creating tags in the UI is a little different user experience: there is a self-loading completion menu that collects all tags of a similar type. This completion menu helps you avoid misspelling tags when entering them more than once; otherwise, you might not be able to group and filter tags properly. It also makes tag entry more efficient.

To create and assign a tag to specific machines, select *Machines* > machine > *Take action* > *Tag*. In the pop-up tag dialogue, enter your proposed tag name in *Search existing or add new tags*, then select *Create tag {tag-name}*. Fill in the form:

- Optionally enter a *Comment*.

- Optionally enter *Kernel options*.

Select *Create and add to tag changes* > *Save*. You can confirm your changes by hovering over the *Tags* list in the *Machines* screen.

#### Adding tags (3.1--/UI)

In the MAAS UI, creating and assigning tags is a combined operation; that is, you create tags as you assign them, rather than creating them first. Creating tags in the UI is a little different user experience: there is a self-loading completion menu that collects all tags of a similar type. This completion menu helps you avoid misspelling tags when entering them more than once; otherwise, you might not be able to group and filter tags properly. It also makes tag entry more efficient.

The process for creating and assigning tags in the UI is generally the same for all tag types: Enter the name of the tag in the *Tags box and press the return key. Select the appropriate completion button to register your changes. The tag you just entered will now be added to the tag auto complete list, in alphabetical order, for re-use with other machines.

#### Adding tags (CLI)

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

#### Kernel option tags

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

#### Removing tags (3.2++/UI)

You have two choices when it comes to eliminating tags from machines in your MAAS instance: you can delete them from all machines, or simply remove them from specific machines.

#### Deleting tags from all machines at once

To delete tags from all machines, select *Machines* > *Tags* > trash can icon > *Delete*. The tag will be unassigned from all machines and deleted. There is no undo.

#### Removing a tag from specific machines

To remove a tag only from specific machines, select *Machines* > machine(s) by checkbox > *Take action* > *Tag*. For each tag you wish to unassign, select *Remove*. When done, select *Save* to finalise your changes.

#### Removing tags (3.1--/UI)

With the MAAS UI, you remove tags, rather than explicitly deleting them. Tags are "deleted" when you have removed them from all machines:

1. Find the *Tags* box.

2. Click the *X* next to the tag you wish to remove.

3. When you're done, select the appropriate completion button to register your changes.

Note that the tag you just removed will be deleted from  the tag auto complete list when it is no longer assigned to any  machines.

#### Removing tags (CLI)

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

#### Unassign tags (UI)

To unassign tags from machines:

1. Select *Machines*.

2. Select the checkbox(es) next to the machine(s) you wish to untag.

3. Select *Take action* > *Tag*. A table of tags appears at the top of the screen.

4. For each tag you wish to unassign, select *Remove*. The text will change to *Discard* with an *X* to the right.

5. If you want to undo a choice before saving, click the *X* to right of *Discard* to undo the proposed change.

6. When you're satisfied with your new tag configuration, select *Save* to finalise and register your choice(s).

> Automatic tags cannot be unassigned manually. You can either update or delete automatic tags.

You can also unassign tags individually by going to *Machines >> {machine-name} >> Configuration >> Tags >> Edit*. The *Tags* table functions exactly the same as what's described above.

#### List tagged nodes

To see how many nodes (Machines, controllers, devices) are tagged, search for GRUB_CMDLINE_LINUX_DEFAULT in the "Installation output" tab of the machine details page. That log should stay around for the lifetime of the deployment of the machine. The log gets overwritten when you redeploy the machine. For example:

```nohighlight
GRUB_CMDLINE_LINUX_DEFAULT="sysrq_always_enabled dyndbg='file drivers/usb/* +p' console=tty1 console=ttyS0"
```

#### Update tags

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

#### List all tags

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

#### Rebuild a tag

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

#### Automatic tags

MAAS 3.2 and above provide greatly expanded tagging capability (through the UI only). You can auto-apply tags to machines that match a custom XPath expression. Setting up an automatic tag lets you recognise special hardware characteristics and settings, e.g., the gpu passthrough.

#### Creating automatic tags (3.4)

To create automatic tags, select *Organisation > Tags* > *Create new tag* and fill in the form:

- Enter the *Tag name*.

- Optionally enter a *Comment*.

- Optionally enter *Kernel options*.

- Enter an XPath-based *Definition*. A tag is considered automatic when the definition field is filled with an XPath expression. The current version of our UI will only validate if your XPath expression is valid or not, but it will not show you which machines it will apply to before you create the tag.

When done, select *Save* to register your changes. Once an automatic tag is created the screen will initially show that 0 machines are tagged. That is because MAAS is running a background task to auto-apply the tag to matching machines. It can take some time to see that the number of machines tagged is populating. 

>**Pro tip**: Kernel options will be applied at boot time. So by default kernel options will not be applied to any machines until they are deployed. If machines are deployed before they are tagged, the kernel option will be applied when these machines are redeployed.

#### Change tag definitions

To change tag definitions: 

1. Select *Organisation > Tags*.

2. Select the pencil icon on the right end of the tag's row.

3. Edit the *Definition*.

4. Select *Save* to register your changes.

Keep in mind that when a new definition is updated, MAAS will re-tag all the machines that match with the new definition. This can take some time, since it is a background process. 

#### Creating automatic tags (3.3/3.2)

To create automatic tags, select *Machines* > *Tags* > *Create new tag* and fill in the form:

- Enter the *Tag name*.

- Optionally enter a *Comment*.

- Optionally enter *Kernel options*.

- Enter an XPath-based *Definition*. A tag is considered automatic when the definition field is filled with an XPath expression. The current version of our UI will only validate if your XPath expression is valid or not, but it will not show you which machines it will apply to before you create the tag.

Select *Save* to register your changes. Once an automatic tag is created the screen will initially show that 0 machines are tagged. That is because MAAS is running a background task to auto-apply the tag to matching machines. It can take some time to see that the number of machines tagged is populating. 

Kernel options will be applied at boot time. So, by default, kernel options will not be applied to any machines until they are deployed. If machines are deployed before they are tagged, the kernel option will be applied when these machines are redeployed.

#### Update tag definitions (UI)

To update tag definitions: 

1. Select *Machines* > *Tags*.

2. Select the pencil icon on the right end of the tag's row.

3. Edit the *Definition*.

4. Select *Save* to register your changes.

Keep in mind that when a new definition is updated, MAAS will re-tag all the machines that match with the new definition. This can take some time, since it is a background process. 

#### Update tag kernel options

*This feature is only available via the MAAS UI.*

To update the kernel options on a tag:

1. Select *Machines* > *Tags*.

2. Select the pencil icon on the right end of the tag's row.

3. Edit the *Kernel options*.

4. Select *Save* to register your changes.

Kernel options can exist for both manual and automatic tags. However, they will be applied during boot time (commissioning and deploying).

If the tagged machines are deployed, the updated kernel option won’t apply until the machines are redeployed. We suggest that you release those machines prior to the update, then redeploy those machines when the kernel options of the tag are updated.

### Specifics for machine tags

Machine tags are by far the most commonly used tag type in MAAS.  This section reiterates some specifics for managing machine tags.

#### Assign machine tags (3.4/UI)

If you want to create a new tag, and simultaneously assign it to one or more machines, select *Machines* > machine(s) (checkbox) > *Categorise* > *Tag*.  Create and/or assign the tag, and then *Save* your work.

#### Assign machine tags (3.3--/UI)

If you want to create a new tag, and simultaneously assign it to one or more machines, select *Machines* > machine(s) (checkbox) > *Take action* > *Tag*.  Create and/or assign the desired tag, and select *Tag machine* to register your changes.

#### Assign machine tags (CLI)

You can assign tags to a physical or virtual machine with the following command:

```nohighlight
maas $PROFILE tag update-nodes $TAG_NAME add=$SYSTEM_ID
```

For example:

```nohighlight
maas admin tag update-nodes new_tag add=g6arks
```

This returns something like the following:

```nohighlight
Success.
Machine-readable output follows:
{
   "added": 1,
   "removed": 0
}
```

You can check your work by listing machine tags, like this:

```nohighlight
maas admin machines read | jq -r \
'(["hostname","sysid","machine_tags"]
|(.,map(length*"-"))),(.[]|[.hostname,.system_id,.tag_names[]])
| @tsv' | column -t
```

This should yield output similar to the following:

```nohighlight
hostname       sysid   machine_tags
--------       -----   ------------
divine-stork   8b3ypp  pod-console-logging  virtual
casual-prawn   4end6r  pod-console-logging  virtual
driven-teal    tgaat6  pod-console-logging  virtual
immune-beetle  43xand  pod-console-logging  virtual
good-osprey    napfxk  pod-console-logging  virtual
smart-hen      c4rwq7  pod-console-logging  virtual
boss-satyr     xn8taa  pod-console-logging  androko
golden-martin  8fxery  pod-console-logging  virtual
crack-guinea   qk4b3g  pod-console-logging  virtual
finer-leech    cy3dtr  pod-console-logging  virtual
free-mouse     gxtbq4  pod-console-logging  virtual
humble-bunny   srqnnb  pod-console-logging  virtual
wanted-muskox  ekw7fh  pod-console-logging  virtual
one-boa        by477d  pod-console-logging  virtual
great-urchin   srnx4g  pod-console-logging  virtual
ace-frog       g6arwg  pod-console-logging  virtual  barbar  farquar  new_tag
alive-marlin   gbwnfb  pod-console-logging  virtual
picked-parrot  am77wn  pod-console-logging  virtual
tough-kit      ke3wc7  pod-console-logging  virtual
legal-whale    8nq3mt  pod-console-logging  virtual
game-sponge    76pdc6  pod-console-logging  virtual
fun-ghoul      qxfm7k  pod-console-logging  virtual
aware-earwig   8m8hs7  pod-console-logging  virtual
chief-crane    7fapx7  pod-console-logging  virtual
select-tapir   4ascbr  pod-console-logging  virtual
on-slug        snfs8d  pod-console-logging  virtual
polite-llama   dbqd4m  pod-console-logging  virtual
frank-coyote   wcmk48  pod-console-logging  virtual
usable-condor  ed8hmy  pod-console-logging  virtual
still-imp      h6ra6d  pod-console-logging  virtual
```

#### Remove machine tags (3.4/UI)

To remove machine tags from a machine, select *Machines* > machine > *Machine summary* > *Tags* > *Edit* and remove the tag.

#### Remove machine tags (3.3--/UI)

To remove machine tags from a machine, select *Machines* > machine > *Machine summary* > *Tags* > *Configuration* > *Edit* and remove the tag.

#### Remove machine tags (CLI)

You can remove a tag from a physical or virtual machine with this command:

```nohighlight
maas $PROFILE tag update-nodes $TAG_NAME remove=$SYSTEM_ID
```

For example:

```nohighlight
maas admin tag update-nodes new_tag remove=g6arwg
```

This would produce output similar to the following:

```nohighlight
Success.
Machine-readable output follows:
{
    "added": 0,
    "removed": 1
}
```

A quick check to verify results should yield something like this:

```nohighlight
hostname       sysid   machine_tags
--------       -----   ------------
ace-frog       g6arwg  pod-console-logging  virtual  barbar  farquar
```

#### Change tags for multiple machines

*This functionality can only be accessed via the MAAS CLI.*

You can simultaneously add and remove tags from multiple machines, as long as you are only modifying one tag, with a command like this one:

```nohighlight
maas $PROFILE tag update-nodes $TAG_NAME add=$SYSTEM_ID1 add=$SYSTEM_ID2 remove=$SYSTEM_ID3
```

For example, to remove the tag "barbar" from machine "g6arwg," but add it to machines "8fxery" and "by477d," you could use a command like this:

```nohighlight
maas admin tag update-nodes barbar add=8fxery add=by477d remove=g6arwg
```

This compound operation would yield a response similar to this:

```nohighlight
Success.
Machine-readable output follows:
{
    "added": 2,
    "removed": 1
}
```

Again, verifying by checking the list of machine tags, we enter a command like this:

```nohighlight
maas admin machines read | jq -r \
'(["hostname","sysid","machine_tags"]
|(.,map(length*"-"))),(.[]|[.hostname,.system_id,.tag_names[]])
| @tsv' | column -t
```

The resulting response looks something like this:

```nohighlight
hostname       sysid   machine_tags
--------       -----   ------------
divine-stork   8b3ypp  pod-console-logging  virtual
casual-prawn   4end6r  pod-console-logging  virtual
driven-teal    tgaat6  pod-console-logging  virtual
immune-beetle  43xand  pod-console-logging  virtual
good-osprey    napfxk  pod-console-logging  virtual
smart-hen      c4rwq7  pod-console-logging  virtual
boss-satyr     xn8taa  pod-console-logging  androko
golden-martin  8fxery  pod-console-logging  virtual  barbar
crack-guinea   qk4b3g  pod-console-logging  virtual
finer-leech    cy3dtr  pod-console-logging  virtual
free-mouse     gxtbq4  pod-console-logging  virtual
humble-bunny   srqnnb  pod-console-logging  virtual
wanted-muskox  ekw7fh  pod-console-logging  virtual
one-boa        by477d  pod-console-logging  virtual  barbar
great-urchin   srnx4g  pod-console-logging  virtual
ace-frog       g6arwg  pod-console-logging  virtual  farquar
alive-marlin   gbwnfb  pod-console-logging  virtual
picked-parrot  am77wn  pod-console-logging  virtual
tough-kit      ke3wc7  pod-console-logging  virtual
legal-whale    8nq3mt  pod-console-logging  virtual
game-sponge    76pdc6  pod-console-logging  virtual
fun-ghoul      qxfm7k  pod-console-logging  virtual
aware-earwig   8m8hs7  pod-console-logging  virtual
chief-crane    7fapx7  pod-console-logging  virtual
select-tapir   4ascbr  pod-console-logging  virtual
on-slug        snfs8d  pod-console-logging  virtual
polite-llama   dbqd4m  pod-console-logging  virtual
frank-coyote   wcmk48  pod-console-logging  virtual
usable-condor  ed8hmy  pod-console-logging  virtual
still-imp      h6ra6d  pod-console-logging  virtual
```

#### List machine tags (3.4/UI)

In the MAAS UI, you don't explicitly list all machine tags; instead, you filter by them using the "Filters" drop-down. Select *Machines* > *Filters* > *Tags* and click on one or more tag names. The machine list will automatically filter by (be limited to) the machines matching the selected tag(s).  Remove a tag from the search filter by deselecting it in the *Tags* section.

#### List machine tags (3.3--/UI)

In the MAAS UI, you don't explicitly list all machine tags; instead, you filter by them using the "Filter by" drop-down.  This filtered list does not distinguish between virtual machines (VMs) and physical machines, unless you've assigned tags to help with that distinction.

Here's how you can filter the machine list by machine tags, using the MAAS UI:

- To list all tags, visit the 'Machines' tab and expand the 'Tags' subsection in the left pane. In this view, you can use tags as machine search filters.

- Select one or several tags. The machines that satisfy all selected tags will display on the right pane. Notice there is a search field at the top of the right pane. You can type a search expression into this field.

Below, tag 'virtual' has been selected (with the mouse), and the search field automatically reflects this. Five machines satisfy this search filter.

![image](upload://f4LDShEPU9tCFBwsO5gnZkkKiG1.png)

Remove a tag from the search filter by either hitting the 'x' character alongside a tag or editing the search expression.

#### List machine tags (CLI)

To list machine tags for all physical and virtual machines, just enter a command similar to this one:

```nohighlight
maas $PROFILE machines read | jq -r '(["hostname","sysid","machine_tags"]|(.,map(length*"-"))),(.[]|[.hostname,.system_id,.tag_names[]]) | @tsv' | column -t
```

For example:

```nohighlight
maas admin machines read | jq -r \
'(["hostname","sysid","machine_tags"]
|(.,map(length*"-"))),(.[]|[.hostname,.system_id,.tag_names[]])
| @tsv' | column -t
```

This gives us a listing similar to this:

```nohighlight
hostname       sysid   machine_tags
--------       -----   ------------
divine-stork   8b3ypp  pod-console-logging  virtual
casual-prawn   4end6r  pod-console-logging  virtual
driven-teal    tgaat6  pod-console-logging  virtual
immune-beetle  43xand  pod-console-logging  virtual
good-osprey    napfxk  pod-console-logging  virtual
smart-hen      c4rwq7  pod-console-logging  virtual
boss-satyr     xn8taa  pod-console-logging  androko
golden-martin  8fxery  pod-console-logging  virtual  barbar
crack-guinea   qk4b3g  pod-console-logging  virtual
finer-leech    cy3dtr  pod-console-logging  virtual
free-mouse     gxtbq4  pod-console-logging  virtual
humble-bunny   srqnnb  pod-console-logging  virtual
wanted-muskox  ekw7fh  pod-console-logging  virtual
one-boa        by477d  pod-console-logging  virtual  barbar
great-urchin   srnx4g  pod-console-logging  virtual
ace-frog       g6arwg  pod-console-logging  virtual  farquar
alive-marlin   gbwnfb  pod-console-logging  virtual
picked-parrot  am77wn  pod-console-logging  virtual
tough-kit      ke3wc7  pod-console-logging  virtual
legal-whale    8nq3mt  pod-console-logging  virtual
game-sponge    76pdc6  pod-console-logging  virtual
fun-ghoul      qxfm7k  pod-console-logging  virtual
aware-earwig   8m8hs7  pod-console-logging  virtual
chief-crane    7fapx7  pod-console-logging  virtual
select-tapir   4ascbr  pod-console-logging  virtual
on-slug        snfs8d  pod-console-logging  virtual
polite-llama   dbqd4m  pod-console-logging  virtual
frank-coyote   wcmk48  pod-console-logging  virtual
usable-condor  ed8hmy  pod-console-logging  virtual
still-imp      h6ra6d  pod-console-logging  virtual
```

#### View machine tags (3.4/UI)

To view the tags assigned to a specific machine, select *Machines* > machine > *Configuration* > *Tags*.

#### View machine tags (3.3--/UI)

To view the tags assigned to a specific machine, use the following procedure:

- On the machine list, select the machine of interest by clicking on its name.

- On the machine detail screen that comes up, look for the tags on one of the cards presented there: the tags for that machine should be listed there.

#### View machine tags (CLI)

To view tags for one physical or machine, you can enter a command like this:

```nohighlight
maas $PROFILE machine read $SYSTEM_ID | jq -r '(["hostname","sysid","machine_tags"]|(.,map(length*"-"))),([.hostname,.system_id,.tag_names[]]) | @tsv' | column -t
```

For example:

```nohighlight
maas admin machine read 8fxery | jq -r \
'(["hostname","sysid","machine_tags"]
|(.,map(length*"-"))),([.hostname,.system_id,.tag_names[]])
| @tsv' | column -t
```

Typical output from this command might look like this:

```nohighlight
hostname       sysid   machine_tags
--------       -----   ------------
golden-martin  8fxery  pod-console-logging  virtual  barbar
```

#### Discover your virtual machine host ID

*This functionality is available only through the MAAS CLI.*

If you don't know your VM host ID, you can discover it with this command:

```nohighlight
maas $PROFILE vmhosts read \
| jq -r '(["vm_host_name","id"]
|(.,map(length*"-"))),(.[]|[.name,.id])
| @tsv' | column -t
```

For example:

```nohighlight
maas admin vmhosts read \
| jq -r '(["vm_host_name","id"]
|(.,map(length*"-"))),(.[]|[.name,.id])
| @tsv' | column -t
```

This should produce output similar to the following:

```nohighlight
vm_host_name      id
------------      --
my-lxd-vm-host-1  1
```

#### Assign tags to a VM host

*This functionality is available only through the MAAS CLI.*

To assign a tag to a virtual machine host, enter the following command:

```nohighlight
maas $PROFILE vmhost add-tag $VMHOST_ID	tag=$TAG_NAME
```

If you don't know the ID of your VM host, you can [look it up beforehand](#heading--discover-your-vm-host-id).

As an example of assigning a tag to a VM host:

```nohighlight
maas admin vmhost add-tag 1 tag=virtual
```

If it worked, this should return `Success`, followed by the JSON that describes the VM host. 

#### Remove VM host tags

*This functionality is available only through the MAAS CLI.*

To remove a tag from a virtual machine host, enter the following command:

```nohighlight
maas $PROFILE vmhost remove-tag $VMHOST_ID tag=$TAG_NAME
```

If you don't know the ID of your VM host, you can [look it up beforehand](#heading--discover-your-vm-host-id).

As an example of removing a tag from a VM host:

```nohighlight
maas admin vmhost remove-tag 1 tag=virtual
```

If it worked, this should return `Success`, followed by the JSON that describes the VM host. 

#### List VM host tags

*This functionality is available only through the MAAS CLI.*

You can list tags for all VM hosts with the following command:

```nohighlight
maas $PROFILE vmhosts read | jq -r '(["vm_host_name","id","tags"]|(.,map(length*"-"))),(.[]|[.name,.id,.tags[]]) | @tsv' | column -t
```

For example:

```nohighlight
maas admin vmhosts read | jq -r '(["vm_host_name","id","tags"]|(.,map(length*"-"))),(.[]|[.name,.id,.tags[]]) | @tsv' | column -t
```

This should yield output similar to the following:

```nohighlight
vm_host_name      id  tags
------------      --  ----
my-lxd-vm-host-1  1   morkopongo  pod-console-logging  virtual
```



#### View VM host tags (3.4/UI)

To view the machine tags assigned to a VM host, select *KVM* > VM host type > VM host > *KVM host settings* > *Tags*.  You can also edit, add, or delete tags from this view. Note that you can only see the tags for a VM host in the same place that you change it.  For a more comprehensive list of VM host tags, use the MAAS CLI.

#### View VM host tags (3.3--/UI)

To view the machine tags assigned to a VM host, select *KVM* > VM host > *KVM host settings* > *Tags. You can also edit, add, or delete tags from this view. Note that you can only see the tags for a VM host in the same place that you change it.  For a more comprehensive list of VM host tags, use the MAAS CLI.

#### View VM host tags (CLI)

If you want to list the tags for just one VM host, you can use a command like this one:

```nohighlight
maas $PROFILE vmhost read $VMHOST_ID \
| jq -r '(["name","id","tags"]
|(.,map(length*"-"))),([.name,.id,.tags[]])
| @tsv' | column -t
```
If you don't know the ID of your VM host, you can [look it up beforehand](#heading--discover-your-vm-host-id).

As an example of viewing tags for one VM host:

```nohighlight
maas admin vmhost read 1 | jq -r '("name","id","tags"]|(.,map(length*"-"))),([.name,.id,.tags[]]) | @tsv' @ column -t
```

Typical output might look something like this:

```nohighlight
name              id  tags
----              --  ----
my-lxd-vm-host-1  1   morkopongo  pod-console-logging
```

### Annotations

Annotations in MAAS are potent tools for adding context and metadata to your machines. They act as supplementary data that allow you to identify, filter, and manage your machines more effectively. Essentially, annotations fall into two categories: 

1. Notes: These are always available, regardless of the machine's state.
2. Dynamic Annotations: These only exist when a machine is in an allocated or deployed state.

This section explains how to use notes and dynamic annotations.

> Dynamic annotations aren't supported in MAAS version 2.9 or earlier.

#### Notes

Notes are persistent descriptions that stay with a machine throughout its life-cycle unless manually altered. You can manage notes through both the MAAS UI and CLI.

##### Notes via UI

To add or modify notes via the MAAS UI:

1. Navigate to *Machines > Machine name > Configuration > Edit*.

2. Your existing notes appear in the *Note* section.

3. Add new or modify existing notes in the *Note* section.

4. Delete irrelevant notes from the same block.

5. Make sure to *Save changes* to confirm your actions.

##### Notes via CLI

Notes using the MAAS CLI are handled a little differently from the UI.

###### Identifying your machines

To determine machine identifiers, run the following command:

```nohighlight
maas $PROFILE machines read \
| jq -r '(["hostname","system_id"]
|(.,map(length*"-"))),(.[]|[.hostname,.system_id])
|@tsv' | column -t
```

###### Managing notes in CLI

You can add or modify a note as follows:

```nohighlight
maas $PROFILE machine update $SYSTEM_ID description="$NOTE"
```

To erase a note, just use an empty string:

```nohighlight
maas $PROFILE machine update $SYSTEM_ID description=""
```

#### Dynamic annotations

Dynamic annotations are ephemeral data, tied to the operational states of allocated or deployed machines. These annotations are especially handy for tracking the live status of your workloads.

##### Identifying eligible machines for dynamic annotations

To list machines that can receive dynamic annotations, execute:

```nohighlight
maas $PROFILE machines read \
| jq -r '(["hostname","system_id","status"]
|(.,map(length*"-"))),(.[]|[.hostname,.system_id,.status_name])
|@tsv' | column -t
```

##### Setting dynamic annotations

You can define dynamic annotations using `key=value` pairs. To set one, use:

```nohighlight
maas $PROFILE machine set-owner-data $SYSTEM_ID $KEY=$VALUE
```

##### Managing dynamic annotations

To change or remove a dynamic annotation, use the following commands:

- For changing: 
```nohighlight
maas $PROFILE machine set-owner-data $SYSTEM_ID $KEY=$NEW_VALUE
```

- For removing: 
```nohighlight
maas $PROFILE machine set-owner-data $SYSTEM_ID $KEY=""
```

##### Listing dynamic annotations

To view all current dynamic annotations, run:

```nohighlight
maas $PROFILE machines read \
| jq -r '(["hostname","system_id","owner_data"]
|(.,map(length*"-"))),(.[]|[.hostname,.system_id,.owner_data[]])
|@tsv' | column -t
```

#### Summary

Annotations in MAAS offer an additional layer of intelligence to your machine management. While notes provide a stable form of annotations, dynamic annotations offer a more fluid form of tracking, directly linked to your machine's operational status.
