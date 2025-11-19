Add a tag to an interface

```bash
maas $PROFILE interface add-tag [--help] [-d] [-k] system_id id [data ...]

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| system_id | The system ID of the machine/device (e.g., `abc123`) |
| id | The ID of the resource (e.g., `1`, `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Add a tag to an interface with the given system_id and<br>interface id.

##### Keyword "tag"
Optional String. The tag to add.


Note: This command accepts JSON.


Delete an interface

```bash
maas $PROFILE interface delete [--help] [-d] [-k] system_id id

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| system_id | The system ID of the machine/device (e.g., `abc123`) |
| id | The ID of the resource (e.g., `1`, `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Delete an interface with the given system_id and interface<br>id.





Disconnect an interface

```bash
maas $PROFILE interface disconnect [--help] [-d] [-k] system_id id

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| system_id | The system ID of the machine/device (e.g., `abc123`) |
| id | The ID of the resource (e.g., `1`, `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Disconnect an interface with the given system_id and<br>interface id. Deletes any linked subnets and IP addresses, and disconnects the<br>interface from any associated VLAN.





Link interface to a subnet

```bash
maas $PROFILE interface link-subnet [--help] [-d] [-k] system_id id [data ...]

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| system_id | The system ID of the machine/device (e.g., `abc123`) |
| id | The ID of the resource (e.g., `1`, `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Link an interface with the given system_id and interface<br>id to a subnet.

##### Keyword "mode"
Optional String. ``AUTO``,<br>``DHCP``, ``STATIC`` or ``LINK_UP`` connection to subnet. Mode definitions:<br><br>- ``AUTO``: Assign this interface a static IP address from the provided<br>subnet. The subnet must be a managed subnet. The IP address will not<br>be assigned until the node goes to be deployed. - ``DHCP``: Bring this interface up with DHCP on the given subnet. Only<br>one subnet can be set to ``DHCP``. If the subnet is managed this<br>interface will pull from the dynamic IP range. - ``STATIC``: Bring this interface up with a static IP address on the<br>given subnet. Any number of static links can exist on an interface. - ``LINK_UP``: Bring this interface up only on the given subnet. No IP<br>address will be assigned to this interface. The interface cannot have<br>any current ``AUTO``, ``DHCP`` or ``STATIC`` links.
##### Keyword "subnet"
Optional Int. Subnet id linked to interface.
##### Keyword "ip_address"
Optional String. IP address for the<br>interface in subnet. Only used when mode is ``STATIC``. If not provided<br>an IP address from subnet will be auto selected.
##### Keyword "force"
Optional Boolean. If True, allows ``LINK_UP``<br>to be set on the interface even if other links already exist. Also<br>allows the selection of any VLAN, even a VLAN MAAS does not believe the<br>interface to currently be on. Using this option will cause all other<br>links on the interface to be deleted. (Defaults to False.)
##### Keyword "default_gateway"
Optional String. True sets the<br>gateway IP address for the subnet as the default gateway for the node<br>this interface belongs to. Option can only be used with the ``AUTO``<br>and ``STATIC`` modes.


Note: This command accepts JSON.


Read an interface

```bash
maas $PROFILE interface read [--help] [-d] [-k] system_id id

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| system_id | The system ID of the machine/device (e.g., `abc123`) |
| id | The ID of the resource (e.g., `1`, `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Read an interface with the given system_id and interface<br>id.





Remove a tag from an interface

```bash
maas $PROFILE interface remove-tag [--help] [-d] [-k] system_id id [data ...]

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| system_id | The system ID of the machine/device (e.g., `abc123`) |
| id | The ID of the resource (e.g., `1`, `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Remove a tag from an interface with the given system_id<br>and interface id.

##### Keyword "tag"
Optional String. The tag to remove.


Note: This command accepts JSON.


Set the default gateway on a machine

