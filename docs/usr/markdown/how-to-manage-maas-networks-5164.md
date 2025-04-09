MAAS provides pre-configured [networks](https://maas.io/docs/about-maas-networking) for convenience and efficiency.  Reconfigure these networks to suit your environment.

## Manage interfaces 

MAAS gives you detailed control over network interfaces for each machine — including physical NICs, VLANs, bonds, and bridges. These interfaces form the backbone of your deployment topology. Learn how to create, view, and manage them using the MAAS UI and CLI.

### Create an interface 

Interfaces define how a machine connects to your network. You can create physical, VLAN, bond, or bridge interfaces — each with its own use case. Begin with the most basic type: the physical interface.

#### Create a physical interface

A physical interface represents a hardware NIC on the machine. MAAS usually detects these automatically during commissioning. You only need to create one if you are:

- manually re-creating the interface layout
- automating machine configuration post-commissioning
- scripting complex interface setups

If the machine is already deployed, you won’t be able to modify or add physical interfaces. Bring it to a “Ready” or “Broken” state first.

**CLI**
```bash 
maas $PROFILE interfaces create-physical $SYSTEM_ID (key=value)....
```

Use key-value pairs to set interface properties like:

- `name=eth0` – Logical name of the interface
- `mac_address=00:16:3e:01:2a:3b` – Required if not auto-detected
- `enabled=true` – Whether the interface is active

Consult the [CLI reference](https://maas.io/docs/interface#p-23244-create-a-physical-interface) for details on parameters and usage.

#### Create a VLAN interface

You will need VLAN separation for many different purposes:

- Assigning a machine to a specific broadcast domain
- Implementing multi-tenancy or network isolation
- Setting up PXE-booting on a specific VLAN

In MAAS, a VLAN is a virtual interface associated with:

- a parent (usually a physical NIC)
- a VLAN ID (typically between 1 and 4094)
- a fabric (the logical layer in MAAS that manages network topology)

You can create a VLAN interface with a command of the form:

```bash
maas $PROFILE interfaces create-vlan $SYSTEM_ID key=value...
```

This command has two required keys and several optional key-value pairs.

| Key            | Description                                                                 |
|----------------|-----------------------------------------------------------------------------|
| `vlan`         | ID of the VLAN in MAAS to assign this interface to                         |
| `parent`       | ID of the parent interface (usually a physical NIC)                        |
| `name`         | (Optional) name of the new interface                                        |
| `mac_address`  | (Optional) MAC address if you're overriding the default                    |
| `tags`         | (Optional) for internal use or automation                                  |

To find `vlan` and `parent` IDs from the MAAS CLI:

```bash
maas $PROFILE vlans read $FABRIC_ID
maas $PROFILE interfaces read $SYSTEM_ID
```

Note that you *cannot* assign a VLAN directly to a physical interface, though once created, this interface can then be bonded, bridged, or assigned IPs just like a physical NIC.

Consult the [CLI help page](https://maas.io/docs/interface#p-23244-create-a-vlan-interface) for more details.

Some common mistakes often plague users when creating a VLAN interface:

- Wrong parent ID: Must be a physical interface.
- Deployed machine: Machine must be in “Ready” or “Broken” state.
- Missing VLAN object: The VLAN must exist in MAAS first — you don’t create it here, you are just creating the interface.
- Fabric mismatch: Parent interface and VLAN must belong to the same fabric.

If you're planning to use DHCP on this VLAN interface, ensure the VLAN is configured correctly in MAAS and the DHCP relay is present.

#### Bond two interfaces

Bonding is used to group two or more physical interfaces into a single logical interface.  You can bond two interfaces for any machine in the "Ready" or "Broken" state (this will not work for deployed machines).  This can:

- Provide failover if one NIC fails
- Enable link aggregation (if supported)

Bonding creates interface redundancy and increased throughput on servers with multiple NICs.  Avoid bonding if:

- You are using Wi-Fi or virtual NICs
- You do not control the network switch (and cannot configure LACP)

Learn more about [bonds](https://maas.io/docs/about-maas-networking#p-20679-bonds), if needed.

##### How to create a bond

**UI:**  
*Machines > (Select machine) > Network > (Select 2 physical interface) > Create bond > (Configure details) > Save interface*  

**CLI:**  
```bash
maas $PROFILE interfaces create-bond $SYSTEM_ID name=$BOND_NAME parents=$IFACE1_ID,$IFACE2_ID <optional parameters>
```

Note that `parents` refer to the IDs of the physical interfaces you want to bond.

Every bond must have a mode, though `bonding_mode` is optional in this command. For MAAS, the default bonding mode is `balance_rr`, which transmits packets sequentially from the first available slave through the last. This mode is chosen as default because it provides load balancing and fault tolerance.

Refer to the [interface CLI reference page](https://maas.io/docs/interface#p-23244-create-a-bond-interface) for detailed instruction on how to use the CLI command and other bonding mode choices.

##### Troubleshooting bond creation

| Symptom          | Likely cause                                    |
|------------------|-------------------------------------------------|
| Bond not created | One or more interfaces not in the correct state |
| No traffic       | Switch does not support bond mode               |
| UI grayed out    | Machine not in "Ready" or "Broken" state        |

#### Create a bridge

Bridge interfaces come in handy in when you're:

- provisioning virtual machines and need them to reach the outside network
- want multiple interfaces to behave like a single network interface
- using KVM, LXD, or libvirt and they require a bridge
- attaching multiple NICs with routes, but without bonding

A bridge interface is a virtual network switch that connects one or more physical or VLAN interfaces together. It can also be used to:

- Allow VMs or containers to share a physical NIC
- Support PXE boot with a bridged external connection
- Route between subnets or bonding multiple interfaces under one IP

Bridging is often confused with bonding. Bonding is about failover or speed; bridging is about routing traffic through multiple interfaces.

To create a bridge interface:

**UI**
*Machines > (Select machine) > Network > (Select interface) > Create bridge > (Configure details) > Save interface*  

**CLI**
```bash
maas $PROFILE interfaces create-bridge $SYSTEM_ID name=br0 parent=$INTERFACE_ID
```

Then link it to a subnet:

```bash
maas $PROFILE interface link-subnet $SYSTEM_ID $BRIDGE_ID subnet=$SUBNET_ID mode=STATIC ip_address=10.0.0.101
```

If you need to get the parent ID to create the bridge:

```bash
maas $PROFILE interfaces read $SYSTEM_ID
```

**CLI+jq**

You can also employ the `jq` tool to make the CLI commands a little easier to use:

```bash
INTERFACE_ID=$(maas $PROFILE machine read $SYSTEM_ID | jq .boot_interface.id)
BRIDGE_ID=$(maas $PROFILE interfaces create-bridge $SYSTEM_ID name=br0 parent=$INTERFACE_ID | jq .id)
SUBNET_ID=$(maas $PROFILE subnets read | jq -r '.[] | select(.cidr == "10.0.0.0/24" and .managed == true).id')
maas $PROFILE interface link-subnet $SYSTEM_ID $BRIDGE_ID subnet=$SUBNET_ID mode="STATIC" ip_address="10.0.0.101"
```

##### Required keys (CLI)

| Key      | Meaning                                                   |
|----------|-----------------------------------------------------------|
| `name`   | Logical name of the bridge (e.g. `br0`)                   |
| `parent` | ID of a physical interface to bridge (can add more later) |


##### Common issues

- This command only works in "Ready" or "Broken" states. No interface changes are allowed on deployed machines.
- The parent interface must not already be part of a bond or another bridge.
- The subnet must be managed by MAAS if you're assigning static IPs.
- You need the correct subnet ID, which may require filtering by CIDR and `managed=true`.

You can bridge more than one interface, but only one at creation; add more with the `update` subcommand.  MAAS does not manage `/etc/netplan` directly — so if you bypass MAAS or work post-deploy, remember that netplan configs matter.

#### Create a bridge with netplan

If you need to create a bridge after deployment -- or for bare-metal tweaking -- you will need to create it *outside* MAAS with netplan.  For example, this is what you might add to `/etc/netplan/50-cloud-init.yaml`:

```yaml
network:
  version: 2
  bridges:
    br0:
      interfaces:
        - enp1s0
      addresses:
        - 10.0.0.101/24
      gateway4: 10.0.0.1
```

Apply this configuration with:

```bash
sudo netplan apply
```

### View and maintain interfaces
 Once created, MAAS interfaces can be listed, reviewed, updated, or deleted. The machine must be in the correct state (`Ready` or `Broken`) to allow most changes. Deployed machines can only be updated in limited ways (e.g., changing MAC addresses for replacement).
 
See the [CLI reference](https://maas.io/docs/interface) for more details.

#### List existing interfaces

Use the MAAS UI or CLI to list all interfaces for a specific machine.

**UI**
*Machines > (Select machine) > Network*

**CLI**
```bash
maas $PROFILE interfaces read $SYSTEM_ID
```

#### View a specific interface

Use this to inspect one interface on a particular machine.

**UI**
*Machines > (Select machine) > Network*

**CLI**
```bash
maas $PROFILE interface read $SYSTEM_ID $INTERFACE_ID
```

#### Update an interface

Update interface parameters — but only if the machine is in `Ready` or `Broken` state. If the machine is `Deployed`, you can update only:

- `name`
- `mac_address`

This allows field-replacement of broken NICs without full re-commissioning.

**CLI**
```bash
maas $PROFILE interface update $SYSTEM_ID $INTERFACE_ID (key=value)...
```

Use the appropriate parameter set for the interface type (physical, bridge, bond, VLAN, etc.).

See [the CLI subcommand reference](https://maas.io/docs/interface#p-23244-update-an-interface) for key options.

#### Delete an interface

Remove an interface that is no longer needed. This is typically used when rolling back a misconfiguration or cleaning up testing setups.

**CLI**
```bash
maas $PROFILE interface delete $SYSTEM_ID $INTERFACE_ID
```

### Manage routes and links

Routing and subnet linking are crucial for machine connectivity. MAAS allows interfaces to be connected, disconnected, or routed with custom logic — via both UI and CLI. 

This section shows how to disconnect interfaces, link or unlink them to subnets, assign gateways, and add static routes. It also explains how to set up loopback interfaces.

#### Disconnect an interface

You can disconnect a given interface from its current network configuration. This action:

- Unlinks any connected subnets
- Removes assigned IP addresses
- Detaches from any associated VLAN

This actioni is only available if the machine is in a `Ready` or `Broken` state.

**CLI**
```bash
maas $PROFILE interface disconnect $SYSTEM_ID $INTERFACE_ID
```

#### Link an interface to a subnet

You can connect an interface to a known subnet. This enables traffic routing and IP assignment. The subnet must exist and be discoverable by MAAS.

**CLI**
```bash
maas $PROFILE interface link-subnet $SYSTEM_ID $INTERFACE_ID mode=<mode> subnet=<SUBNET_ID> [ip_address=<STATIC_IP>]
```

- `mode` is usually `STATIC` or `AUTO`
- `ip_address` is optional unless using `STATIC` mode
- You can link to managed or unmanaged subnets

See [Link and interface to a subnet](https://maas.io/docs/interface#p-23244-link-interface-to-a-subnet) in the CLI reference for full options.

#### Unlink an interface from a subnet

Use this command to remove an interface connection to a subnet without deleting the interface itself.

**CLI**
```bash
maas $PROFILE interface unlink-subnet $SYSTEM_ID $INTERFACE_ID
```

#### Set the default gateway

You can update the gateway for a specific subnet. This is a subnet-level setting that affects routing behavior for all devices on that subnet.

**CLI**
```bash
maas $PROFILE subnet update $SUBNET_CIDR gateway_ip=$MY_GATEWAY
```

#### Add a static route

Route specific traffic between source and destination subnets through a defined gateway. Useful for custom networking setups or multi-NIC systems.

**UI**
*Networking > Subnets > (Select subnet) > Add static route > Fill fields > Save*

**CLI**
```bash
maas $PROFILE static-routes create source=$SOURCE_SUBNET destination=$DEST_SUBNET gateway_ip=$GATEWAY_IP
```

#### Configure a loopback interface

Loopback interfaces can be added after commissioning, using a placeholder MAC address (`00:00:00:00:00:00`). This allows MAAS to recognize it as an intentional loopback, not a misconfigured NIC.

To automate loopback setup, use `cloud-init`.

### Tag interfaces

MAAS allows you to apply **tags** to network interfaces, which can be used for filtering, grouping, automation, or custom selection (e.g., during deployments or scripting).

#### Add a tag to an interface

Use tags to classify interfaces — e.g., `"uplink"`, `"PXE"`, `"isolated"`, etc.

**CLI**
```bash
maas $PROFILE interface add-tag $SYSTEM_ID $INTERFACE_ID tag="my-tag"
```

- You can apply multiple tags to an interface.
- Tags are case-sensitive.
- Useful in complex environments where roles need to be defined or discovered programmatically.

#### Remove a tag from an interface

Remove any tag that is no longer needed.

**CLI**
```bash
maas $PROFILE interface remove-tag $SYSTEM_ID $INTERFACE_ID tag="my-tag"
```

To view existing tags on an interface, use:

**CLI**
```bash
maas $PROFILE interface read $SYSTEM_ID $INTERFACE_ID
```

### Manage dual NICs

Some deployments require dual NIC configurations — for example, separating public internet traffic from private internal communication. MAAS supports this setup via UI, CLI, or external tools like Netplan.

#### Set up dual NICs with MAAS

Assign different roles to each NIC:

- NIC 1 (private subnet): Internal network, typically DHCP (`e.g. 192.168.10.0/24`)
- NIC 2 (public access): External internet, DHCP or static (`e.g. 192.168.1.0/24`)

You can configure both NICs through the MAAS UI or CLI by setting interface modes and linking subnets.

### Set up dual NICs with Netplan

You can bypass MAAS for some configs by editing `/etc/netplan/50-cloud-init.yaml`:

```yaml
network:
  version: 2
  ethernets:
    ens18:
      addresses:
        - 192.168.10.5/24
      gateway4: 192.168.10.1
    ens19:
      addresses:
        - 192.168.1.10/24
      gateway4: 192.168.1.1
      nameservers:
        addresses:
          - 8.8.8.8
          - 8.8.4.4
```

Apply the configuration to make it effective:

```bash
sudo netplan apply
```

### Manage network discovery

MAAS can automatically detect devices on your network, including those it doesn’t manage — like switches, routers, IoT.

Use network discovery to:

- Map live devices in connected subnets
- Track rogue IPs or MACs
- Audit networks for new arrivals


#### Basic discovery setup

##### Enable discovery

Turn discovery on to allow MAAS to detect devices on active subnets.

**UI** 
*Networking > Network discovery > Configuration > Enabled*

**CLI**
```bash
maas $PROFILE maas set-config name=network_discovery value="enabled"
```

##### Disable discovery

Stop automatic scanning if you are done, or want manual control.

**UI**
*Networking > Network discovery > Configuration > Disabled*

**CLI**
```bash
maas $PROFILE maas set-config name=network_discovery value="disabled"
```

##### Set discovery scan interval

Control how often MAAS scans for devices.

**UI**
*Networking > Network discovery > Configuration > Active subnet mapping interval*

**CLI**
```bash
maas $PROFILE maas set-config name=active_discovery_interval value=<seconds>
```

##### Clear all discovered devices

Start fresh by removing all discoveries to date.

**UI**
*Networking > Network discovery > Clear all discoveries*

**CLI**
```bash
maas $PROFILE discoveries clear all=true
```

##### Scan specific subnets

Focus your scans to pinpoint specific servers.

**UI**
*Networking > Network discovery > Configuration > Subnet mapping > [CIDR selections]*

**CLI**
```bash
maas $PROFILE discoveries scan cidr=10.0.0.0/24
```

#### Fine-tune discovery (CLI only)

Use these commands for specific discovery needs.

##### Force a re-scan

Overwrite cached data and rescan everything.

```bash
maas $PROFILE discoveries scan force=true
```

##### Use ping instead of nmap

This is useful if `nmap` is blocked or too aggressive for your network bandwidth.

```bash
maas $PROFILE discoveries scan always_use_ping=true
```

##### Slow the scan down

Limiting bandwidth may be helpful on flaky networks.

```bash
maas $PROFILE discoveries scan slow=true
```

##### Control thread count

Reduce load or speed things up.

```bash
maas $PROFILE discoveries scan thread=4
```

#### Filter discovered devices

MAAS can filter results for deeper inspection.

- By unknown IP:
```bash
maas $PROFILE discoveries by-unknown-ip
```

- By unknown MAC:
```bash
maas $PROFILE discoveries by-unknown-mac
```

- By both:
```bash
maas $PROFILE discoveries by-unknown-mac-and-ip
```

#### Clear discoveries (selective)

Delete specific findings that are not currently helpful.

- **By IP and MAC**
```bash
maas $PROFILE discoveries clear-by-mac-and-ip ip=10.0.0.9 mac=00:11:22:33:44:55
```

- **Delete neighbors**
```bash
maas $PROFILE discoveries clear neighbours=true
```

- **Delete mDNS**
```bash
maas $PROFILE discoveries clear mdns=true
```

## Manage subnets

The following instructions are based on MAAS 3.4. For earlier versions, the UI element names may differ.*

### Examine subnets

**UI**
*Networking > Subnets > (Select subnet)*

**CLI**
 - List subnets:
    ```bash
    maas $PROFILE subnets read
    ```
  - Retrieve details of a specific subnet:
    ```bash
    maas $PROFILE subnet read $SUBNET_ID
    ```

### Toggle subnet management

**UI**
*Subnets > (Select subnet) > Edit > Managed allocation > Save*

**CLI**
  - Enable management:
    ```bash
    maas $PROFILE subnet update $SUBNET_CIDR managed=true
    ```
  - Disable management:
    ```bash
    maas $PROFILE subnet update $SUBNET_CIDR managed=false
    ```

### Configure DNS servers per subnet

**UI**
*Subnets > (Select subnet)j > Edit > DNS servers > Save*

**CLI**
  ```bash
  maas $PROFILE subnet update $SUBNET_CIDR dns_servers=$DNS_SERVER_IPS
  ```

### Add static routes

**UI**
*Subnets > (Select subnet) > Static routes > Add static route > Enter Gateway IP > Enter Destination subnet > Enter (optional) Metric > Save*

**CLI**
  ```bash
  maas $PROFILE static-routes create source=$SOURCE_SUBNET destination=$DEST_SUBNET gateway_ip=$GATEWAY_IP
  ```

## Manage VLANs

### Create VLAN

**UI**
*Subnets > Add > VLAN > (Fill fields) > Add VLAN*

**CLI**
```bash
maas $PROFILE vlans create $FABRIC_ID name=$VLAN_NAME vid=$VLAN_ID
```

### Assign VLAN to interface  

**UI**
*Machines > (Select machine> > (Select physical interface) > Actions > Add VLAN*

**CLI**
```bash
maas $PROFILE interfaces create-vlan $SYSTEM_ID vlan=$VLAN_ID parent=$INTERFACE_ID
```

### Delete VLAN  

**UI**
*Subnets* > (Select VLAN) > Delete VLAN > Delete VLAN*

**CLI**
```bash
maas $PROFILE vlan delete $FABRIC_ID $VLAN_ID
```

## Manage IP addresses

### Static IP via netplan  

Modify `/etc/netplan/50-cloud-init.yaml`:  
```yaml
network:
  ethernets:
    ens160:
      addresses:
        - 192.168.0.100/24
      gateway4: 192.168.0.1
      nameservers:
        addresses:
          - 8.8.8.8
          - 8.8.4.4
```

### Reserve IPs  

#### Reserve a single IP

**CLI**
```bash
maas $PROFILE ipaddresses reserve ip=$IP_ADDRESS_STATIC_SINGLE
```

#### Reserve a dynamic range

**UI**
*Subnets > (Select subnet> > (Scroll down> > Reserve range > Reserve dynamic range > (Fill fields) > Reserve*

**CLI**
```bash
maas $PROFILE ipranges create type=dynamic subnet=$SUBNET_ADDRESS start_ip=$IP_DYNAMIC_RANGE_LOW end_ip=$IP_DYNAMIC_RANGE_HIGH
```

#### Reserve a static range

**UI**
*Subnets > (Select subnet> > (Scroll down) > Reserve range > Reserve range > (Fill fields) Reserve*

**CLI**
```bash
maas $PROFILE ipranges create type=reserved subnet=$SUBNET_ADDRESS start_ip=$IP_STATIC_RANGE_LOW end_ip=$IP_STATIC_RANGE_HIGH
```
	
