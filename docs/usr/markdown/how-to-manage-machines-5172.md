MAAS offers powerful tools to manage machines, from discovery and commissioning to deployment, configuration, and troubleshooting. This guide covers everything you need, whether working with bare metal servers, virtual machines, or pre-deployed systems.

## Discover machines 

Before managing machines, you need to discover, identify, and locate them.

### Discover active devices

MAAS monitors network traffic to automatically detect connected devices, including machines, switches, bridges, and other network hardware. 

**UI**
*Networking* > *Network discovery*

**CLI**
```bash
    maas $PROFILE discoveries read
```

### List machines

#### Show all registered machines

**UI**
*Machines* (View list)

**CLI**
```bash
    maas $PROFILE machines read | jq -r '(["HOSTNAME","SYSID","STATUS"] | join(","))'
```

#### Show a specific machine

Every machine has a unique system ID; find them with this command:

**UI**
1. *Machines* > *[machine]* 
2. Check browser URL: `...machine/<SYSTEM_ID>/summary`)

**CLI**
```bash
    maas admin machines read | jq -r '(["HOSTNAME","SYSID"] | (., map(length*"-"))),(.[] | [.hostname, .system_id]) | @tsv' | column -t
```

Use the system ID to get details for a particular machine.

**UI**
*Machines* > [Select machine]

**CLI**
```bash
    maas $PROFILE machine read $SYSTEM_ID
```

### Search for machines

Use MAAS search syntax to find specific machines.

**UI**
*Hardware* > *Machines > *[Search bar]* and enter a search term; MAAS updates the list dynamically.

Search syntax:
| Type | Example |
|:----|:----|
| Exact | pod:=able-cattle |
| Partial | pod:able,cattle |
| Negation | pod:!cattle |

**CLI**
```bash
    maas $PROFILE machines read | jq -r '(["HOSTNAME","SYSID","STATUS"] | join(","))'
```

#### Filter machines by parameters

Filter your search against many attributes, using the MAAS UI.

**UI**
*Hardware* > *Machines* > *Filters*

MAAS dynamically builds search terms that you can mimic, copy and re-use.

## Enable new machines

Machines are automatically commissioned when added to MAAS.

### Add a machine

To manually add a machine, provide architecture, MAC address, and power settings.

**UI**
*Machines* > *Add hardware*

**CLI**
```bash
    maas $PROFILE machines create architecture=$ARCH \
    mac_addresses=$MAC_ADDRESS power_type=$POWER_TYPE \
    power_parameters_power_id=$POWER_ID \
    power_parameters_power_address=$POWER_ADDRESS 
    power_parameters_power_pass=$POWER_PASSWORD
```
MAAS automatically commissions newly-added machines.  To change this, enter:

```nohighlight
    maas $PROFILE maas set-config name=enlist_commissioning value=false
```

#### Add machines via chassis

Use the chassis feature to add multiple machines at once. 

**UI**
*Machines* > *Add hardware* > *Chassis* > (fill in the form) > *Save*

The required fields will change based on the type of chassis you choose.

#### Clone a machine
 
Quickly duplicate an existing machine’s configuration.

**UI**
*Machines* > *[machine]* > *Take action* > *Clone*

**CLI**
```bash
    maas $PROFILE machine clone $SOURCE_SYSTEM_ID new_hostname=$NEW_HOSTNAME
```

### Use LXD VMs

MAAS can also provision virtual machines (VMs).  LXD is the recommended VM host.

#### Set up LXD for use with MAAS
##### Remove old LXD versions

```bash
    sudo apt-get purge -y *lxd* *lxc*
    sudo apt-get autoremove -y
```

##### Install & initialize LXD

```bash
    sudo snap install lxd
    sudo snap refresh
    sudo lxd init
```
- Clustering: `no`
- Storage: `dir`
- MAAS Connection: `no`
- Existing Bridge: `yes` (`br0`)
- Trust Password: Provide a password

##### Disable DHCP for the LXD bridge