```bash
maas $PROFILE interface set-default-gateway [--help] [-d] [-k] system_id id [data ...]

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| system_id | The system ID of the machine/device (e.g., `abc123`) |
| id | The ID of the resource (e.g., `1`, `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Set the given interface id on the given system_id as the<br>default gateway. If this interface has more than one subnet with a gateway IP in the<br>same IP address family then specifying the ID of the link on<br>this interface is required.

##### Keyword "link_id"
Optional Int. ID of the link on this<br>interface to select the default gateway IP address from.


Note: This command accepts JSON.


Unlink interface from subnet

```bash
maas $PROFILE interface unlink-subnet [--help] [-d] [-k] system_id id [data ...]

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| system_id | The system ID of the machine/device (e.g., `abc123`) |
| id | The ID of the resource (e.g., `1`, `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Unlink an interface with the given system_id and interface<br>id from a subnet.

##### Keyword "id"
Optional Int. ID of the subnet link on the<br>interface to remove.


Note: This command accepts JSON.


Update an interface

```bash
maas $PROFILE interface update [--help] [-d] [-k] system_id id [data ...]

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| system_id | The system ID of the machine/device (e.g., `abc123`) |
| id | The ID of the resource (e.g., `1`, `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Update an interface with the given system_id and interface<br>id. Note: machines must have a status of Ready or Broken to have access to<br>all options. Machines with Deployed status can only have the name<br>and/or mac_address updated for an interface. This is intended to allow<br>a bad interface to be replaced while the machine remains deployed.

##### Keyword "name"
Optional String. (Bridge interfaces) Name of the<br>interface.
##### Keyword "mac_address"
Optional String. (Bridge interfaces) MAC<br>address of the interface.
##### Keyword "tags"
Optional String. (Bridge interfaces) Tags for<br>the interface.
##### Keyword "vlan"
Optional Int. (Bridge interfaces) VLAN id the<br>interface is connected to.
##### Keyword "parents"
Optional Int. (Bond interfaces) Parent<br>interface ids that make this bond.
##### Keyword "parent"
Optional Int. (Bridge interfaces) Parent<br>interface ids for this bridge interface.
##### Keyword "bridge_type"
Optional String. (Bridge interfaces) Type<br>of bridge to create. Possible values are: ``standard``, ``ovs``.
##### Keyword "bridge_stp"
Optional Boolean. (Bridge interfaces) Turn<br>spanning tree protocol on or off. (Default: False).
##### Keyword "bridge_fd"
Optional Int. (Bridge interfaces) Set<br>bridge forward delay to time seconds. (Default: 15).
##### Keyword "bond_miimon"
Optional Int. (Bonds) The link monitoring<br>frequency in milliseconds. (Default: 100).
##### Keyword "bond_downdelay"
Optional Int. (Bonds) Specifies the<br>time, in milliseconds, to wait before disabling a slave after a link<br>failure has been detected.
##### Keyword "bond_updelay"
Optional Int. (Bonds) Specifies the<br>time, in milliseconds, to wait before enabling a slave after a link<br>recovery has been detected.
##### Keyword "bond_lacp_rate"
Optional String. (Bonds) Option<br>specifying the rate in which we'll ask our link partner to transmit<br>LACPDU packets in 802.3ad mode. Available options are ``fast`` or<br>``slow``. (Default: ``slow``).
##### Keyword "bond_xmit_hash_policy"
Optional String. (Bonds) The<br>transmit hash policy to use for slave selection in balance-xor,<br>802.3ad, and tlb modes. Possible values are: ``layer2``, ``layer2+3``,<br>``layer3+4``, ``encap2+3``, ``encap3+4``.
##### Keyword "bond_mode"
Optional String. (Bonds)<br>The operating mode of the bond. (Default: ``active-backup``). Supported bonding modes (bond-mode):<br><br>- ``balance-rr``: Transmit packets in sequential order from the first<br>available slave through the last. This mode provides load balancing<br>and fault tolerance. - ``active-backup``: Only one slave in the bond is active. A different<br>slave becomes active if, and only if, the active slave fails. The<br>bond's MAC address is externally visible on only one port (network<br>adapter) to avoid confusing the switch. - ``balance-xor``: Transmit based on the selected transmit hash policy.<br>The default policy is a simple [(source MAC address XOR'd with<br>destination MAC address XOR packet type ID) modulo slave count]. - ``broadcast``: Transmits everything on all slave interfaces. This<br>mode provides fault tolerance. - ``802.3ad``: IEEE 802.3ad Dynamic link aggregation. Creates<br>aggregation groups that share the same speed and duplex settings.<br>Utilizes all slaves in the active aggregator according to the 802.3ad<br>specification. - ``balance-tlb``: Adaptive transmit load balancing: channel bonding<br>that does not require any special switch support. - ``balance-alb``: Adaptive load balancing: includes balance-tlb plus<br>receive load balancing (rlb) for IPV4 traffic, and does not require<br>any special switch support. The receive load balancing is achieved by<br>ARP negotiation.
##### Keyword "mtu"
Optional String. Maximum transmission unit.
##### Keyword "accept_ra"
Optional String. Accept router<br>advertisements. (IPv6 only)
##### Keyword "link_connected"
Optional Boolean. (Physical interfaces) Whether or not the interface is physically<br>connected to an uplink. (Default: True).
##### Keyword "interface_speed"
Optional Int. (Physical interfaces)<br>The speed of the interface in Mbit/s. (Default: 0).
##### Keyword "link_speed"
Optional Int. (Physical interfaces)<br>The speed of the link in Mbit/s. (Default: 0).


