MAAS offers powerful tools to manage machines, from discovery and commissioning to deployment, configuration, and troubleshooting. This guide covers everything you need, whether working with bare metal servers, virtual machines, or pre-deployed systems.

## Discover and find machines 

Before managing machines, you need to discover, identify, and locate them.

### Discover active devices

MAAS monitors network traffic to automatically detect connected devices, including machines, switches, bridges, and other network hardware. 

**UI**  
*Networking* > *Network discovery*  

**CLI**  
```bash
    maas $PROFILE discoveries read
```

### Find a machine’s system ID  

Everything in MAAS revolves around the system ID, which is easily located.  

**UI**  
1. *Machines* > *[machine]* 
2. Check browser URL: `...machine/<SYSTEM_ID>/summary`)  

**CLI**  
```bash
    maas admin machines read | jq -r '(["HOSTNAME","SYSID"] | (., map(length*"-"))),(.[] | [.hostname, .system_id]) | @tsv' | column -t
```

### List machines

View all the machines in your MAAS instance.
  
**UI**  
*Machines* (View list)  

**CLI**  
```bash
    maas $PROFILE machines read | jq -r '(["HOSTNAME","SYSID","STATUS"] | join(","))'
```

> Related: [Commission machines](https://maas.io/docs/how-to-manage-machines#p-9078-commission-test-machines) | [Control power](https://maas.io/docs/how-to-manage-machines#p-9078-control-machine-power)

### Search for machines

Use MAAS search syntax to find specific machines.  

**UI**  
*Hardware* > *Machines > *[Search bar]* and enter a search term; MAAS updates the list dynamically.  

Search syntax:
| Type | Example |
|:----|:----|
| Exact | pod:=able-cattle |
|Partial | pod:able,cattle |
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

## Add & configure machines

By default, machines are automatically commissioned when added to MAAS.

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


### Add machines via chassis

Use the chassis feature to add multiple machines at once. 

**UI**
*Machines* > *Add hardware* > *Chassis* > (fill in the form) > *Save*

The required fields will change based on the type of chassis you choose.

### Clone a machine
 
Quickly duplicate an existing machine’s configuration.

**UI**  
*Machines* > *[machine]* > *Take action* > Clone*  

**CLI**  
```bash
    maas $PROFILE machine clone $SOURCE_SYSTEM_ID new_hostname=$NEW_HOSTNAME
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

### Add LXD for VM hosts

LXD setup is straightforward.

#### Remove old LXD versions

```bash
    sudo apt-get purge -y *lxd* *lxc*
    sudo apt-get autoremove -y
```

#### Install & initialize LXD

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

#### Disable DHCP for LXD’s bridge

```bash
    lxc network set lxdbr0 dns.mode=none
    lxc network set lxdbr0 ipv4.dhcp=false
    lxc network set lxdbr0 ipv6.dhcp=false
```

### Add a VM HOST

Use the recommended LXD host to create new LXD VMs.

**UI**
1. *KVM* > *LXD* > *Add LXD host* > Enter *Name*, *LXD address* and select *Generate new certificate*  
3. Run the provided command in the terminal to add trust.  
4. *Check authentication* > *Add new project* | *Select existing project* > *Save LXD host*.  

**CLI**
```bash
    maas $PROFILE vm-hosts create type=lxd power_address=$LXD_ADDRESS project=$PROJECT_NAME
```

### Add VMs  

Newly-created LXD VMs are automatically commissioned by default.

**UI**
*KVM* > *VM host name* > *Add VM* > *Name* > *Cores* > *RAM* > *Disks* > *Compose machine*  

**CLI**  
```bash
    maas $PROFILE vm-host compose $VM_HOST_ID cores=4 memory=8G disks=1:size=20G
```

### Move VMs between projects  

LXD VMs can be moved between [LXD projects](https://maas.io/docs/about-lxd).

```bash
    lxc move $VM_NAME $VM_NAME --project default --target-project $PROJECT_NAME
```
### Delete VMs

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

## Commission & test machines  

Commissioning gathers hardware information needed to correctly deploy images.

### Commission a machine  

Commission a machine to make it deployable.  

**UI**  
*Machines* > *[machine(s)]* > *Take action* > *Commission*  

**CLI**  
```bash
maas $PROFILE machine commission $SYSTEM_ID
```

### Run tests

Ensure the hardware is working correctly.

**UI**  
*Machines* > *[machine(s)]* > *Take action* > *Test*  

**CLI**  
```bash
maas $PROFILE machine test $SYSTEM_ID tests=cpu,storage
```

### View test results

Periodically review test results, even when there are no failures.

**UI**  
*Machines* > *[machine(s)]* > *Test results*  

**CLI**  
```bash
maas $PROFILE machine read $SYSTEM_ID | jq '.test_results'
```

### Override failed tests

**UI**  
*Machines* > *[machine(s)]* > *Take action* > *Override test results*  

**CLI**  
```bash
maas $PROFILE machine set-test-result $SYSTEM_ID result=passed
```

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

### Deploy to RAM 

Deploy an ephemeral instance (into machine RAM, ignoring any disk drives).

Learn more about [ephemeral deployment](https://maas.io/docs/about-deploying-machines#p-17464-deploying-ephemeral-os-instances-maas-35-and-higher)

**UI**
*Machines* > *[machine(s)]* > *Take action* > *Deploy* > *Deploy in memory* > *Deploy machine*

**CLI**
```bash
maas $PROFILE machine deploy $SYSTEM_ID ephemeral_deploy=true
```

### Deploy as a VM host

Deploy a bare-metal machine as a virtual machine host.

**UI**  
*Machines* > *[machine]* > *Take action* > *Deploy* > *Install KVM*  

**CLI**  
```bash
maas $PROFILE machine deploy $SYSTEM_ID install_kvm=True
```

### Deploy with custom cloud-init scripts

Use cloud-init to vary machine use-cases and application loads.

**UI**  
*Machines* > *[machine]* > *Take action* > *Deploy* > *Configuration options*  

**CLI**  
```bash
maas $PROFILE machine deploy $SYSTEM_ID cloud_init_userdata="$(cat cloud-init.yaml)"
```

## Configure other deployment settings

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

### View Hardware Sync Updates

View updates in the MAAS UI or CLI:
```bash
maas $PROFILE machine read $SYSTEM_ID
```

### Configure Hardware Sync Interval

Configure the sync interval in [MAAS settings](https://maas.io/docs/configuration-reference#p-17901-maas-behavior-settings).


### Set kernel version

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

### Set kernel parameters

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
