MAAS provisions bare metal servers and virtual machines. It creates a single point of control that removes a lot of the logistical errors associated with manual hookup, configuration, and discovery. MAAS also makes it easy to run your racks -- or even your whole datacenter -- remotely. MAAS networking makes all this possible.

## Fabrics

In MAAS, a fabric is the highest-level grouping of network topology that reflects the Layer 2 physical infrastructure — essentially, a single Ethernet broadcast domain, such as what exists behind a physical switch or set of interconnected switches that share MAC-layer reachability.

Each fabric represents a distinct, isolated physical network segment, and cannot overlap with other fabrics. Within each fabric:

- You define VLANs (Virtual LANs), which segment traffic logically.
- Each VLAN exists within one and only one fabric.
- Each subnet is associated with a VLAN, and therefore with a fabric indirectly.
- All network interfaces that belong to the same Layer 2 domain (e.g., a single unmanaged switch or bonded switches) should be placed in the same fabric.

A fabric models the real-world wiring or switching environment of your data center, helping MAAS understand and manage network isolation, provisioning domains, and failover behavior more precisely.

Key technical characteristics of a fabric:

- Each rack controller interface in MAAS must be mapped to a VLAN, which in turn maps to a fabric.
- MAAS assumes no Layer 2 connectivity across fabrics. If two machines need to communicate at Layer 2, they must be in the same fabric.
- MAAS uses fabrics to determine DHCP scope boundaries, IP assignment separation, and PXE boot reachability.
- MAAS can automatically create new fabrics if it detects Layer 2 segmentation during interface discovery.
- While VLANs group logical traffic, fabrics group physical topology.

For example, if you have:

- Two physical switches that are not connected,
- Where each switch serves a group of machines
- With no VLAN trunking or Layer 2 bridging between them,

Then MAAS should treat these as two distinct fabrics, even if their IP subnets appear similar, because there is no Layer 2 path between them.

## VLAN (Virtual LAN)

In MAAS, a VLAN (Virtual LAN) is a logical network layer that enables you to segment traffic within a single fabric. VLANs allow different network segments to coexist on the same physical infrastructure while maintaining traffic separation.

Each VLAN in MAAS is uniquely defined by the fabric it belongs to, a numeric VLAN ID (VID) ranging from 0 to 4095, and an optional descriptive name that makes it easier to identify and manage.

VLANs in MAAS can be either tagged or untagged. A tagged VLAN includes an embedded identifier in the Ethernet frame (using 802.1Q tagging), which allows multiple VLANs to traverse a single physical interface—typically required for trunk ports. An untagged VLAN, by contrast, carries traffic without any VLAN tags and usually corresponds to the default VLAN on an access port .

MAAS uses VLANs to organize and scope subnets within a fabric. When you create a subnet in MAAS, you must associate it with a specific VLAN. This association determines which machines or interfaces can access that subnet. VLANs also control how services such as DHCP, DNS, PXE booting, and metadata delivery are applied within the network, helping administrators isolate different functions or environments.

For example, you might create VLAN 100 within fabric-0 to handle production systems, while VLAN 200 on the same fabric could be reserved for testing. In more advanced scenarios, you could configure a trunk port that carries both VLANs using tagging, allowing a single interface to manage traffic for both networks while keeping them logically isolated.

## Subnets

In MAAS, a subnet is a Layer 3 network segment defined by a network address and a subnet mask length, typically expressed in CIDR notation (e.g., 192.168.10.0/24). Subnets are essential for organizing IP address allocation, managing DHCP services, and controlling network access within a specific VLAN and fabric.
>>>>>>> 768fad1d7 (major update to explanations of network components and services)

Each subnet in MAAS is associated with a particular VLAN, ensuring that IP address management and network services are correctly scoped within the network topology. When creating a subnet, administrators specify parameters such as the CIDR block, gateway IP, and DNS settings. MAAS supports both IPv4 and IPv6 subnets, allowing for flexible network configurations .

MAAS distinguishes between managed and unmanaged subnets. In a managed subnet, MAAS handles all aspects of IP address allocation, including leasing addresses for DHCP from a reserved dynamic IP range and assigning static addresses outside of this range. Conversely, in an unmanaged subnet, MAAS does not control IP address allocation, and administrators must manage IP assignments manually .

Subnets also support the definition of reserved IP ranges. These ranges can be designated for specific purposes, such as infrastructure devices, external DHCP servers, or other services. Additionally, MAAS allows for the configuration of static routes between subnets, facilitating communication across different network segments .