Note: This command accepts JSON.


Create a bond interface

```bash
maas $PROFILE interfaces create-bond [--help] [-d] [-k] system_id [data ...]

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| system_id | The system ID of the machine/device (e.g., `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Create a bond interface on a machine.

##### Keyword "name"
Optional String. Name of the interface.
##### Keyword "mac_address"
Optional String. MAC address of the<br>interface.
##### Keyword "tags"
Optional String. Tags for the interface.
##### Keyword "vlan"
Optional String. VLAN the interface is connected<br>to. If not provided then the interface is considered disconnected.
##### Keyword "parents"
Optional Int. Parent interface ids that make<br>this bond.
##### Keyword "bond_mode"
Optional String. The<br>operating mode of the bond. (Default: active-backup). Supported bonding modes:<br><br>- ``balance-rr``: Transmit packets in sequential order from the first<br>available slave through the last. This mode provides load balancing<br>and fault tolerance. - ``active-backup``: Only one slave in the bond is active. A different<br>slave becomes active if, and only if, the active slave fails. The<br>bond's MAC address is externally visible on only one port (network<br>adapter) to avoid confusing the switch. - ``balance-xor``: Transmit based on the selected transmit hash policy.<br>The default policy is a simple [(source MAC address XOR'd with<br>destination MAC address XOR packet type ID) modulo slave count]. - ``broadcast``: Transmits everything on all slave interfaces. This<br>mode provides fault tolerance. - ``802.3ad``: IEEE 802.3ad dynamic link aggregation. Creates<br>aggregation groups that share the same speed and duplex settings.<br>Uses all slaves in the active aggregator according to the 802.3ad<br>specification. - ``balance-tlb``: Adaptive transmit load balancing: channel bonding<br>that does not require any special switch support. - ``balance-alb``: Adaptive load balancing: includes balance-tlb plus<br>receive load balancing (rlb) for IPV4 traffic, and does not require<br>any special switch support. The receive load balancing is achieved by<br>ARP negotiation.
##### Keyword "bond_miimon"
Optional Int. The link monitoring<br>frequency in milliseconds. (Default: 100).
##### Keyword "bond_downdelay"
Optional Int. Specifies the time, in<br>milliseconds, to wait before disabling a slave after a link failure has<br>been detected.
##### Keyword "bond_updelay"
Optional Int. Specifies the time, in<br>milliseconds, to wait before enabling a slave after a link recovery has<br>been detected.
##### Keyword "bond_lacp_rate"
Optional String. Option specifying the<br>rate at which to ask the link partner to transmit LACPDU packets in<br>802.3ad mode. Available options are ``fast`` or ``slow``. (Default:<br>``slow``).
##### Keyword "bond_xmit_hash_policy"
Optional String. The transmit<br>hash policy to use for slave selection in balance-xor, 802.3ad, and tlb<br>modes. Possible values are: ``layer2``, ``layer2+3``, ``layer3+4``,<br>``encap2+3``, ``encap3+4``. (Default: ``layer2``)
##### Keyword "bond_num_grat_arp"
Optional Int. The number of peer<br>notifications (IPv4 ARP or IPv6 Neighbour Advertisements) to be issued<br>after a failover. (Default: 1)
##### Keyword "mtu"
Optional Int. Maximum transmission unit.
##### Keyword "accept_ra"
Optional Boolean. Accept router<br>advertisements. (IPv6 only)


