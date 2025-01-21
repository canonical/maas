> *Errors or typos? Topics missing? Hard to read? <a href="https://docs.google.com/forms/d/e/1FAIpQLScIt3ffetkaKW3gDv6FDk7CfUTNYP_HGmqQotSTtj2htKkVBw/viewform?usp=pp_url&entry.1739714854=https://maas.io/docs/the-role-of-maas-networks" target = "_blank">Let us know.</a>*

MAAS provisions bare metal servers and virtual machines. It creates a single point of control that removes a lot of the logistical errors associated with manual hookup, configuration, and discovery. MAAS also makes it very easy to run your racks -- or even your whole datacenter -- remotely. This document explains how MAAS networking makes all this possible.

## Network discovery

One of the first ways that MAAS cuts down on manual errors is called network discovery. MAAS listens passively to IP traffic on any network it can see. As it does so, it observes other devices receiving and responding to TCP packets, and it captures each device's IP address. MAAS also captures any other identifying information that's available. For example, it also uses mDNS to collect and present the hostname, if available. All of the captured information is summarized in a discovery dashboard.

Discovery runs periodically to capture any network changes. This feature, which can be toggled, helps ensure that you quickly catch every device change in your local MAAS network.

## IPMI networking

Machines that MAAS can provision have a baseboard management controller or BMC. A BMC is a separate CPU often included on the motherboard of servers and devices. Its capabilities are limited to managing and monitoring the health of the device. The BMC has sensors for physical characteristics like temperature and power supply voltage, and controls for rebooting or power-cycling the device.

MAAS uses the BMC to turn remote devices on or off, and reboot them at will. A BMC can also monitor BIOS or UEFI, provide a serial console for the device, and do a few other things with the hardware -- but most of them are uninteresting from a MAAS perspective. For the purposes of this discussion, our main interest in the BMC is the ability to power cycle and reboot machines.

## Network booting and PXE

Power-cycling a machine is all well and good, but MAAS can't actually provision the machine until it's enabled to network boot. This just means that the BIOS or UEFI firmware must be set to first attempt to boot from the network connection on the device's Network Interface Card (NIC).

This also means the NIC must be capable of PXE booting (PXE stands for Preboot Execution Environment). PXE booting is pretty basic: the NIC tries to discover a DHCP server on its connection and waits for an answer. The answer must contain two things: a usable IP address and a server that can provide booting instructions.

## DHCP

So we've seen that the BMC handles power cycling the machine, and the NIC handles booting it remotely. Let's quickly dive into DHCP, which mediates the boot process.

DHCP stands for Dynamic Host Control Protocol, which simply means that it gives a host a unique IP address that won't collide with other devices on that network. The DHCP protocol consists of four messages:

* DISCOVER: The machine that wants an IP address asks to discover any DHCP servers visible to its network segment.
* OFFER: Any available DHCP server on the segment offers to lease the machine a specific, unique IP address.
* REQUEST: The machine requests to accept one of the offers (there can be more than one DHCP server on a network).
* ACKNOWLEDGE: The DHCP server confirms to the machine that the offered IP is now leased to that machine.

DHCP also offers several optional services, like configuring DNS, gateway, and routing; load-balancing and failover; and VLAN and QoS configuration. MAAS depends on one of these optional features: bootstrapping services (PXE booting). Properly configured DHCP is capable of specifying several PXE-boot parameters:

* next-server: Specifies the TFTP/HTTP server for PXE booting clients.
* filename: Specifies the path to the boot file (e.g., bootloader) for PXE boot.
* option 67: Also used to specify the boot file name in some DHCP configurations.
* option 66: Points to the boot server hostname or IP address.

Because MAAS needs to provide specially-configured DHCP to a PXE-booting server – specifically the next-server address – the bundled, pre-configured MAAS DHCP server should be used. It is possible to link to external DHCP servers or relays, but not recommended.

## IP range management and static IP assignments

Let’s delve into why the MAAS-provided DHCP server is recommended.

The first reason has to do with IP address assignments. If an external server (or a relay to some external server) is used, static routes would have to be carefully set to avoid issues. It’s much easier to simply use the bundled, pre-configured DHCP server with MAAS, which automates handling of static IP addresses. Visual feedback in the MAAS UI makes it obvious which IP addresses are in use and whether or not they are static.

Second, MAAS intentionally offers a more scalable solution by allowing administrators to define explicit IP ranges. MAAS centralizes IP management, reducing the need for manual configuration and ensuring that static IPs are applied consistently across your infrastructure. You can allocate static IP addresses from a pool or manually assign them during deployment, or simply let MAAS handle IP assignment from the pool. This capability makes MAAS – and the pre-configured DHCP server shipped with MAAS – the better choice for environments where consistent IP addressing is crucial for server stability and accessibility.

## Next server and the NBP

A third reason MAAS-provided DHCP is recommended has to do with PXE booting. Successful PXE booting requires that an optional DHCP parameter called next-server be set. When network booting, the PXE-capable NIC sends a DHCP request to its connected networks, asking for an IP address for itself, and also for the IP address of a connected TFTP (Trivial File Transport Protocol) server that can provide a bootable file called a NBP (Network Boot Packet).