By organizing networks into subnets, MAAS provides a structured approach to IP address management, ensuring efficient allocation and control over network resources.

## Spaces

In MAAS, a space is a logical grouping of subnets that facilitates network traffic segmentation at the Layer 3 (network) level. Spaces allow administrators to define and control how services and machines communicate within the network infrastructure.

Each space in MAAS is created independently and can encompass one or more subnets. These subnets are associated with specific VLANs and fabrics, but the space itself provides an abstraction that enables grouping based on desired communication patterns or administrative domains. This design allows for flexible network configurations without being tightly coupled to the underlying physical topology .

Spaces are particularly useful when deploying applications with Juju, as they can be used to bind application endpoints to specific network segments. This binding ensures that application traffic flows through designated subnets, enhancing security, performance, and compliance. For instance, an administrator might create separate spaces for public-facing services and internal databases, ensuring that sensitive data remains isolated from external networks .

It's important to note that while spaces group subnets for logical organization, they do not inherently enforce isolation. Proper network policies and configurations must be applied to achieve the desired level of separation between spaces.

## The role of spaces and fabrics

MAAS allows you to logically group networks using spaces and fabrics. VLANs always exist in some fabric and can optionally join a space. If you want to create a group of specific VLANs, create a new fabric and associate it with the VLANs. If you want to create a group of subnets, first make sure that the subnets can be independently selected by fabric id and VLAN id combinations and then create a new space and associate it with the relevant combinations.

## Interfaces

In MAAS, a network interface represents the connection point between a machine and its network, encompassing both physical and virtual configurations. These interfaces are pivotal in defining how a machine communicates within the network topology managed by MAAS.​

Each interface in MAAS is associated with a specific VLAN, which in turn is linked to a fabric. This hierarchical relationship ensures that network configurations are organized and that machines are correctly integrated into the desired network segments.​

Interfaces can be of various types:​

- Physical interfaces: These correspond to the actual Network Interface Cards (NICs) present on a machine. MAAS typically detects these during the commissioning process.​

- VLAN interfaces: Virtual interfaces that allow a physical NIC to handle traffic for multiple VLANs, facilitating network segmentation and multi-tenancy.​

- Bond interfaces: These aggregate multiple physical interfaces to provide redundancy or increased throughput.​

- Bridge interfaces: Used to connect multiple network segments at the data link layer, often employed in virtualization scenarios.​

MAAS provides tools to create, view, and manage these interfaces through both its Web UI and CLI. For instance, to create a physical interface via the CLI, one might use:​

```bash
maas $PROFILE interfaces create-physical $SYSTEM_ID name=eth0 mac_address=00:16:3e:01:2a:3b enabled=true
```

This command specifies the interface's name and MAC address, and enables it. ​

It's important to note that modifications to interfaces are restricted when a machine is in a deployed state. To make changes, the machine should be set to a "Ready" or "Broken" state. ​

### Bridges

Bridges aggregate interface traffic at the cost of complexity. MAAS offers centralized bridge creation and management directly from the UI or CLI. MAAS bridges are automatically integrated with VLANs and bonds, making it easier to reduce redundancy, avoid mistakes, and improve performance.

Note that while Netplan provides a simpler way to configure bridges manually (through YAML files), MAAS-managed bridges don't require manual configuration. In some cases, though, such as integrating MAAS-managed systems into external environments, Netplan is the right answer.

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

## Network discovery

MAAS passively monitors ARP traffic to detect devices on the network. It records IP and MAC addresses, tracking changes over time. If available, it also captures hostnames via mDNS. Discovery runs periodically and updates a dashboard with detected devices. This feature can be enabled or disabled.

## IPMI networking

Machines have a baseboard management controller (BMC), a separate CPU dedicated to managing and monitoring device health. The BMC can power-cycle the device, so MAAS uses the BMC to turn machines on or off, or reboot them via PXE.  MAAS can't provision a machine until it's enabled to network boot, that is, until the firmware is set to boot first from device's Network Interface Card (NIC).

## DNS management in MAAS

In MAAS, DNS (Domain Name System) management is integral to the orchestration of network services, ensuring that machines can resolve hostnames to IP addresses within the managed infrastructure.

### Integrated DNS

