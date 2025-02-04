> *Errors or typos? Topics missing? Hard to read? <a href="https://docs.google.com/forms/d/e/1FAIpQLScIt3ffetkaKW3gDv6FDk7CfUTNYP_HGmqQotSTtj2htKkVBw/viewform?usp=pp_url&entry.1739714854=https://maas.io/docs/configuring-maas-controllers" target = "_blank">Let us know.</a>*

This guide walks through the MAAS workflow.  Equivalent UI and CLI commands are given when available.

## Discover devices

MAAS listens to connected networks and monitors IP traffic to discover active devices:

**UI** 
*Networking > Network discovery*

**CLI**
  ```nohighlight
     maas $PROFILE discoveries read
  ```

This action can be used to find the MAC addresses of connected devices, which may be valid machines that can be added to MAAS.

## Add machines

Add any valid machine for which you know the architecture, MAC address, power type, and power parameters:

**UI**
*Machines > Add hardware > Machine*; fill in the details and *Save*.

**CLI**
  ```bash
  maas $PROFILE machines create architecture=$ARCH mac_addresses=$MAC_ADDRESS \
    power_type=$POWER_TYPE power_parameters_power_id=$POWER_ID \
    power_parameters_power_address=$POWER_ADDRESS power_parameters_power_pass=$POWER_PASSWORD
  ```

> See "Power type reference guide" for acceptable values.

MAAS will automatically attempt to commission the machine.

## Find machine ID 

Most of the CLI commands which follow require the machine *system ID*, which can be easily discovered:

**UI**
 1. *Hardware > Machines > [machine]*
 2. In the browser address bar, the next-to-last parameter is the system ID:
 
```nohighlight
   http://192.168.1.106:5240/MAAS/r/machine/mwwh8g/summary
                                            ^^^^^^
```

**CLI*
```nohighlight
   maas admin machines read | jq -r '(["HOSTNAME","SIS'S"] | (., map(length*"-"))),
(.[] | [.hostname, .system_id]) | @tsv' | column -t
```

Tag the machine with its system ID for easy reference in the UI.

> See "Create a tag"

## Set machine power type