```bash
    lxc network set lxdbr0 dns.mode=none
    lxc network set lxdbr0 ipv4.dhcp=false
    lxc network set lxdbr0 ipv6.dhcp=false
```

#### Add a VM HOST

Use the recommended LXD host to create new LXD VMs.

**UI**
1. *KVM* > *LXD* > *Add LXD host* > Enter *Name*, *LXD address* and select *Generate new certificate*.
2. Run the provided command in the terminal to add trust.
3. *Check authentication* > *Add new project* | *Select existing project* > *Save LXD host*.

**CLI**
```bash
    maas $PROFILE vm-hosts create type=lxd power_address=$LXD_ADDRESS project=$PROJECT_NAME
```

#### Add VMs

Newly-created LXD VMs are automatically commissioned by default.

**UI**
*KVM* > *VM host name* > *Add VM* > *Name* > *Cores* > *RAM* > *Disks* > *Compose machine*

**CLI**
```bash
    maas $PROFILE vm-host compose $VM_HOST_ID cores=4 memory=8G disks=1:size=20G
```

#### Move VMs between LXD projects

LXD VMs can be moved between [LXD projects](https://maas.io/docs/about-lxd).

```bash
    lxc move $VM_NAME $VM_NAME --project default --target-project $PROJECT_NAME
```
#### Delete VMs

Deleted VMs cannot be recovered.

**UI**
*Machine* > *[machine]* > *Delete* > *Delete machine*

**CLI**
  ```bash
  maas $PROFILE machine delete $SYSTEM_ID
  ```

## Control machine power

Turn machines on if needed; turn them off abruptly or gracefully.

### Turn on a machines

Machine booting varies by PXE or deployed OS.

**UI**
*Machines* > *[machine]* > *Take action* > *Power on*

**CLI**
```bash
maas $PROFILE machine start $SYSTEM_ID
```

### Turn off a machine

Use this method when you want to immediately turn off a machine.

**UI**
*Machines* > *[machine]* > *Take action* > *Power off*

**CLI**
```bash
maas $PROFILE machine stop $SYSTEM_ID
```

### Soft power-off

Use this method to initiate a system shutdown.

```bash
maas $PROFILE machine stop $SYSTEM_ID force=false
```

### Set power type 

Set the correct power type so MAAS can control the machine.

**UI**
*Machines* > *[machine]* > *Configuration* > *Power* > *Edit*

**CLI**
```bash
    maas $PROFILE machine update $SYSTEM_ID power_type="$POWER_TYPE"
```

#### Verifying Redfish activation

You can check if a machine communicates via Redfish with the command:

```nohighlight
    dmidecode -t 42
```

You can also review the `30-maas-01-bmc-config` commissioning script's output if the machine is already enlisted in MAAS.

## Commission & test machines

Commissioning gathers hardware information needed to correctly deploy images.

### Commission machines

Commission a machine to make it deployable.

**UI**
*Machines* > *[machine(s)]* > *Take action* > *Commission*

**CLI**
```bash
maas $PROFILE machine commission $SYSTEM_ID
```

### Test machines

Ensure the hardware is working correctly.

**UI**
*Machines* > *[machine(s)]* > *Take action* > *Test*

**CLI**
```bash
maas $PROFILE machine test $SYSTEM_ID tests=cpu,storage
```

#### View test results

Periodically review test results, even when there are no failures.

**UI**
*Machines* > *[machine(s)]* > *Test results*

**CLI**
```bash
maas $PROFILE machine read $SYSTEM_ID | jq '.test_results'
```

#### Override failed tests

**UI**
*Machines* > *[machine(s)]* > *Take action* > *Override test results*

**CLI**
```bash
maas $PROFILE machine set-test-result $SYSTEM_ID result=passed
```

## Configure deployment

Set kernel versions, boot options, and storage configuration on deployment; manage hardware sync.


### Enable hardware sync (MAAS 3.2+)

To enable hardware sync:

- **MAAS 3.4+ UI:**
  *Machines* > machine > *Actions* > *Deploy* > *Periodically sync hardware* > *Start deployment*.

- **Other versions UI:**
  *Take action* > *Deploy* > *Periodically sync hardware* > *Start deployment*.

- **CLI:**
  ```bash
  maas $PROFILE machine deploy $SYSTEM_ID osystem=$OSYSTEM distro_series=$VERSION enable_hw_sync=true
  ```

#### View hardware sync updates

View updates in the MAAS UI or CLI:
```bash
maas $PROFILE machine read $SYSTEM_ID
```

### Configure hardware sync interval

Configure the sync interval in [MAAS settings](https://maas.io/docs/configuration-reference#p-17901-maas-behavior-settings).

### Configure kernels

Many kernel parameters, including the kernel version, can be specified prior to deployment.

#### Set kernel version

Set the system-wide, default minimum kernel version for commissioning:

**UI**
*Settings* > *Configuration* > *Commissioning* > *Default minimum kernel version*

**CLI**
```bash
maas $PROFILE maas set-config name=default_min_hwe_kernel value=$KERNEL
```

Set a default minimum kernel version per machine:

**UI**
*Machines* > *[machine]* > *Configuration* > *Edit* > *Minimum kernel*

**CLI**
```bash
maas $PROFILE machine update $SYSTEM_ID min_hwe_kernel=$HWE_KERNEL
```

Deploy a machine with a specific kernel:

**UI**
*Machines* > *[machine]* > *Take action* > *Deploy* > *[Choose kernel]*

**CLI**
```bash
maas $PROFILE machine deploy $SYSTEM_ID distro_series=$SERIES hwe_kernel=$KERNEL
```

#### Set kernel parameters

Specify system-wide boot options.

**UI**
*Settings* > *Kernel parameters*

**CLI**
```bash
maas $PROFILE maas set-config name=kernel_opts value='$KERNEL_OPTIONS'
```

### Configure storage layout

Specify a default layout for all machines:

**UI**
*Settings > Storage > Default layout*

**CLI**
```bash
maas $PROFILE maas set-config name=default_storage_layout value=$LAYOUT_TYPE
```

Specify a storage layout for a specific machine:

**UI**
*Machines* > *[machine]* > *Storage* > *[Edit layout]*

**CLI**
```bash
maas $PROFILE machine set-storage-layout $SYSTEM_ID storage_layout=$LAYOUT_TYPE
```

Machines must be in the "Ready" state to modify their storage layout.

#### Flat layout

A flat layout means one partition uses the whole disk, formatted with an `ext4` filesystem and mounted as root (`/`).  Create a per-machine flat layout with these commands:

**UI**
*Machines* > Choose machine > *Storage* > *Change storage layout* > Choose dropdown "Flat"

**CLI**
```bash
maas $PROFILE machine set-storage-layout $SYSTEM_ID storage_layout=flat
```

The flat layout is ideal for general-purpose filesystems that support large files and volumes.  A flat layout supports a short list of options, including boot size, root size, and root device designation.

[About the flat layout](https://maas.io/docs/about-machine-customization#p-17465-flat-storage-layout) | [Flat layout setup reference](https://maas.io/docs/reference-maas-storage#p-17455-flat-layout)

#### LVM layout

An LVM layout offers flexible and dynamic disk management, with easier resizing, snapshots, and volume management.  Create an LVM layout with the following commands:

**UI**
*Machines* > Choose machine > *Storage* > *Change storage layout* > Choose dropdown "LVM"

**CLI**
```bash
maas $PROFILE machine set-storage-layout $SYSTEM_ID storage_layout=lvm
```

LVM comes in handy when using multiple physical disks as a single, larger volume -- something that a flat layout will not support.  In addition to the `flat` configuration options, LVM also supports naming volume groups, as well as creating logical volumes with specific names and sizes.

[About the LVM layout](https://maas.io/docs/about-machine-customization#p-17465-lvm-layout) | [LVM layout setup reference](https://maas.io/docs/reference-maas-storage#p-17455-lvm-layout)

#### bcache layout

The bcache layout uses the boot disk as the backing device and a Solid-State Drive (SSD) as the cache.  This arrangement speeds up read and write operations by caching frequently-accessed data on the SSD.

Create a bcache layout with the following commands:

**UI**
*Machines* > Choose machine > *Storage* > *Change storage layout* > Choose dropdown "bcache"

**CLI**
```bash
maas $PROFILE machine set-storage-layout $SYSTEM_ID storage_layout=bcache
```

Note that an SSD device must be available to create this layout.  If SSD is not available when these commands are given, MAAS defaults to the `flat` layout.

The `bcache` layout is useful and cost effective when you want to improve I/O performance by leveraging SSDs as cache for larger, slower disks.  Also, applications that are read-intensive can benefit from `bcache` as well.

`bcache` introduces new options: the physical block device to use for caching, and the size of cache partition (or "no partition" to use the whole block device).

[About the bcache layout](https://maas.io/docs/about-machine-customization#p-17465-bcache-layout) | [bcache layout setup reference](https://maas.io/docs/reference-maas-storage#p-17455-bcache-layout)

#### VMFS6/VMFS7 layouts

The VMFS6 layout is specifically designed for deploying VMWare ESXi hosts.  It automates the creation of the partitions and datastores required for VMWare.  Use the following commands to create a `vmfs6` or `vmfs7` layout:

**UI**
*Machines* > Choose machine > *Storage* > *Change storage layout* > Choose dropdown "VMFS6" or dropdown "VMFS7"

**CLI**
```bash
maas $PROFILE machine set-storage-layout $SYSTEM_ID storage_layout=vmfs6
```
or
```bash
maas $PROFILE machine set-storage-layout $SYSTEM_ID storage_layout=vmfs7
```

The choice of VMFS6 or VMFS7 depends on the VMWare version being deployed.  Both layouts allow you to specify the root device and root filesystem size. Note that the resultant filesystem layout should not be altered.

[VMFS6/7 layout setup reference](https://maas.io/docs/reference-maas-storage#p-17455-vmfs6-layout)

#### Blank layout

The `blank` layout removes all existing storage configuration from a machine's disks.  No actual disk layout is provided, so partitions, filesystems and mount points must be created manually.  Create this layout with the following commands:

**UI**
*Machines* > Choose machine > *Storage* > *Change storage layout* > Choose dropdown "No storage..."

**CLI**
```bash
maas $PROFILE machine set-storage-layout $SYSTEM_ID storage_layout=blank
```

Note that machines with the `blank` layout cannot be deployed; you must first configure storage manually or via `curtin` in a commissioning script.

#### Custom layouts

MAAS version 3.1 and higher allow you to define a custom storage layout for a machine, via a custom commissioning script. You must upload a script which conforms to the following rules:

- it must run after the `40-maas-01-machine-resources` script and before the `50-maas-01-commissioning` one, so it should have a name that starts with anything between `41-` and `49-`. This ensures the script can access the JSON file created by the former which provides info about the machine hardware and network resources. In addition, the custom script can directly inspect the machine it's running on to determine how to configure storage.
- it can read machine hardware/network information from the JSON file at the path specified by `$MAAS_RESOURCES_FILE`
- it must output a JSON file at the path specified by `$MAAS_STORAGE_CONFIG_FILE` with the desired storage layout
- names of disks provided in the custom layout must match the ones detected by MAAS and provided in the resources file.

##### Config format

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

##### Disk

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

##### LVM

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

An `lvm` entry defines a VG (volume group) composed by a set of disks or partitions (listed as `members`). Optionally it's possible to specify the LVs (logical volumes) to create.
Those are defined similarly to partitions, with a name and size (and optionally the filesystem).

##### bcache

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

##### RAID

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
  ...
  }
```

A `raid` entry defines a RAID with a set of member devices.
Spare devices can also be specified.

## Deploy machines

Deploy machines to make them available for use.

### Allocate a machine

Claim exclusive ownership of a machine to avoid conflicts.

**UI**
*Machines* > *[machine(s)]* > *Take action* > *Allocate*

**CLI**
```bash
maas $PROFILE machines allocate system_id=$SYSTEM_ID
```

### Deploy a machine

Simultaneously deploy multiple machines, if desired, within resource limits.

**UI**
*Machines* > *[machine(s)]* > *Take action* > *Deploy* > *Deploy machine*

**CLI**
```bash
maas $PROFILE machine deploy $SYSTEM_ID
```

#### Deploy to RAM 

Deploy an ephemeral instance (into machine RAM, ignoring any disk drives).

Learn more about [ephemeral deployment](https://maas.io/docs/about-deploying-machines#p-17464-deploying-ephemeral-os-instances-maas-35-and-higher)

**UI**
*Machines* > *[machine(s)]* > *Take action* > *Deploy* > *Deploy in memory* > *Deploy machine*

**CLI**
```bash
maas $PROFILE machine deploy $SYSTEM_ID ephemeral_deploy=true
```

#### Deploy as a VM host

Deploy a bare-metal machine as a virtual machine host.

**UI**
*Machines* > *[machine]* > *Take action* > *Deploy* > *Install KVM*

**CLI**
```bash
maas $PROFILE machine deploy $SYSTEM_ID install_kvm=True
```

#### Deploy with custom cloud-init scripts

Use cloud-init to vary machine use-cases and application loads.

**UI**
*Machines* > *[machine]* > *Take action* > *Deploy* > *Configuration options*

**CLI**
```bash
maas $PROFILE machine deploy $SYSTEM_ID cloud_init_userdata="$(cat cloud-init.yaml)"
```

## Rescue & recovery

Use rescue mode to log onto a running machine and diagnose issues.

### Enter rescue mode

**UI**
*Machines* > *[machine]* > *Take action* > *Enter rescue mode*

**CLI**
```bash
maas $PROFILE machine enter-rescue-mode $SYSTEM_ID
```

### SSH into a machine to diagnose issues

Diagnose machine failures using standard tools and methods.

```bash
    ssh ubuntu@$MACHINE_IP
```

### Exit rescue mode

Attempt to put the machine back in service.

**UI**
*Machines* > *[machine]* > *Take action* > *Exit rescue mode*

**CLI**
```bash
maas $PROFILE machine exit-rescue-mode $SYSTEM_ID
```

### Mark a machine as broken

Indicate to all users that a machine is not currently usable.

**UI**
*Machines* > *[machine]* > *Take action* > *Mark broken*

**CLI**
```bash
maas $PROFILE machines mark-broken $SYSTEM_ID
```

### Mark a machine as fixed

Remove the "broken" designation.

**UI**
*Machines* > *[machine]* > *Take action* > *Mark fixed*

**CLI**
```bash
maas $PROFILE machines mark-fixed $SYSTEM_ID
```

## Release or remove machines

Release a machine to return it to the "Ready" state.  Remove a machine to permanently delete it from MAAS.

### Release a machine

MAAS will indicate if a machine cannot currently be released.

**UI**
*Machines* > *[machine]* > *Take action* > *Release*

**CLI**
```bash
maas $PROFILE machines release $SYSTEM_ID
```

#### Erase disks on release

Erasing a disk can take a long time, depending on the chosen method.

**UI**
*Machines* > *[machine]* > *Take action* > *Release* > *Enable disk erasure options*

**CLI**
```bash
maas $PROFILE machine release $SYSTEM_ID erase=true secure_erase=true quick_erase=true
```

### Delete a machine

Once deleted, a machine cannot be recovered.

**UI**
*Machines* > *[machine]* > *Take action* > *Delete*

**CLI**
```bash
maas $PROFILE machine delete $SYSTEM_ID
```

### Force delete a stuck machine

Force MAAS to delete a stuck machine using the CLI only.

```bash
maas $PROFILE machine delete $SYSTEM_ID force=true
```

## Verify everything

Periodically review your machine list to verify settings.

**UI**
*Machines* > *(View list or search)*

**CLI**
```bash
maas $PROFILE machines read | jq -r '.[].hostname'
```

