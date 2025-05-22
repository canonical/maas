Enter keyword arguments in the form `key=value`.

## Delete a subnet

```bash
maas $PROFILE subnet delete [--help] [-d] [-k] id [data ...] 
```

#### Positional arguments
- id

Delete a subnet with the given ID.

#### Command-line options
| Option         | Effect                                        |
|----------------|-----------------------------------------------|
| --help, -h     | Show this help message and exit.              |
| -d, --debug    | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check                 |

## Summary of IP addresses

```bash
maas $PROFILE subnet ip-addresses [--help] [-d] [-k] id [data ...] 
```

#### Positional arguments
- id


Returns a summary of IP addresses assigned to this subnet.

#### Keyword "with_username"
Optional Int. If '0', suppresses the display of usernames associated with each address. '1' == True, '0' == False. (Default: '1')

#### Keyword "with_summary"
Optional Int. If '0', suppresses the display of nodes, BMCs, and and DNS records associated with each address. '1' == True, '0' == False. (Default: True)

#### Keyword "with_node_summary"
Optional Int. Deprecated. Use 'with_summary'.

#### Command-line options
| Option         | Effect                                        |
|----------------|-----------------------------------------------|
| --help, -h     | Show this help message and exit.              |
| -d, --debug    | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check                 |

## Get a subnet

```bash
maas $PROFILE subnet read [--help] [-d] [-k] id [data ...] 
```

#### Positional arguments
- id

Get information about a subnet with the given ID.

#### Command-line options
| Option         | Effect                                        |
|----------------|-----------------------------------------------|
| --help, -h     | Show this help message and exit.              |
| -d, --debug    | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check                 |

## List reserved IP ranges

```bash
maas $PROFILE subnet reserved-ip-ranges [--help] [-d] [-k] id [data ...]
```

#### Positional arguments
- id

Lists IP ranges currently reserved in the subnet.

#### Command-line options
| Option         | Effect                                        |
|----------------|-----------------------------------------------|
| --help, -h     | Show this help message and exit.              |
| -d, --debug    | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check                 |

## Get subnet statistics

```bash
maas $PROFILE subnet statistics [--help] [-d] [-k] id [data ...] 
```

#### Positional arguments
- id


Returns statistics for the specified subnet, including:

- **num_available**: the number of available IP addresses
- **largest_available**: the largest number of contiguous free IP addresses
- **num_unavailable**: the number of unavailable IP addresses
- **total_addresses**: the sum of the available plus unavailable addresses
- **usage**: the (floating point) usage percentage of this subnet
- **usage_string**: the (formatted unicode) usage percentage of this subnet
- **ranges**: the specific IP ranges present in this subnet (if specified)

Note: to supply additional optional parameters for this request, add them to the request URI, for example:

``/subnets/1/?op=statistics&include_suggestions=1``

#### Keyword "include_ranges"
Optional Int. If '1', includes detailed information about the usage of this range. '1' == True, '0' == False.

#### Keyword "include_suggestions"
Optional Int. If '1', includes the suggested gateway and dynamic range for this subnet, if it were to be configured. '1' == True, '0' == False.

#### Command-line options
| Option         | Effect                                        |
|----------------|-----------------------------------------------|
| --help, -h     | Show this help message and exit.              |
| -d, --debug    | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check                 |

## List unreserved IP ranges

```bash
maas $PROFILE subnet unreserved-ip-ranges [--help] [-d] [-k] id [data ...]
```

#### Positional arguments
- id

Lists IP ranges currently unreserved in the subnet.

#### Command-line options
| Option         | Effect                                        |
|----------------|-----------------------------------------------|
| --help, -h     | Show this help message and exit.              |
| -d, --debug    | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check                 |

## Update a subnet

```bash
maas $PROFILE subnet update [--help] [-d] [-k] id [data ...] 
```

#### Positional arguments
- id


Update a subnet with the given ID.

#### Keyword "cidr"
Optional String. The network CIDR for this subnet.

#### Keyword "name"
Optional String. The subnet's name.

#### Keyword "description"
Optional String. The subnet's description.

#### Keyword "vlan"
Optional String. VLAN this subnet belongs to. Defaults to the default VLAN for the provided fabric or defaults to the default VLAN in the default fabric (if unspecified).

#### Keyword "fabric"
Optional String. Fabric for the subnet. Defaults to the fabric the provided VLAN belongs to, or defaults to the default fabric.

#### Keyword "vid"
Optional Int. VID of the VLAN this subnet belongs to. Only used when vlan is not provided. Picks the VLAN with this VID in the provided fabric or the default fabric if one is not given.

#### Keyword "gateway_ip"
Optional String. The gateway IP address for this subnet.

#### Keyword "rdns_mode"
Optional Int.  How reverse DNS is handled for this subnet.  One of:

