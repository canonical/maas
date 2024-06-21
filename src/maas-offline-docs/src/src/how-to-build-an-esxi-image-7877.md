You can create a custom ESXi image. MAAS cannot directly deploy the VMware ESXi ISO; a specialised image must be created from the ISO. Canonical has created a Packer template to automatically do this for you; this page explains how to use it.

## Verify requirements

VMware ESXi has a specific set of requirements and limitations which are more stringent than MAAS.

## Basic requirements

The machine building the deployment image must be a GNU/Linux host with a dual core x86_64 processor supporting hardware virtualisation with at least 4GB of RAM and 10GB of disk space available. Additionally the qemu-kvm and qemu-utils packages must be installed on the build system.

## libvirt testing

While VMware ESXi does not support running in any virtual machine it is possible to deploy to one. The libvirt machine must be a KVM instance with at least CPU 2 cores and 4GB of RAM. To give VMware ESXi access to hardware virtualisation go into machine settings, CPUs, and select 'copy host CPU configuration.'

VMware ESXi has no support for libvirt drivers. Instead an emulated IDE disk and an emulated e1000 NIC must be used.

## Storage limitations

Only data stores may be configured using the devices available on the system. The first 9 partitions of the disk are reserved for VMware ESXi operating system usage.


**WARNING**: VMware does not support cloning boot devices - you may run into issues triggered by non-unique UUID. This may lead to data corruption on VMFS data stores when using cloned boot devices.


## Network limitations

Bridges are not supported in VMware ESXi. In addition, certain MAAS bond modes are mapped to VMware ESXi NIC team sharing with load balancing, as follows:

- balance-rr - portid
- active-backup - explicit
- 802.3ad - iphash, LACP rate and XMIT hash policy settings are ignored.

No other bond modes are currently supported.


**WARNING**: VMware ESXi does not allow VMs to use a PortGroup that has a VMK attached to it. All configured devices will have a VMK attached. To use a vSwitch with VMs you must leave a device or alias unconfigured in MAAS.


## qemu-nbd error

If the image fails to build due to a `qemu-nbd` error, try disconnecting the device with: 

```nohighlight
$ sudo qemu-nbd -d /dev/nbd4
```

## Prerequisites

- A machine running Ubuntu 18.04+ with the ability to run KVM virtual machines.
- qemu-utils
- Python Pip
- Packer
- The VMware ESXi installation ISO must be [downloaded manually](https://www.vmware.com/go/get-free-esxi)**^**.
- MAAS 2.5 or above, MAAS 2.6 required for storage configuration

## Install packer

Packer is easily installed from its Debian package:

```nohighlight
sudo apt install packer
```

This should install with no additional prompts.

## Install dependencies

```nohighlight
sudo apt install qemu-utils
```

## Install Python `pip`

```nohighlight
sudo apt install pip
```

## Get the templates

You can obtain the packer templates by cloning the [packer-maas github repository](https://github.com/canonical/packer-maas.git)**^**, like this:

```nohighlight
git clone https://github.com/canonical/packer-maas.git
```

Make sure to pay attention to where the repository is cloned. This package should install with no additional prompts.

## Locate ESXi

The appropriate packer template can be found in the subdirectory `vmware-esxi` in the packer repository.

## Customise the image

The deployment image may be customized by modifying `packer-maas/vmware-esxi/KS.CFG`.

## Build the image
## Build ESXi

You can easily build the image using the Makefile:

```nohighlight
$ make ISO=/path/to/VMware-VMvisor-Installer-6.7.0.update03-14320388.x86_64.iso
```

## OR run manually

Alternatively, you can manually run packer. Your current working directory must be in `packer-maas/vmware-esxi`, where this file is located. Once in `packer-maas/vmware-esxi`, you can generate an image with:

```nohighlight
$ sudo PACKER_LOG=1 packer build -var 'vmware_esxi_iso_path=/path/to/VMware-VMvisor-Installer-6.7.0.update03-14320388.x86_64.iso' vmware-esxi.json
```


`vmware-esxi.json` is configured to run Packer in headless mode. Only packer output will be seen. If you wish to see the installation output, connect to the VNC port given in the packer output, or remove the line containing "headless" in `vmware-esxi.json`.


Installation is non-interactive.

## Upload to MAAS

You can upload the ESXi image to MAAS with the following command:

```nohighlight
$ maas $PROFILE boot-resources create name='esxi/6.7' title='VMware ESXi 6.7' architecture='amd64/generic' filetype='ddgz' content@=vmware-esxi.dd.gz
```