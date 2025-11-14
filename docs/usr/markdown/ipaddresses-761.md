List IP addresses

```bash
maas $PROFILE ipaddresses read [--help] [-d] [-k] [data ...]

```


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
List all IP addresses known to MAAS. By default, gets a listing of all IP addresses allocated to the<br>requesting user.

##### Keyword "ip"
Optional String. If specified, will only display<br>information for the specified IP address.
##### Keyword "all"
Optional Boolean. (Admin users only) If True, all<br>reserved IP addresses will be shown. (By default, only addresses of<br>type 'User reserved' that are assigned to the requesting user are<br>shown.)
##### Keyword "owner"
Optional String. (Admin users only) If<br>specified, filters the list to show only IP addresses owned by the<br>specified username.


Note: This command accepts JSON.


Release an IP address

```bash
maas $PROFILE ipaddresses release [--help] [-d] [-k] [data ...]

```


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Release an IP address that was previously reserved by the<br>user.

##### Keyword "ip"
Optional String. The IP address to release.
##### Keyword "force"
Optional Boolean. If True, allows a MAAS<br>administrator to force an IP address to be released, even if it is not<br>a user-reserved IP address or does not belong to the requesting user.<br>Use with caution.
##### Keyword "discovered"
Optional Boolean. If True, allows a MAAS<br>administrator to release a discovered address. Only valid if 'force' is<br>specified. If not specified, MAAS will attempt to release any type of<br>address except for discovered addresses.


Note: This command accepts JSON.


Reserve an IP address

```bash
maas $PROFILE ipaddresses reserve [--help] [-d] [-k] [data ...]

```


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Reserve an IP address for use outside of MAAS. Returns an IP address that MAAS will not allow any of its known nodes<br>to use; it is free for use by the requesting user until released by the<br>user. The user must supply either a subnet or a specific IP address within a<br>subnet.

##### Keyword "subnet"
Optional String. CIDR representation of the<br>subnet on which the IP reservation is required. E.g. 10.1.2.0/24
##### Keyword "ip"
Optional String. The IP address, which must be<br>within a known subnet.
##### Keyword "ip_address"
Optional String. (Deprecated.) Alias for<br>'ip' parameter. Provided for backward compatibility.
##### Keyword "hostname"
Optional String. The hostname to use for the<br>specified IP address. If no domain component is given, the default<br>domain will be used.
##### Keyword "mac"
Optional String. The MAC address that should be<br>linked to this reservation.


Note: This command accepts JSON.
