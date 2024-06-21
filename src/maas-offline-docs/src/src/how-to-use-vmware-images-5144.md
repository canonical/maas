> *Errors or typos? Topics missing? Hard to read? <a href="https://docs.google.com/forms/d/e/1FAIpQLScIt3ffetkaKW3gDv6FDk7CfUTNYP_HGmqQotSTtj2htKkVBw/viewform?usp=pp_url&entry.1739714854=https://maas.io/docs/integrating-vmware-images" target = "_blank">Let us know.</a>*

To deploy VMware ESXi through MAAS, you'll need to create a specialised image using an official VMware ISO. Canonical offers a [GitHub repository](https://github.com/canonical/packer-maas) of community-contributed [packer](https://www.packer.io/) templates to automate this process.

> **Note**: VMware [does not support cloning boot devices](https://kb.vmware.com/s/article/84280). This may lead to [issues](https://kb.vmware.com/s/article/84349) like data corruption on VMFS data stores with cloned boot devices.

## Prerequisites

To create and deploy a VMware image, you'll need:

- MAAS 2.5.0+
- A machine running Ubuntu 18.04+
- **CPU**: 4 cores at 2GHz
- **Memory**: 8GB RAM (16GB recommended)
- **Disk space**: 11GB
- [VMware ESXi ISO](https://my.vmware.com/en/web/vmware/evalcenter?p=free-esxi6)
- [Packer](https://www.packer.io/intro/getting-started/install.html)
- Tested with Packer 1.3.4 64-bit Linux binaries
- [Packer template for MAAS](https://github.com/canonical/packer-maas) custom image

## Features and limits

## Cloning VMware images

As previously mentioned, VMware [does not support cloning boot devices](https://kb.vmware.com/s/article/84280). This limitation may cause data corruption issues on VMFS data stores.

## VMware + MAAS networks

- ESXi doesn't support Linux bridges.
- Supported bond modes are mapped as follows:
  - balance-rr to portid
  - active-backup to explicit
  - 802.3ad to iphash
- No other bond modes are currently supported.
- A PortGroup with a VMK attached cannot be used for VMs.

## VMware + MAAS storage

Custom storage configurations are unsupported; MAAS will extend `datastore1` to the full size of the deployment disk.

## ESXi H/W support

VMware has [specific hardware requirements](https://www.vmware.com/resources/compatibility/search.php). Running ESXi in a virtual machine or MAAS virsh Pod is not supported.

## Customising images

Modify the `packer-maas/vmware-esxi/http/vmware-esxi-ks.cfg` file to customise the image.

## Building an image

Load the `nbd` kernel module:

```nohighlight
sudo modprobe nbd
```

Navigate to the appropriate directory:

```nohighlight
cd /path/to/packer-maas/vmware-esxi
```

Build the image:

```nohighlight
sudo packer build -var 'vmware_esxi_iso_path=/path/to/VMware-VMvisor-Installer-6.7.0-8169922.x86_64.iso' vmware-esxi.json
```

## Uploading an image

To upload the image to MAAS, use:

```nohighlight
maas $PROFILE boot-resources create name='esxi/6.7' title='VMware ESXi 6.7' architecture='amd64/generic' filetype='ddgz' content@=vmware-esxi.dd.gz
```