MAAS includes an integrated DNS service that automatically manages DNS records for machines under its control. When a machine is commissioned or deployed, MAAS creates corresponding A (IPv4) and AAAA (IPv6) records, facilitating seamless name resolution within the network. This automation simplifies network management and reduces the potential for configuration errors.

### Upstream DNS configuration

For domains not managed by MAAS, administrators can configure upstream DNS servers. This setup allows MAAS to forward DNS queries for external domains to specified upstream servers, ensuring comprehensive name resolution capabilities. 

### DNS records management

MAAS provides flexibility in managing DNS records:

- Automatic record creation: As mentioned, MAAS automatically generates DNS records for machines it manages. 

- Manual record management: Administrators can manually create, modify, or delete DNS records using the MAAS CLI. This includes adding custom A, AAAA, CNAME, MX, and SRV records as needed. 

### Integration with external DNS

In environments where an external DNS is already in place, MAAS can coexist by managing a specific subdomain. For instance, MAAS can be configured to handle the `maas.example.com` subdomain, while the primary DNS service manages the broader `example.com` domain. This approach allows for seamless integration without disrupting existing DNS infrastructures.

### Best practices

- Leverage MAAS's integrated DNS: Utilizing MAAS's built-in DNS service ensures tight integration with machine lifecycle events, promoting consistency and reducing administrative overhead.

- Configure upstream DNS thoughtfully: Ensure that upstream DNS servers are correctly specified to facilitate external domain resolution without conflicts. 

- Maintain clear domain boundaries: When integrating with external DNS services, clearly delineate the domains managed by MAAS to prevent overlaps and ensure reliable name resolution.

By adhering to these practices, administrators can ensure robust and efficient DNS management within their MAAS-managed environments.

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

Because MAAS needs to configure DHCP with these options, the bundled MAAS DHCP server should be used. You can use external DHCP servers or relays, but it is not recommended.  This bundled server redefines DHCP management by integrating advanced features:

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

- Integrated IP Address Management (IPAM): MAAS integrates DHCP with IPAM to automatically manage the allocation, tracking, and reclamation of IP addresses across large networks. This integration helps in efficiently using IP resources, reducing conflicts, and ensuring that all devices have appropriate network configurations.  This means that user IP configuration takes on a new level of reliability and granularity.

- Automated provisioning of network-dependent services: MAAS automates the provisioning of network-dependent services like DNS, NTP, and PXE boot configurations along with DHCP leases. This means that when MAAS manages a device's DHCP settings, it can also configure these devices to use specific DNS servers or NTP servers, streamlining network setup tasks.  This equates to a series of error-prone steps that the user does *not* need to worry about.

- Real-time network bootstrapping: MAAS supports complex network bootstrapping scenarios including the use of next-server (PXE boot server) and bootfile-name parameters which are critical for deploying operating systems in a network environment. This is particularly useful in automated data center management where servers may need to be re-imaged or upgraded without manual intervention.  Again, this automates actions that users might normally need to undertake manually.

- Granular access control and security policies: MAAS offers granular control over DHCP options and includes security policies that can be customized for different nodes or subnets. Features like DHCP snooping and dynamic ARP inspection can be integrated into the DHCP process to enhance security and control over the network.

- Advanced monitoring and reporting: MAAS provides advanced monitoring and reporting features for DHCP interactions, meaning that users do not have to be as fluent with command-line network diagnostics.  Administrators can view detailed logs of DHCP transactions, monitor the state of DHCP scopes, and track the historical usage of IP addresses, enabling effective troubleshooting and network management.

- Seamless integration with hardware enrollments: MAAS seamlessly integrates DHCP services with the hardware enrollment processes. As new machines are added to the network, MAAS can automatically enroll them, provision them based on predefined templates, and manage their lifecycle directly from the initial DHCP handshake.  This eliminates the need for users and administrators to constantly inventory the physical network to keep the headcount up-to-date.

### Replacing DHCP snippets 

With the deprecation of DHCP snippets in MAAS 3.6 and later, administrators need to adopt alternative methods to achieve similar DHCP configurations. Here are some general approaches to replicate common functionalities previously handled by DHCP snippets.

#### Reserving IP addresses for specific hosts

Previously, DHCP snippets allowed for reserving IP addresses within a DHCP pool for specific hosts. Now, MAAS provides built-in mechanisms to reserve IPs without relying on snippets. This can be managed through the MAAS UI or CLI by assigning static IP addresses to machines or reserving IPs within a subnet. ​

#### Configuring DHCP options (e.g., PXE boot settings)

