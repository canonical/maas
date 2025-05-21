MAAS provisions bare metal servers and virtual machines. It creates a single point of control that removes a lot of the logistical errors associated with manual hookup, configuration, and discovery. MAAS also makes it easy to run your racks -- or even your whole datacenter -- remotely. MAAS networking makes all this possible.

## Network discovery

MAAS passively monitors ARP traffic to detect devices on the network. It records IP and MAC addresses, tracking changes over time. If available, it also captures hostnames via mDNS. Discovery runs periodically and updates a dashboard with detected devices. This feature can be enabled or disabled.

## IPMI networking

Machines have a baseboard management controller (BMC), a separate CPU dedicated to managing and monitoring device health. The BMC can power-cycle the device, so MAAS uses the BMC to turn machines on or off, or reboot them via PXE. MAAS can't provision a machine until it's enabled to network boot, that is, until the firmware is set to boot first from device's Network Interface Card (NIC).

## DHCP

When PXE booting, DHCP (Dynamic Host Control Protocol) mediates the process. DHCP gives the machine a unique IP address that won't collide with other devices on that network. The DHCP protocol consists of four messages:

* DISCOVER: The machine that wants an IP address asks to discover any DHCP servers visible to its network segment.
* OFFER: Any available DHCP server on the segment offers to lease the machine a specific, unique IP address.
* REQUEST: The machine requests to accept one of the offers (there can be more than one DHCP server on a network).
* ACKNOWLEDGE: The DHCP server confirms to the machine that the offered IP is now leased to that machine.

DHCP also offers several optional services, which MAAS uses to specify:

* next-server: Specifies the TFTP/HTTP server for PXE booting clients.
* filename: Specifies the path to the boot file (e.g. bootloader) for PXE boot.
* option 67: Also used to specify the boot file name in some DHCP configurations.
* option 66: Points to the boot server hostname or IP address.

Because MAAS needs to configure DHCP with these options, the bundled MAAS DHCP server should be used. You can use external DHCP servers or relays, but it is not recommended. This bundled server redefines DHCP management by integrating advanced features:

- Setting lease times and boot options: MAAS sets short lease times suitable for PXE booting and high-turnover environments, with specialized options for PXE and iPXE to support network-based system deployments.

- Dynamic configuration and templating: MAAS employs a dynamic approach through an API and database, allowing real-time generation of DHCP settings based on the current network status and deployment requirements.

- Failover and high availability: MAAS includes robust failover settings and can configure DHCP on multiple rack controllers per VLAN for enhanced reliability.

- OMAPI integration and key management: MAAS utilizes OMAPI extensively to manage DHCP settings and leases programmatically, enhancing security and control.

- Advanced network interface handling: MAAS automatically selects the optimal network interface for DHCP services, considering various types such as physical, VLAN, and bonds.

- Notification hooks and state management: MAAS uses notification hooks for commit, expiry, and release events, and employs the `DHCPState` class to monitor and react to changes in configuration states dynamically.

- Service integration: MAAS integrates DHCP configuration with DNS and NTP settings management, ensuring that all network services are synchronized and responsive to each machine's needs.

- Service monitoring and immediate feedback: MAAS integrates with service monitors to manage DHCP states effectively, applying changes instantly without needing restarts.

- Asynchronous and concurrent operations: MAAS supports asynchronous operations and uses concurrency controls to ensure that DHCP management is efficient and non-disruptive.

### Implied user capabilities with MAAS-managed DHCP

MAAS also introduces non-standard capabilities for the bundled DHCP server:

- Dynamic reconfiguration of DHCP settings: MAAS allows users to dynamically reconfigure DHCP settings via a web UI or API without the need for server restarts. This capability is essential for environments where network configurations frequently change, such as in data centers or development labs.

- Integrated IP Address Management (IPAM): MAAS integrates DHCP with IPAM to automatically manage the allocation, tracking, and reclamation of IP addresses across large networks. This integration helps in efficiently using IP resources, reducing conflicts, and ensuring that all devices have appropriate network configurations. This means that user IP configuration takes on a new level of reliability and granularity.

- Automated provisioning of network-dependent services: MAAS automates the provisioning of network-dependent services like DNS, NTP, and PXE boot configurations along with DHCP leases. This means that when MAAS manages a device's DHCP settings, it can also configure these devices to use specific DNS servers or NTP servers, streamlining network setup tasks. This equates to a series of error-prone steps that the user does *not* need to worry about.

- Real-time network bootstrapping: MAAS supports complex network bootstrapping scenarios including the use of next-server (PXE boot server) and bootfile-name parameters which are critical for deploying operating systems in a network environment. This is particularly useful in automated data center management where servers may need to be re-imaged or upgraded without manual intervention. Again, this automates actions that users might normally need to undertake manually.

- Granular access control and security policies: MAAS offers granular control over DHCP options and includes security policies that can be customized for different nodes or subnets. Features like DHCP snooping and dynamic ARP inspection can be integrated into the DHCP process to enhance security and control over the network.

