Enter keyword arguments in the form `key=value`.

## Add a tag to an interface

```bash
maas $PROFILE interface add-tag [--help] [-d] [-k] system_id id [data ...]
```

#### Positional arguments
- system_id
- id


Add a tag to an interface with the given `system_id` and interface `id`.

#### Keyword "tag"
Optional String. The tag to add.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Delete an interface

```bash
maas $PROFILE interface delete [--help] [-d] [-k] system_id id [data ...]
```

#### Positional arguments
- system_id
- id

Delete an interface with the given `system_id` and interface `id`.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Disconnect an interface

```bash
maas $PROFILE interface disconnect [--help] [-d] [-k] system_id id [data ...]
```

#### Positional arguments
- system_id
- id

Disconnect an interface with the given `system_id` and interface `id`.

Deletes any linked subnets and IP addresses, and disconnects the interface from any associated VLAN.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Link interface to a subnet

```bash
maas $PROFILE interface link-subnet [--help] [-d] [-k] system_id id [data ...]
```

#### Positional arguments
- system_id
- id


Link an interface with the given `system_id` and interface `id` to a subnet.

#### Keyword "mode"
Required String.  ``AUTO``,``DHCP``, ``STATIC`` or ``LINK_UP`` connection to subnet.

Mode definitions:

- ``AUTO``: Assign this interface a static IP address from the provided subnet. The subnet must be a managed subnet. The IP address will not be assigned until the node goes to be deployed.

- ``DHCP``: Bring this interface up with DHCP on the given subnet. Only one subnet can be set to ``DHCP``. If the subnet is managed this interface will pull from the dynamic IP range.
  
- ``STATIC``: Bring this interface up with a static IP address on the given subnet. Any number of static links can exist on an interface.

- ``LINK_UP``: Bring this interface up only on the given subnet. No IP address will be assigned to this interface. The interface cannot have any current ``AUTO``, ``DHCP`` or ``STATIC`` links.

#### Keyword "subnet"
Required Int. Subnet id linked to interface.

#### Keyword "ip_address"
Optional String.  IP address for the interface in subnet. Only used when mode is ``STATIC``. If not provided an IP address from subnet will be auto selected.

#### Keyword "force"
Optional Boolean.  If True, allows ``LINK_UP`` to be set on the interface even if other links already exist. Also allows the selection of any VLAN, even a VLAN MAAS does not believe the interface to currently be on. Using this option will cause all other links on the interface to be deleted. (Defaults to False.)

#### Keyword "default_gateway"
Optional String.  True sets the gateway IP address for the subnet as the default gateway for the node this interface belongs to. Option can only be used with the ``AUTO`` and ``STATIC`` modes.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Read an interface

```bash
maas $PROFILE interface read [--help] [-d] [-k] system_id id [data ...] 
```

#### Positional arguments
- system_id
- id

Read an interface with the given `system_id` and interface `id`.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Remove a tag from an interface

```bash
maas $PROFILE interface remove-tag [--help] [-d] [-k] system_id id [data ...]
```

#### Positional arguments
- system_id
- id


Remove a tag from an interface with the given `system_id` and interface `id`.

#### Keyword "tag"
Optional String. The tag to remove.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Set the default gateway on a machine

```bash
maas $PROFILE interface set-default-gateway [--help] [-d] [-k] system_id id [data ...]
```

#### Positional arguments
- system_id
- id

Set the given interface id on the given `system_id` as the default gateway.

If this interface has more than one subnet with a gateway IP in the same IP address family then specifying the ID of the link on this interface is required.

#### Keyword "link_id"
Optional Int. ID of the link on this interface to select the default gateway IP address from.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Unlink interface from subnet

```bash
maas $PROFILE interface unlink-subnet [--help] [-d] [-k] system_id id [data ...]
```

#### Positional arguments
- system_id
- id


Unlink an interface with the given `system_id` and interface `id` from a subnet.

#### Keyword "id"
Optional Int. ID of the subnet link on the interface to remove.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Update an interface

```bash
maas $PROFILE interface update [--help] [-d] [-k] system_id id [data ...]
```

#### Positional arguments
- system_id
- id


Update an interface with the given `system_id` and interface `id`.

Note: machines must have a status of Ready or Broken to have access to all options. Machines with Deployed status can only have the name and/or mac_address updated for an interface. This is intended to allow a bad interface to be replaced while the machine remains deployed.

#### Keyword "name"
Optional String. (Physical interfaces) Name of the interface.

#### Keyword "mac_address"
Optional String. (Physical interfaces) MAC address of the interface.

#### Keyword "tags"
Optional String. (Physical interfaces) Tags for the interface.

#### Keyword "vlan"
Optional Int.  (Physical interfaces) Untagged VLAN id the interface is connected to.  If not set then the interface is considered disconnected.

#### Keyword "name"
Optional String. (Bond interfaces) Name of the interface.

#### Keyword "mac_address"
Optional String. (Bond interfaces) MAC address of the interface.

#### Keyword "tags"
Optional String. (Bond interfaces) Tags for the interface.

