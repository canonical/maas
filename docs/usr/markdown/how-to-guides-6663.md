This section provides practical, step-by-step guidance for getting the most out of MAAS — from planning your deployment to integrating with automation tools. Use this guide when you're ready to apply MAAS in real-world scenarios and want clear, operational documentation.

## Plan and prepare

Before installing anything, make sure MAAS is the right fit. Confirm that your intended use matches the reference architecture. Clarify your environment's requirements, choose the right installation method (Snap vs. Deb), and decide on deployment targets: bare metal, VMs, or a mix. These choices will shape your entire setup.

<!-- * *Confirm intended use matches reference architecture* -->
* [Examine and confirm requirements](https://maas.io/docs/installation-requirements)
* [Choose the installation type](https://maas.io/docs/how-to-get-maas-up-and-running#p-9034-install-maas-snap-or-packages)

## Install and set up

Here, you'll install and initialize MAAS, then configure it to manage your infrastructure. Whether you're working with LXD, KVM, or another cloud provider, this section walks you through connecting MAAS to your virtual or physical environment.

* [Install MAAS](https://maas.io/docs/how-to-get-maas-up-and-running)
* [Initialize MAAS](https://maas.io/docs/how-to-get-maas-up-and-running#p-9034-post-install-setup-poc)
* [Set up your cloud](https://maas.io/docs/how-to-manage-machines#p-9078-enable-new-machines)

## Provision and deploy

This section covers how to enlist machines into MAAS, test and commission them, and then deploy your desired OS or workloads. It also includes advanced topics like custom image creation, ephemeral deployments, and how to manage machines MAAS didn’t originally deploy.

* [Enlist machines](https://maas.io/docs/how-to-manage-machines#p-9078-discover-machines)
* [Commission/test machines](https://maas.io/docs/how-to-manage-machines#p-9078-commission-test-machines)
* [Deploy machines](https://maas.io/docs/how-to-manage-machines#p-9078-deploy-machines)
* [Confirm deployment](https://maas.io/docs/how-to-manage-machines#p-9078-ssh-into-a-machine-to-diagnose-issues)
* [Customize deployment](https://maas.io/docs/how-to-manage-machines#p-9078-configure-deployment)
* Special deployments
  * [Custom images: building, using, and maintaining](https://maas.io/docs/how-to-build-custom-images)
  * [Ephemeral deployments](https://maas.io/docs/how-to-manage-machines#p-9078-deploy-to-ram-ephemeral-deployment)
<!--  * *Enlisting running machines (as if deployed by MAAS)* -->

## Manage MAAS

Once your systems are running, it's time to manage them effectively. Learn how to label machines with metadata (tags, zones, annotations), configure storage layouts, and handle networking at the fabric, VLAN, and subnet level—including advanced options like DHCP overrides and air gaps.

* [Labeling machines](https://maas.io/docs/how-to-manage-machine-groups)
  * [Tags](https://maas.io/docs/how-to-manage-machine-groups#p-19384-tags-and-annotations)
  * [Resource pools](https://maas.io/docs/how-to-manage-machine-groups#p-19384-resource-pools)
  * [Availability zones](https://maas.io/docs/how-to-manage-machine-groups#p-19384-availability-zones)
  * [Notes](https://maas.io/docs/how-to-manage-machine-groups#p-19384-manage-notes)
  * [Annotations](https://maas.io/docs/how-to-manage-machine-groups#p-19384-manage-dynamic-annotations)
* Storage
  * [Storage types](https://maas.io/docs/reference-maas-storage)
  * [Storage layout](https://maas.io/docs/how-to-manage-machines#p-9078-configure-storage-layout)
* [Networks](https://maas.io/docs/how-to-manage-networks)
  * [VLANs](https://maas.io/docs/how-to-manage-networks#p-9070-manage-vlans)
  * [Subnets](https://maas.io/docs/how-to-manage-networks#p-9070-manage-subnets)
  * [Special DNS / DHCP / NTP settings](https://maas.io/docs/how-to-manage-network-services)
  * [Creating an air gap](https://maas.io/docs/how-to-set-up-air-gapped-maas)
* [Power control](https://maas.io/docs/how-to-manage-machines#p-9078-control-machine-power)
  * [Specific machine types](https://maas.io/docs/how-to-manage-machines#p-9078-set-power-type)
 <!-- * Generic IPMI -->
<!--  * Webhook -->
<!--  * Other generic power types -->
<!-- * PXE booting
  * OOB BMC
  * WakeOnLAN
  * S5/G0 loops
  * PXE-power-type interactions -->
<!--  * Integrating with corporate systems -->
<!--  * Fabrics -->
<!--  * Spaces -->
  
## Monitor and troubleshoot

This section helps you observe and debug your MAAS deployment using tools like Prometheus and Loki. Learn to identify issues with logs, performance, or machine behavior—and get strategies for fixing common problems across your infrastructure.

* [Using Prometheus and Loki](https://maas.io/docs/how-to-monitor-maas)
* [Debugging via logs](https://maas.io/docs/how-to-use-logging)
* [Auditing with logs](https://maas.io/docs/how-to-use-logging#p-14514-auditing-maas)
* [Troubleshooting machine behaviors](https://maas.io/docs/how-to-manage-machines#p-9078-rescue-recovery)
* [Troubleshooting network issues](https://maas.io/docs/maas-troubleshooting-guide)
<!-- * Troubleshooting performance -->

## Scale and optimize

Ready to grow? Learn how to replicate controllers for high availability, set up VM clusters, combine hardware and virtual setups, and handle complex deployments. This section is essential for production-grade MAAS installations.

* [Setting up HA & controller replication](https://maas.io/docs/how-to-manage-high-availability)
* [Advanced deployments](https://maas.io/docs/reference-terraform)
<!-- * Clustering VMs -->
<!-- * Hybrid hardware/VM configurations -->

## Automate and integrate

Finally, make MAAS part of your larger automation pipeline. Learn how to use the MAAS API, CLI scripting, Terraform, and integrate with tools like Charmed MAAS. Use this section to build repeatable, scalable provisioning workflows.

* [Using the MAAS API](https://maas.io/docs/api) <!-- & webhooks -->
* [Using Terraform](https://maas.io/docs/reference-terraform)
<!-- * Integrating MAAS into a cloud-provisioning workflow -->
<!-- * Scripting with the MAAS CLI -->
<!-- * Charmed MAAS -->
