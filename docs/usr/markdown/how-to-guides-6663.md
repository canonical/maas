Knowing the components and machine states of MAAS is one thing; understanding how they fit together into a provisioning workflow is another. This cheat sheet is designed to make that process clear.

## Install and configure MAAS

Only four steps are required to [get MAAS up and running](https://maas.io/docs/how-to-get-maas-up-and-running):

 - Install MAAS or upgrade an older version.
 - Choose whether you want to build a proof-of-concept or jump straight to production.
 - Configure MAAS domain name services (DNS) and image acquisition.
 - Enable DHCP to provide IP addresses to provisioned machines.
 -  And don't forget to [back up MAAS](https://maas.io/docs/how-to-back-up-maas) once you get it running properly.

## Fine-tune MAAS networks

MAAS provides pre-configured versions of DHCP, NTP, STP and DNS for routine operation. If your situation is different, you may want to [manage networks](https://maas.io/docs/how-to-manage-networks) to suit your environment:

- Make routine adjustments, like adding default gateways, loopback, bridges, and bonds, or even enable two-NIC interfaces.
- Manage network discovery, which automatically detects connected devices to limit guesswork.
- Manage standard network infrastructure, like subnets, VLANs, local DHCP configuration, and IP addresses.
- [Manage network services](https://maas.io/docs/how-to-manage-network-services) -- like DHCP, DNS and NTP -- to match your local and corporate policies.

## Provision & manage servers

[Manage machines](https://maas.io/docs/how-to-manage-machines) to build and flex data centers with MAAS:

- Discover which devices are already connected and find them again when you need them.
- Add and configure machines, whether bare metal or virtual, and manage their power state.
- Discover and remember server capabilities by commissioning machines.
- Deploy machines to make them productive.
- Create specialty configurations for specific needs and special cases.
- Rescue, recover and recycle machines, including full data erasure.

## Group machines for quick categorization & redeployment

[Manage machine groups](https://maas.io/docs/how-to-manage-machine-groups) create failover redundancy (availability zones), ensure functional allocation (resource pools), easily track machine capabilities(tags) and track operational status (notes and annotations):

- Set up to create redundant failover for critical systems.
- Assign resource pools to budget provisioning by corporate or data center function.
- Keep track of machine setup and tooling with tags.
- Remember what machines are doing both offline (notes) and when in production (annotations).

## Manage deployment OS images

MAAS supports a wide range of Linux, Windows, and specialty operating systems, so it pays to [manage images](https://maas.io/docs/how-to-manage-images) carefully:

- Set up [image SimpleStreams to keep your standard images up-to-date.
- Use custom and local mirrors to improve download performance.
- [Build your own Ubuntu images](https://maas.io/docs/how-to-build-ubuntu-images).
- [Build custom images](https://maas.io/docs/how-to-build-custom-images), including RHEL, CentOS, Oracle Linux, VMWare ESXI, Windows, and others.

## Keep things running smoothly

Performance, security, and auditing are integrated capabilities of MAAS.

- [Manage high availability](https://maas.io/docs/how-to-manage-high-availability) by managing your region and rack controllers carefully and keeping them tuned.
- [Use logging](https://maas.io/docs/how-to-use-logging) wisely to keep track.
- [Monitor MAAS](https://maas.io/docs/how-to-monitor-maas) to manage performance and find bottlenecks.
- [Enhance MAAS security](https://maas.io/docs/how-to-enhance-maas-security) and manage MAAS users to maintain data and operational security.

## Handle specialty situations

Deal with a variety of special cases:

- Deploy [real-time](https://maas.io/docs/how-to-deploy-a-real-time-kernel) or [FIPS-compliant](https://maas.io/docs/how-to-deploy-a-fips-compliant-kernel) kernels.
- Run MAAS in [air-gapped mode](https://maas.io/docs/how-to-set-up-air-gapped-maas).
- [Script your MAAS instance with Python](https://maas.io/docs/how-to-script-maas-with-python).
- [Deploy virtual machines on an IBM Z series machine](https://maas.io/docs/how-to-deploy-vms-on-ibm-z).

Some of these steps are repeated frequently or done on demand. This general workflow will drive provisioning in the right direction.
