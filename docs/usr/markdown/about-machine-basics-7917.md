MAAS provisions bare-metal or virtual servers on a reachable network segment.

## Machine List

The machine list in MAAS is a central dashboard displaying servers with details like status, power state, owner, and tags. Hovering over status icons reveals additional information, such as warnings for failed hardware tests. The Add hardware menu enables adding new machines or chassis. Selecting machines activates the Take action menu for various operations. Filtering options allow refining the machine list based on attributes and keywords.

## CLI Dashboard

A non-interactive machine dashboard can be generated via the CLI with `jq`:

```nohighlight
maas admin machines read | jq -r '(["FQDN","POWER","STATUS", "OWNER", "TAGS", "POOL", "NOTE", "ZONE"] | (., map(length*"-"))),
(.[] | [.hostname, .power_state, .status_name, .owner // "-", .tag_names[0] // "-", .pool.name, .description // "-", .zone.name]) | @tsv' | column -t
```

This output provides an overview of each machine’s state, tags, and assignment.

## Machine Summary

Selecting a machine’s FQDN or MAC address (in the UI) opens a summary view with key details:

- Overview: Status, OS version, and owner.
- CPU & Memory: Specs and test links.
- Storage: Disk layout and modification options.
- Domain & Zone: Configuration settings with edit links.
- Power Type: Configurable power settings.
- Tags: Assigned tags with edit options.

Most machine events are accessible from the *Machines* menu.

### USB & PCI Devices

Machines may include USB or PCI devices such as keyboards, GPUs, or network cards. These devices are detected during commissioning and listed under the *PCI devices* and *USB* tabs, showing device type, vendor ID, product ID, driver name, NUMA node (if applicable), and address.

These devices can be removed via the CLI:

```nohighlight
maas $PROFILE node-device delete $SYSTEM_ID $DEVICE_ID
```

Recommissioning the machine will restore detected devices.

### Network Configuration

The *Network* tab allows viewing and editing machine network settings. Changes can be made while a machine is in the 'Ready' state.

### Booting & Power Management

The *Booting* tab provides machine configuration options, including PXE boot settings.

- *Hard Power-Off* immediately shuts down power.
- *Soft Power-Off (MAAS 3.5+)* gracefully shuts down the OS.

### Storage Management

MAAS supports various storage configurations, including:

- Traditional partitioning, LVM, RAID, and bcache.
- UEFI boot mechanisms.
- Storage configuration for CentOS and RHEL, including RAID and custom partitioning (ZFS and bcache excluded).

Storage layouts are applied during commissioning, and users can modify configurations as needed. Multiple disk erasure options are available when releasing a machine.

