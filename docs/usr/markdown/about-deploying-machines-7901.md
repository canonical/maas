Deployment is the central purpose of MAAS: taking bare-metal or virtual hardware and turning it into a running machine with an operating system and configuration ready for workloads. This section explains how deployment works, what components are involved, and what you can expect when MAAS installs an OS on a machine.


## From allocation to deployment

Before deployment can begin, a machine must be:

1. Commissioned – so MAAS knows its hardware profile and can schedule it.
2. Allocated – reserved for a specific user or process, ensuring no other workflow can interfere.

Once a machine is allocated, MAAS can drive it through the deployment sequence.


## The role of curtin and cloud-init

Two key technologies power MAAS deployments:

- Curtin (“curt installer”): A fast, image-based installer. Curtin runs inside a small ephemeral environment, prepares the hardware (partitioning, RAID, filesystem creation), and writes the target operating system image to disk.
- Cloud-init: A first-boot configuration tool embedded in the target OS image. Cloud-init handles user-data, networking, package installs, and any customisation you’ve provided.

Together, curtin and cloud-init ensure that machines emerge from deployment both installed and configured.


## Deployment sequence in detail

The following steps trace the boot and installation process for a typical deployment:

1. Power on: MAAS uses the machine’s BMC (IPMI, Redfish, iLO, etc.) to trigger a power-on.
2. DHCP discovery: The machine sends a DHCP discover. The MAAS DHCP service replies with an IP address and the location of a boot server.
3. Network Boot Program (NBP): The firmware downloads a bootloader (via TFTP or HTTP).
4. Ephemeral image request: The bootloader asks MAAS for a bootable kernel and initrd.
5. Ephemeral environment boot: MAAS delivers a kernel, initrd, and a compressed SquashFS root filesystem. The machine boots into this RAM-only environment.
6. Curtin runs: Inside the ephemeral OS, curtin executes. It applies preseed instructions, partitions disks, configures storage, and lays down the target OS image.
7. Target image installation: Curtin fetches the target image (Ubuntu, CentOS, RHEL, or a custom image) from the MAAS image store and installs it onto the machine’s storage.
8. Reboot into target OS: Once installation is complete, the machine reboots from local disk.
9. Cloud-init takes over: On first boot, the embedded cloud-init in the target OS configures networking, applies SSH keys, installs packages, and runs any user-defined scripts.
10. Deployed state: The machine is now operational, running the chosen OS with your configuration applied.


## Access to deployed machines

By default, MAAS injects your SSH keys into the deployed machine and enables login for the `ubuntu` user. Other orchestration layers, like [Juju](https://juju.is/), may add additional keys and perform further service-level configuration.

This makes it possible to log in immediately after deployment without touching the machine’s console.


## Preseeding and customisation

Curtin supports preseed files, allowing administrators to influence how storage, networking, or packages are configured during deployment. Cloud-init adds a second layer of flexibility, running scripts and applying configuration on first boot.

Between curtin preseeds and cloud-init user-data, you can tailor deployments to a very fine level of detail.


## Ephemeral OS deployments (MAAS 3.5+)

Since MAAS 3.5, you can choose to deploy an ephemeral OS instance:

- The entire operating system runs from memory, with no disk installation.
- This is useful for stateless workloads, temporary testing, or security-sensitive use cases.
- For Ubuntu images, MAAS configures full networking automatically. For non-Ubuntu images, only the PXE interface is configured; additional interfaces must be set up manually.

Ephemeral deployment is available in the deployment configuration screen by selecting “Deploy in memory.”


## Why image-based deployment?

MAAS no longer uses the older Debian installer (d-i). Instead, curtin installs images directly. This provides:

- Much faster deployment (no per-package downloads).
- Consistency across machines.
- Support for prebuilt custom images.

The images provided by MAAS are delivered as kernel/initrd pairs plus a SquashFS filesystem, streamed efficiently over HTTP.


## Key takeaway

Deployment in MAAS is a tightly choreographed sequence:

Allocate → PXE boot → ephemeral environment → curtin installs → cloud-init configures → reboot → deployed.

By combining curtin’s fast, image-based installation with cloud-init’s flexible first-boot configuration, MAAS delivers machines that are not just provisioned but production-ready.

## Next steps

- Learn how to [customize machines](https://canonical.com/maas/docs/about-machine-customization) to deliver precisely-tailored configurations.
- Discover some of the [pre-packaged configurations](https://canonical.com/maas/docs/how-to-use-cloud-init-with-maas) you can deploy using cloud-init.