MAAS must be able to power cycle a machine through the  [BMC](https://en.wikipedia.org/wiki/Intelligent_Platform_Management_Interface#Baseboard_management_controller)**^**.  Until you set the power type, a machine can't be commissioned.

**UI**
*Hardware > Machines > [machine] > Configuration > Power configuration > Edit > Power type*; select the power type and fill in the neccessary fields, then choose *Save changes*.

**CLI**
```nohighlight
    maas $PROFILE machine update $SYSTEM_ID power_type="$POWER_TYPE"
```

Use these commands to change a machine's power type when necessary.

## Clone machines

MAAS can copy the network and/or storage configuration of one existing machine onto another:


  ```bash
  maas $PROFILE machine clone $SOURCE_SYSTEM_ID new_hostname=$NEW_HOSTNAME
  ```
  Replace `$SOURCE_SYSTEM_ID` with the system ID of the source machine and `$NEW_HOSTNAME` with the desired hostname for the clone.

## List machines


  ```bash
  maas $PROFILE machines read | jq -r '(["HOSTNAME","SYSID","STATUS"] | join(","))'
  ```

## Find machines

Here's how to form a MAAS search parameter:

![MAAS Search Parameter](https://discourse-maas-io-uploads.s3.us-east-1.amazonaws.com/original/2X/d/dcf5037cdd886eb85a2d305fd3df111b38865cea.png)

 - Use spaces for 'AND'
 - Enclose in parends and separated with commas for 'OR'

**UI**
*Hardware > Machines > [Search bar]* and enter a search term; MAAS progresses the search with each character typed.

For exact matches, prefix the search value with '='; for partial matches, omit it; and for negation, prefix a '!':

```no-highlight
Exact: pod:=able-cattle
Partial: pod:able,cattle
Negated: pod:!cattle
```

MAAS uses 'AND' logic by default for multiple terms. For instance, `pod:able,cattle cpu:=5` will show machines in pods named `able` or `cattle` with 5 CPU cores.

## Find by filtering

**UI**
*Hardware > Machines > Filters dropdown > [Parameter dropdown] > [Available value]* 

You may select values for multiple parameters.  MAAS builds the search term in the *Search box* and updates the machine list in real time. You can copy and save these search terms to an external list, or learn how to construct them manually by observation.

## View machine details


  ```bash
  maas $PROFILE machine read $SYSTEM_ID | jq '.'
  ```


## Abort any operation


  ```bash
  maas $PROFILE machine abort $SYSTEM_ID
  ```

## Turn on a machine


  ```bash
  maas $PROFILE machine start $SYSTEM_ID
  ```

## Turn off a machine


  ```bash
  maas $PROFILE machine stop $SYSTEM_ID
  ```

## Soft power-off a machine


  ```bash
  maas $PROFILE machine stop $SYSTEM_ID force=false
  ```

## Customize commissioning

Commissioning gathers the necessary information to successfully deploy a machine in a later step. You may optionally upload commissioning scripts to extend or modify the commissioning process:


*Settings > User scripts > Upload*; upload your script.

## Commission a machine

MAAS automatically commissions a newly-added machine.  Commissioning can also be started manually:

**UI**
*Machines > machine > Actions > Commission*; choose *Commission machine*.

**CLI**
  ```bash
  maas $PROFILE machine commission $SYSTEM_ID
  ```
## Test machines

Basic machine testing is part of the commissioning process. Tests can also be run manually:

**UI**
*Machines > machine > Actions > Test*. Select the tests to run (e.g., CPU, memory, storage) and choose *Start tests*.

**CLI**
  ```bash
  maas $PROFILE machine test $SYSTEM_ID tests=cpu,storage
  ```

## View test results

Test results can be viewed for a machine at any time:

**UI**
*Machines > machine > Test results*.

**CLI**
  ```bash
  maas $PROFILE machine read $SYSTEM_ID | jq '.test_results'
  ```

## Override failed testing


  ```bash
  maas $PROFILE machine set-test-result $SYSTEM_ID result=passed
  ```

## Test network connectivity

In addition to operational testing, MAAS can also test your network link

  ```bash
  maas $PROFILE machine network-interface $SYSTEM_ID test-connectivity
  ```

## Validate networks


  ```bash
  maas $PROFILE subnets read | jq '.[] | {name: .name, cidr: .cidr, vlan: .vlan}'
  ```

## List availability zones

  ```bash
  maas $PROFILE availability-zones read
  ```
## Create an availability zone

  ```bash
  maas $PROFILE availability-zones create name=$ZONE_NAME
  ```

## Attach an availability zone

  ```bash
  maas $PROFILE machine update $SYSTEM_ID zone=$ZONE_NAME
  ```
  
## Detach an availability zone


## Delete an availability zone


## List resource pools

  ```bash
  maas $PROFILE resource-pools read
  ```
## Create a resource pool

  ```bash
  maas $PROFILE resource-pools create name=$POOL_NAME
  ```
## Attach a resource pool

  ```bash
  maas $PROFILE machine update $SYSTEM_ID pool=$POOL_NAME
  ```

## Detach a resource pool

## Remove a resource pool

## List tags

  ```bash
  maas $PROFILE tags read
  ```

## Create a tag

- **Create a tag:**
  ```bash
  maas $PROFILE tags create name=$TAG_NAME comment="$COMMENT"
  ```

## Attach a tag 

  ```bash
  maas $PROFILE tag update-nodes $TAG_NAME add=$SYSTEM_ID
  ```

## Detach a tag

  ```bash
  maas $PROFILE tag update-nodes $TAG_NAME remove=$SYSTEM_ID
  ```

## Remove a tag

## Allocate a machine

Allocation confers ownership of a machine to the user who allocates it.  Other users cannot commandeer an allocation machine.

**CLI**
  ```bash
  maas $PROFILE machines allocate system_id=$SYSTEM_ID
  ```

## Allocate many machines

**UI**
*Machines > machine > Take action > Allocate*.

**CLI**
  ```bash
  maas $PROFILE machines allocate
  ```

## Preset curtin commands

Curtin customizes machine hardware (e.g., disk partitions) immediately prior to deployment. You can add Curtin commands via the `curtin_userdata` template or by adding a custom file. Curtin supports `early` and `late` hooks for pre/post-installation customization.

	- **Early Command Example:**
```yaml
  early_commands:
    signal: ["wget", "--no-proxy", "http://example.com/", "--post-data", "system_id=&signal=starting_install", "-O", "/dev/null"]
  ```
  - **Late Commands Example:**
	```yaml
  late_commands:
    add_repo: ["curtin", "in-target", "--", "add-apt-repository", "-y", "ppa:my/ppa"]
    custom: ["curtin", "in-target", "--", "sh", "-c", "/bin/echo -en 'Installed ' > /tmp/maas_system_id"]
  ```

## Add cloud-init scripts

Machine configuration can be modified with cloud-init scripts prior to being deployed (put in service).

**UI**
*Machines > machine > Actions > Deploy > Configuration options*; add your custom cloud-init script in the provided field.

**CLI**
  ```bash
  maas $PROFILE machine deploy $SYSTEM_ID cloud_init_userdata="$(cat cloud-init.yaml)"
  ```

## Set deployment timeout

MAAS aborts a deployment attempt if not successful within the timeout:

**CLI**
  ```bash
  maas $PROFILE maas set-config name=node-timeout value=$NUMBER_OF_MINUTES
  ```

> Note: the timeout is set in minutes.

## Set machine kernel

MAAS can deploy machines using a default minimum kernel level for the chosen OS image:

**UI**  
*Settings* > *Configuration* > *Commissioning* > *Default minimum kernel version* > *Save*.
  
**CLI**
  ```bash
  maas $PROFILE maas set-config name=default_min_hwe_kernel value=$KERNEL
  ```

You can also set a minimum kernel version for a specific machine:

**UI**
*Machines* > machine > *Configuration* > *Edit* > *Minimum kernel*.

**CLI**
  ```bash
  maas $PROFILE machine update $SYSTEM_ID min_hwe_kernel=$HWE_KERNEL
  ```

Finally, you can also set a specific kernel version for deployment, on a per-machine basis only:

**UI**  
*Machines* > machine > *Take action* > *Deploy* > choose kernel > *Deploy machine*.

**CLI**
  ```bash
  maas $PROFILE machine deploy $SYSTEM_ID distro_series=$SERIES hwe_kernel=$KERNEL
  ```

In all cases, MAAS will refuse or abort the deployment if the specified kernel version is not available.

## Set boot options

MAAS can apply global kernel boot options to all machines:

**UI**
*Settings* > *Kernel parameters* > enter options > *Save*.

**CLI**
  ```bash
  maas $PROFILE maas set-config name=kernel_opts value='$KERNEL_OPTIONS'
  ```

Machines may also be tagged with kernel options:

**CLI**
   ```bash
   maas $PROFILE tags create name='$TAG_NAME' comment='$TAG_COMMENT' kernel_opts='$KERNEL_OPTIONS'
   ```

You can verify the tags before deployment:

**CLI**
  ```bash
  maas admin tags read | jq -r '(["tag_name","tag_comment","kernel_options"] |(.,map(length*"-"))),(.[]|[.name,.comment,.kernel_opts]) | @tsv' | column -t
  ```

## Set hardware sync

On MAAS versions 3.2 and higher, you can enable hardware sync for machines that are already running, but not yet connected to MAAS. 

**UI**
*Machines* > machine > *Actions* > *Deploy* > *Periodically sync hardware* > *Start deployment*.

**CLI**
  ```bash
  maas $PROFILE machine deploy $SYSTEM_ID osystem=$OSYSTEM distro_series=$VERSION enable_hw_sync=true
  ```
  
Configure the sync interval in the MAAS settings.

## Set storage options

MAAS can enforce a default storage layout for all machines:

**UI**
*Settings > Storage > [choose default layout]*

**CLI**
  ```bash
  maas $PROFILE maas set-config name=default_storage_layout value=$LAYOUT_TYPE
  ```

You can also set a storage layout for any single 'Ready' machine:

**CLI**
  ```bash
  maas $PROFILE machine set-storage-layout $SYSTEM_ID storage_layout=$LAYOUT_TYPE [$OPTIONS]
  ```

## Deploy a machine

**UI**
*Machines > machine > Take action > Deploy*.

**CLI**
  ```bash
  maas $PROFILE machine deploy $SYSTEM_ID
  ```

## Create a VM host

Machines may also be deployed as a host system for virtual machines:


  ```bash
  maas $PROFILE machine deploy $SYSTEM_ID install_kvm=True
  ```

## Add deployed machines

MAAS can add existing, operating machines as if they had been deployed by MAAS.

**CLI**
  ```bash
  maas $PROFILE machines create deployed=true hostname=mymachine \
    architecture=amd64 mac_addresses=$MAC mac_addresses=$MAC power_type=manual
  ```

**Via the machine itself**
  ```bash
  wget http://$MAAS_IP:5240/MAAS/maas-run-scripts
  chmod 755 maas-run-scripts
  ./maas-run-scripts register-machine --hostname mymachine \
    http://$MAAS_IP:5240/MAAS $MAAS_API_TOKEN
  ```

## Monitor hardware sync

If you've enabled hardware sync, you can monitor it:

**CLI**
  ```bash
  maas $PROFILE machine read $SYSTEM_ID
  ```

## Enter rescue mode


  ```bash
  maas $PROFILE machine enter-rescue-mode $SYSTEM_ID
  ```

## Rescue machines

Access the machine via SSH to perform diagnostics or repairs:

  ```bash
  ssh ubuntu@$MACHINE_IP
  ```

## Exit rescue mode


  ```bash
  maas $PROFILE machine exit-rescue-mode $SYSTEM_ID
  ```

## Mark machines as broken

**UI**
*Machines > machine > Take action > Mark broken*.

**CLI**
  ```bash
  maas $PROFILE machines mark-broken $SYSTEM_ID
  ```

## Mark machines as fixed

**UI**
*Machines > machine > Take action > Mark fixed*.

**CLI**
  ```bash
  maas $PROFILE machines mark-fixed $SYSTEM_ID
  ```

## Release machines

**UI**
*Machines > machine > Take action > Release*.

**CLI**
  ```bash
  maas $PROFILE machines release $SYSTEM_ID
  ```

## Erase disks on release

MAAS can erase a disk before releasing a machine:

**CLI**
  ```bash
  maas $PROFILE machine release $SYSTEM_ID comment="some comment" erase=true [secure_erase=true || quick_erase=true]
  ```

Secure erasure uses the drive's secure erase feature, if available. Quick erasure wipes 2MB at the start and end of the disk; not as secure, but faster. If no options are specified, the disk will be overwritten with null bytes, which is very slow.

You can specify conditional erasure, that is, perform secure erasure if available, or quick erasure if not:

**CLI**
  ```bash
  maas $PROFILE machine release $SYSTEM_ID comment="some comment" erase=true secure_erase=true quick_erase=true
  ```

## Remove a machine

**UI**
*Machines > [Select the machine] > Take Action > Delete* and confirm the deletion.

**CLI**
  ```bash
  maas $PROFILE machine delete $SYSTEM_ID
  ```

Replace `$SYSTEM_ID` with the system ID of the machine to be removed. You can also force deletion from the CLI, if the machine is stuck in an invalid state:

**CLI**
  ```bash
  maas $PROFILE machine delete $SYSTEM_ID force=true
  ```

## Verify removal

List machines to confirm the machine is gone:

**UI**
*Hardware > Machines*; scan the list or use the *Search bar* to check.

**CLI*
  ```bash
  maas $PROFILE machines read | jq -r '.[].hostname'
  ```

If the machine wasn't removed, ensure it's not in a locked or allocated state.
