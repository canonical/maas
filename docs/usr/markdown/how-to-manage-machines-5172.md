
MAAS gives you end-to-end control of machines: from discovery and commissioning to deployment, configuration, troubleshooting, and eventual release.  This applies to bare metal servers, virtual machines (VMs), or pre-deployed systems.

This page is your one-stop reference for managing machines in MAAS.


## Discover machines

Before you can manage machines, MAAS must detect and register them.

### Discover active devices
MAAS monitors network traffic to find connected devices (machines, switches, bridges, and more).

- **UI**: *Networking* > *Network discovery*
- **CLI**:
  ```bash
  maas $PROFILE discoveries read
  ```

### List machines

- Show all machines
  - **UI**: *Machines* (view list)
  - **CLI**:
    ```bash
    maas $PROFILE machines read | jq -r '(["HOSTNAME","SYSID","STATUS"] | join(","))'
    ```

- Show a specific machine
  - **UI**:
    1. *Machines* > *[machine]*
    2.  URL shows: `/machine/<SYSTEM_ID>/summary`
    3.  Select *Summary* for details
  - **CLI**:
    ```bash
    maas admin machines read | jq -r '(["HOSTNAME","SYSID"] | (., map(length*"-"))),(.[] | [.hostname, .system_id]) | @tsv' | column -t
    maas $PROFILE machine read $SYSTEM_ID
    ```

### Search machines

Use MAAS search syntax:

| Type     | Example              |
| Exact    | `pod:=able-cattle`   |
| Partial  | `pod:able,cattle`    |
| Negation | `pod:!cattle`        |

- **UI**: *Hardware* > *Machines* > use the search bar
- **CLI**:
  ```bash
  maas $PROFILE machines read | jq -r '(["HOSTNAME","SYSID","STATUS"] | join(","))'
  ```

### Filter by parameters
- **UI**: *Hardware* > *Machines* > *Filters*
- **Notes**: MAAS builds the search terms for you.  You can copy and re-use them for future searches.


## Enable new machines

New machines are commissioned automatically when added.

### Add a machine
Provide architecture, MAC address, and power settings.

- **UI**: *Machines* > *Add hardware* > fill in fields > *Save*
- **CLI**:
  ```bash
  maas $PROFILE machines create architecture=$ARCH   mac_addresses=$MAC_ADDRESS power_type=$POWER_TYPE   power_parameters_power_id=$POWER_ID   power_parameters_power_address=$POWER_ADDRESS 
  power_parameters_power_pass=$POWER_PASSWORD
  ```

Disable auto-commissioning if needed:
```nohighlight
maas $PROFILE maas set-config name=enlist_commissioning value=false
```

### Add via chassis
Add multiple machines at once.

- **UI**: *Machines* > *Add hardware* > *Chassis* > fill in details > *Save*

### Clone a machine
Duplicate configuration.

- **UI**: *Machines* > *[machine]* > *Take action* > *Clone*
- **CLI**:
  ```bash
  maas $PROFILE machine clone $SOURCE_SYSTEM_ID new_hostname=$NEW_HOSTNAME
  ```

### Use LXD VMs
Provision VMs with LXD.

1.  Set up LXD
   - Remove old versions, install, initialize, and disable DHCP on bridges.
   - **CLI only**:
     ```bash
     sudo apt-get purge -y *lxd* *lxc*
     sudo apt-get autoremove -y
     sudo snap install lxd
     sudo lxd init
     lxc network set lxdbr0 dns.mode=none
     lxc network set lxdbr0 ipv4.dhcp=false
     lxc network set lxdbr0 ipv6.dhcp=false
     ```

2.  Add a VM host:
   - **UI**: *KVM* > *LXD* > *Add LXD host* > enter details > run trust command > *Save LXD host*
   - **CLI**:
     ```bash
     maas $PROFILE vm-hosts create type=lxd power_address=$LXD_ADDRESS project=$PROJECT_NAME
     ```

3.  Add VMs:
   - **UI**: *KVM* > *VM host* > *Add VM* > fill in cores, RAM, disks > *Compose machine*
   - **CLI**:
     ```bash
     maas $PROFILE vm-host compose $VM_HOST_ID cores=4 memory=8G disks=1:size=20G
     ```

4.  Move or delete VMs:
   - **UI**: *Machines* > *[VM]* > *Take action* > *Delete*
   - **CLI**:
     ```bash
     lxc move $VM_NAME $VM_NAME --project default --target-project $PROJECT_NAME
     maas $PROFILE machine delete $SYSTEM_ID
     ```