#### Keyword "vlan"
Optional Int.  (Bond interfaces) Untagged VLAN id the interface is connected to. If not set then the interface is considered disconnected.

#### Keyword "parents"
Optional Int. (Bond interfaces) Parent interface ids that make this bond.

#### Keyword "tags"
Optional String. (VLAN interfaces) Tags for the interface.

#### Keyword "vlan"
Optional Int. (VLAN interfaces) Tagged VLAN id the interface is connected to.

#### Keyword "parent"
Optional Int. (VLAN interfaces) Parent interface ids for the VLAN interface.

#### Keyword "name"
Optional String. (Bridge interfaces) Name of the interface.

#### Keyword "mac_address"
Optional String. (Bridge interfaces) MAC address of the interface.

#### Keyword "tags"
Optional String. (Bridge interfaces) Tags for the interface.

#### Keyword "vlan"
Optional Int. (Bridge interfaces) VLAN id the interface is connected to.

#### Keyword "parent"
Optional Int. (Bridge interfaces) Parent interface ids for this bridge interface.

#### Keyword "bridge_type"
Optional String. (Bridge interfaces) Type of bridge to create. Possible values are: ``standard``, ``ovs``.

#### Keyword "bridge_stp"
Optional Boolean. (Bridge interfaces) Turn spanning tree protocol on or off.  (Default: False).

#### Keyword "bridge_fd"
Optional Int. (Bridge interfaces) Set bridge forward delay to time seconds.  (Default: 15).

#### Keyword "bond_miimon"
Optional Int. (Bonds) The link monitoring frequency in milliseconds.  (Default: 100).

#### Keyword "bond_downdelay"
Optional Int.  (Bonds) Specifies the time, in milliseconds, to wait before disabling a slave after a link failure has been detected.

#### Keyword "bond_updelay"
Optional Int.  (Bonds) Specifies the time, in milliseconds, to wait before enabling a slave after a link recovery has been detected.

#### Keyword "bond_lacp_rate"
Optional String.  (Bonds) Option specifying the rate in which we'll ask our link partner to transmit LACPDU packets in 802.3ad mode.  Available options are ``fast`` or ``slow``.  (Default: ``slow``).

#### Keyword "bond_xmit_hash_policy"
Optional String.  (Bonds) The transmit hash policy to use for slave selection in balance-xor, 802.3ad, and tlb modes.  Possible values are: ``layer2``, ``layer2+3``, ``layer3+4``, ``encap2+3``, ``encap3+4``.

#### Keyword "bond_mode"
Optional String.  (Bonds)
The operating mode of the bond.  (Default: ``active-backup``).

Supported bonding modes (bond-mode):

- ``balance-rr``: Transmit packets in sequential order from the first available slave through the last. This mode provides load balancing and fault tolerance.

- ``active-backup``: Only one slave in the bond is active. A different slave becomes active if, and only if, the active slave fails. The bond's MAC address is externally visible on only one port (network adapter) to avoid confusing the switch.

