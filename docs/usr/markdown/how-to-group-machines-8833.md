Machine groups allow you to categorize machines for easy recognition and bulk action.

[About machine groups](https://maas.io/docs/about-machine-groups).

## Availability zones

Availability zones (AZs) in MAAS improve fault tolerance, service performance, and power management by organizing resources across physical or network areas. If there is failure in one AZ, you can quickly switch to another one.

### Manage availability zones

Create, update and delete availability zones as desired.

#### Create an availability zone

**UI**
*Main menu* > *AZs* > *Add AZ* > Enter *Name*, *Description* > *Add AZ*.

**CLI**
```sh
maas $PROFILE zones create name=$ZONE_NAME description=$ZONE_DESCRIPTION
```

#### Update an availability zone

**UI**
*Main menu* > *AZs* > Select AZ > *Edit* > Update *Name*, *Description* > *Update AZ*.

**CLI**
```sh
maas $PROFILE zone update $OLD_ZONE_NAME name=$NEW_ZONE_NAME \
description=$ZONE_DESCRIPTION
```

#### Delete an availability zone

**UI**
*Main menu* > *AZs* > Select zone > *Delete AZ* > *Delete AZ*.

**CLI**
```sh
maas $PROFILE zone delete $ZONE_NAME
```

#### List availability zones

**UI**
*Main menu* > *AZs*

**CLI**
```sh
maas $PROFILE zones read \
| jq -r '(["ZONE","NAME","DESCRIPTION"]
| (., map(length*"-"))), (.[] | [.id, .name, .description])
| @tsv' | column -t
```

Example output:
```sh
ZONE  NAME         DESCRIPTION
----  ----         -----------
5     BizOffice
1     default
4     Inventory
2     Medications
3     Payroll
6     ProServ
```

### Assign a machine to an availability zone

**UI (MAAS 3.4)**
*Machines* > Select machines > *Categorise* > *Set zone* > Choose *Zone* > *Set zone for machine*.

**UI**
*Machines* > Select machines > *Take action* > *Set zone* > Choose *Zone* > *Set zone for machine*.

**CLI**
```sh
maas $PROFILE machines read | jq '.[] | .hostname, .system_id'
maas admin machine update $SYSTEM_ID zone=$ZONE_NAME
```

## Resource pools

MAAS uses resource pools to group machines and VM hosts for better allocation. New machines default to the "default" pool. Resource pools are useful when you are budgeting a limited number of machines across different datacenter functions.

### Manage resource pools

Create, update, delete and list resource pools as needed.

#### Create a resource pool  

**UI** 
- **MAAS 3.4:** *Organisation* > *Pools* > *Add pool* > Enter *Name* & *Description* > *Save pool*.  
- **Earlier versions:** *Resource* > *Add pool* > Enter *Name* & *Description* > *Add pool*.  

**CLI**  
```nohighlight
maas $PROFILE resource-pools create name=$NAME description="$DESCRIPTION"
```
#### Update a pool  

**CLI**  
```nohighlight
maas $PROFILE resource-pool update $RESOURCE_POOL_ID name=newname description="A new description."
```

> `description` is optional.  

#### Delete a resource pool  

**UI**  
- **MAAS 3.4:** *Organisation* > *Pools* > *(trash can)* > *Delete*.  
- **Earlier versions:** *Resource* > *(trash can)* > *Delete*.  

**CLI**  
```nohighlight
maas $PROFILE resource-pool delete $RESOURCE_POOL_ID
```

#### List resource pools  

**CLI**  
```nohighlight
maas $PROFILE resource-pools read
```

#### View a single pool  

**CLI**  
```nohighlight
maas $PROFILE resource-pool read $RESOURCE_POOL_ID
```

### Assign machines to pools

Attach or detach machines from a resource pool at any time.

#### Attach a machine to a pool  

**UI**  
- **MAAS 3.4 forward:** *Machines* > Select machine > *Categorise* > *Set pool* > Select *Resource pool* > *Set pool*.  
- **Earlier versions:** *Machines* > Select machine > *Configuration* > Set *Resource pool* > *Save changes*.  

**CLI**  
```nohighlight
maas $PROFILE machine update $SYSTEM_ID pool=$POOL_NAME
```
#### Detach a machine from a pool  

**UI**  
- **MAAS 3.4:** Same as "Add a machine to a pool," but select **"default"** as the resource pool.  
- **Earlier versions:** *Machines* > *(machine)* > *Configuration* > Set pool to **"default"** > *Save changes*.  

**CLI**  
```nohighlight
maas $PROFILE machine update $SYSTEM_ID pool="default"
```

#### Attach a VM host to a pool  

**UI**  
- **MAAS 3.4:** *KVM* > *LXD* > Select VM host > *KVM host settings* > *Resource pool* > *Save changes*.  
- **Earlier versions:** Assign pool during VM host creation or edit VM host settings.  

**CLI**  
```nohighlight
maas $PROFILE vm-host update $SYSTEM_ID pool=$POOL_NAME
```

#### Detach a VM host from a pool  

**UI**  
- **MAAS 3.4:** Same as "Add a VM host to a pool," but select **"default"** as the resource pool.  
- **Earlier versions:** Edit VM host settings and assign to **"default"**.  

**CLI**  
```nohighlight
maas $PROFILE vm-host update $SYSTEM_ID pool="default"
```

## Tags and annotations

MAAS also offers methods to label machines at all life-cycle stages, including tags, notes, and dynamic annotations. Tags are persistent labels that remain associated with machines until you remove them.

### How to name a tag

When working with tags, there are some universal rules you need to follow: 

1. Tag names can include any combination of alphabetic letters (a-zA-Z), numbers (0-9), dashes (-) and underscores (_).
2. Tag names can be a maximum of 256 characters in length.
3. Tag names *cannot* include spaces.

In general, names that do not conform to these rules cannot be created.

### Tagging machines

Manage machine tags on the fly, as they are created and attached to machines.

#### Add a tag

**UI**
*Machines* > (Select machine) > *Take action* > *Tag* > (Enter tag name) > *Create tag* > (Fill out form) > *Create and add to tag changes* > *Save*.

**UI (Version 3.1 and older)**
Enter the tag name in the *Tags* box > *(Return)* > (Select completion).

**CLI**
```nohighlight
maas $PROFILE tags create name=$TAG_NAME comment='$TAG_COMMENT'
```

#### Add a kernel option tag

**CLI (only)**
```nohighlight
maas $PROFILE tags create name='$TAG_NAME' \
    comment='$TAG_COMMENT' kernel_opts='$KERNEL_OPTIONS'
```
#### Delete a tag from all machines

**UI**
*Machines* > *Tags* > (Trash can icon) > *Delete*

**CLI**
```nohighlight
maas $PROFILE tag delete $TAG_NAME
```

#### Delete a tag from specific machines

*Machines* > (Select machines) > *Take action* > *Tag* > *Remove* > *Save*.

#### Remove tags

With MAAS 3.1 and earlier versions, you remove tags, rather than explicitly deleting them. Tags are "deleted" when you have removed them from all machines.

**UI**
*Tags box* > (Select the *X* next to tag to remove) > (Select appropriate completion button)

#### Unassign tags

**UI (only)**
*Machines* > (Select machine) > *Take action* > *Tag* > *Remove* (on specific tag) *Save*

#### List tagged nodes

**CLI (only)**
```nohighlight
GRUB_CMDLINE_LINUX_DEFAULT="sysrq_always_enabled dyndbg='file drivers/usb/* +p' console=tty1 console=ttyS0"
```

#### Update tags

**CLI (only)**
```nohighlight
maas $PROFILE tag update $TAG_NAME comment='$TAG_COMMENT'
```

#### List all tags

**CLI (only)**
```nohighlight
maas $PROFILE tags read | jq -r '(["tag_name","tag_comment"]|(.,map(length*"-"))),(.[]|[.name,.comment]) | @tsv' | column -t
```

#### Rebuild a tag

If you need to update tags for all machines – without having to recommission them – you can accomplish this with the rebuild command:

**CLI (only)**
```nohighlight
maas $PROFILE tag rebuild $TAG
```

This command automatically applies the tag to all machines regardless of state, even machines that are actively deployed.

### Manage automatic tags

MAAS 3.2 and above can auto-apply tags to machines based on XPath expressions. 

#### Create automatic tags (MAAS 3.4 and above)

**UI**
*Organisation > Tags* > *Create new tag* > (Fill in form) > *Save*

> Note: Adding and XPath expression makes a tag automatic.

#### Change tag definitions

**UI**
*Organisation* > *Tags* > (Pencil icon) > (Edit definition) > *Save*

MAAS will re-tag all matching machines in a background process.

#### Creating automatic tags (3.3/3.2)

*Machines* > *Tags* > *Create new tag* > (Fill in form) > *Save*

> Note: Adding and XPath expression makes a tag automatic.

#### Update tag definitions

**UI**
*Machines* > *Tags* > (Pencil icon) > Edit the *Definition* > *Save*.

MAAS will re-tag all matching machines in the background.

#### Update tag kernel options

**UI (only)**
*Machines* > *Tags* > (Select pencil icon) > *Kernel options* > *Save*.

Kernel options can exist for both manual and automatic tags. However, they will be applied during boot time (commissioning and deploying). If the tagged machines are deployed, the updated kernel option won’t apply until the machines are redeployed. We suggest that you release those machines prior to the update, then redeploy those machines when the kernel options of the tag are updated.

### Manage VM host tags

Apply tags to VM hosts to help distinguish them.

#### Assign tags to a VM host

**CLI (only)
```nohighlight
maas $PROFILE vmhosts read \
| jq -r '(["vm_host_name","id"]
|(.,map(length*"-"))),(.[]|[.name,.id])
| @tsv' | column -t
maas $PROFILE vmhost add-tag $VMHOST_ID	tag=$TAG_NAME
```
#### Remove VM host tags

**CLI (only)**
```nohighlight
maas $PROFILE vmhost remove-tag $VMHOST_ID tag=$TAG_NAME

### List VM host tags

**CLI (only)**
```nohighlight
maas $PROFILE vmhosts read | jq -r '(["vm_host_name","id","tags"]|(.,map(length*"-"))),(.[]|[.name,.id,.tags[]]) | @tsv' | column -t
```
#### View VM host tags (MAAS 3.4)

**UI**
*KVM* > (VM host type) > (VM host) > *KVM host settings* > *Tags*.  You can also edit, add, or delete tags from this view. 

#### View VM host tags (MAAS 3.3 and below)

**UI**
*KVM* > (VM host) > *KVM host settings* > *Tags*. You can also edit, add, or delete tags from this view. 

#### View VM host tags (CLI)

**CLI**
```nohighlight
maas $PROFILE vmhost read $VMHOST_ID \
| jq -r '(["name","id","tags"]
|(.,map(length*"-"))),([.name,.id,.tags[]])
| @tsv' | column -t
```

## Annotations

Annotations add context and metadata to your machines for identification and filtering.  There are two types: notes, which are static and survive throughout the life-cycle; and dynamic annotations, which only exist during deployment.

> Note: Dynamic annotations aren't supported in MAAS version 2.9 or earlier.

### Manage notes

Notes are longer, persistent descriptions that stay with a machine throughout its life-cycle unless manually altered.

#### Add or modify notes

**UI**
*Machines* > (Machine) > *Configuration* > *Edit* > *Note* > (Edits) > *Save changes*.

**CLI**
```nohighlight
maas $PROFILE machines read \
| jq -r '(["hostname","system_id"]
|(.,map(length*"-"))),(.[]|[.hostname,.system_id])
|@tsv' | column -t
maas $PROFILE machine update $SYSTEM_ID description="$NOTE"
```

To erase a note, just use an empty string.

### Manage dynamic annotations

Dynamic annotations are ephemeral data attached to allocated or deployed machines.

#### Identify eligible machines

To list machines that can receive annotations, execute:

**CLI (only)**
```nohighlight
maas $PROFILE machines read \
| jq -r '(["hostname","system_id","status"]
|(.,map(length*"-"))),(.[]|[.hostname,.system_id,.status_name])
|@tsv' | column -t
```

#### Set an annotation

Set annotations using `key=value` pairs:

**CLI (only)**
```nohighlight
maas $PROFILE machine set-owner-data $SYSTEM_ID $KEY=$VALUE
```

#### Change an annotation

**CLI (only)**
```nohighlight
maas $PROFILE machine set-owner-data $SYSTEM_ID $KEY=$NEW_VALUE
```

#### Remove an annotation

**CLI (only)**
```nohighlight
maas $PROFILE machine set-owner-data $SYSTEM_ID $KEY=""
```

#### List annotations

**CLI (only)**
```nohighlight
maas $PROFILE machines read \
| jq -r '(["hostname","system_id","owner_data"]
|(.,map(length*"-"))),(.[]|[.hostname,.system_id,.owner_data[]])
|@tsv' | column -t
```
