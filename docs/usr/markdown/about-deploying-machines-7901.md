> *Errors or typos? Topics missing? Hard to read? <a href="https://docs.google.com/forms/d/e/1FAIpQLScIt3ffetkaKW3gDv6FDk7CfUTNYP_HGmqQotSTtj2htKkVBw/viewform?usp=pp_url&entry.1739714854=https://maas.io/docs/about-deploying-machines" target = "_blank">Let us know.</a>*

This page explains the mechanics of MAAS machine deployment.

## Deployment process

Once a machine has been commissioned, the next logical step is to deploy it. Deploying a machine means, effectively, to [install an operating system on it](/t/how-to-manage-maas-images/6192), along with any other application loads you wish to run on that machine.

A detailed picture of deployment looks something like this:

![image](https://discourse-maas-io-uploads.s3.us-east-1.amazonaws.com/original/2X/f/f7e0fb1916bca084de75fc0479bfec3c95adf7b6.png)

Before deploying a machine, MAAS must allocate it (status 'Allocated'). Allocating a machine reserves the machine for the exclusive use of the allocation process. The machine is no longer available to any other process, including another MAAS instance, or a process such as Juju.

The agent that triggers deployment may vary. For instance, if the machines are destined to run complex, inter-related services that scale up or down frequently, like a "cloud" resource, then [Juju](https://jaas.ai/)**^** is the recommended deployment agent. Juju will also install and configure services on the deployed machines. If you want to use MAAS to install a base operating system and work on the machines manually, then you can deploy a machine directly with MAAS.

## Access to deployed machines

Machines deployed with MAAS will also be ready to accept connections via SSH, to the 'ubuntu' user account. This connection assumes that you have imported an SSH key has to your MAAS account. This is explained in [SSH keys](/t/how-to-manage-user-access/5184).

Juju adds SSH keys to machines under its control.

## Pre-seeding deployments

MAAS also supports machine customisation with a process called "preseeding." For more information about customising machines, see [How to customise machines](/t/how-to-customise-machines/5108).

## Basic requirements for deployment

To deploy, you must configure the underlying machine to netboot. Such a machine will undergo the following process, outlined in the above diagram:

1. MAAS boots the machine via the machine's BMC, using whatever power driver is necessary to properly communicate with the machine.
2. The booted machine sends a DHCP Discover request.
3. The MAAS-managed DHCP server (ideally) responds with an IP address and the location of a MAAS-managed HTTP or TFTP boot server.
4. The machine uses the HTTP/TFTP location to request a usable Network Boot Program (NBP).
5. The machine receives the NBP and boots.
6. The machine firmware requests a bootable image.
7. MAAS sends an ephemeral OS image, including an initrd; this ephemeral (RAM-only) image is necessary for `curtin` to carry out any hardware-prep instructions (such as disk partitioning) before the deployed OS is booted.
8. The initrd mounts a SquashFS image, also ephemerally, over HTTP.
9. The machine boots the ephemeral image.
10. The ephemeral image runs `curtin`, with passed pre-seed information, to configure the machine's hardware.
11. The desired deployment (target) image is retrieved by `curtin`, which installs and boots that deployment image. Note that the curtin installer uses an image-based method and is now the only installer used by MAAS. Although the older debian-installer method has been removed, curtin continues to support preseed files. For more information about customising machines see [How to customise machines](/t/how-to-customise-machines/5108).
12. The target image runs its embedded `cloud-init` script set, including any customisations and pre-seeds.

Once this is done, the target image is up and running on the machine, and the machine can be considered successfully deployed.

Also note that, before deploying, you should take two key actions:

1. Review and possibly set the [Ubuntu kernels](/t/how-to-customise-machines/5108) that will get used by deployed machines.

2. Ensure any pertinent SSH keys are imported (see [SSH keys](/t/how-to-manage-user-access/5184) to MAAS so it can connect to deployed machines.

## Deploying ephemeral OS instances (MAAS 3.5 and higher)

With the release of MAAS 3.5, ephemeral deployments for Ubuntu and custom images are possible.  These ephemeral deployments run completely in the machine's memory and need not access (or be aware of) any disk resources.  

Note that networking is only set up for Ubuntu images. For non-Ubuntu images, you only get the PXE interface set up to do DHCP against MAAS. All other interfaces need to be configured manually after deployment.

You can choose an ephemeral OS deployment from the deployment configuration screen in the machine list: Just select the "Deploy in memory" option and deploy as normal.