Enter keyword arguments in the form `key=value`.

## List IP addresses

```bash
maas $PROFILE ipaddresses read [--help] [-d] [-k] [data ...] 
```

List all IP addresses known to MAAS. By default, gets a listing of all IP addresses allocated to the requesting user.

#### Keyword "ip"
Optional String. If specified, will only display information for the specified IP address.

#### Keyword "all"
Optional Boolean.  (Admin users only) If True, all reserved IP addresses will be shown. (By default, only addresses of type 'User reserved' that are assigned to the requesting user are shown.)

#### Keyword "owner"
Optional String.  (Admin users only) If specified, filters the list to show only IP addresses owned by the specified username.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Release an IP address

```bash
maas $PROFILE ipaddresses release [--help] [-d] [-k] [data ...] 
```

Release an IP address that was previously reserved by the user.

#### Keyword "ip"
Required String. The IP address to release.

#### Keyword "force"
Optional Boolean.  If True, allows a MAAS administrator to force an IP address to be released, even if it is not a user-reserved IP address or does not belong to the requesting user. Use with caution.

#### Keyword "discovered"
Optional Boolean.  If True, allows a MAAS administrator to release a discovered address. Only valid if 'force' is specified. If not specified, MAAS will attempt to release any type of address except for discovered addresses.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Reserve an IP address

```bash
maas $PROFILE ipaddresses reserve [--help] [-d] [-k] [data ...] 
```

Reserve an IP address for use outside of MAAS. Returns an IP adddress that MAAS will not allow any of its known nodes to use; it is free for use by the requesting user until released by the user.

The user must supply either a subnet or a specific IP address within a subnet.

#### Keyword "subnet"
Optional String. CIDR representation of the subnet on which the IP reservation is required. E.g. 10.1.2.0/24

#### Keyword "ip"
Optional String. The IP address, which must be within a known subnet.

#### Keyword "ip_address"
Optional String. (Deprecated.) Alias for 'ip' parameter. Provided for backward compatibility.

#### Keyword "hostname"
Optional String.  The hostname to use for the specified IP address.  If no domain component is given, the default domain will be used.

#### Keyword "mac"
Optional String. The MAC address that should be linked to this reservation.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

