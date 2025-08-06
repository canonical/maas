Understand MAAS by exploring three core areas: machines, MAAS-managed infrastructure, and reliability tools.  Each section connects you to concepts and tasks that keep your data center running smoothly.

## Machines

Machines are the core component of MAAS and the primary driver of the provisioning workflow.

- Learn [how MAAS defines a machine](https://canonical.com/maas/docs/machines) and views its capabilities.
- Get familiar with [the machine life-cycle](https://canonical.com/maas/docs/about-the-machine-life-cycle), which prescribes how machines move through the provisioning process.
- Conceptualize [commissioning](https://canonical.com/maas/docs/about-commissioning-machines) -- how MAAS gathers the hardware information needed for later deployment.
- Discover all the ways you can [customize](https://canonical.com/maas/docs/about-customising-machines) deployment to suit your use case.
- Find out about [deployment](https://canonical.com/maas/docs/about-deploying-machines) and why it's valuable to also [deploy already-provisioned machines](https://canonical.com/maas/docs/about-deploying-running-machines).
- Learn about [LXD projects](https://canonical.com/maas/docs/about-lxd) to simplify VM deployments.
- Understand the value and utility of [grouping machines](https://canonical.com/maas/docs/labelling-devices). 

## MAAS-managed infrastructure

MAAS nuances networking with a pre-configured set of tools, designed to make provisioning more convenient and less error-prone.

- [Network discovery](https://canonical.com/maas/docs/the-role-of-maas-networks#p-20679-network-discovery) reveals every network device that MAAS can see.
- MAAS configures [DHCP](https://canonical.com/maas/docs/the-role-of-maas-networks#p-20679-dhcp) to handle a specific [network booting process](https://canonical.com/maas/docs/the-role-of-maas-networks#p-20679-network-booting-and-pxe), so that machines can [boot in a controlled way](https://canonical.com/maas/docs/the-role-of-maas-networks#p-20679-next-server-and-the-nbp).
- MAAS also manages [DNS](https://canonical.com/maas/docs/the-role-of-maas-networks#p-20679-dns) and [NTP](https://canonical.com/maas/docs/the-role-of-maas-networks#p-20679-ntp) for more efficient provisioning.
- MAAS defines some unique convenience constructs, such as [spaces and fabrics](https://canonical.com/maas/docs/the-role-of-maas-networks#p-20679-spaces-and-fabrics), that influence how you design and plan your provisioning networks.
- Many [other MAAS network customizations](https://canonical.com/maas/docs/the-role-of-maas-networks#p-20679-other-customizations) are worth discovering.
- [Region and rack controllers](https://canonical.com/maas/docs/about-high-availability) do the heavy-lifting of maintaining your data centers.
- Take inventory of the available OS images, including [standard images](https://canonical.com/maas/docs/the-importance-of-images-in-maas#p-17467-standard-images), a number of established [custom images](https://canonical.com/maas/docs/the-importance-of-images-in-maas#p-17467-custom-images) with build instructions, and a [general purpose tool](https://canonical.com/maas/docs/the-importance-of-images-in-maas#p-17467-packer) to create many other custom images.

## Reliability tools

Keep your data center intact and reliable.

- Take stock of where we stand with [MAAS performance](https://canonical.com/maas/docs/boosting-maas-performance).
- Learn about the MAAS catalog of [events](https://canonical.com/maas/docs/an-overview-of-maas-events) for auditing and debugging issues.
- Dive deep into the MAAS [logging](https://canonical.com/maas/docs/about-log-files) domain to understand what is captured.
- Get a better handle on the thinking behind [MAAS security](https://canonical.com/maas/docs/ensuring-security-in-maas) to help you design and maintain a hardened stance.
