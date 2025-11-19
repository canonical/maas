Delete a subnet

```bash
maas $PROFILE subnet delete [--help] [-d] [-k] id

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| id | The ID of the resource (e.g., `1`, `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Delete a subnet with the given ID.





Summary of IP addresses

```bash
maas $PROFILE subnet ip-addresses [--help] [-d] [-k] id [data ...]

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| id | The ID of the resource (e.g., `1`, `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Returns a summary of IP addresses assigned to this subnet.

##### Keyword "with_username"
Optional Int. If '0', suppresses the<br>display of usernames associated with each address. '1' == True, '0' ==<br>False. (Default: '1')
##### Keyword "with_summary"
Optional Int. If '0', suppresses the<br>display of nodes, BMCs, and DNS records associated with each<br>address. '1' == True, '0' == False. (Default: True)
##### Keyword "with_node_summary"
Optional Int. Deprecated. Use<br>'with_summary'.


Note: This command accepts JSON.


Get a subnet

```bash
maas $PROFILE subnet read [--help] [-d] [-k] id

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| id | The ID of the resource (e.g., `1`, `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Get information about a subnet with the given ID.





List reserved IP ranges

```bash
maas $PROFILE subnet reserved-ip-ranges [--help] [-d] [-k] id

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| id | The ID of the resource (e.g., `1`, `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Lists IP ranges currently reserved in the subnet.





Get subnet statistics

```bash
maas $PROFILE subnet statistics [--help] [-d] [-k] id [data ...]

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| id | The ID of the resource (e.g., `1`, `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Returns statistics for the specified subnet, including:<br><br>- **num_available**: the number of available IP addresses<br>- **largest_available**: the largest number of contiguous free IP<br>  addresses<br>- **num_unavailable**: the number of unavailable IP addresses<br>- **total_addresses**: the sum of the available plus unavailable<br>  addresses<br>- **usage**: the (floating point) usage percentage of this subnet<br>- **usage_string**: the (formatted unicode) usage percentage of this<br>  subnet<br>- **ranges**: the specific IP ranges present in ths subnet (if<br>  specified)<br><br>Note: to supply additional optional parameters for this request, add<br>them to the request URI: e.g.<br>``/subnets/1/?op=statistics&include_suggestions=1``

##### Keyword "include_ranges"
Optional Int. If '1', includes<br>detailed information about the usage of this range. '1' == True, '0' ==<br>False.
##### Keyword "include_suggestions"
Optional Int. If '1', includes<br>the suggested gateway and dynamic range for this subnet, if it were to<br>be configured. '1' == True, '0' == False.


Note: This command accepts JSON.


List unreserved IP ranges

```bash
maas $PROFILE subnet unreserved-ip-ranges [--help] [-d] [-k] id

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| id | The ID of the resource (e.g., `1`, `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Lists IP ranges currently unreserved in the subnet.





Update a subnet

```bash
maas $PROFILE subnet update [--help] [-d] [-k] id [data ...]

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| id | The ID of the resource (e.g., `1`, `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Update a subnet with the given ID.