- ``0`` Disabled: No reverse zone is created.
- ``1`` Enabled: Generate reverse zone.
- ``2`` RFC2317: Extends '1' to create the necessary parent zone with the appropriate CNAME resource records for the network, if the network is small enough to require the support described in RFC2317.

#### Keyword "allow_dns"
Optional Int. Configure MAAS DNS to allow DNS resolution from this subnet. '0' == False, '1' == True.

#### Keyword "allow_proxy"
Optional Int. Configure maas-proxy to allow requests from this subnet. '0' == False, '1' == True.

#### Keyword "dns_servers"
Optional String. Comma-separated list of DNS servers for this subnet.

#### Keyword "managed"
Optional Int. In MAAS 2.0+, all subnets are assumed to be managed by default.

#### Keyword "disabled_boot_architectures"
Optional String.  A comma or space separated list of boot architectures which will not be responded to by isc-dhcpd. Values may be the MAAS name for the boot architecture, the IANA hex value, or the isc-dhcpd octet. 

Only managed subnets allow DHCP to be enabled on their related dynamic ranges. (Thus, dynamic ranges become "informational only"; an indication that another DHCP server is currently handling them, or that MAAS will handle them when the subnet is enabled for management.)

Managed subnets do not allow IP allocation by default. The meaning of a "reserved" IP range is reversed for an unmanaged subnet. (That is, for managed subnets, "reserved" means "MAAS cannot allocate any IP address within this reserved block". For unmanaged subnets, "reserved" means "MAAS must allocate IP addresses only from reserved IP ranges."

#### Command-line options
| Option         | Effect                                        |
|----------------|-----------------------------------------------|
| --help, -h     | Show this help message and exit.              |
| -d, --debug    | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check                 |

## Create a subnet

```bash
maas $PROFILE subnets create [--help] [-d] [-k] [data ...] 
```

Creates a new subnet.

#### Keyword "cidr"
Required String. The network CIDR for this subnet.

#### Keyword "name"
Optional String. The subnet's name.

#### Keyword "description"
Optional String. The subnet's description.

#### Keyword "vlan"
Optional String. VLAN this subnet belongs to. Defaults to the default VLAN for the provided fabric or defaults to the default VLAN in the default fabric (if unspecified).

#### Keyword "fabric"
Optional String. Fabric for the subnet. Defaults to the fabric the provided VLAN belongs to, or defaults to the default fabric.

#### Keyword "vid"
Optional Int. VID of the VLAN this subnet belongs to. Only used when vlan is not provided. Picks the VLAN with this VID in the provided fabric or the default fabric if one is not given.

#### Keyword "gateway_ip"
Optional String. The gateway IP address for this subnet.

#### Keyword "rdns_mode"
Optional Int.  How reverse DNS is handled for this subnet.  One of:

- ``0`` Disabled: No reverse zone is created.
- ``1`` Enabled: Generate reverse zone.
- ``2`` RFC2317: Extends '1' to create the necessary parent zone with the appropriate CNAME resource records for the network, if the network is small enough to require the support described in RFC2317.

#### Keyword "allow_dns"
Optional Int. Configure MAAS DNS to allow DNS resolution from this subnet. '0' == False, '1' == True.

#### Keyword "allow_proxy"
Optional Int. Configure maas-proxy to allow requests from this subnet. '0' == False, '1' == True.

#### Keyword "dns_servers"
Optional String. Comma-separated list of DNS servers for this subnet.

#### Keyword "managed"
Optional Int. In MAAS 2.0+, all subnets are assumed to be managed by default.

#### Keyword "disabled_boot_architectures"
Optional String.  A comma or space separated list of boot architectures which will not be responded to by isc-dhcpd. Values may be the MAAS name for the boot architecture, the IANA hex value, or the isc-dhcpd octet.

Only managed subnets allow DHCP to be enabled on their related dynamic ranges. (Thus, dynamic ranges become "informational only"; an indication that another DHCP server is currently handling them, or that MAAS will handle them when the subnet is enabled for management.)

Managed subnets do not allow IP allocation by default. The meaning of a "reserved" IP range is reversed for an unmanaged subnet. (That is, for managed subnets, "reserved" means "MAAS cannot allocate any IP address within this reserved block". For unmanaged subnets, "reserved" means "MAAS must allocate IP addresses only from reserved IP ranges."

#### Command-line options
| Option         | Effect                                        |
|----------------|-----------------------------------------------|
| --help, -h     | Show this help message and exit.              |
| -d, --debug    | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check                 |

## List all subnets

```bash
maas $PROFILE subnets read [--help] [-d] [-k] [data ...] 
```

Get a list of all subnets. 

#### Command-line options
| Option         | Effect                                        |
|----------------|-----------------------------------------------|
| --help, -h     | Show this help message and exit.              |
| -d, --debug    | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check                 |

