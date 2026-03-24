# Explanation

Understand MAAS better through three key areas: machine life-cycle, MAAS-managed infrastructure, and reliability tools.

## Machines

Machines are the core component of MAAS and the primary driver of the provisioning workflow.

- Learn [how MAAS defines a machine](explanation/machine-basics.md) and views its capabilities.
- Get familiar with [the machine life-cycle](explanation/the-machine-life-cycle.md), which prescribes how machines move through the provisioning process.
- Conceptualize [commissioning](explanation/commissioning-machines.md) -- how MAAS gathers the hardware information needed for later deployment.
- Discover all the ways you can [customize](explanation/machine-customization.md) deployment to suit your use case.
- Find out about [deployment](explanation/deploying-machines.md) and why it's valuable to also [deploy already-provisioned machines](explanation/deploying-running-machines.md).
- Learn about [LXD projects](how-to-guides/manage-machines.md#use-lxd-vms) to simplify VM deployments.
- Understand the value and utility of [grouping machines](explanation/machine-groups.md).

## MAAS-managed infrastructure

MAAS nuances networking with a pre-configured set of tools, designed to make provisioning more convenient and less error-prone.

- [Network discovery](explanation/networking.md#network-discovery) reveals every network device that MAAS can see.
- MAAS configures [DHCP](explanation/networking.md#dhcp) to handle a specific network booting process, so that machines can boot in a controlled way.
- MAAS also manages [DNS](explanation/networking.md#dns) and [NTP](explanation/networking.md#ntp) for more efficient provisioning.
- MAAS defines some unique convenience constructs, such as [spaces and fabrics](explanation/networking.md#spaces-and-fabrics), that influence how you design and plan your provisioning networks.
- Many [other MAAS network customizations](explanation/networking.md#other-customizations) are worth discovering.
- [Region and rack controllers](how-to-guides/manage-high-availability.md#enable-ha-for-rack-controllers) do the heavy-lifting of maintaining your data centers.
- Take inventory of the available OS images, including [standard images](explanation/images.md#standard-images), a number of established [custom images](explanation/images.md#custom-images) with build instructions, and a [general purpose tool](explanation/images.md#packer) to create many other custom images.

## Reliability tools

Keep your data center intact and reliable.

- Take stock of where we stand with [MAAS performance](explanation/performance.md).
- Learn about the MAAS catalog of [events](explanation/events.md#about-audit-events) for auditing and debugging issues.
- Dive deep into the MAAS [logging](explanation/logging.md) domain to understand what is captured.
- Get a better handle on the thinking behind [MAAS security](how-to-guides/enhance-maas-security.md) to help you design and maintain a hardened stance.

```{toctree}
:titlesonly:
:maxdepth: 2
:hidden:

machine-basics
the-machine-life-cycle
commissioning-machines
commissioning-scripts
machine-customization
deploying-machines
deploying-running-machines
lxd-projects
machine-groups
networking
controllers
images
performance
events
logging
security
```