##### Keyword "cidr"
Optional String. The network CIDR for this<br>subnet.
##### Keyword "name"
Optional String. The subnet's name.
##### Keyword "description"
Optional String. The subnet's<br>description.
##### Keyword "vlan"
Optional String. VLAN this subnet belongs to.<br>Defaults to the default VLAN for the provided fabric or defaults to the<br>default VLAN in the default fabric (if unspecified).
##### Keyword "fabric"
Optional String. Fabric for the subnet.<br>Defaults to the fabric the provided VLAN belongs to, or defaults to the<br>default fabric.
##### Keyword "vid"
Optional Int. VID of the VLAN this subnet belongs<br>to. Only used when vlan is not provided. Picks the VLAN with this VID<br>in the provided fabric or the default fabric if one is not given.
##### Keyword "gateway_ip"
Optional String. The gateway IP address<br>for this subnet.
##### Keyword "rdns_mode"
Optional Int. How reverse<br>DNS is handled for this subnet. One of:<br><br>- ``0`` Disabled: No reverse zone is created.<br>- ``1`` Enabled: Generate reverse zone.<br>- ``2`` RFC2317: Extends '1' to create the necessary parent zone with<br>the appropriate CNAME resource records for the network, if the<br>network is small enough to require the support described in RFC2317.
##### Keyword "allow_dns"
Optional Int. Configure MAAS DNS to allow<br>DNS resolution from this subnet. '0' == False, '1' == True.
##### Keyword "allow_proxy"
Optional Int. Configure maas-proxy to<br>allow requests from this subnet. '0' == False, '1' == True.
##### Keyword "dns_servers"
Optional String. Comma-separated list of<br>DNS servers for this subnet.
##### Keyword "managed"
Optional Int. In MAAS 2.0+,<br>all subnets are assumed to be managed by default.
##### Keyword "disabled_boot_architectures"
Optional String. A comma<br>or space separated list of boot architectures which will not be<br>responded to by isc-dhcpd. Values may be the MAAS name for the boot<br>architecture, the IANA hex value, or the isc-dhcpd octet. Only managed subnets allow DHCP to be enabled on their related dynamic<br>ranges. (Thus, dynamic ranges become "informational only"; an<br>indication that another DHCP server is currently handling them, or that<br>MAAS will handle them when the subnet is enabled for management.)<br><br>Managed subnets do not allow IP allocation by default. The meaning of a<br>“reserved” IP range is reversed for an unmanaged subnet. (That is, for<br>managed subnets, “reserved” means "MAAS cannot allocate any IP address<br>within this reserved block". For unmanaged subnets, “reserved” means<br>"MAAS must allocate IP addresses only from reserved IP ranges."


Note: This command accepts JSON.


Create a subnet

```bash
maas $PROFILE subnets create [--help] [-d] [-k] [data ...]

```


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Creates a new subnet.

##### Keyword "cidr"
Optional String. The network CIDR for this<br>subnet.
##### Keyword "name"
Optional String. The subnet's name.
##### Keyword "description"
Optional String. The subnet's<br>description.
##### Keyword "vlan"
Optional String. VLAN this subnet belongs to.<br>Defaults to the default VLAN for the provided fabric or defaults to the<br>default VLAN in the default fabric (if unspecified).
##### Keyword "fabric"
Optional String. Fabric for the subnet.<br>Defaults to the fabric the provided VLAN belongs to, or defaults to the<br>default fabric.
##### Keyword "vid"
Optional Int. VID of the VLAN this subnet belongs<br>to. Only used when vlan is not provided. Picks the VLAN with this VID<br>in the provided fabric or the default fabric if one is not given.
##### Keyword "gateway_ip"
Optional String. The gateway IP address<br>for this subnet.
##### Keyword "rdns_mode"
Optional Int. How reverse<br>DNS is handled for this subnet. One of:<br><br>- ``0`` Disabled: No reverse zone is created.<br>- ``1`` Enabled: Generate reverse zone.<br>- ``2`` RFC2317: Extends '1' to create the necessary parent zone with<br>the appropriate CNAME resource records for the network, if the<br>network is small enough to require the support described in RFC2317.
##### Keyword "allow_dns"
Optional Int. Configure MAAS DNS to allow<br>DNS resolution from this subnet. '0' == False, '1' == True.
##### Keyword "allow_proxy"
Optional Int. Configure maas-proxy to<br>allow requests from this subnet. '0' == False, '1' == True.
##### Keyword "dns_servers"
Optional String. Comma-separated list of<br>DNS servers for this subnet.
##### Keyword "active_discovery"
Optional Int. Configure MAAS to detect<br>machines on the network by actively probing for devices.
##### Keyword "managed"
Optional Int. In MAAS 2.0+,<br>all subnets are assumed to be managed by default.
##### Keyword "disabled_boot_architectures"
Optional String. A comma<br>or space separated list of boot architectures which will not be<br>responded to by isc-dhcpd. Values may be the MAAS name for the boot<br>architecture, the IANA hex value, or the isc-dhcpd octet. Only managed subnets allow DHCP to be enabled on their related dynamic<br>ranges. (Thus, dynamic ranges become "informational only"; an<br>indication that another DHCP server is currently handling them, or that<br>MAAS will handle them when the subnet is enabled for management.)<br><br>Managed subnets do not allow IP allocation by default. The meaning of a<br>“reserved” IP range is reversed for an unmanaged subnet. (That is, for<br>managed subnets, “reserved” means "MAAS cannot allocate any IP address<br>within this reserved block". For unmanaged subnets, “reserved” means<br>"MAAS must allocate IP addresses only from reserved IP ranges."


Note: This command accepts JSON.


List all subnets

```bash
maas $PROFILE subnets read [--help] [-d] [-k]

```


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Get a list of all subnets.
