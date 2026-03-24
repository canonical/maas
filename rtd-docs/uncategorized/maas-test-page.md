# MAAS test page

This section provides practical, step-by-step guidance for getting the most out of MAAS—from planning your deployment to integrating with automation tools. Use this guide when you're ready to apply MAAS in real-world scenarios and want clear, operational documentation.

## Plan and prepare

Before installing anything, make sure MAAS is the right fit. Confirm that your intended use matches the reference architecture. Clarify your environment's requirements, choose the right installation method (Snap vs. Deb), and decide on deployment targets: bare metal, VMs, or a mix. These choices will shape your entire setup.

* Confirm intended use matches reference architecture*
* [Examine and confirm requirements](reference/configuration-guides/installation-requirements.md)
* [Choose the installation type](how-to-guides/get-maas-up-and-running.md#install-maas)

## Install and set up

Here, you'll install and initialize MAAS, then configure it to manage your infrastructure. Whether you're working with LXD, KVM, or another cloud provider, this section walks you through connecting MAAS to your virtual or physical environment.

* [Install MAAS](how-to-guides/get-maas-up-and-running.md)
* [Initialize MAAS](how-to-guides/get-maas-up-and-running.md#post-install-setup)
* [Set up your cloud](how-to-guides/manage-machines.md#enable-new-machines)

## Provision and deploy

This section covers how to enlist machines into MAAS, test and commission them, and then deploy your desired OS or workloads. It also includes advanced topics like custom image creation, ephemeral deployments, and how to manage machines MAAS didn’t originally deploy.

* [Enlist machines](how-to-guides/manage-machines.md#discover-machines)
* [Commission/test machines](how-to-guides/manage-machines.md#commission-test-machines)
* [Deploy machines](how-to-guides/manage-machines.md#deploy-machines)
* [Confirm deployment](how-to-guides/manage-machines.md#rescue-recovery)
* [Customize deployment](how-to-guides/manage-machines.md#configure-deployment)
* Special deployments
  * [Custom images: building, using, and maintaining](how-to-guides/build-custom-images.md)
  * [Ephemeral deployments](how-to-guides/manage-machines.md#deploy-machines)
 *Enlisting running machines (as if deployed by MAAS)*

## Manage MAAS

Once your systems are running, it's time to manage them effectively. Learn how to label machines with metadata (tags, zones, annotations), configure storage layouts, and handle networking at the fabric, VLAN, and subnet level—including advanced options like DHCP overrides and air gaps.

* [Labeling machines](how-to-guides/manage-machine-groups.md)
  * [Tags](how-to-guides/manage-machine-groups.md#manage-tags-in-maas)
  * [Resource pools](how-to-guides/manage-machine-groups.md#manage-resource-pools)
  * [Availability zones](how-to-guides/manage-machine-groups.md#manage-availability-zones)
  * [Notes](how-to-guides/manage-machine-groups.md#manage-notes-in-maas)
  * [Annotations](how-to-guides/manage-machine-groups.md#manage-dynamic-annotations-in-maas)
* Storage
  * [Storage types](reference/configuration-guides/storage.md)
  * [Storage layout](how-to-guides/manage-machines.md#storage-layouts)
* [Networks](how-to-guides/manage-networks.md)
  * [VLANs](how-to-guides/manage-networks.md#manage-vlans)
  * [Subnets](how-to-guides/manage-networks.md#manage-subnets)
  * Fabrics
  * Spaces
  * [Special DNS / DHCP / NTP settings](how-to-guides/manage-network-services.md)
  * [Creating an air gap](how-to-guides/set-up-air-gapped-maas.md)
  * Integrating with corporate systems
* [Power control](how-to-guides/manage-machines.md#control-machine-power)
  * [Specific machine types](how-to-guides/manage-machines.md#control-machine-power)
  * Generic IPMI
  * Webhook
  * Other generic power types
* PXE booting
  * OOB BMC
  * WakeOnLAN
  * S5/G0 loops
  * PXE-power-type interactions
  
## Monitor and troubleshoot

This section helps you observe and debug your MAAS deployment using tools like Prometheus and Loki. Learn to identify issues with logs, performance, or machine behavior—and get strategies for fixing common problems across your infrastructure.

* [Using Prometheus and Loki](how-to-guides/monitor-maas.md)
* [Debugging via logs](how-to-guides/use-logging.md)
* [Auditing with logs](how-to-guides/use-logging.md#auditing-maas)
* [Troubleshooting machine behaviors](how-to-guides/manage-machines.md#rescue-recovery)
* [Troubleshooting network issues](reference/configuration-guides/troubleshooting.md)
* Troubleshooting performance

## Scale and optimize

Ready to grow? Learn how to replicate controllers for high availability, set up VM clusters, combine hardware and virtual setups, and handle complex deployments. This section is essential for production-grade MAAS installations.

* Clustering VMs
* Hybrid hardware/VM configurations
* [Setting up HA & controller replication](how-to-guides/manage-high-availability.md)
* [Advanced deployments](reference/configuration-guides/terraform.md)

## Automate and integrate

Finally, make MAAS part of your larger automation pipeline. Learn how to use the MAAS API, CLI scripting, Terraform, and integrate with tools like Charmed MAAS. Use this section to build repeatable, scalable provisioning workflows.

* [Using the MAAS API](reference/api-reference/index.md) & webhooks
* Scripting with the MAAS CLI
* Charmed MAAS
* [Using Terraform](reference/configuration-guides/terraform.md)
* Integrating MAAS into a cloud-provisioning workflow