If you are able to correctly configure your external/relayed DHCP to provide the address of a valid TFTP server with a MAAS-compatible NBP, so much the better. In most cases, though, it’s much easier to simply use the MAAS-provided DHCP server.

## DNS

MAAS directly integrates DNS management, allowing settings at the subnet level, reducing configuration drift and the all-too-common DNS errors. Whether you're using internal DNS servers for private networks or external ones for public services, MAAS provides a more streamlined and centralized solution for DNS management.

## NTP

In a MAAS-managed environment, time synchronization via NTP is centralized, making it easier to ensure that all machines have consistent and accurate time settings. While external NTP servers can be used, MAAS allows you to configure NTP settings during the deployment process, ensuring that machines automatically sync with the correct time sources.

MAAS uses Chrony to synchronize time across region and rack controllers, to coordinate operations and maintain accurate logs. Rack controllers provide NTP settings via DHCP, so deployed machines automatically receive the right time. This reduces the need for manual configuration and helps avoid common issues related to time drift, which can cause problems with logging, authentication, and other time-sensitive processes. By handling NTP settings centrally, MAAS ensures that time synchronization is reliable across all managed systems.

## VLANs

VLANs (Virtual LANs) are a common way to create logically separate networks using the same physical infrastructure.

Managed switches can assign VLANs to each logical “port” in either a “tagged” or an “untagged” manner. A VLAN is said to be “untagged” on a particular port when it is the default VLAN for that port and requires no special configuration to access it. Nodes connected to untagged VLANs are unaware of VLANs and do not require any special configuration for VLAN support.

You can also use tagged VLANs with MAAS nodes. If a switch port is configured to allow tagged VLAN frames from a MAAS node, that node can automatically access interfaces on that VLAN. Nodes connected to tagged VLANs must support VLAN tagging and be configured to tag traffic with the correct VLAN ID. Tagged VLANs are useful for nodes that require access to multiple VLANs or for advanced networking setups, such as traffic segregation.

MAAS allows you to create and manage VLANs from a single interface, enabling secure and scalable segmentation without additional infrastructure. VLANs and subnets are embedded into the provisioning workflow, so tagged and untagged VLANs, as well as subnets contained within them, can be managed from a single interface. A clean, clear interface ensures the correct network settings, which in turn reduces errors.

## Spaces and fabrics

MAAS allows you to logically group networks using spaces and fabrics.

Fabrics are a L1 physical layer concept used to group VLANs. In MAAS, a fabric always has an associated VLAN. Unless otherwise specified, a “Default VLAN” is created for every fabric, to which every new VLAN-aware object in the fabric will be associated with by default and cannot exist separate from a VLAN. Similarly, a subnet always has an associated VLAN even if it’s the default. Therefore, subnets in MAAS are always reachable through a fabric.

Spaces are a L3 network layer concept used to group subnets. Spaces are created without any association with other network elements. In order to assign a space both a fabric id and a VLAN id need to be specified. Note that there is not any direct association between subnets and spaces. However, if the VLAN associated with the space is not assigned to any subnet, the space can’t actually do anything useful when it’s addressed by Juju.

To summarize, in MAAS, VLANs always exist in some fabric and can optionally join a space. If you want to create a group of specific VLANs, create a new fabric and associate it with the VLANs. If you want to create a group of subnets, first make sure that the subnets can be independently selected by fabric id and VLAN id combinations and then create a new space and associate it with the relevant combinations.

## Other customizations

There are a few additional MAAS-centric network customization options.

### Network validation

MAAS can validate connectivity and speed on network connections prior to deployment.

### Static routes

MAAS can define static routes globally to avoid configuration drift, ensure consistency, and create better control over traffic flow. Static routes are particularly valuable in environments requiring specific traffic paths for security, redundancy, or performance.

### Loopback interfaces in MAAS-managed environments

Loopback interfaces are necessary for BGP and FRR, but tricky to configure. MAAS provides the capability to centrally define and configure loopback interfaces directly.

### Bridges

Bridges aggregate interface traffic at the cost of complexity. MAAS offers centralized bridge creation and management directly from the UI or CLI. MAAS bridges are automatically integrated with VLANs and bonds, making it easier to reduce redundancy, avoid mistakes, and improve performance.

Note that while Netplan provides a simpler way to configure bridges manually (through YAML files), MAAS-managed bridges don't require manual configuration. In some cases, though, such as integrating MAAS-managed systems into external environments, Netplan is the right answer.

### Multi-NIC configurations

MAAS automatically detects and configures all available interfaces, including multi-NIC machines.

### Gateways

MAAS centralizes gateway configuration across all connected machines. You can modify gateway settings easily, which is especially useful in environments where gateway configurations need to be updated regularly for many machines.

### Bonds

Network bonding is crucial for high-availability environments, and MAAS makes it easier to create and manage bonds across multiple interfaces. Instead of configuring bonds manually on each machine, MAAS allows you to create bonds from its UI or CLI, applying them consistently across your infrastructure.

MAAS supports a range of bonding modes, such as active-backup or balance-rr, giving you flexibility based on your network's needs. With MAAS handling bonds centrally, you can ensure that redundant interfaces are always configured properly, reducing the risk of network downtime and improving overall performance.
