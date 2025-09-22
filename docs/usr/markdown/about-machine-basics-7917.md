In MAAS, a machine is a physical or virtual server that MAAS can provision, configure, and manage. To understand how MAAS treats machines, it helps to start with the basics: what a machine is at the hardware level, how it boots, how it is controlled, and how MAAS represents those components.


## What is a machine?

A *machine* is any server that can:

- Boot over the network (PXE/iPXE): Machines start from firmware (BIOS or UEFI), fetch a bootloader over the network, and run a small image provided by MAAS.
- Report its hardware inventory: Once booted, MAAS commissions the machine, probing CPU, memory, storage, and network devices.
- Be controlled remotely: Machines expose a BMC (Baseboard Management Controller) or equivalent power interface (IPMI, Redfish, iLO, etc.) so MAAS can power them on/off and reconfigure them without human intervention.

Machines can be bare-metal servers, VMs on a hypervisor, or even virtual hardware defined in a cloud environment — as long as they can PXE boot and present a controllable power interface.


## Machine components

When MAAS talks about machines, it models the following dimensions:

- Identity: Hostname, domain, owner, system ID.
- Power management: IPMI, Redfish, iLO, etc. allow MAAS to power cycle the machine.
- CPU & memory: Discovered during commissioning; used for scheduling workloads.
- Storage: Disks, partitions, and layouts (RAID, LVM, bcache).
- Networking: Interfaces, fabrics, VLANs, subnets, and IP assignments.
- Location: Zones (physical placement), resource pools (ownership/quota), and tags (custom labels).
- Attached devices: PCI/USB devices such as GPUs or NICs.

This structured representation lets MAAS track, allocate, and configure machines consistently.


## How machines boot under MAAS

1. PXE/iPXE request: The machine firmware requests a boot image from the network.
2. MAAS responds: MAAS provides a bootloader and kernel/initrd tailored to the deployment stage.
3. Commissioning: MAAS runs tests and gathers hardware inventory.
4. Deployment: MAAS installs the requested operating system with user-defined configuration (cloud-init).
5. Operational state: The machine reboots into its installed OS and is ready for workloads.

At every step, MAAS uses the BMC interface to ensure the machine can be powered on/off or rebooted reliably.


## Machines in the MAAS UI

In the web UI, machines appear in the *Machines* list, with columns for status, power state, owner, pool, zone, and tags. From here, you can:

- Filter and search for machines.
- Add new hardware manually or via chassis import.
- Select machines to take bulk actions (commission, deploy, release).

Clicking a machine opens its summary, which shows:

- Overview: Lifecycle state, OS, owner.
- CPU & Memory: Hardware specs and test results.
- Storage: Disk layouts and editing options.
- Network: Interfaces and IP assignments.
- Domain & Zone: Placement and scoping information.
- Power settings: Configured power type and credentials.
- Tags & Notes: Metadata for organizing workloads.


## CLI equivalent

The same data can be retrieved programmatically. For example:

```bash
maas $PROFILE machines read | jq -r '(["FQDN","POWER","STATUS","OWNER","POOL","ZONE"] | (., map(length*"-"))),
(.[] | [.hostname, .power_state, .status_name, .owner // "-", .pool.name, .zone.name]) | @tsv' | column -t
```

This command lists machines with their state, ownership, pool, and zone.


## Normal machine behaviour

Once integrated into MAAS, machines follow a consistent lifecycle:

- New → Commissioning → Ready → Deployed → Released.
- Hardware changes are detected and updated during commissioning.
- Devices removed manually will reappear when recommissioned.
- Network and storage layouts are applied during commissioning and can be edited before deployment.
- On release, MAAS can securely erase storage to prepare the machine for reallocation.

## Key takeaway

A machine in MAAS is not just an entry in a table. It’s a full representation of a server: its hardware, network identity, power controls, and configuration. By abstracting these details, MAAS makes it possible to provision and manage fleets of servers as easily as you might manage VMs in a cloud.

## Next steps

 - Learn about the [MAAS machine life-cycle](https://canonical.com/maas/docs/about-the-machine-life-cycle).
 - Understand how and why to [commission machines](https://canonical.com/maas/docs/about-commissioning-machines).

