Organize machine provisioning at scale with a structured, repeatable workflow.


## Install and configure MAAS

Only four steps are required to get MAAS up and running:

 - [Install MAAS](https://maas.io/docs/how-to-install-maas#p-9034-install-maas-snap-or-packages) or [upgrade an older version](https://maas.io/docs/how-to-install-maas#p-9034-notes-on-upgrading-maas).
 - Choose whether you want a  [proof-of-concept](https://maas.io/docs/how-to-install-maas#p-9034-post-install-setup-poc) or [production](https://maas.io/docs/how-to-install-maas#p-9034-post-install-setup-production) instance.
 - [Configure MAAS](https://maas.io/docs/how-to-install-maas#p-9034-configuring-and-starting-maas) domain name services (DNS) and image acquisition.
 - [Enable DHCP](https://maas.io/docs/how-to-install-maas#p-9034-enabling-dhcp) to provide IP addresses to provisioned machines.

## Fine-tune MAAS networks

MAAS provides pre-configured versions of DHCP, NTP, STP and DNS for routine operation.  If your situation is different, you may want to fine-tune your networking:

- [Make routine adjustments](https://maas.io/docs/how-to-customise-maas-networks#p-9070-routine-network-management), like default gateways, loopback, bridges, and bonds, or even [enable two-NIC interfaces](https://maas.io/docs/how-to-customise-maas-networks#p-9070-two-nic-setup).
- [Manage network discovery](https://maas.io/docs/how-to-customise-maas-networks#p-9070-network-discovery), which automatically detects connected devices.
- Manage day-to-day networking, like [subnets](https://maas.io/docs/how-to-customise-maas-networks#p-9070-subnets), [VLANs](https://maas.io/docs/how-to-customise-maas-networks#p-9070-vlans), local [DHCP configuration](https://maas.io/docs/how-to-customise-maas-networks#p-9070-dhcp-management), and [IP management](https://maas.io/docs/how-to-customise-maas-networks#p-9070-ip-management).
- Nuance [NTP](https://maas.io/docs/how-to-customise-maas-networks#p-9070-ntp-management) and [DNS](https://maas.io/docs/how-to-customise-maas-networks#p-9070-dns-management) operation to match your local environment.

## Provision & manage servers

Explore automated provisioning with MAAS:

- [Find connected machines](https://maas.io/docs/how-to-manage-machines#p-9078-find-machines).
- [Add and configure machines](https://maas.io/docs/how-to-manage-machines#p-9078-add-configure-machines), whether bare metal or virtual, and [manage their power state](https://maas.io/docs/how-to-manage-machines#p-9078-control-machine-power).
- Discover server capabilities by [commissioning machines](https://maas.io/docs/how-to-manage-machines#p-9078-commission-test-machines).
- [Deploy machines](https://maas.io/docs/how-to-manage-machines#p-9078-deploy-machines) to make them productive.
- Configure [specialty configurations](https://maas.io/docs/how-to-manage-machines#p-9078-configure-machine-settings) for specific needs.
- [Rescue, recover](https://maas.io/docs/how-to-manage-machines#p-9078-rescue-recovery) and [recycle](https://maas.io/docs/how-to-manage-machines#p-9078-release-or-remove-machines) machines, including full data erasure.

## Group machines for easy identification

Availability zones provide failover; resource pools group machines for easy tracking; tags and annotations provide a more freeform labeling system.  All three groups are searchable from both UI and CLI.

- Set up [availability zones](https://maas.io/docs/how-to-manage-machine-groups#p-19384-availability-zones) to create redundant failover.
- Assign [resource pools](https://maas.io/docs/how-to-manage-machine-groups#p-19384-resource-pools) to budget provisioning.
- Label and even control machine behavior with [tags and annotations](https://maas.io/docs/how-to-manage-machine-groups#p-19384-tags-and-annotations).

## Manage deployment OS images

MAAS supports a very wide range of Linux, Windows, and specialty operating systems.

- Set up [image SimpleStreams](https://maas.io/docs/how-to-manage-images#p-9030-switch-image-streams) to keep up-to-date.
- Use [custom](https://maas.io/docs/how-to-manage-images#p-9030-use-a-custom-mirror) and [local](https://maas.io/docs/how-to-manage-images#p-9030-use-a-local-mirror) mirrors to improve download performance.
- [Build your own Ubuntu images](https://maas.io/docs/how-to-build-ubuntu-images)
- [Build custom images](https://maas.io/docs/how-to-build-custom-images), including RHEL, CentOS, Oracle Linux, VMWare ESXI, Windows, and others.

## Keep things running smoothly

Performance, security, and auditing are integrated capabilities of MAAS.

- [Use logging](https://maas.io/docs/how-to-use-logging) wisely to keep track.
- [Monitor MAAS](https://maas.io/docs/how-to-monitor-maas) to manage performance and find bottlenecks.
- [Enhance MAAS security](https://maas.io/docs/how-to-enhance-maas-security) and [manage MAAS users](https://maas.io/docs/how-to-enhance-maas-security#p-9102-manage-users) to maintain data and operational security.
- [Enable high availability](https://maas.io/docs/how-to-enable-high-availability) to scale workloads.

## Handle specialty situations

Deploy real-time or FIPS-compliant kernels, run MAAS in an air-gapped environment, and write Python programs to control MAAS.  You can even deploy virtual machines on an IBM Z Series.

- Deploy [real-time](https://maas.io/docs/how-to-deploy-a-real-time-kernel) or [FIPS-compliant](https://maas.io/docs/how-to-deploy-a-fips-compliant-kernel) kernels.
- Run MAAS in [air-gapped mode](https://maas.io/docs/how-to-configure-an-air-gapped-maas).
- [Script your MAAS instance with Python](https://maas.io/docs/how-to-use-the-python-api-client).
- [Deploy virtual machines on an IBM Z series machine](https://maas.io/docs/how-to-deploy-vms-on-ibm-z).
