> *Errors or typos? Topics missing? Hard to read? <a href="https://docs.google.com/forms/d/e/1FAIpQLScIt3ffetkaKW3gDv6FDk7CfUTNYP_HGmqQotSTtj2htKkVBw/viewform?usp=pp_url&entry.1739714854=https://maas.io/docs/how-to-manage-machines" target = "_blank">Let us know.</a>

Most of the day-to-day work of managing machines is covered here. Utilising machines to do work -- for example, commissioning, testing, and deploying them -- is discussed in [How to deploy machines](/t/how-to-deploy-machines-with-maas/5112). 

## Add machines

In the MAAS UI, select *Machines* > *Add hardware* > *Machine* > fill in the form > *Save machine* (or *Save and add another*).  The fields in this form are as follows:

- **Machine name**: This field is used to identify the machine to the user.  It can be set to anything, though it is often set to the MAC address of the machine in question.  This field is optional, in that MAAS will assign a unique, nonsense name if you leave it blank.  You can change this nonsense name later, if desired.

- **Domain**: This field sets the domain name of the domain managed by MAAS.  It can be set to anything; MAAS assigns the domain name "maas" by default.

- **Architecture**: This field refers to the architecture of the machine being added.

- **Minimum Kernel**: This field supplies a drop-down of possible kernels available for deployment on this machine.

- **Zone**: This field allows you to set the availability zone, selected from AZs that you have already created (if any).

- **Resource pool**: This field allows you to set the resource pool for this machine, selected from pools you have already created (if any).

- **MAC Address**: You should fill in this field with the MAC address of the machine you are adding.  Note that the MAC address entered here must use a colon (":") separator, although some MAC addresses are written with dash ("-") separators.

- **Power type**: You must select the power type supported by the machine you are adding, and fill in additional required fields that appear.  See [Power management reference](/t/how-to-set-up-power-drivers/5246) for details on the available power types and the relevant parameters for each type.

To create a new machine at the command line, enter the following command:

```nohighlight
stormrider@wintermute:~$ maas admin machines create \
> architecture=$ARCH \
> max_addresses=$MAC_ADDRESS \
> power_type=$POWER_TYPE \
> power_parameters_power_id=$POWER_ID \
> power_parameters_power_address=$POWER_ADDRESS \
> power_parameters_power_pass=$POWER_PASSWORD
```

When you enter the command (substituting the `$...` parameters for your own particulars), the screen will pause for a moment, and then return a stream of JSON relating to the added machine.

Here's an example with a local laptop MAAS install, using KVMs as virtual machines:

```nohighlight
stormrider@wintermute:~$ maas admin machines create \
> architecture=amd64 \
> max_addresses=52:54:00:6f:b4:af \
> power_type=virsh \
> power_parameters_power_id=50f6cca2-5d89-43b9-941c-90c9fcd7c156 \
> power_parameters_power_address=qemu+ssh://stormrider@192.168.123.1/system \
> power_parameters_power_pass=xxxxxxx
```

The variable fields in the `machines create` command (the `$...` items) are as follows, in this example: 

```nohighlight
> architecture=$ARCH \
> mac_addresses=$MAC_ADDRESS \
> power_type=$POWER_TYPE \
> power_parameters_power_id=$POWER_ID \
> power_parameters_power_address=$POWER_ADDRESS \
> power_parameters_power_pass=$POWER_PASSWORD
```

- `$ARCH`: This field refers to the architecture of the machine being added, `amd64` in the local laptop example.

- `$MAC_ADDRESS`: This is the MAC address of the boot-enabled NIC for the machine being added.  Note that the MAC address entered here must use a colon (":") separator, although some MAC addresses are written with dash ("-") separators.

- `$POWER_TYPE`: You must select the power type supported by the machine you are adding, and fill in additional required fields that appear.  See [Power management reference](/t/how-to-set-up-power-drivers/5246) for details on the available power types and the relevant parameters for each type. In this example, we've used a "virsh" power type (a libvirt KVM), but your choice will depend on your hardware.

- `$POWER_ID`: This is generally the UUID of the machine being added.

