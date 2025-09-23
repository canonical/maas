MAAS models networking objects in this order: fabric > VLAN > subnet > IP. You will usually create them in that sequence, then attach interfaces to the appropriate VLAN/subnet.

This page shows you how to:

- Create and manage fabrics, VLANS, subnets, and IP ranges (CRUD, CLI-first).
- Configure and maintain interfaces (physical, VLAN interfaces, bonds, bridges).
- Reserve IP addresses and ranges.
- Enable network discovery and configure additional DNS servers.

> For deeper concepts, see [About MAAS Networking](https://canonical.com/maas/docs/about-maas-networking).

---

## Cheat sheet: Set variables once, then CRUD by object

Paste once; edit for your environment:

```bash
# set your variables (edit these)
PROFILE=admin
FABRIC_NAME=fabric-1
FABRIC_ID=1                  # Optional; you can use FABRIC_NAME instead
VLAN_NAME=prod
VLAN_ID=100                  # Use 0 for untagged
SYSTEM_ID=abcd12
INTERFACE_ID=3
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

### Fabrics — CLI

```bash
# create
maas $PROFILE fabrics create name=$FABRIC_NAME

# read
maas $PROFILE fabrics read

# update (rename)
maas $PROFILE fabric update $FABRIC_NAME name=fabric-prod

# delete
maas $PROFILE fabric delete $FABRIC_NAME
```

### Fabrics — UI

Create / Read / Update / Delete
- Create: *Networking* > *Fabrics* > *Add Fabric* > *Name* > *Add*
- Read: *Networking* > *Fabrics* (table lists all)
- Rename: *Networking* > *Fabrics* > *(Fabric)* > *Edit* > *Name* > *Save*
- Delete: *Networking* > *Fabrics* > *(Fabric)* > *Delete* > *Confirm*

---

### VLANs — CLI

```bash
# create (by fabric name)
maas $PROFILE vlans create $FABRIC_NAME name=$VLAN_NAME vid=$VLAN_ID

# read VLANS in a fabric
maas $PROFILE vlans read $FABRIC_NAME

# update (toggle DHCP or MTU)
maas $PROFILE vlan update $FABRIC_NAME $VLAN_ID dhcp_on=true mtu=9000

# untagged VLAN (vid=0) example: enable DHCP and set primary rack
maas $PROFILE vlan update $FABRIC_NAME 0 dhcp_on=true primary_rack=<rack-name>

# delete
maas $PROFILE vlan delete $FABRIC_NAME $VLAN_ID
```

### VLANs — UI

Create / Read / Update / Delete
- Create: *Networking* > *Fabrics* > *(Fabric)* > *Add VLAN* > *Name, VID (use 0 for Untagged)* > *Add*
- Read: *Networking* > *Fabrics* > *(Fabric)* (VLANs tab lists all)
- Update (DHCP/MTU/Primary rack): *Networking* > *Fabrics* > *(Fabric)* > *(VLAN)* > *Edit* > *Toggle DHCP, set MTU, Primary rack* > *Save*
- Delete: *Networking* > *Fabrics* > *(Fabric)* > *(VLAN)* > *Delete* > *Confirm*

Untagged VLAN (VID=0)
- *Networking* > *Fabrics* > *(Fabric)* > *VLAN “Untagged (0)”* > *Edit* > *Enable DHCP, set Primary rack* > *Save*

## Manage subnets

Subnets live inside VLANs. This is where you set gateways, define ranges, and decide whether MAAS manages IP allocation.

Managed vs unmanaged (MAAS behavior)
- Managed subnet: MAAS manages IP assignments for the entire CIDR, except user-reserved ranges. “Reserved” = excluded from MAAS assignment.
- Unmanaged subnet: MAAS does not manage the whole CIDR. You can still create Reserved ranges; “Reserved” = usable by MAAS. MAAS will allocate only from those Reserved ranges.

### Subnets — UI

- Create: *Networking* > *Subnets* > *Add Subnet* > *CIDR, VLAN (pick from this Fabric), Gateway (optional)* > *Add*
- Read: *Networking* > *Subnets* (table)* > *click subnet for details
- Enable/Disable Managed: *Networking* > *Subnets* > *(Subnet)* > *Edit* > *Managed allocation (On/Off)* > *Save*
- Additional DNS Servers: *Networking* > *Subnets* > *(Subnet)* > *Edit* > *DNS Servers* > *Save*
- Delete: *Networking* > *Subnets* > *(Subnet)* > *Delete* > *Confirm*

Static Routes
- *Networking* > *Subnets* > *(Subnet)* > *Static Routes* > *Add* > *Source, Destination, Gateway (optional Metric)* > *Save*

### Subnets — CLI

```bash
# create (attach to VLAN; set a gateway)
maas $PROFILE subnets create cidr=$SUBNET_CIDR vlan=$VLAN_ID gateway_ip=$GATEWAY_IP

# read (all / one)
maas $PROFILE subnets read
maas $PROFILE subnet read $SUBNET_ID

# update: Managed On/Off
maas $PROFILE subnet update $SUBNET_CIDR managed=true
maas $PROFILE subnet update $SUBNET_CIDR managed=false

# update: Additional DNS servers (MAAS injects itself automatically)
maas $PROFILE subnet update $SUBNET_CIDR dns_servers=$DNS_SERVER_IPS

# delete
maas $PROFILE subnet delete $SUBNET_ID
```

## Manage IP addresses

Reserve single IPs or ranges to control allocation.

### IP Addresses — UI

- Reserve a Single IP: *Networking* > *Subnets* > *(Subnet)* > *Reserved Ranges* > *Reserve IP* > *Enter IP* > *Reserve*
- Dynamic Range (DHCP Pool): *Networking* > *Subnets* > *(Subnet)* > *Reserved Ranges* > *Reserve Range* > *Type: Dynamic* > *Start/End* > *Reserve*
- Reserved Static Range: *Networking* > *Subnets* > *(Subnet)* > *Reserved Ranges* > *Reserve Range* > *Type: Reserved* > *Start/End* > *Reserve*
- Edit/Delete a Range: *Networking* > *Subnets* > *(Subnet)* > *Reserved Ranges* > *(Range)* > *Edit/Delete*

### IP addresses — CLI

```bash
# reserve a single IP
maas $PROFILE ipaddresses reserve ip=$IP_STATIC_SINGLE

# dynamic range (DHCP pool)
maas $PROFILE ipranges create type=dynamic subnet=$SUBNET_CIDR start_ip=$IP_DYNAMIC_RANGE_LOW end_ip=$IP_DYNAMIC_RANGE_HIGH

# reserved static range
maas $PROFILE ipranges create type=reserved subnet=$SUBNET_CIDR start_ip=$IP_STATIC_RANGE_LOW end_ip=$IP_STATIC_RANGE_HIGH
```

## Manage interfaces (on a machine)

Interfaces determine how machines connect to subnets. MAAS supports physical, VLAN interface (on a parent NIC), bond, and bridge. Most changes require the machine to be **Ready** or **Broken**.

### Interfaces — UI

Find the machine first: *Machines* > *(Machine)* > *Network tab*

Create / Link / Update / Delete
- Create VLAN interface: *Network* > *Add Interface* > *VLAN* > *Parent: (NIC)* > *VLAN: (Select)* > *Create*
- Create bond: *Network* > *Add Interface* > *Bond* > *Select parents* > *Mode (e.g., 802.3ad)* > *Create*
- Create bridge: *Network* > *Add Interface* > *Bridge* > *Parent: (NIC or VLAN)* > *Create*
- Link to subnet (Static/DHCP): *Network* > *(Interface)* > *Edit* > *IPv4* > *Mode: Static or Auto (DHCP)* > *Subnet (and IP if static)* > *Save*
- Unlink/disconnect: *Network* > *(Interface)* > *Edit* > *Remove subnet / disconnect* > *Save*
- Delete interface: *Network* > *(Interface)* > *Delete* > *Confirm*
- Change MAC/Other props: *Network* > *(Interface)* > *Edit* > *Save*  
  *(Note: Most edits require the machine to be **Ready** or **Broken**, not **Deployed**.)*

### Interfaces — CLI

```bash
# read / update / delete
maas $PROFILE interfaces read $SYSTEM_ID
maas $PROFILE interface read $SYSTEM_ID $INTERFACE_ID
maas $PROFILE interface update $SYSTEM_ID $INTERFACE_ID key=value...
maas $PROFILE interface delete $SYSTEM_ID $INTERFACE_ID

# link / unlink / disconnect
maas $PROFILE interface link-subnet $SYSTEM_ID $INTERFACE_ID mode=STATIC subnet=$SUBNET_ID ip_address=10.0.0.101
maas $PROFILE interface unlink-subnet $SYSTEM_ID $INTERFACE_ID
maas $PROFILE interface disconnect $SYSTEM_ID $INTERFACE_ID
```

Common types
- Physical: Detected during commissioning.
- VLAN interface: Virtual interface tied to a parent NIC + VLAN ID.
- Bond: Group NICs for redundancy/throughput (e.g., 802.3ad).
- Bridge: Share a NIC with VMs/containers or implement L2 connectivity.

See the [Interface reference](https://canonical.com/maas/docs/interface) for full options.

## Manage routes

Use static routes for custom pathing between subnets.

### Routes — UI

- Default gateway (subnet level): *Networking* > *Subnets* > *(Subnet)* > *Edit* > *Gateway IP* > *Save*
- Per-subnet static route: *Networking* > *Subnets* > *(Subnet)* > *Static Routes* > *Add* > *Save*

### Routes — CLI

```bash
maas $PROFILE static-routes create source=$SUBNET_CIDR destination=10.10.0.0/16 gateway_ip=$GATEWAY_IP
maas $PROFILE subnet update $SUBNET_CIDR gateway_ip=$GATEWAY_IP
```

## Tag interfaces

Tags help classify Interfaces for automation (e.g., `uplink`, `pxe`).

### Tags — UI

- Add tag: *Machines* > *(Machine)* > *Network* > *(Interface)* > *Edit* > *Tags* > *Add* > *Save*
- Remove tag: *Machines* > *(Machine)* > *Network* > *(Interface)* > *Edit* > *Tags* > *Remove* > *Save*

### Tags — CLI

```bash
maas $PROFILE interface add-tag $SYSTEM_ID $INTERFACE_ID tag=my-tag
maas $PROFILE interface remove-tag $SYSTEM_ID $INTERFACE_ID tag=my-tag
```

## Manage network discovery

Use discovery to detect devices on connected subnets.

### Discovery — UI

Global & per-subnet
- Enable/disable globally: *Networking* > *Network Discovery* > *Configuration* > *Enabled/Disabled* > *Save*
- Per-subnet active discovery: *Networking* > *Subnets* > *(Subnet)* > *Edit* > *Active Discovery (On/Off)* > *Save*
- Scan specific subnets (if available in your version): *Networking* > *Network Discovery* > *Subnet Mapping* > *Select Subnets* > *Save*
- Clear all discoveries: *Networking* > *Network Discovery* > *Clear All Discoveries* > *Confirm*

### Discovery — CLI

```bash
# global on/off
maas $PROFILE maas set-config name=network_discovery value=enabled
maas $PROFILE maas set-config name=network_discovery value=disabled

# per-subnet active discovery
maas $PROFILE subnet update $SUBNET_CIDR active_discovery=true
maas $PROFILE subnet update $SUBNET_CIDR active_discovery=false

# clear all discoveries
maas $PROFILE discoveries clear all=true
```

> Learn more: [Discovery](https://canonical.com/maas/docs/discovery)

## Verify your changes

### Verify — UI

- Fabrics/VLANs: *Networking* > *Fabrics* > *(Fabric)*
- Subnets/Ranges/Routes: *Networking* > *Subnets* > *(Subnet)*
- Interfaces on machines: *Machines* > *(Machine)* > *Network*
- Discovery results: *Networking* > *Network Discovery* > *Results*

### Verify — CLI

- Confirm CLI reads show expected fabrics, VLANS, subnets, ranges, and interfaces.
- On deployed machines, verify connectivity with:
  ```bash
  ip addr
  ip route
  ping 8.8.8.8 -c 3
  ```

## Next steps

- About MAAS Networking: https://canonical.com/maas/docs/about-maas-networking
- Discovery: https://canonical.com/maas/docs/discovery