Note: This command accepts JSON.


Create a bridge interface

```bash
maas $PROFILE interfaces create-bridge [--help] [-d] [-k] system_id [data ...]

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| system_id | The system ID of the machine/device (e.g., `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Create a bridge interface on a machine.

##### Keyword "name"
Optional String. Name of the interface.
##### Keyword "mac_address"
Optional String. MAC address of the<br>interface.
##### Keyword "tags"
Optional String. Tags for the interface.
##### Keyword "vlan"
Optional String. VLAN the interface is connected<br>to.
##### Keyword "parent"
Optional Int. Parent interface id for this<br>bridge interface.
##### Keyword "bridge_type"
Optional String. The type of bridge<br>to create. Possible values are: ``standard``, ``ovs``.
##### Keyword "bridge_stp"
Optional Boolean. Turn spanning tree<br>protocol on or off. (Default: False).
##### Keyword "bridge_fd"
Optional Int. Set bridge forward delay<br>to time seconds. (Default: 15).
##### Keyword "mtu"
Optional Int. Maximum transmission unit.
##### Keyword "accept_ra"
Optional Boolean. Accept router<br>advertisements. (IPv6 only)


Note: This command accepts JSON.


Create a physical interface

```bash
maas $PROFILE interfaces create-physical [--help] [-d] [-k] system_id [data ...]

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| system_id | The system ID of the machine/device (e.g., `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Create a physical interface on a machine and device.

##### Keyword "name"
Optional String. Name of the interface.
##### Keyword "mac_address"
Optional String. MAC address of the<br>interface.
##### Keyword "tags"
Optional String. Tags for the interface.
##### Keyword "vlan"
Optional String. Untagged VLAN the interface is<br>connected to. If not provided then the interface is considered<br>disconnected.
##### Keyword "mtu"
Optional Int. Maximum transmission unit.
##### Keyword "accept_ra"
Optional Boolean. Accept router<br>advertisements. (IPv6 only)


Note: This command accepts JSON.


Create a VLAN interface

```bash
maas $PROFILE interfaces create-vlan [--help] [-d] [-k] system_id [data ...]

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| system_id | The system ID of the machine/device (e.g., `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Create a VLAN interface on a machine.

##### Keyword "tags"
Optional String. Tags for the interface.
##### Keyword "vlan"
Optional String. Tagged VLAN the interface is<br>connected to.
##### Keyword "parent"
Optional Int. Parent interface id for this VLAN<br>interface.
##### Keyword "mtu"
Optional Int. Maximum transmission unit.
##### Keyword "accept_ra"
Optional Boolean. Accept router<br>advertisements. (IPv6 only)


Note: This command accepts JSON.


List interfaces

```bash
maas $PROFILE interfaces read [--help] [-d] [-k] system_id

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| system_id | The system ID of the machine/device (e.g., `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
List all interfaces belonging to a machine, device, or<br>rack controller.