- `$POWER_ADDRESS/$POWER_PASSWORD`: In the case of a KVM, these are the only parameters that need to be entered.  See [Power types](https://maas.io/docs/api#power-types)**^** in the API reference for details on the available power types and the relevant parameters for each type.

## Add machines via chassis (UI)

You can use the chassis feature to add multiple machines at once. To do this, select *Machines* > *Add hardware* > *Chassis* > fill in the form > *Save...."  The required fields will change based on the type of chassis you choose.

## Delete USB and PCI (CLI)

> Note that USB and PCI devices are not visible in MAAS 2.9 and below.

To delete PCI/USB devices from the machine in any machine state, use the following command:

```nohighlight
maas $PROFILE node-device delete $SYSTEM_ID $DEVICE_ID
```

where:

- $PROFILE   = your user profile (e.g., "admin")
- $SYSTEM_ID = the ID of the machine in question (e.g., "ngx7ry")
- $DEVICE_ID = the ID of the device you want to delete 

If the device is still present in the system, it will be recognised again (and thus "recreated") when the machine is commissioned again.

## Clone machines (MAAS 3.1 and above, UI only)

To clone machines, select *Machines* > choose machine > *Actions* > *Clone from* > ***source machine*** > ***options*** > *Clone to machine*.

## Soft power off (MAAS 3.5 and above, UI only)

To power-off machines "softly" -- that is, by asking the deployed OS to shut down gracefully -- choose *Machines* > ***machines*** > *Power* > *Soft Power Off* > *Confirm*.

## List machines

To list machines:

* In the MAAS UI, select *Machines*.

* Via the CLI, enter a command similar to this one:

```nohighlight
    maas $PROFILE machines read | jq -r '(["HOSTNAME","SYSID",
    "POWER","STATUS","OWNER", "TAGS", "POOL","VLAN","FABRIC",
    "SUBNET"] | (., map(length*"-"))),(.[] | [.hostname, .system_id, 
    .power_state, .status_name, .owner // "-",.tag_names[0] // "-", 
    .pool.name,.boot_interface.vlan.name,.boot_interface.vlan.fabric,
    .boot_interface.links[0].subnet.name]) | @tsv' | column -t
```
    
    This will return a relatively compact machine listing:
    
```nohighlight
    HOSTNAME      SYSID   POWER  STATUS     OWNER  TAGS                 POOL     VLAN      FABRIC    SUBNET
     --------      -----   -----  ------     -----  ----                 ----     ----      ------    ------
     lxd-vm-1      r8d6yp  off    Deployed   admin  pod-console-logging  default  untagged  fabric-1  10.124.141.0/24
     lxd-vm-2      tfftrx  off    Allocated  admin  pod-console-logging  default  untagged  fabric-1  10.124.141.0/24
     lxd-vm-3      grwpwc  off    Ready      -      pod-console-logging  default  untagged  fabric-1  10.124.141.0/24
     lxd-vm-4      6s8dt4  off    Deployed   admin  pod-console-logging  default  untagged  fabric-1  10.124.141.0/24
     lxd-vm-5      pyebgm  off    Allocated  admin  pod-console-logging  default  untagged  fabric-1  10.124.141.0/24
     lxd-vm-6      ebnww6  off    New        -      pod-console-logging  default  untagged  fabric-1  
     libvirt-vm-1  m7ffsg  off    Ready      -      pod-console-logging  default  untagged  fabric-1  10.124.141.0/24
     libvirt-vm-2  kpawad  off    Ready      -      pod-console-logging  default  untagged  fabric-1  10.124.141.0/24
     libvirt-vm-3  r44hr6  error  Ready      -      pod-console-logging  default  untagged  fabric-1  10.124.141.0/24
     libvirt-vm-4  s3sdkw  off    Ready      -      pod-console-logging  default  untagged  fabric-1  10.124.141.0/24
     libvirt-vm-5  48dg8m  off    Ready      -      pod-console-logging  default  untagged  fabric-1  10.124.141.0/24
     libvirt-vm-6  bacx77  on     Deployed   admin  pod-console-logging  default  untagged  fabric-1  10.124.141.0/24
```
    
## View machine details

To open a detailed view of a machine's status and configuration:

* In the MAAS 3.4 UI, select *Machines* > <machine name>.

* With the UI for all other MAAS versions, select a given machine's *FQDN* or *MAC address*.

* Via the MAAS CLI, execute the following shell script:

```nohighlight
    #!/bin/nohighlight
    
    maas admin machine read r3rd6h | jq '.' > /tmp/machine-json
    cat /tmp/machine-json | jq -r '([.hostname,.status_name,"| Power:",.power_state,"| Kernel:",.hwe_kernel,"| Owner:",.owner]) | @tsv' | column -t -o " " > /tmp/machine-details
    cat /tmp/machine-json | jq -r '(["CPU:",.architecture,"/",.cpu_count,"core(s) /",.cpu_speed,"Mhz","| Type:",.hardware_info.cpu_model]) | @tsv' | column -t -o " " >> /tmp/machine-details
    cat /tmp/machine-json | jq -r '(["Memory:",.memory,"MB | Storage:",.storage,"MB | Power type:",.power_type]) | @tsv' | column -t -o " " >> /tmp/machine-details
    cat /tmp/machine-json | jq -r '(["Zone:",.zone.name,"| Resource pool:",.pool.name,"| Domain:",.domain.name]) | @tsv' | column -t -o " " >> /tmp/machine-details
    cat /tmp/machine-json | jq -r '(["Tags:",.tag_names[]]) | @tsv' | column -t -o " " >> /tmp/machine-details
    cat /tmp/machine-json | jq -r '(["SYSTEM Vendor:",.hardware_info.system_vendor,"| Product:",.hardware_info.system_product]) | @tsv' | column -t -o " " >> /tmp/machine-details
    cat /tmp/machine-json | jq -r '([".......Vsn:",.hardware_info.system_version,"| Serial:",.hardware_info.system_serial]) | @tsv' | column -t -o " " >> /tmp/machine-details
    cat /tmp/machine-json | jq -r '(["MAINBOARD Vendor:",.hardware_info.mainboard_vendor,"| Product:",.hardware_info.mainboard_product]) | @tsv' | column -t -o " " >> /tmp/machine-details
    cat /tmp/machine-json | jq -r '(["..........Firmware:",.hardware_info.mainboard_firmware_vendor]) | @tsv' | column -t -o " " >> /tmp/machine-details
    cat /tmp/machine-json | jq -r '(["..........Firmware Vsn:",.hardware_info.mainboard_firmware_version,"| Date:",.hardware_info.mainboard_firmware_date]) | @tsv' | column -t -o " " >> /tmp/machine-details
    cat /tmp/machine-json | jq -r '(["NETWORK: Vendor:",.boot_interface.vendor]) | @tsv' | column -t -o " " >> /tmp/machine-details
    cat /tmp/machine-json | jq -r '([".........Name:",.boot_interface.name,"| MAC:",.boot_interface.mac_address,"| Link speed:",.boot_interface.link_speed,"Mbps"]) | @tsv' | column -t -o " " >> /tmp/machine-details
    cat /tmp/machine-json | jq -r '([".........Fabric:",.boot_interface.vlan.fabric,"| MAAS DHCP:",.boot_interface.vlan.dhcp_on,"| SR-IOV:",.boot_interface.sriov_max_vf]) | @tsv' | column -t -o " " >> /tmp/machine-details
    cat /tmp/machine-details
```
    
    This shell script should produce output similar to the following:
    
```nohighlight
    merry-cobra Deployed | Power: on | Kernel: ga-20.04 | Owner: admin
    CPU: amd64/generic / 1 core(s) / 1600 Mhz | Type: Intel(R) Core(TM) i5-8265U CPU
    Memory: 2048 MB | Storage: 8000.004096 MB | Power type: lxd
    Zone: default | Resource pool: default | Domain: maas
    Tags: pod-console-logging virtual
    SYSTEM Vendor: QEMU | Product: Standard PC (Q35 + ICH9, 2009)
    .......Vsn: pc-q35-5.2 | Serial: Unknown
    MAINBOARD Vendor: Canonical Ltd. | Product: LXD
    ..........Firmware: EFI Development Kit II / OVMF
    ..........Firmware Vsn: 0.0.0 | Date: 02/06/2015
    NETWORK: Vendor: Red Hat, Inc.
    .........Name: enp5s0 | MAC: 00:16:3e:cc:17:58 | Link speed: 0 Mbps
    .........Fabric: fabric-5 | MAAS DHCP: true | SR-IOV: 0
```

## Find network info (UI)

To find network info for a specific machine, select *Machines* > machine name > *Network*.

## Find storage info (UI)

To view/edit machine storage info:

To find network info for a specific machine, select *Machines* > machine name > *Storage*.

## View PCI devices (MAAS 3.4 only)

To view the list of PCI devices associated with a given machine, select *Machines* > machine name > *PCI devices*.

## View USB devices (MAAS 3.4 only)

To view the list of USB devices associated with a given machine, select *Machines* > machine name > *USB*.

## View commissioning logs (UI)

To view commissioning logs for a given machine, select *Machines* > machine name > *Commissioning* > *View details* (or *View previous tests*).

## View test logs (UI)

To view commissioning logs for a given machine, select *Machines* > machine name > *Test* > *View details* (or *View previous tests*).

## View raw log output (UI)

To view raw log output for a given machine, select *Machines* > machine name > *Logs* > *Installation output*.

## View event logs

To view event logs for a given machine, select *Machines* > machine name > *Logs* > *Download* > <drop-down selection>.

## View configuration info

To view configuration info for a given machine, select *Machines* > machine name > *Configuration*.

More information on power configuration will be found in the [Power management](/t/how-to-set-up-power-drivers/5246) section of this documentation.