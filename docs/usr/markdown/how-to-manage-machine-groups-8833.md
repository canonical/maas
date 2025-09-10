At scale, a MAAS deployment can quickly turn into a forest of machines that are hard to track. Grouping helps make sense of that sprawl. The goal isn’t just tidiness; groups give you practical handles for filtering, access control, and high-availability strategies.  For more information about these labels, refer to [About machine groups](https://canonical.com/maas/docs/about-machine-groups).

## Manage availability zones

Availability zones (AZs) help you group machines for any desired purposes that depends on a single, unique label per machine. In MAAS, you can create, update, delete, and assign machines to zones.  You can also use any MAAS interface to search for machines bearing a particular AZ.

### Create an availability zone

**UI**
*Main menu* > *AZs* > *Add AZ* > Enter *Name*, *Description* > *Add AZ*.

**CLI**
```sh
# $PROFILE = your admin profile name
# $ZONE_NAME = name of the zone to create
# $ZONE_DESCRIPTION = description of the new zone
#
maas $PROFILE zones create name=$ZONE_NAME description=$ZONE_DESCRIPTION
```

### Update an availability zone

**UI**
*Main menu* > *AZs* > Select AZ > *Edit* > Update *Name*, *Description* > *Update AZ*.

**CLI**
```sh
# $PROFILE = your admin profile name
# $OLD_ZONE_NAME = current name of zone to be updated
# $NEW_ZONE_NAME = updated zone name, if applicable
# $ZONE_DESCRIPTION = updated zone description, if applicable
maas $PROFILE zone update $OLD_ZONE_NAME name=$NEW_ZONE_NAME \
description=$ZONE_DESCRIPTION
```

### Delete an availability zone

**UI**
*Main menu* > *AZs* > Select zone > *Delete AZ* > *Delete AZ*.

**CLI**
```sh
# $PROFILE = your admin profile name
# $ZONE_NAME = name of zone to delete
#
maas $PROFILE zone delete $ZONE_NAME
```

### List availability zones

**UI**
*Main menu* > *AZs*

**CLI**
```sh
# $PROFILE = your admin profile name
#
maas $PROFILE zones read \
| jq -r '(["ZONE","NAME","DESCRIPTION"]
| (., map(length*"-"))), (.[] | [.id, .name, .description])
| @tsv' | column -t
```

Example output:
```sh
ZONE  NAME         DESCRIPTION
5     BizOffice
1     default
4     Inventory
2     Medications
3     Payroll
6     ProServ
```

### Assign a machine to an availability zone

**UI (MAAS 3.4++)**
*Machines* > Select machines > *Categorise* > *Set zone* > Choose *Zone* > *Set zone for machine*.

**UI (Earlier versions)**
*Machines* > Select machines > *Take action* > *Set zone* > Choose *Zone* > *Set zone for machine*.

**CLI**

First, find the machine's system ID:
```sh
# $PROFILE = your admin profile name
# 
maas $PROFILE machines read | jq '.[] | .hostname, .system_id'
```

Then assign it to a zone:
```sh
# $PROFILE = your admin profile name
# $SYSTEM_ID = system ID of machine to assign
# $ZONE_NAME = zone to which machine should be assigned
# 
maas $PROFILE machine update $SYSTEM_ID zone=$ZONE_NAME
```

### Find machines that belong to an availability zone

**UI**
Select *Machines*.

Use the filter at the top of the table to select the desired Zone. The list updates in real time to show only machines in matching zones.

**CLI**
```sh
# $PROFILE = your admin profile name
# $ZONE_NAME = desired zone you want to view
#
maas $PROFILE machines read zone=$ZONE_NAME
```

This returns a list of all machines currently assigned to that availability zone.

## Manage resource pools
Resource pools allow you to group machines for access control and organizational purposes. In MAAS, you can create, update, delete, and assign machines to pools.  You can also search for machines matching full or partial resource pool name.

### Create a resource pool

**UI**
1. From the main menu, select **Pools**.
2. Click **Add pool**.
3. Enter a **Name** and (optionally) a **Description**.
4. Click **Add pool**.

**CLI**
```sh
# $PROFILE = your admin profile name
# $POOL_NAME = name of new resource pool
# $POOL_DESCRIPTION = description of new pool
#
maas $PROFILE resource-pools create name=$POOL_NAME description=$POOL_DESCRIPTION
```

### Update a resource pool

**UI**
Select *Pools* > [pool to edit] > *Edit* > update *Name* and/or *Description* > *Update pool*

**CLI**
```sh
# $PROFILE = your admin profile name
# $POOL_ID = ID of pool to update
# $NEW_NAME = updated name of pool
# $NEW_DESCRIPTION = updated description of this pool 
#
maas $PROFILE resource-pool update $POOL_ID name=$NEW_NAME description=$NEW_DESCRIPTION
```

### Delete a resource pool

**UI**
*Pools* > [select pool to delete] > *Delete pool* > *Delete pool*

**CLI**
```sh
# $PROFILE = your admin profile name
# $POOL_ID = ID of pool to delete
#
maas $PROFILE resource-pool delete $POOL_ID
```

### List resource pools

**UI**
*Pools*

**CLI**
```sh
# $PROFILE = your admin profile name
#
maas $PROFILE resource-pools read \
| jq -r '(["ID","NAME","DESCRIPTION"]
| (., map(length*"-"))), (.[] | [.id, .name, .description])
| @tsv' | column -t
```

Example output:

```sh
ID  NAME        DESCRIPTION
1   default     Default pool
2   staging     Test/staging systems
3   finance     Finance department workloads
```

### Assign a machine to a resource pool

**UI**
*Machines* > [machine(s) to assign] > *Take action* > *Set pool* > [choose pool] > *Set pool for machine*

**CLI**
First, find the machine’s system ID:

```sh
# $PROFILE = your admin profile name
#
maas $PROFILE machines read | jq '.[] | .hostname, .system_id'
```

Then assign it to a pool:

```sh
# $PROFILE = your admin profile name
# $SYSTEM_ID = system ID of machine being assigned
# $POOL_ID = pool to which to assign the machine
#
maas $PROFILE machine update $SYSTEM_ID pool=$POOL_ID
```

### Find machines that belong to a resource pool

**UI**

From the main menu, select *Machines*.

Use the filter at the top of the table to select the desired Pool.  The list updates to show only machines in matching pools.

**CLI**
```sh
# $PROFILE = your admin profile name
# $POOL_NAME = desired pool you want to view
#
maas $PROFILE machines read pool=$POOL_NAME
```

## Manage tags in MAAS

Tags are persistent labels that remain associated with machines until you remove them. They can be created manually or automatically (via XPath expressions) and are useful for filtering, commissioning, deployment, and even attaching kernel options.

### Naming rules for tags
- Tag names can include: alphabetic letters (a–z, A–Z), numbers (0–9), dashes (-), and underscores (_).
- Tag names cannot include spaces.
- Maximum length: 256 characters.
- Tags that don’t follow these rules cannot be created.

### Create a tag

**UI (MAAS 3.2 and above)**
*Organisation* > *Tags* > *Create new tag* > Enter *Name*, *Comment*, *Xpath expression* > *Save*

**Cli**
```
# $PROFILE = your admin profile name
# $TAG_NAME = name of the newly-created tag
# $TAG_COMMENT = comment to associate with the tag
#
maas $PROFILE tags create name=$TAG_NAME comment="$TAG_COMMENT"
```

### Add kernel option tags

**UI**
*Organization* > *Tags* > *Create new tag* or [Click the pencil icon to edit a tag] > *Kernel options* > [Enter desired kernel options] > *Save*

**CLI**
```
# $PROFILE = your admin profile name
# $TAG_NAME = name for new kernel option tag
# $TAG_COMMENT = comment to associate with the tag
# $KERNEL_OPTIONS = kernel options for the tag to carry to machines with this tag
#
maas $PROFILE tags create name="$TAG_NAME"     comment="$TAG_COMMENT" kernel_opts="$KERNEL_OPTIONS"
```

### Assign or unassign tags from machines

**UI (MAAS 3.4 and newer)**
*Machines* > [Select machine(s)] > *Take action* > *Tag* > [add or Remove tags] > *Save*

**UI (MAAS 3.1 and earlier)**
- Use the **Tags box** on the machine’s page. Remove tags by clicking the **X**.

**CLI**
```
# $PROFILE = your admin profile name
# $SYSTEM_ID = machine to which tag should be assigned
# $TAG_NAME = tag to be assigned
#
maas $PROFILE machines read | jq '.[] | .hostname, .system_id'
maas $PROFILE machine update $SYSTEM_ID tags=$TAG_NAME
```

### Remove or delete tags

**UI**
- Delete from all machines: *Machines* > *Tags* > [Trash can icon] > *Confirm*

- Remove from selected machines: *Machines* > [Select machines] > *Take action* > *Tag* > *Remove* > *Save*.

**CLI**
```
# $PROFILE = your admin profile name
# $TAG_NAME = name of tag to be removed
#
maas $PROFILE tag delete $TAG_NAME
```

### Update a tag

**UI**
*Organisation* > *Tags* > [pencil icon] > Update *Name*, *Comment*, *Definition*, *Kernel options* > *Save*

**CLI**
```
# $PROFILE = your admin profile name
# $TAG_NAME = tag to be updated
# $TAG_COMMENT = updated tag comment
#
maas $PROFILE tag update $TAG_NAME comment="$TAG_COMMENT"
```

### List all tags

**UI**
*Organisation* > *Tags*

**CLI**
```
# $PROFILE = your admin profile name
maas $PROFILE tags read | jq -r '(["tag_name","tag_comment"]
|(.,map(length*"-"))),(.[]|[.name,.comment]) | @tsv' | column -t
```

### Rebuild a tag

**CLI only**
```
# $PROFILE = your admin profile name
# $TAG_NAME = tag to be rebuilt
#
maas $PROFILE tag rebuild $TAG_NAME
```


### Manage automatic tags

**UI**
*Organisation* > *Tags* > *Create new tag* > [Fill in the form] > *Save*

**Update automatic tags**
- Edit the tag definition (pencil icon) and save.
- MAAS re-tags matching machines in the background.

**Update kernel options on automatic tags**
- UI only: Edit the tag, change kernel options, and save.
- Options apply at boot; redeploy machines for changes to take effect.


### VM host tags

**UI**
*KVM* > [VM host type] > [VM host] > *KVM host settings* > *Tags* > *Add* / *Edit* / *Delete*

**CLI**
```
# $PROFILE = your admin profile name
#
maas $PROFILE vmhosts read | jq -r '(["vm_host_name","id"]
|(.,map(length*"-"))),(.[]|[.name,.id]) | @tsv' | column -t

# $VMHOST_ID = ID of VM host to which tag is added
# $TAG_NAME = tag to be added
#
maas $PROFILE vmhost add-tag $VMHOST_ID tag=$TAG_NAME


maas $PROFILE vmhost remove-tag $VMHOST_ID tag=$TAG_NAME

maas $PROFILE vmhost read $VMHOST_ID | jq -r '(["name","id","tags"]
|(.,map(length*"-"))),([.name,.id,.tags[]]) | @tsv' | column -t
```

### Find tagged machines

**UI**
*Machines* > *Filters* dropdown > Expand *Tags* > [Select tags]

Filter will gradually winnow down to only those machines carrying the tags you picked.  You can actually combine other items in this filter (pool, zone, status...).

**CLI**
```
# $PROFILE = your admin profile name
maas $PROFILE machines read | jq -r '.[] | select(.tags[]? == "TAG_NAME") | [.hostname,.system_id] | @tsv'
```

## Manage notes in MAAS

Notes are longer, persistent descriptions attached to a machine. They remain with the machine throughout its life-cycle unless manually updated or cleared.

### Add or modify notes

**UI**
1. Go to **Machines > (Machine)**.
2. Select **Configuration > Edit**.
3. Enter or edit the **Note** field.
4. Click **Save changes**.

**CLI**
```
# $PROFILE = your admin profile name
maas $PROFILE machines read | jq -r '(["hostname","system_id"]
|(.,map(length*"-"))),(.[]|[.hostname,.system_id]) | @tsv' | column -t

maas $PROFILE machine update $SYSTEM_ID description="$NOTE"
```

### Delete a note

**UI**
*Machines* > [Select machine] > *Configuration* > *Edit* > [Erase the note field] > *Save changes*

**CLI**
```
# $PROFILE = your admin profile name
maas $PROFILE machine update $SYSTEM_ID description=""
```

### Search for machines with notes

**CLI**
```
# $PROFILE = your admin profile name
maas $PROFILE machines read | jq -r '.[] | select(.description != null and .description != "") | [.hostname,.system_id,.description] | @tsv'
```

## Manage dynamic annotations in MAAS

Dynamic annotations are ephemeral, key–value metadata attached to machines. They only exist during allocation or deployment and are lost when the machine is released.

> **Note**: Dynamic annotations are not supported in MAAS 2.9 or earlier.

### Identify eligible machines

**CLI only**
```
# $PROFILE = your admin profile name
maas $PROFILE machines read | jq -r '(["hostname","system_id","status"]
|(.,map(length*"-"))),(.[]|[.hostname,.system_id,.status_name]) | @tsv' | column -t
```

### Set an annotation

**CLI only**
```
# $PROFILE = your admin profile name
maas $PROFILE machine set-workload-annotations $SYSTEM_ID KEY=VALUE
```

### Update an annotation

**CLI only**
```
# $PROFILE = your admin profile name
maas $PROFILE machine set-workload-annotations $SYSTEM_ID KEY=NEW_VALUE
```

### Remove an annotation

**CLI only**
```
# $PROFILE = your admin profile name
maas $PROFILE machine set-workload-annotations $SYSTEM_ID KEY=""
```

### List annotations

**CLI only**
```
# $PROFILE = your admin profile name
maas $PROFILE machines read | jq -r '(["hostname","system_id","owner_data"]
|(.,map(length*"-"))),(.[]|[.hostname,.system_id,.owner_data]) | @tsv'
```

### Search for machines with a specific annotation

**CLI only**
```
# $PROFILE = your admin profile name
maas $PROFILE machines read | jq -r '.[] | select(.owner_data.KEY == "VALUE") | [.hostname,.system_id] | @tsv'
```

## Best practices: Choosing the right grouping tool

### Machine grouping cheat sheet

| Grouping tool        | General usage in MAAS                                                                 | Special case: GU                                                                 | Special case: OpenStack                                                              | Special case: RBAC                                                        |
| **Tags**             | Flexible labels, multiple per machine. Use for filtering, commissioning, or deployment selection. Can be manual or automatic (XPath). | Juju ignores tags directly, but you can target machines indirectly by tag when adding them to models or constraints. | Same as Juju—tags aren’t first-class in OpenStack, but can help when mapping hardware to specific use cases before handoff. | No direct tie-in to RBAC; tags are just metadata.                         |
| **Availability zones (AZs)** | One per machine. Conceptually “fault domains.” In plain MAAS, it’s just a label.                         | Juju respects AZs as failover zones. Workloads can be scheduled across zones for HA. | OpenStack also respects AZs as placement/failover domains; ensures workloads don’t all land in the same failure point. | No RBAC connection—zones don’t control access, just placement.            |
| **Resource pools**   | One per machine. Just a label in plain MAAS, often used for org or project grouping.   | Juju does not use pools.                                                            | OpenStack does not use pools.                                                        | Pools are the main grouping mechanism tied to RBAC. Assigning a pool restricts which users or teams can access those machines. |


If you’re trying to decide which grouping mechanism to use, it helps to think in terms of what problem you’re solving:

- Use tags when you need flexibility. Tags are lightweight, many-to-many, and perfect for slicing across your fleet based on characteristics or ad-hoc labels. They don’t control access or failover, but they’re ideal for tasks like “deploy only machines with SSDs” or “commission all nodes tagged gpu.”

- Use availability zones or resource pools as one-to-many labels when you are not interested in fault domains or access control.  Just remember that you can only have one of each per machine, so if you decide later to add fault domains or access control via Juju or OpenStack, you may need to transition your current one-to-one groupings to tags.

- Use availability zones when you might later care about high availability or fault domains. By themselves, zones are just labels, but when paired with Juju or OpenStack, they become meaningful: those tools will spread workloads across zones so that a failure in one zone doesn’t take everything down. If you’re running without those tools, zones can still act as “big buckets” to divide machines into, but they shine most in HA contexts.

- Use resource pools when access control might later be the priority. Pools tie directly into RBAC, letting you say “team A can only use machines in pool X.” Outside of RBAC, they’re just another single-label grouping mechanism, but if you want to enforce organizational boundaries -- like separating dev and prod users -- pools are the right choice.

In short: tags = many-to-many flexible filters, zones = one-to-many failover domains, pools = one-to-many access control.
	
