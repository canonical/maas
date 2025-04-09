Prior to deployment, MAAS machines can be customised in a number of ways, including:

- machine storage.
- commissioning and deployment configurations (known as "pre-seeding").
- custom Ubuntu kernels.
- kernel boot options. 

In MAAS v3.2+, machines can be modified post-deployment — while running — by swapping hardware or adjusting the VM from the host. This enables you to:

- add or remove disks
- add or remove network interfaces
- add or remove PCI devices
- add or remove USB devices

> *You cannot make these changes to a deployed machine using MAAS.*

During deployment, you can enable periodic hardware sync, allowing deployed machines to update BMC settings and tags in real time as changes occur.

## Customising storage 

MAAS configures machine storage, supporting traditional partitioning, LVM, RAID, bcache, and UEFI boot.

> *MAAS does not support deploying ZFS beyond the root device; doing so is not recommended.*

Storage depends on physical disks but is configured using a layout, applied during commissioning. Modify storage at the filesystem level post-deployment and choose from various disk erasure options when releasing a machine.

MAAS supports storage setup for CentOS and RHEL, including RAID, LVM, and custom partitioning (excluding ZFS and bcache). This requires an updated Curtin version, [available via PPA](https://launchpad.net/ubuntu/+source/curtin).

### UEFI booting 

All layout types support UEFI boot, with MAAS automatically creating a 512MB FAT32 EFI partition (/boot/efi on sda1). Users need only enable UEFI — no further action is required. However, UEFI must remain enabled throughout the machine’s lifecycle; disabling it after enlistment will cause failures.

### Block devices 

Once the initial storage layout has been configured on a machine, you can perform many operations to view and adjust the entire storage layout for the machine. In MAAS there are two different types of block devices.

**Physical* 

A physical block device is a physically attached block device such as a 100GB hard drive connected to a server.

**Virtual* 

A virtual block device is a block device that is exposed by the Linux kernel when an operation is performed. Almost all the operations on a physical block device can be performed on a virtual block device, such as a RAID device exposed as md0.

### Partitions 

As with block devices, MAAS and the MAAS API offer a great deal of control over the creation, formatting, mounting and deletion of partitions.

## Storage restrictions 

There are three restrictions for the storage configuration:

1.  An EFI partition is required to be on the boot disk for UEFI.
2.  You cannot place partitions on logical volumes.
3.  You cannot use a logical volume as a Bcache backing device.

Violating these restrictions will prevent a successful deployment.

### VMFS data stores 

MAAS configures VMware VMFS Datastore layouts to maximize local disk use for ESXi. The VMFS6 layout, required for ESXi, creates a datastore1 VMFS Datastore using leftover boot disk space after OS partitioning.

### Final storage mods 

Once MAAS provisions a machine with block devices, via a layout or administrator customisation, a regular user can modify the resulting storage configuration at the filesystem level.

### Disk erasure 

Disk erasure removes data from a machine’s disks upon release. Users can set a default configuration or select from three erasure types:

1.  Standard erasure - Overwrites all data with zeros.
2.  Secure erasure -Secure erase works like Standard erase but is much faster since the disk's firmware handles it. However, some disks—especially SCSI, SAS, and FC—may not support this method.
3.  Quick erasure - Same as Standard erase but only targets the first 1 MB and the last 1 MB of each disk. This removes the partition tables and/or superblock from the disk, making data recovery difficult but not impossible.

Pay attention: if all three options are checked when the machine is released, the following order of preference is applied:

1. Use 'secure erase' if the disk supports it
2. If it does not, then use 'quick erase'

## Pre-seeding 

During enlistment, deployment, commissioning, and installation, MAAS sends [Tempita-derived](https://raw.githubusercontent.com/ravenac95/tempita/master/docs/index.txt) configuration files to cloud-init. This pre-seeding process configures a machine’s ephemeral and installation environments, allowing customization.

Preseeding in MAAS can be achieved in two ways:

1. [Curtin](https://launchpad.net/curtin)**^**, a preseeding system similar to Kickstart or d-i (Debian Installer), applies customisation during operating system (OS) image installation. MAAS performs these changes on deployment, during OS installation, but before the machine reboots into the installed OS. Curtin customisations are perfect for administrators who want their deployments to have identical setups all the time, every time. [This blog post](https://blog.ubuntu.com/2017/06/02/customising-maas-installs)**^** contains an excellent high-level overview of custom MAAS installs using Curtin.

2. [Cloud-init](https://launchpad.net/cloud-init)**^**, a system for setting up machines immediately after instantiation. cloud-init applies customisations after the first boot, when MAAS changes a machine's status to 'Deployed.' Customisations are per-instance, meaning that user-supplied scripts must be re-specified on redeployment. Cloud-init customisations are the best way for MAAS users to customise their deployments, similar to how the various cloud services prepare VMs when launching instances.

## Tempita templates

Tempita templates are used to generate preseed files during machine enlistment, commissioning, and deployment phases. These templates, located in /etc/maas/preseeds/, create configuration files that guide machine setup. For instance, during commissioning, MAAS uses these templates to send configuration data to the cloud-init process on target machines.

### Templates (snap) 

The [Tempita](https://raw.githubusercontent.com/ravenac95/tempita/master/docs/index.txt)**^** template files are found in the `/var/snap/maas/current/preseeds/` directory on the region controller. Each template uses a filename prefix that corresponds to a particular phase of MAAS machine deployment:

### Templates (deb) 

The [Tempita](https://raw.githubusercontent.com/ravenac95/tempita/master/docs/index.txt)**^** template files are found in the `/etc/maas/preseeds/` directory on the region controller. Each template uses a filename prefix that corresponds to a particular phase of MAAS machine deployment:

|       Phase       |                 Filename prefix                 |
|:-----------------|:-----------------------------------------------|
| Enlistment  |                      enlist                     |
| Commissioning |                  commissioning                  |
| Installation | curtin ([Curtin](https://launchpad.net/curtin))**^** |

Additionally, the template for each phase typically consists of two files. The first is a higher-level file that often contains little more than a URL or a link to further credentials, while a second file contains the executable logic.

The `enlist` template, for example, contains only minimal variables, whereas `enlist_userdata` includes both user variables and initialisation logic.

Tempita’s inheritance mechanism is the reverse of what you might expect. Inherited files, such as `enlist_userdata`, become the new template which can then reference variables from the higher-level file, such as `enlist`.

### Template naming 

MAAS interprets templates in lexical order by their filename. This order allows for base configuration options and parameters to be overridden based on a combination of operating system, architecture, sub-architecture, release, and machine name.

Some earlier versions of MAAS only support Ubuntu. If the machine operating system is Ubuntu, then filenames without `{os}` will also be tried, to maintain backward compatibility.

Consequently, template files are interpreted in the following order:

1. `{prefix}_{os}_{node_arch}_{node_subarch}_{release}_{node_name}` or `{prefix}_{node_arch}_{node_subarch}_{release}_{node_name}`

2. `{prefix}_{os}_{node_arch}_{node_subarch}_{release}` or `{prefix}_{node_arch}_{node_subarch}_{release}`

3. `{prefix}_{os}_{node_arch}_{node_subarch}` or `{prefix}_{node_arch}_{node_subarch}`

4. `{prefix}_{os}_{node_arch}` or `{prefix}_{node_arch}`

5. `{prefix}_{os}`

6. `{prefix}`

7. `generic`

The machine needs to be the machine name, as shown in the web UI URL.

The prefix can be either `enlist`, `enlist_userdata`, `commissioning`, `curtin`, `curtin_userdata` or `preseed_master`. Alternatively, you can omit the prefix and the following underscore.

For example, to create a generic configuration template for Ubuntu 16.04 Xenial running on an x64 architecture, the file would need to be called `ubuntu_amd64_generic_xenial_node`.

To create the equivalent template for curtin_userdata, the file would be called `curtin_userdata_ubuntu_amd64_generic_xenial_node`.

Any file targeting a specific machine will replace the values and configuration held within any generic files. If those values are needed, you will need to copy these generic template values into your new file.


## Custom Ubuntu kernels

MAAS supports four types of kernels for its Ubuntu machines:

- General availability kernels
- Hardware enablement kernels
- Hardware enablement kernels (pre-release)
- Low latency kernels

### GA kernels 

The *general availability* (GA) kernel is based on the *generic* kernel that ships with a new Ubuntu version. Subsequent fixes are applied regularly by the 'stable' *stream* used when setting up the global image source for MAAS.

MAAS denotes a GA kernel like this:

`ga-<version>`: The GA kernel reflects the major kernel version of the shipped Ubuntu release. For example, 'ga-16.04' is based on the 'generic' 4.4 Ubuntu kernel. As per Ubuntu policy, a GA kernel will never have its major version upgraded until the underlying release is upgraded.

### HWE kernels 

New hardware gets released all the time. If an Ubuntu host runs an older kernel, it's unlikely that MAAS can support the hardware. Canonical does make every effort to back-port more recent kernels enabling more hardware. The acronym HWE stands for "Hardware Enablement."

You also gain kernel improvements and new features when installing an HWE kernel.


There is the notion of an HWE *stack*, which refers to the window manager and kernel when the Ubuntu host is running a desktop environment. HWE stacks do not apply to MAAS since machines are provisioned strictly as non-graphical servers.


Note that these back-ported/HWE kernels are only available for LTS releases (e.g. Trusty, Xenial, etc.). For example, the first available HWE kernel for Ubuntu 16.04 LTS (Xenial) will be the GA kernel from Ubuntu 16.10 (Yakkety).

Before MAAS 2.1 on Xenial, HWE kernels are referred to by the notation `hwe-<release letter>`. So, to install the Yakkety HWE kernel on Xenial, the `hwe-y` kernel is used. By default, when using the web UI, MAAS imports all available HWE kernels along with its generic boot images. So if you are importing Trusty images, then the following HWE kernels are included: `hwe-u`, `hwe-v`, `hwe-w`, `hwe-x` (presuming the Xenial HWE kernel is available).

In MAAS 2.1, starting with Xenial kernels, the notation has changed. The following is used to refer to the latest HWE kernel available for Xenial: `hwe-16.04`.

See [LTS Enablement Stack](https://wiki.ubuntu.com/Kernel/LTSEnablementStack)**^** (Ubuntu wiki) for the latest information on HWE.

### Pre-release HWE 

The pre-release HWE kernel is known as the *edge* HWE kernel.

MAAS denotes the edge kernel like this: `hwe-<version>-edge`.

So 'hwe-16.04' is considered older than 'hwe-16.04-edge'.

See [Rolling LTS Enablement Stack](https://wiki.ubuntu.com/Kernel/RollingLTSEnablementStack#hwe-16.04-edge) (Ubuntu wiki)**^** for more information.

### Low-latency kernels 

The low-latency kernel is based on the GA kernel, but uses a more aggressive configuration to reduce latency. It is categorised as a soft real-time kernel. 

MAAS denotes a low latency kernel in three ways:

1.  `hwe-x-lowlatency`: the Xenial low latency HWE kernel for Trusty
2.  `ga-16.04-lowlatency`: the low latency GA kernel for Xenial
3.  `hwe-16.04-lowlatency`: the low latency HWE kernel for Xenial

### Choosing a kernel 

The kernel installed on a machine during deployment is, by default, the Ubuntu release's native kernel (GA). However, it is possible to tell MAAS to use a different kernel. Via the Web UI, MAAS can help you choose one of these kernels. There are three different contexts for your choice:

1.  globally (default minimum enlistment and commissioning kernel)
2.  per machine (minimum deploy kernel)
3.  per machine during deployment (specific deploy kernel)

## Kernel boot options 

MAAS can specify kernel boot options to machines on both a global basis (UI and CLI) and a per-machine basis (CLI-only). A full catalogue of available options can be found in the [Linux kernel parameters list](https://www.kernel.org/doc/html/latest/admin-guide/kernel-parameters.html)**^** at [kernel.org](https://www.kernel.org)**^**.
