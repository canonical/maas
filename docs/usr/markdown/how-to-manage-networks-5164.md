MAAS models networking in this order: Fabric > VLAN > Subnet > IP. In most deployments you will create and configure them in that sequence, and then attach interfaces on machines to the appropriate VLAN/subnet.

This page shows you how to:

- Create and manage fabrics, VLANs, subnets, and IP ranges.
- Configure and maintain interfaces (physical, VLAN interfaces, bonds, bridges).
- Reserve IP addresses and ranges.
- Enable network discovery and configure additional DNS servers.

> For deeper concepts, see [About MAAS networking](https://canonical.com/maas/docs/about-maas-networking).


## Quick setup variables (edit once)

Paste these into your shell and adjust the values for your environment. They’re used throughout the CLI examples below.

```bash
PROFILE=admin
FABRIC_NAME=fabric-1          # Or use a custom name
FABRIC_ID=1                   # Optional; name also works in most commands
VLAN_NAME=prod
VLAN_ID=100                   # Use 0 for untagged VLAN
SYSTEM_ID=abcd12              # The machine's system id
INTERFACE_ID=3                # Interface id on that machine
SUBNET_CIDR=10.0.0.0/24
SUBNET_ID=42
GATEWAY_IP=10.0.0.1
DNS_SERVER_IPS=1.1.1.1,8.8.8.8
IP_STATIC_SINGLE=10.0.0.50
IP_DYNAMIC_RANGE_LOW=10.0.0.100
IP_DYNAMIC_RANGE_HIGH=10.0.0.199
IP_STATIC_RANGE_LOW=10.0.0.200
IP_STATIC_RANGE_HIGH=10.0.0.249
```


## Fabrics

What: A fabric groups VLANs that share L2 connectivity inside MAAS.

### Do it in the UI
Go to Networking > Fabrics to perform fabric-related actions:

- Create: *Add Fabric* > *Name* > *Add*
- Read: Fabrics table lists all
- Update: *(Fabric)* > *Edit* > change *Name* > *Save*
- Delete: *(Fabric)* > *Delete* > *Confirm*

### Do it with the CLI
```bash
# Create
maas $PROFILE fabrics create name=$FABRIC_NAME

# Read
maas $PROFILE fabrics read

# Update (rename)
maas $PROFILE fabric update $FABRIC_NAME name=fabric-prod

# Delete
maas $PROFILE fabric delete $FABRIC_NAME
```


## VLANs

What: Layer‑2 segments inside a fabric; VID 0 denotes the untagged VLAN.

### Do it in the UI
Go to Networking > Fabrics > (Fabric) for VLAN actions:

- Create: *Add VLAN* > set *Name* and *VID* (0 = Untagged) > *Add*
- Read: *(Fabric)* shows the VLANs list
- Update (e.g., DHCP/MTU/Primary rack): *(VLAN)* > *Edit* > toggle/adjust > *Save*
- Delete: *(VLAN)* > *Delete* > *Confirm*
- Untagged VLAN (VID=0): *(VLAN “Untagged (0)”)* > *Edit* > enable DHCP and set Primary rack > *Save*

### Do it with the CLI
```bash
# Create (by fabric name)
maas $PROFILE vlans create $FABRIC_NAME name=$VLAN_NAME vid=$VLAN_ID

# Read VLANs in a fabric
maas $PROFILE vlans read $FABRIC_NAME

# Update VLAN options (examples)
maas $PROFILE vlan update $FABRIC_NAME $VLAN_ID dhcp_on=true mtu=9000

# Untagged VLAN (vid=0): enable DHCP and set primary rack
maas $PROFILE vlan update $FABRIC_NAME 0 dhcp_on=true primary_rack=<rack-name>

# Delete
maas $PROFILE vlan delete $FABRIC_NAME $VLAN_ID
```


## Subnets

What: L3 networks that live inside a VLAN. Here you set gateways, define ranges, and decide whether MAAS manages IP allocation.

### Managed vs. unmanaged (what MAAS actually does)

- Managed subnet: MAAS manages IP assignment for the entire CIDR except user‑reserved ranges. “Reserved” means “exclude from MAAS assignment.”
- Unmanaged subnet: MAAS does not manage the entire CIDR. You may still create Reserved ranges; in this case “Reserved” means “MAAS may allocate only from these ranges.”

### Do it in the UI
Go to Networking > Subnets for subnet actions:

- Create: *Add Subnet* > choose *CIDR*, *VLAN* (from a fabric), optional *Gateway* > *Add*
- Read: Subnets table shows all > click a subnet for details
- Enable/Disable “Managed”: *(Subnet)* > *Edit* > *Managed allocation* On/Off > *Save*
- Additional DNS Servers: *(Subnet)* > *Edit* > *DNS Servers* > *Save*
- Static Routes: *(Subnet)* > *Static Routes* > *Add* > set *Source*, *Destination*, *Gateway*, optional *Metric* > *Save*
- Delete: *(Subnet)* > *Delete* > *Confirm*

### Do it with the CLI
```bash
# Create (attach to VLAN; set a gateway)
maas $PROFILE subnets create cidr=$SUBNET_CIDR vlan=$VLAN_ID gateway_ip=$GATEWAY_IP

# Read (all / one)
maas $PROFILE subnets read
maas $PROFILE subnet read $SUBNET_ID

# Toggle Managed allocation
maas $PROFILE subnet update $SUBNET_CIDR managed=true
maas $PROFILE subnet update $SUBNET_CIDR managed=false

# Configure additional DNS servers (MAAS adds itself automatically)
maas $PROFILE subnet update $SUBNET_CIDR dns_servers=$DNS_SERVER_IPS

# Add a per‑subnet static route
maas $PROFILE static-routes create source=$SUBNET_CIDR destination=10.10.0.0/16 gateway_ip=$GATEWAY_IP

# Delete
maas $PROFILE subnet delete $SUBNET_ID
```


## IP addresses and ranges

What: Reserve single IPs or ranges to control allocation behavior.

### Do it in the UI
Go to Networking > Subnets > (Subnet) > Reserved Ranges:

- Single IP: *Reserve IP* > enter address > *Reserve*
- Dynamic range (DHCP pool): *Reserve Range* > Type: *Dynamic* > *Start/End* > *Reserve*
- Reserved static range: *Reserve Range* > Type: *Reserved* > *Start/End* > *Reserve*
- Edit/Delete a range: click a range > *Edit* / *Delete*

### Do it with the CLI
```bash
# Reserve a single IP address in this subnet’s CIDR
# (This marks the address in MAAS; assignment to a machine happens when you link
# an interface in STATIC mode to this IP.)
maas $PROFILE ipaddresses reserve ip=$IP_STATIC_SINGLE

# Create a dynamic range (DHCP pool)
maas $PROFILE ipranges create type=dynamic subnet=$SUBNET_CIDR   start_ip=$IP_DYNAMIC_RANGE_LOW end_ip=$IP_DYNAMIC_RANGE_HIGH

# Create a reserved static range (excluded from MAAS auto‑assignment on managed subnets;
# used *as the only pool* on unmanaged subnets)
maas $PROFILE ipranges create type=reserved subnet=$SUBNET_CIDR   start_ip=$IP_STATIC_RANGE_LOW end_ip=$IP_STATIC_RANGE_HIGH
```

> Note on single‑IP reservations: the example above reserves the address in MAAS. To give that IP to a specific machine, link the interface in STATIC mode to that IP (see Interfaces > CLI below).


## Interfaces (on a machine)

What: How a machine connects to subnets. MAAS supports physical, VLAN interface (on a parent NIC), bond, and bridge.

> Many interface changes require the machine state to be Ready or Broken (not Deployed). Where a command has a state requirement, it’s noted.

### Do it in the UI
Find the machine first: Machines > (Machine) > Network.

- Create VLAN interface: *Add Interface > VLAN* > select *Parent NIC* & *VLAN* > *Create* (Ready/Broken)
- Create bond: *Add Interface > Bond* > select parents & *Mode* (e.g., *802.3ad*) > *Create* (Ready/Broken)
- Create bridge: *Add Interface > Bridge* > select *Parent* (NIC or VLAN) > *Create* (Ready/Broken)
- Link to subnet (Static/DHCP): *(Interface)* > *Edit* > IPv4 *Mode*: *Static* or *Auto (DHCP)* > choose *Subnet*, and if static, set *IP* > *Save*
- Unlink / disconnect: *(Interface)* > *Edit* > remove subnet / disconnect > *Save* (Ready/Broken)
- Rename / MAC change / other props: *(Interface)* > *Edit* > change values > *Save*
  - *Renaming an interface is allowed even on Deployed machines.*
- Delete interface: *(Interface)* > *Delete* > *Confirm* (Ready/Broken)

### Do it with the CLI
```bash
# Read / inspect
maas $PROFILE interfaces read $SYSTEM_ID
maas $PROFILE interface read $SYSTEM_ID $INTERFACE_ID

# Update (meaningful example): rename an interface  (works on Deployed machines)
maas $PROFILE interface update $SYSTEM_ID $INTERFACE_ID name=public-uplink

# Link in STATIC mode to a specific IP (machine must be Ready/Broken)
maas $PROFILE interface link-subnet $SYSTEM_ID $INTERFACE_ID   mode=STATIC subnet=$SUBNET_ID ip_address=$IP_STATIC_SINGLE

# Link in AUTO (DHCP) mode (machine must be Ready/Broken)
maas $PROFILE interface link-subnet $SYSTEM_ID $INTERFACE_ID   mode=AUTO subnet=$SUBNET_ID

# Unlink / disconnect (machine must be Ready/Broken)
maas $PROFILE interface unlink-subnet $SYSTEM_ID $INTERFACE_ID
maas $PROFILE interface disconnect $SYSTEM_ID $INTERFACE_ID

# Delete the interface (machine must be Ready/Broken)
maas $PROFILE interface delete $SYSTEM_ID $INTERFACE_ID
```

Common types

- Physical: Detected during commissioning.
- VLAN interface: Virtual NIC tied to a parent physical NIC plus a VLAN ID.
- Bond: Group NICs for redundancy/throughput (e.g., 802.3ad).
- Bridge: Share a NIC with VMs/containers or implement L2 connectivity.

See the Interface reference for full options (canonical.com/maas/docs/interface).


## Routes

Use default gateways and static routes to control pathing between subnets.

### Do it in the UI
- Default gateway (per subnet): Networking > Subnets > (Subnet) > Edit > Gateway IP > Save
- Static route (per subnet): Networking > Subnets > (Subnet) > Static Routes > Add > Save

### Do it with the CLI
```bash
# Add a static route on a subnet
maas $PROFILE static-routes create source=$SUBNET_CIDR destination=10.10.0.0/16 gateway_ip=$GATEWAY_IP

# Set default gateway on a subnet
maas $PROFILE subnet update $SUBNET_CIDR gateway_ip=$GATEWAY_IP
```


## Tags (on interfaces)

Tags help classify interfaces for filtering and automation (examples: `uplink`, `pxe`).

### Do it in the UI
- Add tag / Remove tag: Machines > (Machine) > Network > (Interface) > Edit > Tags > Add/Remove > Save

### Do it with the CLI
```bash
maas $PROFILE interface add-tag $SYSTEM_ID $INTERFACE_ID tag=my-tag
maas $PROFILE interface remove-tag $SYSTEM_ID $INTERFACE_ID tag=my-tag
```


## Network discovery

Discovery detects devices on connected subnets (switches, routers, IoT, etc.). You can control it globally and per subnet.

### Do it in the UI
- Global enable/disable: Networking > Network Discovery > Configuration > Enabled/Disabled > Save
- Per‑subnet active discovery: Networking > Subnets > (Subnet) > Edit > Active Discovery (On/Off) > Save
- Scan specific subnets (if available in your version): Networking > Network Discovery > Subnet Mapping > Select Subnets > Save
- Clear all discoveries: Networking > Network Discovery > Clear All Discoveries > Confirm

### Do it with the CLI
```bash
# Global on/off
maas $PROFILE maas set-config name=network_discovery value=enabled
maas $PROFILE maas set-config name=network_discovery value=disabled

# Per‑subnet active discovery
maas $PROFILE subnet update $SUBNET_CIDR active_discovery=true
maas $PROFILE subnet update $SUBNET_CIDR active_discovery=false

# Clear all discoveries
maas $PROFILE discoveries clear all=true
```

> Learn more: canonical.com/maas/docs/discovery


## Verify your changes

### In the UI
- Fabrics/VLANs: Look under the Networking option.
- Subnets/Ranges/Routes: Also under Networking.
- Machine interfaces: Look at the machine's Network tab.
- Discovery results: See Results, under Network Discovery.

### With the CLI
- Check that reads reflect your changes for fabrics, vlans, subnets, ranges, and interfaces.
- On deployed machines, confirm connectivity:
  ```bash
  ip addr
  ip route
  ping -c 3 8.8.8.8
  ```

## Next steps

- Learn [about MAAS netorking](https://canonical.com/maas/docs/about-maas-networking)
- Understand [discovery](https://canonical.com/maas/docs/discovery).
