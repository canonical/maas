> *Errors or typos? Topics missing? Hard to read? <a href="https://docs.google.com/forms/d/e/1FAIpQLScIt3ffetkaKW3gDv6FDk7CfUTNYP_HGmqQotSTtj2htKkVBw/viewform?usp=pp_url&entry.1739714854=https://maas.io/docs/the-importance-of-images-in-maas" target = "_blank">Let us know.</a>*

MAAS provides supported images for stable Ubuntu releases, and for CentOS 7 and CentOS 8.0 releases.  Other images can be [customised](/t/how-to-customise-images/5104) for use with MAAS.

MAAS images are more than just the operating system kernel.  In fact, a usable MAAS image consists of at least four things:

- a [bootloader](https://images.maas.io/ephemeral-v3/stable/bootloaders/)**^**, which boots the computer to the point that an operating system can be loaded.  MAAS currently uses one of three types of bootloaders: open firmware, PXE, and UEFI.
- a bootable kernel.
- an initial ramdisk.
- a squashfs filesystem.

If you were to look at the `squashfs.manifest`, you'd see something like this:

```nohighlight
adduser	3.118ubuntu5
apparmor	3.0.4-2ubuntu2.1
apport	2.20.11-0ubuntu82.1
apport-symptoms	0.24
apt	2.4.5
apt-utils	2.4.5
base-files	12ubuntu4.1
base-passwd	3.5.52build1
bash	5.1-6ubuntu1
bash-completion	1:2.11-5ubuntu1
bc	1.07.1-3build1
bcache-tools	1.0.8-4ubuntu3
bind9-dnsutils	1:9.18.1-1ubuntu1.1
bind9-host	1:9.18.1-1ubuntu1.1
bind9-libs:amd64	1:9.18.1-1ubuntu1.1
binutils	2.38-3ubuntu1
binutils-common:amd64	2.38-3ubuntu1
binutils-x86-64-linux-gnu	2.38-3ubuntu1
bolt	0.9.2-1
bsdextrautils	2.37.2-4ubuntu3
bsdutils	1:2.37.2-4ubuntu3
btrfs-progs	5.16.2-1
busybox-initramfs	1:1.30.1-7ubuntu3
busybox-static	1:1.30.1-7ubuntu3
byobu	5.133-1
ca-certificates	20211016
cloud-guest-utils	0.32-22-g45fe84a5-0ubuntu1
cloud-init	22.2-0ubuntu1~22.04.3
cloud-initramfs-copymods	0.47ubuntu1
cloud-initramfs-dyn-netconf	0.47ubuntu1
command-not-found	22.04.0
console-setup	1.205ubuntu3
console-setup-linux	1.205ubuntu3
coreutils	8.32-4.1ubuntu1
cpio	2.13+dfsg-7
cron	3.0pl1-137ubuntu3
```

This snippet gives you a basic idea of the kinds of things that have to be loaded onto a drive in order for the system to function independently.

## How images are synced (MAAS 3.5 and forward)

MAAS previously stored the boot resources (boot-loaders, kernels and disk images) in the MAAS database, and then replicated them on all Rack controllers. This make operations difficult and slow, as the database quickly became huge and files had to be transferred to all Racks before they were available for use. To address this issue, we have moved the resource storage from the database to the Region controller, and repurposed the storage in the Rack.

### Storing boot resources in the Region Controllers

All boot resources are stored in the local disk in each Controller host (`/var/lib/maas/image-storage` for *deb* or `$SNAP_COMMON/maas/image-storage` for *snap*). MAAS checks the contents of these directories on every start-up, removing unknown/stale files and downloading any missing resource. 

MAAS checks the amount of disk space available before downloading any resource, and stops synchronising files if there isn't enough free space. This error will be reported in the logs and a banner in the Web UI.

### Storage use by the Rack Controller 

Images are no longer copied from the MAAS database to the rack. Instead, the rack downloads images from the region on-demand.  This works well with the redesign of the rack controller (now known as the *MAAS agent*), which has been re-imagined as a 4G LRU caching agent.  The MAAS agent has limited storage space, managing cache carefully, but it is possible to configure the size of this cache if you need to do so.

As boot resources are now downloaded from a Region controller on-demand, a fast and reliable network connection between Regions and Racks is essential for a smooth operation. Adjusting the cache size might also be important for performance if you regularly deploy a large number of different systems.

### One-time image migration process

The first Region controller that upgrades will try to move all images out of the database. This is a background operation performed after all database migrations are applied, and **it's not reversible**. This is also a blocking operation, so MAAS might be un-available for some time (i.e., you should plan for some downtime during the upgrade process). 

MAAS will check if the host has enough disk space before starting to export the resources, and it will not proceed otherwise. In order to discover how much disk space you need for all your images, you can run the following SQL query in MAAS database before upgrading:

```nohighlight
select sum(n."size") from (select distinct on (f."sha256") f."size" from maasserver_bootresourcefile f order by f."sha256") n;
```

The controllers are no longer capable of serving boot resources directly from the database, and won't be able to commission or to deploy machines until this migration succeeds. If the process fails, you must free enough disk space and restart the controller for the migration to be attempted again.

### Sync works differently

When downloading boot resources from an upstream source (e.g. images.maas.io), MAAS divides the workload between all Region controllers available, so each file is downloaded only once, but not all by the same controller. After all external files were fetched, the controllers synchronise files among them in a peer-to-peer fashion. This requires **direct communication between Regions to be allowed**, so you should review your firewall rules before upgrading.

In this new model, a given image is *only* available for deployment after *all* regions have it, although stale versions can be used until everyone is up to date. This differs from previous versions where the boot resource needed to be copied to all Rack controllers before it was available, meaning that the images should be ready for use sooner.

## How images deploy

Here's a conceptual view of the way that images get deployed to create a running MAAS machine:

![image](https://discourse-maas-io-uploads.s3.us-east-1.amazonaws.com/original/2X/4/4bcb44d49eae1238d6cbd3724f2ec7cab6b8acab.jpeg)

This is a good place to explain how images work, including the nuances of `cloud-init` and `curtin` configurations.  Let's take it from the top.

Before a machine can be deployed, it must be added to MAAS, commissioned, and allocated.  Machines can be added to MAAS either by [enlistment](/t/about-machines/6695), which establishes the configuration and resources of the machine.  Finally, that machine must be allocated, that is, assigned to the control of one and only one user, so that conflicting commands to the same machine are not possible.  This aggregate step is represented by the green lines in the above diagram.

When MAAS receives the "deploy" command from the user (blue lines), it must first retrieve (from the MAAS DB) the machine info that was gathered about the machine during commissioning (red lines).  MAAS then boots the machine and waits for the machine's firmware to request a bootable "ephemeral" OS.  This ephemeral OS must be one of the images supplied by [the MAAS simplestreams](https://images.maas.io)**^** and cannot be a custom OS image.

At the point that MAAS must send the ephemeral OS to the machine, MAAS needs to have this OS downloaded to the rack controller, based on earlier selections made by the user (yellow lines).  Assuming that the a suitable simplestreams image is available, MAAS can send it to the machine.  This ephemeral OS is not deployed, but it is used to download and deploy the image you've chosen for the machine.

When the ephemeral OS boots, it immediately spawns [curtin](https://curtin.readthedocs.io/en/latest/topics/overview.html)**^**.  Curtin deployment of the target image can be customised with pre-seeds, shown by the brown lines in the diagram.  These pre-seeds control things which are difficult to change once the target OS has been installed (such as [partitioning](http://caribou.kamikamamak.com/2015/06/26/custom-partitioning-with-maas-and-curtin-2/)**^**.  Things which can be customised after the target image is running are generally configured with [cloud-init](https://cloudinit.readthedocs.io/en/latest/)**^**, represented by the pink lines.

To continue with the deployment flow, curtin retrieves the target image, either from the rack controller's cache (if the image is standard) or from the MAAS DB (if the image is custom).  Curtin then installs the target image and reboots the machine.  When the target image boots, it retrieves cloud-init configuration either from the MAAS metadata server (proxied by the region controller), or from cloud-init configuration data packed with the target image -- whichever is "closer".

Once cloud-init has finished, the machine is deployed, that is, up and running, ready to perform whatever functions have been assigned to it.

## Key takeaways

The flowchart above is a bit complicated, but there are few key takeaways you should remember:

1. Machines have to be added, either by enlistment or direct user action, before they can be deployed.

2. Machines must be commissioned before deployment, so that MAAS knows what resources the machine has available.

3. Machines must be allocated before deployment, to lock out all other users (so that no command deadlock can occur).

4. You must have selected and downloaded at least one suitable image from the MAAS simplestreams before you can deploy a machine, because this simplestreams image is used to boot the machine from the network, so that the target OS can then be installed on the machine.

5. If you need to customise things about the machine that can't be changed after the target OS is installed (like partitioning drives), you must use curtin pre-seeds to do this.  You must specify these pre-seeds before you start deployment.

6. If you want to customise things about the machine that can be changed after the target OS is installed (like downloading and installing an application),  you must use cloud-init to do this.  You must specify this cloud-init configuration, at the very least, before deployment begins.

7. If you wish to deploy a custom image, you must pack it and upload it to MAAS before deployment begins.

## Boot sources matter

A region controller downloads its images from a boot source. The main characteristics of a boot source are location (URL) and an associated GPG public keyring.


A boot resource is another name for an image. So boot resources are found within a boot source.


MAAS stores images in the region controller's database, from where the rack controller proxies them to the individual machines.  It's important to note that for ESXi images, network configuration includes only these five parameters:

1.   DHCP
2.   Static/auto IP assignments
3.   Aliases
4.   VLANs
5.   Bonds

Bonds are mapped to NIC teaming in only three ways:

1.   balance-rr -- portid
2.   active-backup -- explicit
3.   802.3ad -- iphash, LACP rate and XMIT hash policy settings ignored

MAAS comes configured with a boot source that should suffice for most users:

[`https://images.maas.io/ephemeral-v3/stable/`](https://images.maas.io/ephemeral-v3/stable/)**^**

The above URL points to the 'stable' stream (for the v3 format). See [Local image mirror](/t/how-to-mirror-maas-images/5927) for some explanation regarding the availability of other streams.

Although the backend supports multiple boot sources, MAAS itself uses a single source. If multiple sources are detected, the web UI will print a warning and will be unable to manage images.