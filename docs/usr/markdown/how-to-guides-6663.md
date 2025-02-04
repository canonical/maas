> *Errors or typos? Topics missing? Hard to read? <a href="https://docs.google.com/forms/d/e/1FAIpQLScIt3ffetkaKW3gDv6FDk7CfUTNYP_HGmqQotSTtj2htKkVBw/viewform?usp=pp_url&entry.1739714854=https://maas.io/docs/how-to-guides" target = "_blank">Let us know.</a>*

Welcome to the comprehensive guide for configuring and managing your MAAS (Metal as a Service) environment. This section provides a step-by-step approach to help you master MAAS, from the basics to advanced customization and maintenance.

## Core configuration

Start with the foundational steps needed to set up your MAAS environment. This section covers everything from installing MAAS to deploying and locating machines, ensuring that your setup is robust and functional. Learn how to monitor and troubleshoot issues effectively to keep your infrastructure running smoothly.

- [Install or upgrade MAAS](/t/-/5128)
- [Customise networks](/t/-/5164)
- [Customise DHCP](/t/-/5132)
- [Choose OS images](/t/-/5124)
- [Configure controllers](/t/-/5172)
- [Configure machines](/t/-/7844)
- [Commission machines](/t/-/7859)
- [Allocate machines](/t/-/7858)
- [Deploy machines](/t/-/5112)
- [Locate machines](/t/how-to-locate-machines/5192)
- [Monitor MAAS](/t/how-to-monitor-maas/5204)
- [Troubleshoot issues](/t/how-to-troubleshoot-common-issues/5333)

## Tuning performance

Optimize your MAAS setup for better performance and reliability. This section guides you through managing IP ranges, mirroring images, and enabling high availability to ensure your environment is efficient and resilient.

- [Manage IP ranges](/t/-/5136)
- [Mirror MAAS images](/t/-/5927)
- [Enable high availability](/t/-/5120)

## Adjusting your instance

Customize your MAAS environment to meet specific operational needs. From managing storage and adjusting settings to setting up power drivers and configuring air-gapped instances, this section provides the tools for fine-tuning your setup.

- [Customise machines](/t/-/5108)
- [Manage storage](/t/-/7846)
- [Adjust MAAS settings](/t/how-to-change-maas-settings/8035)
- [Set up power drivers](/t/-/5246)
- [Set up air-gapped MAAS](/t/how-to-configure-an-air-gapped-maas/5212)

## Using virtual machines

Leverage virtual machine capabilities within MAAS to enhance your infrastructure. Learn how to use LXD, manage virtual machines, and deploy on specialized hardware like IBM Z.

- [Use virtual machines](/t/-/6500)
- [Set up external LXD](/t/how-to-set-up-external-lxd/5208)
- [Use external LXD](/t/how-to-use-external-lxd/5140)
- [Use LXD projects](/t/how-to-use-lxd-projects/7871)
- [Manage virtual machines](/t/how-to-manage-virtual-machines/5148)
- [Deploy VMs on IBM Z](/t/how-to-deploy-vms-on-ibm-z/7885)

## Finding issues in the logs

Effective log management is key to identifying and resolving issues. This section explains how to use various logs, audit MAAS, and interpret testing data to maintain a secure and operational environment.

- [Use logging](/t/how-to-use-logging/6956)
- [Use MAAS systemd logs](/t/how-to-use-maas-systemd-logs/8103)
- [Read event logs](/t/how-to-read-event-logs/5252)
- [Read commissioning logs](/t/how-to-read-commissioning-logs/5248)
- [Interpret testing logs](/t/how-to-interpret-testing-logs/5314)
- [Audit MAAS](/t/how-to-audit-maas/5987)
- [Review audit logs](/t/how-to-review-audit-logs/5256)

## Grouping machines

Organize your machines for better management using tags, availability zones, and resource pools. This section covers how to categorize and annotate machines to streamline your operations.

- [Use availability zones](/t/-/5152)
- [Use resource pools](/t/-/7845)
- [Annotate machines](/t/how-to-annotate-machines/5929)
- [Manage tags](/t/how-to-manage-tags/5928)
- [Use machine tags](/t/how-to-use-machine-tags/5224)
- [Use network tags](/t/how-to-use-network-tags/5228)
- [Use controller tags](/t/how-to-use-controller-tags/5216)
- [Use storage tags](/t/how-to-use-storage-tags/5232)

## Scripting MAAS

Automate tasks and interact programmatically with MAAS using scripts and APIs. This section introduces cloud-init, the MAAS API, and Python scripting for more efficient management.

- [Use cloud-init with MAAS](/t/how-to-use-cloud-init-with-maas/9122)
- [Login to the MAAS API](/t/how-to-authenticate-to-the-maas-api/5060)
- [Script MAAS with Python](/t/how-to-use-the-python-api-client/5404)

## Securing your instance

Protect your MAAS environment with enhanced security measures. Learn to manage user access, implement TLS, and integrate with Vault for secure configuration and data management.

- [Enhance MAAS security](/t/how-to-enhance-maas-security/5196)
- [Manage user access](/t/how-to-manage-user-access/5184)
- [Implement TLS](/t/how-to-implement-tls/5116)
- [Integrate Vault](/t/how-to-integrate-vault/6942)

## Building kernels

Customize your deployment by building specialized kernels and images. This section guides you through deploying real-time or FIPS-compliant kernels and building various OS images for different use cases.

- [Deploy a real-time kernel](/t/-/6658)
- [Deploy a FIPS kernel](/t/-/7743)
- [Use VMWare images](/t/-/5144)
- [Customise images](/t/-/5104)
- [Build MAAS images](/t/-/7872)
- [Build Ubuntu](/t/-/7873)
- [Build RHEL 7](/t/-/7874)
- [Build RHEL 8](/t/-/7875)
- [Build CentOS 7](/t/-/7876)
- [Build Oracle Linux 8](/t/-/8078)
- [Build Oracle Linux 9](/t/-/8079)
- [Build ESXi](/t/-/7877)
- [Build Windows](/t/-/7878)

## Maintaining MAAS

Ensure the long-term stability of your MAAS environment with regular maintenance tasks. Learn how to back up and upgrade MAAS to keep your system secure and up-to-date.

- [Back up MAAS](/t/-/5096)