- ``balance-xor``: Transmit based on the selected transmit hash policy. The default policy is a simple [(source MAC address XOR'd with destination MAC address XOR packet type ID) modulo slave count].

- ``broadcast``: Transmits everything on all slave interfaces. This mode provides fault tolerance.

- ``802.3ad``: IEEE 802.3ad Dynamic link aggregation. Creates aggregation groups that share the same speed and duplex settings. Utilizes all slaves in the active aggregator according to the 802.3ad specification.

- ``balance-tlb``: Adaptive transmit load balancing: channel bonding that does not require any special switch support.

- ``balance-alb``: Adaptive load balancing: includes balance-tlb plus receive load balancing (rlb) for IPV4 traffic, and does not require any special switch support. The receive load balancing is achieved by ARP negotiation.

#### Keyword "mtu"
Optional String. Maximum transmission unit.

#### Keyword "accept_ra"
Optional String. Accept router advertisements. (IPv6 only)

#### Keyword "link_connected"
Optional Boolean. (Physical interfaces) Whether or not the interface is physically connected to an uplink.  (Default: True).

#### Keyword "interface_speed"
Optional Int. (Physical interfaces) The speed of the interface in Mbit/s. (Default: 0).

#### Keyword "link_speed"
Optional Int. (Physical interfaces) The speed of the link in Mbit/s. (Default: 0).

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Create a bond interface

```bash
maas $PROFILE interfaces create-bond [--help] [-d] [-k] system_id [data ...]
```

#### Positional arguments
- system_id


Create a bond interface on a machine.

#### Keyword "name"
Required String. Name of the interface.

#### Keyword "mac_address"
Optional String. MAC address of the interface.

#### Keyword "tags"
Optional String. Tags for the interface.

#### Keyword "vlan"
Optional String. VLAN the interface is connected to. If not provided then the interface is considered disconnected.

#### Keyword "parents"
Required Int. Parent interface ids that make this bond.

#### Keyword "bond_mode"
Optional String.  The operating mode of the bond.  (Default: active-backup).

Supported bonding modes:

- ``balance-rr``: Transmit packets in sequential order from the first available slave through the last. This mode provides load balancing and fault tolerance.

- ``active-backup``: Only one slave in the bond is active. A different slave becomes active if, and only if, the active slave fails. The bond's MAC address is externally visible on only one port (network adapter) to avoid confusing the switch.

- ``balance-xor``: Transmit based on the selected transmit hash policy. The default policy is a simple [(source MAC address XOR'd with destination MAC address XOR packet type ID) modulo slave count].

- ``broadcast``: Transmits everything on all slave interfaces. This mode provides fault tolerance.

- ``802.3ad``: IEEE 802.3ad dynamic link aggregation. Creates aggregation groups that share the same speed and duplex settings. Uses all slaves in the active aggregator according to the 802.3ad specification.

- ``balance-tlb``: Adaptive transmit load balancing: channel bonding that does not require any special switch support.

- ``balance-alb``: Adaptive load balancing: includes balance-tlb plus receive load balancing (rlb) for IPV4 traffic, and does not require any special switch support. The receive load balancing is achieved by ARP negotiation.

#### Keyword "bond_miimon"
Optional Int. The link monitoring frequency in milliseconds.  (Default: 100).

#### Keyword "bond_downdelay"
Optional Int.  Specifies the time, in milliseconds, to wait before disabling a slave after a link failure has been detected.

#### Keyword "bond_updelay"
Optional Int.  Specifies the time, in milliseconds, to wait before enabling a slave after a link recovery has been detected.

#### Keyword "bond_lacp_rate"
Optional String.  Option specifying the rate at which to ask the link partner to transmit LACPDU packets in 802.3ad mode. Available options are ``fast`` or ``slow``. (Default: ``slow``).

#### Keyword "bond_xmit_hash_policy"
Optional String.  The transmit
hash policy to use for slave selection in balance-xor, 802.3ad, and tlb
modes. Possible values are: ``layer2``, ``layer2+3``, ``layer3+4``, ``encap2+3``, ``encap3+4``. (Default: ``layer2``)

#### Keyword "bond_num_grat_arp"
Optional Int.  The number of peer notifications (IPv4 ARP or IPv6 Neighbor Advertisements) to be issued after a failover. (Default: 1)

#### Keyword "mtu"
Optional Int. Maximum transmission unit.

#### Keyword "accept_ra"
Optional Boolean. Accept router advertisements. (IPv6 only)

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Create a bridge interface

```bash
maas $PROFILE interfaces create-bridge [--help] [-d] [-k] system_id [data ...]
```

#### Positional arguments
- system_id


Create a bridge interface on a machine.

#### Keyword "name"
Optional String. Name of the interface.

#### Keyword "mac_address"
Optional String. MAC address of the interface.

#### Keyword "tags"
Optional String. Tags for the interface.

#### Keyword "vlan"
Optional String. VLAN the interface is connected to.

#### Keyword "parent"
Optional Int. Parent interface id for this bridge interface.

#### Keyword "bridge_type"
Optional String. The type of bridge to create. Possible values are: ``standard``, ``ovs``.

#### Keyword "bridge_stp"
Optional Boolean. Turn spanning tree protocol on or off. (Default: False).

#### Keyword "bridge_fd"
Optional Int. Set bridge forward delay to time seconds. (Default: 15).

#### Keyword "mtu"
Optional Int. Maximum transmission unit.

#### Keyword "accept_ra"
Optional Boolean. Accept router advertisements. (IPv6 only)

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Create a physical interface

```bash
maas $PROFILE interfaces create-physical [--help] [-d] [-k] system_id [data ...]
```

#### Positional arguments
- system_id


Create a physical interface on a machine and device.

#### Keyword "name"
Optional String. Name of the interface.

#### Keyword "mac_address"
Required String. MAC address of the interface.

#### Keyword "tags"
Optional String. Tags for the interface.

#### Keyword "vlan"
Optional String.  Untagged VLAN the interface is connected to. If not provided then the interface is considered disconnected.

#### Keyword "mtu"
Optional Int. Maximum transmission unit.

#### Keyword "accept_ra"
Optional Boolean. Accept router advertisements. (IPv6 only)

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Create a VLAN interface

```bash
maas $PROFILE interfaces create-vlan [--help] [-d] [-k] system_id [data ...]
```

#### Positional arguments
- system_id


Create a VLAN interface on a machine.

#### Keyword "tags"
Optional String. Tags for the interface.

#### Keyword "vlan"
Required String. Tagged VLAN the interface is connected to.

#### Keyword "parent"
Required Int. Parent interface id for this VLAN interface.

#### Keyword "mtu"
Optional Int. Maximum transmission unit.

#### Keyword "accept_ra"
Optional Boolean. Accept router advertisements. (IPv6 only)

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## List interfaces

```bash
maas $PROFILE interfaces read [--help] [-d] [-k] system_id [data ...] 
```

#### Positional arguments
- system_id

List all interfaces belonging to a machine, device, or rack controller.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