Custom DHCP options, such as setting PXE boot parameters, were often configured using snippets. In the absence of snippets, these settings can be managed through MAAS's DHCP configuration interface. For instance, to set PXE boot options, administrators can specify the necessary parameters directly in the DHCP configuration for the relevant subnet or VLAN. ​

#### Managing DHCP relay configurations

For environments utilizing DHCP relays, MAAS allows the configuration of relay settings without the need for snippets. Administrators can set up DHCP relay by specifying the relay VLAN and target VLAN within the MAAS interface, ensuring proper DHCP traffic forwarding. ​

#### Handling advanced DHCP configurations

Complex DHCP configurations that previously relied on snippets may require alternative solutions. While MAAS's built-in features cover many standard use cases, certain advanced configurations might necessitate external DHCP management or custom integrations. In such cases, administrators should evaluate the specific requirements and consider leveraging external tools or scripts to achieve the desired functionality.

## IP range management and static IP assignments in MAAS

In MAAS, effective IP address management is achieved through the strategic use of IP ranges within each subnet. These ranges dictate how IP addresses are allocated to machines during various stages such as commissioning, deployment, and regular operation. 

### Types of IP ranges in MAAS

1. Dynamic ranges: These are pools of IP addresses that MAAS uses for automatic assignment during machine commissioning and deployment. When a machine is set to use DHCP, it receives an IP from this dynamic range. This setup is ideal for environments where manual IP management is impractical.

2. Reserved ranges: Reserved ranges are blocks of IP addresses that MAAS will not assign automatically. These are typically used for infrastructure devices, external DHCP servers, or other critical systems requiring static IPs. In managed subnets, MAAS avoids assigning IPs within these ranges, ensuring no conflicts with manually configured devices. 

3. Reserved dynamic ranges: These are specific to MAAS-managed DHCP services. They are used during the enlistment and commissioning phases to provide temporary IP addresses to machines. Once a machine is deployed, it can be assigned a static IP outside of this range.

### Static IP assignments

MAAS offers flexibility in assigning static IP addresses:

- Manual assignment: Administrators can manually assign a static IP to a machine's interface, ensuring it remains consistent across reboots and deployments.

- Auto assignment: MAAS can automatically assign a static IP from a predefined pool, simplifying the provisioning process while maintaining IP consistency.

It's important to note that when using an external DHCP server, MAAS cannot automatically reserve or manage IP addresses. In such scenarios, careful coordination is required to prevent IP conflicts. MAAS recommends using its integrated DHCP server for seamless IP management. 

### Best practices

- Define clear IP ranges: Establish distinct dynamic and reserved ranges within each subnet to prevent overlaps and conflicts.

- Use MAAS DHCP services: Leveraging MAAS's built-in DHCP server simplifies IP management and reduces the risk of misconfigurations.

- Monitor IP allocations: Regularly review IP assignments through the MAAS UI to ensure efficient utilization and identify potential issues.

- Coordinate with external services: If integrating with external DHCP or DNS services, ensure proper configuration to maintain network stability.

By adhering to these practices, administrators can ensure a robust and conflict-free IP management strategy within MAAS.

## NTP

In a MAAS-managed environment, time synchronization via NTP is centralized, making it easier to ensure that all machines have consistent and accurate time settings. While external NTP servers can be used, MAAS allows you to configure NTP settings during the deployment process, ensuring that machines automatically sync with the correct time sources.

MAAS uses Chrony to synchronize time across region and rack controllers, to coordinate operations and maintain accurate logs. Rack controllers provide NTP settings via DHCP, so deployed machines automatically receive the right time. This reduces the need for manual configuration and helps avoid common issues related to time drift, which can cause problems with logging, authentication, and other time-sensitive processes. By handling NTP settings centrally, MAAS ensures that time synchronization is reliable across all managed systems.


## Other customizations

There are a few additional MAAS-centric network customization options.

### Network validation

MAAS can validate connectivity and speed on network connections prior to deployment.

### Static routes

MAAS can define static routes globally to avoid configuration drift, ensure consistency, and create better control over traffic flow. Static routes are particularly valuable in environments requiring specific traffic paths for security, redundancy, or performance.

### Multi-NIC configurations

MAAS automatically detects and configures all available interfaces, including multi-NIC machines.

### Gateways

MAAS centralizes gateway configuration across all connected machines. You can modify gateway settings easily, which is especially useful in environments where gateway configurations need to be updated regularly for many machines.