## Control machine power

MAAS manages machine power on/off.

- Power on:
  - **UI**: *Machines* > *[machine]* > *Take action* > *Power on*
  - **CLI**:
    ```bash
    maas $PROFILE machine start $SYSTEM_ID
    ```

- Power off:
  - **UI**: *Machines* > *[machine]* > *Take action* > *Power off*
  - **CLI**:
    ```bash
    maas $PROFILE machine stop $SYSTEM_ID
    ```

- Soft shutdown:
  - **CLI only**:
    ```bash
    maas $PROFILE machine stop $SYSTEM_ID force=false
    ```

Set the correct power type:
- **UI**: *Machines* > *[machine]* > *Configuration* > *Power* > *Edit*
- **CLI**:
  ```bash
  maas $PROFILE machine update $SYSTEM_ID power_type="$POWER_TYPE"
  ```


## Commission & test machines

Commissioning collects hardware info and prepares machines for deployment.

- Commission:
  - **UI**: *Machines* > *[machine]* > *Take action* > *Commission*
  - **CLI**:
    ```bash
    maas $PROFILE machine commission $SYSTEM_ID
    ```

- Test:
  - **UI**: *Machines* > *[machine]* > *Take action* > *Test*
  - **CLI**:
    ```bash
    maas $PROFILE machine test $SYSTEM_ID tests=cpu,storage
    ```

- View results:
  - **UI**: *Machines* > *[machine]* > *Test results*
  - **CLI**:
    ```bash
    maas $PROFILE machine read $SYSTEM_ID | jq '.test_results'
    ```

- Override failures:
  - **UI**: *Machines* > *[machine]* > *Take action* > *Override test results*
  - **CLI**:
    ```bash
    maas $PROFILE machine set-test-result $SYSTEM_ID result=passed
    ```


## Configure deployment

Deployment lets you adjust kernels, storage, and hardware sync.

### Hardware sync (3.2+)
- **UI**: *Machines* > *[machine]* > *Take action* > *Deploy* > *Periodically sync hardware* > *Start deployment*
- **CLI**:
  ```bash
  maas $PROFILE machine deploy $SYSTEM_ID osystem=$OSYSTEM distro_series=$VERSION enable_hw_sync=true
  ```

### Kernel configuration
- System-wide kernel version:
  - **UI**: *Settings* > *Configuration* > *Commissioning* > *Default minimum kernel version*
  - **CLI**:
    ```bash
    maas $PROFILE maas set-config name=default_min_hwe_kernel value=$KERNEL
    ```

- Per-machine kernel version:
  - **UI**: *Machines* > *[machine]* > *Configuration* > *Minimum kernel*
  - **CLI**:
    ```bash
    maas $PROFILE machine update $SYSTEM_ID min_hwe_kernel=$HWE_KERNEL
    ```

- Kernel parameters:
  - **UI**: *Settings* > *Kernel parameters*
  - **CLI**:
    ```bash
    maas $PROFILE maas set-config name=kernel_opts value='$KERNEL_OPTIONS'
    ```

All layouts can be set in UI or CLI.

- **UI**:
  *Machines* > *[machine]* > *Storage* > *Change storage layout* > select desired layout > *Save*

- **CLI**:
  ```bash
  maas $PROFILE machine set-storage-layout $SYSTEM_ID storage_layout=<layout_type>
  ```

Replace `<layout_type>` with one of:

#### Flat layout
One partition uses the whole disk (ext4, mounted at `/`).
```bash
maas $PROFILE machine set-storage-layout $SYSTEM_ID storage_layout=flat
```

#### LVM layout
Flexible logical volumes, supports resizing and snapshots.
```bash
maas $PROFILE machine set-storage-layout $SYSTEM_ID storage_layout=lvm
```

#### Bcache layout
SSD acts as cache for a larger backing disk.

```bash
maas $PROFILE machine set-storage-layout $SYSTEM_ID storage_layout=bcache
```

#### VMFS6/VMFS7 layouts
For VMware ESXi hosts.  Automates required datastore creation.
```bash
maas $PROFILE machine set-storage-layout $SYSTEM_ID storage_layout=vmfs6
maas $PROFILE machine set-storage-layout $SYSTEM_ID storage_layout=vmfs7
```

#### Blank layout
Removes all storage config — you must configure manually.
```bash
maas $PROFILE machine set-storage-layout $SYSTEM_ID storage_layout=blank
```

