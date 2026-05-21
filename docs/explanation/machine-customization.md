# Machine customization

MAAS allows you to tailor machines before and during deployment. This includes configuring storage, setting kernel options, and applying preseeds. Some modifications can also be detected post-deployment, although MAAS itself cannot change a deployed machine’s hardware profile.

## Pre-deployment customisation

Before a machine is deployed, you can customise:

- Storage layouts – partitioning, LVM, RAID, bcache, and UEFI boot.
- Preseeding – commissioning and deployment configurations applied by curtin or cloud-init.
- Kernel choice – GA, HWE, pre-release HWE, or low-latency kernels.
- Kernel parameters – boot-time options for tuning or troubleshooting.

## Post-deployment detection

From MAAS 3.2 onward, you can modify a running machine outside MAAS (e.g. by swapping hardware or adjusting a VM definition). MAAS can then detect:

- Added or removed disks.
- Added or removed NICs.
- Added or removed PCI/USB devices.

⚠️ You cannot make these changes through MAAS once a machine is deployed — they must be done at the host or hardware layer. MAAS will only observe the new state.

Optionally, you can enable periodic hardware sync so deployed machines report updated BMC settings and tags in real time.

## Storage layouts

Storage in MAAS is built on physical block devices but expressed as a layout, applied during commissioning. Layouts determine how disks are partitioned, formatted, and mounted. When a machine is released, MAAS can also erase disks using one of several erasure modes.

Supported layouts include:

- Flat – a single ext4 root partition (plus EFI system partition if UEFI).
- LVM – flexible volume groups and logical volumes with snapshot support.
- Bcache – pairs an HDD backing device with an SSD cache for performance.
- RAID – combines multiple disks for redundancy or throughput.

> MAAS supports CentOS and RHEL storage (RAID, LVM, custom partitioning) with a recent [Curtin](https://launchpad.net/curtin). ZFS is not supported beyond the root device.

Each layout has its own configuration options (e.g. `vg_name`, `root_device`, `cache_mode`) and trade-offs. Flat is simplest, LVM is most flexible, bcache accelerates I/O, RAID improves resilience or performance.

## UEFI boot

All layouts support UEFI. MAAS automatically creates a 512 MB FAT32 EFI partition (`/boot/efi`). UEFI must remain enabled for the life of the machine.

## Block devices and partitions

MAAS distinguishes between:

- Physical block devices – disks physically attached to a server.
- Virtual block devices – devices exposed by the kernel (e.g. RAID arrays, bcaches).

Both can be partitioned, formatted, and mounted through MAAS or its API.

## Disk erasure

When a machine is released, MAAS can wipe its disks. Options include:

1. Secure erase – fast firmware-based erase (if supported).
2. Standard erase – overwrite with zeros.
3. Quick erase – wipe first/last 1 MB (removes partition tables/superblocks).

If multiple methods are enabled, MAAS prefers secure erase, then quick erase.

## Preseeding

MAAS uses [Tempita](https://raw.githubusercontent.com/ravenac95/tempita/master/docs/index.txt) templates to generate preseed files for different phases (enlistment, commissioning, installation). These templates control both ephemeral and installed environments.

Two main tools apply preseeds:

- Curtin – applies storage and OS configuration during installation, before first boot. Ideal for consistent, repeatable setups.
- Cloud-init – applies customisations on first boot (packages, scripts, user data). Best for per-instance customisation.

Templates are matched in lexical order, from the most specific (`curtin_userdata_ubuntu_amd64_generic_xenial_node`) to generic fallbacks. This lets you override behaviour per OS, release, or machine.

## Kernel choices

MAAS can deploy machines with one of four Ubuntu kernel families:

- GA (General Availability): The default kernel shipped with an LTS release.
- HWE (Hardware Enablement): Back-ported newer kernels for newer hardware.
- HWE edge (pre-release): Latest kernels in development.
- Low-latency: Configured to reduce latency, often used in soft real-time workloads.

Kernel selection can be set:

1. Globally – the minimum enlistment/commissioning kernel.
2. Per machine – the minimum deploy kernel.
3. Per deployment – a specific kernel at deployment time.

## Kernel boot options

MAAS can set kernel boot parameters:

- Globally – via the UI or CLI.
- Per machine – via the CLI.

You can pass any option supported by the Linux kernel. See the [kernel parameters list](https://www.kernel.org/doc/html/latest/admin-guide/kernel-parameters.html) for details.

## Key takeaway

Machine customisation in MAAS spans three layers:

1. Storage – layouts, partitions, erasure.
2. Configuration – preseeds (curtin/cloud-init), templates.
3. Kernel – type, version, and boot options.

Together these features let you tune deployments for anything from simple test servers to complex production systems.