- Advanced monitoring and reporting: MAAS provides advanced monitoring and reporting features for DHCP interactions, meaning that users do not have to be as fluent with command-line network diagnostics. Administrators can view detailed logs of DHCP transactions, monitor the state of DHCP scopes, and track the historical usage of IP addresses, enabling effective troubleshooting and network management.

- Seamless integration with hardware enrollments: MAAS seamlessly integrates DHCP services with the hardware enrollment processes. As new machines are added to the network, MAAS can automatically enroll them, provision them based on predefined templates, and manage their lifecycle directly from the initial DHCP handshake. This eliminates the need for users and administrators to constantly inventory the physical network to keep the headcount up-to-date.

## IP range management and static IP assignments

If an external DHCP server (or relay) is used, static routes would have to be carefully set to avoid issues. It is much easier to simply use the bundled, pre-configured DHCP server with MAAS, which automates handling of static IP addresses. Visual feedback in the MAAS UI makes it obvious which IP addresses are in use and whether or not they are static.

Also, MAAS scales better by allowing administrators to define explicit IP ranges. MAAS centralizes IP management, reducing the need for manual configuration and ensuring that static IPs are applied consistently across your infrastructure. You can allocate static IP addresses from a pool or manually assign them during deployment, or simply let MAAS handle IP assignment from the pool. This capability makes MAAS – and the pre-configured DHCP server shipped with MAAS – the better choice for environments where consistent IP addressing is crucial for server stability and accessibility.

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

## Subnets

A subnet in MAAS is an L3 IP segment (192.168.1.0/24), tied to a VLAN within a fabric. MAAS manages DHCP, DNS, and IP assignments per subnet. Subnets can be managed (MAAS controls IP allocation) or unmanaged (manual configuration).

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

MAAS supports a range of bond parameters:

- **`mac_address`**: Specifies the unique Media Access Control (MAC) address assigned to the network interface, serving as its hardware identifier on the network.

- **`tags`**: Assigns descriptive labels to the interface, facilitating organization, management, or application of specific configurations within MAAS.

- **`vlan`**: Designates the Virtual Local Area Network (VLAN) ID that the interface connects to. If omitted, the interface is treated as not connected to any VLAN.

- **`parents`**: Lists the IDs of interfaces that are combined to form a bonded interface, indicating which physical interfaces are aggregated.

- **`bond_mode`**: Defines the bonding policy determining how the bonded interface manages traffic across its member interfaces.

- **`bond_miimon`**: Sets the frequency (in milliseconds) at which the bond verifies the link status of its member interfaces, with a default of 100 ms.

- **`bond_downdelay`**: Specifies the time (in milliseconds) the bond waits before marking a member interface as inactive after detecting a link failure.

- **`bond_updelay`**: Indicates the time (in milliseconds) the bond waits before marking a member interface as active after detecting a link recovery.

- **`bond_lacp_rate`**: Determines the frequency at which Link Aggregation Control Protocol Data Units (LACPDUs) are sent in 802.3ad mode. Options are "fast" (every 1 second) or "slow" (every 30 seconds), with "slow" as the default.

- **`bond_xmit_hash_policy`**: Specifies the method used to select a slave interface for outgoing traffic in certain bonding modes, influencing load balancing behavior.

- **`bond_num_grat_arp`**: Sets the number of gratuitous ARP messages sent after a failover event to update peer devices about the new MAC address location.

- **`mtu`**: Defines the Maximum Transmission Unit, indicating the largest size (in bytes) of packets that the interface can transmit.

- **`accept_ra`**: Indicates whether the interface accepts IPv6 Router Advertisements, which are used for automatic network configuration.

MAAS also supports many bonding modes:

- **`balance-rr`**: Transmit packets in sequential order from the first
  available slave through the last. This mode provides load balancing
  and fault tolerance.

- **`active-backup`**: Only one slave in the bond is active. A different
  slave becomes active if, and only if, the active slave fails. The
  bond's MAC address is externally visible on only one port (network
  adapter) to avoid confusing the switch.

- **`balance-xor`**: Transmit based on the selected transmit hash policy.
  The default policy is a simple [(source MAC address XOR'd with
  destination MAC address XOR packet type ID) modulo slave count].

- **`broadcast`**: Transmits everything on all slave interfaces. This
  mode provides fault tolerance.

- **`802.3ad`**: IEEE 802.3ad dynamic link aggregation. Creates
  aggregation groups that share the same speed and duplex settings.
  Uses all slaves in the active aggregator according to the 802.3ad
  specification.

- **`balance-tlb`**: Adaptive transmit load balancing: channel bonding
  that does not require any special switch support.

- ``balance-alb``: Adaptive load balancing: includes balance-tlb plus
  receive load balancing (rlb) for IPV4 traffic, and does not require
  any special switch support. The receive load balancing is achieved by
  ARP negotiation.
  
> *See [Bond two interfaces](https://maas.io/docs/how-to-manage-maas-networks#p-9070-bond-two-interfaces) for how-to instructions.*

