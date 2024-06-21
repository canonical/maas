> *Errors or typos? Topics missing? Hard to read? <a href="https://docs.google.com/forms/d/e/1FAIpQLScIt3ffetkaKW3gDv6FDk7CfUTNYP_HGmqQotSTtj2htKkVBw/viewform?usp=pp_url&entry.1739714854=https://maas.io/docs/the-role-of-maas-networks" target = "_blank">Let us know.</a>*

MAAS networking combines unique and standard networking concepts applied distinctively to MAAS. 
 
## PXE booting

PXE (Preboot eXecution Environment) lets machines boot through a Network Interface Card (NIC). It uses a small hardware footprint for simplicity and efficiency. Key components include a universal network device interface, UDP/IP stack, DHCP module, and TFTP module. As configured for MAAS, TFTP uses larger block and window sizes to boost throughput. PXE relies heavily on DHCP for IP assignment and TFTP for transferring boot programs and files.

## Power drivers

Embedded in MAAS, power drivers interface with a machine's BMC (Baseboard Management Controller) for remote power cycling. Different machines and BMCs require specific drivers, though standard IPMI drivers are often compatible. IPMI connects directly to the hardware for various management functions, primarily used in MAAS for power cycling.

## Proxies

Proxies act as intermediaries in network transactions, offering benefits such as privacy, security, and load balancing. MAAS includes an internal HTTP caching proxy for all managed subnet hosts and allows for external proxy configuration.

## RPC

Remote Procedure Call (RPC) in MAAS facilitates communication between region and rack controllers, crucial for transferring PXE configurations.

## Network discovery

MAAS listens to the network, reporting discovered devices on IPv4 subnets, including those advertising hostnames through DNS. You can add these device to MAAS as desired.

## Subnets

Subnets in MAAS, both IPv4 and IPv6, are layer 3 networks defined by a network address and mask length. They require minimal configuration, primarily names and descriptions. Subnets allow for several management options, such as DHCP leases and static address assignments.

## VLANs

Virtual LANs (VLANs) separate networks that use the same physical infrastructure. MAAS supports both tagged and untagged VLANs on managed switches. Each fabric in MAAS has a default VLAN.

## IPv6

IPv6 support in MAAS mirrors IPv4, requiring a static address range for rack controller interfaces. MAAS statically configures default IPv6 routes and does not rely on RAs. It can manage DHCP and DNS for IPv6, although it is optional.

## Availability zones

Availability zones in MAAS aid in fault tolerance, service performance, and power management. They can represent different physical or network areas, helping to assign resources efficiently and manage system workload and energy consumption.

## Subnet management

MAAS can manage subnets to handle IP address allocation, including DHCP leases and static addresses. Managed subnets lease addresses from reserved ranges, while unmanaged subnets only allocate from these ranges. IP address tracking is available for both managed and unmanaged subnets.