#### Custom layout (MAAS 3.1+)
Upload a commissioning script that outputs a JSON layout.
- Script must run after `40-maas-01-machine-resources` and before `50-maas-01-commissioning`.
- Script must write to `$MAAS_STORAGE_CONFIG_FILE`.
- Device names in JSON must match those detected by MAAS.

⚠️ **Notes**:
- Machine must be in **Ready** state before changing storage layouts.
- `blank` layout machines can’t be deployed until storage is reconfigured.
- `bcache` requires an SSD device present, otherwise MAAS falls back to flat.


## Deploy machines

- Allocate:
  - **UI**: *Machines* > *[machine]* > *Take action* > *Allocate*
  - **CLI**:
    ```bash
    maas $PROFILE machines allocate system_id=$SYSTEM_ID
    ```

- Deploy:
  - **UI**: *Machines* > *[machine]* > *Take action* > *Deploy*
  - **CLI**:
    ```bash
    maas $PROFILE machine deploy $SYSTEM_ID
    ```

- Ephemeral deployment (RAM only):
  - **UI**: *Machines* > *[machine]* > *Take action* > *Deploy in memory*
  - **CLI**:
    ```bash
    maas $PROFILE machine deploy $SYSTEM_ID ephemeral_deploy=true
    ```

- Deploy as VM host:
  - **UI**: *Machines* > *[machine]* > *Take action* > *Deploy* > *Install KVM*
  - **CLI**:
    ```bash
    maas $PROFILE machine deploy $SYSTEM_ID install_kvm=True
    ```

- Deploy with cloud-init:
  - **UI**: *Machines* > *[machine]* > *Take action* > *Deploy* > *Configuration options*
  - **CLI**:
    ```bash
    maas $PROFILE machine deploy $SYSTEM_ID cloud_init_userdata="$(cat cloud-init.yaml)"
    ```
	
## Rescue & recovery

Use rescue mode to log in and diagnose issues.

- Enter rescue mode:
  - **UI**: *Machines* > *[machine]* > *Take action* > *Enter rescue mode*
  - **CLI**:
    ```bash
    maas $PROFILE machine enter-rescue-mode $SYSTEM_ID
    ```

- SSH into machine:
  ```bash
  ssh ubuntu@$MACHINE_IP
  ```

- Exit rescue mode:
  - **UI**: *Machines* > *[machine]* > *Take action* > *Exit rescue mode*
  - **CLI**:
    ```bash
    maas $PROFILE machine exit-rescue-mode $SYSTEM_ID
    ```

- Mark broken/fixed:
  - **UI**: *Machines* > *[machine]* > *Take action* > *Mark broken* / *Mark fixed*
  - **CLI**:
    ```bash
    maas $PROFILE machines mark-broken $SYSTEM_ID
    maas $PROFILE machines mark-fixed $SYSTEM_ID
    ```


## Release or remove machines

- Release:
  - **UI**: *Machines* > *[machine]* > *Take action* > *Release*
  - **CLI**:
    ```bash
    maas $PROFILE machines release $SYSTEM_ID
    ```

- Erase disks on release:
  - **UI**: *Machines* > *[machine]* > *Release* > *Enable disk erasure options*
  - **CLI**:
    ```bash
    maas $PROFILE machine release $SYSTEM_ID erase=true secure_erase=true quick_erase=true
    ```

- Delete:
  - **UI**: *Machines* > *[machine]* > *Take action* > *Delete*
  - **CLI**:
    ```bash
    maas $PROFILE machine delete $SYSTEM_ID
    ```

- Force delete stuck machines (CLI only):
  ```bash
  maas $PROFILE machine delete $SYSTEM_ID force=true
  ```


## Verify machines

Periodically check your machine list.

- **UI**: *Machines* > view list or search
- **CLI**:
  ```bash
  maas $PROFILE machines read | jq -r '.[].hostname'
  ```


## Safety nets
- Commission before deploy to ensure correct hardware info.
- Test results help catch failures before deployment.
- Erase disks when releasing machines that handled sensitive data.


## Next steps
- Understand [machine basics](https://canonical.com/maas/docs/about-machine-basics)
- Learn about the [machine life-cycle](https://canonical.com/maas/docs/about-the-machine-life-cycle)
- Learn more about [commissioning machines](https://canonical.com/maas/docs/about-commissioning-machines)
- Discover more about [deploying machines](https://canonical.com/maas/docs/about-deploying-machines)
