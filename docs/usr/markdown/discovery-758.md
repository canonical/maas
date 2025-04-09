Enter keyword arguments in the form `key=value`.

## List all discovered devices with an unknown IP address

```bash
maas $PROFILE discoveries by-unknown-ip [--help] [-d] [-k] [data ...] 
```

Lists all discovered devices with an unknown IP address.  Filters the list of discovered devices by excluding any discoveries where a known MAAS node is configured with the IP address of a discovery, or has been observed using it after it was assigned by a MAAS-managed DHCP server.

Discoveries are listed in the order they were last observed on the network (most recent first).

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Lists all discovered devices completely unknown to MAAS

```bash
maas $PROFILE discoveries by-unknown-ip-and-mac [--help] [-d] [-k] [data ...]
```

Lists all discovered devices completely unknown to MAAS. Filters the list of discovered devices by excluding any discoveries where a known MAAS node is configured with either the MAC address or the IP address of a discovery.

Discoveries are listed in the order they were last observed on the network (most recent first).

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## List all discovered devices with unknown MAC

```bash
maas $PROFILE discoveries by-unknown-mac [--help] [-d] [-k] [data ...] 
```

Filters the list of discovered devices by excluding any discoveries where an interface known to MAAS is configured with a discovered MAC address.

Discoveries are listed in the order they were last observed on the network (most recent first).

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Delete all discovered neighbours

```bash
maas $PROFILE discoveries clear [--help] [-d] [-k] [data ...] 
```

Deletes all discovered neighbours and/or mDNS entries. Note: One of ``mdns``, ``neighbours``, or ``all`` parameters must be supplied.

#### Keyword "mdns"
Optional Boolean. Delete all mDNS entries.

#### Keyword "neighbours"
Optional Boolean. Delete all neighbour entries.

#### Keyword "all"
Optional Boolean. Delete all discovery data.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Delete discoveries that match a MAC and IP

```bash
maas $PROFILE discoveries clear-by-mac-and-ip [--help] [-d] [-k] [data ...]
```

Deletes all discovered neighbours (and associated reverse DNS entries) associated with the given IP address and MAC address.

#### Keyword "ip"
Required String. IP address

#### Keyword "mac"
Required String. MAC address

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## List all discovered devices

```bash
maas $PROFILE discoveries read [--help] [-d] [-k] [data ...] 
```

Lists all the devices MAAS has discovered. Discoveries are listed in the order they were last observed on the network (most recent first).

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Run discovery scan on rack networks

```bash
maas $PROFILE discoveries scan [--help] [-d] [-k] [data ...] 
```

Immediately run a neighbour discovery scan on all rack networks.

This command causes each connected rack controller to execute the 'maas-rack scan-network' command, which will scan all CIDRs configured on the rack controller using 'nmap' (if it is installed) or 'ping'.

Network discovery must not be set to 'disabled' for this command to be useful. 

Scanning will be started in the background, and could take a long time on rack controllers that do not have 'nmap' installed and are connected to large networks.

If the call is a success, this method will return a dictionary of results with the following keys:

``result``: A human-readable string summarizing the results.

``scan_attempted_on``: A list of rack system_id values where a scan was attempted. (That is, an RPC connection was successful and a subsequent call was intended.)

``failed_to_connect_to``: A list of rack system_id values where the RPC connection failed.

``scan_started_on``: A list of rack system_id values where a scan was successfully started.

``scan_failed_on``: A list of rack system_id values where a scan was attempted, but failed because a scan was already in progress.

``rpc_call_timed_out_on``: A list of rack system_id values where the RPC connection was made, but the call timed out before a ten second timeout elapsed.

#### Keyword "cidr"
Optional String.  The subnet CIDR(s) to scan (can be specified multiple times). If not specified, defaults to all networks.

#### Keyword "force"
Optional Boolean.  If True, will force the scan, even if all networks are specified. (This may not be the best idea, depending on acceptable use agreements, and the politics of the organization that owns the network.) Note that this parameter is required if all networks are specified. Default: False.

#### Keyword "always_use_ping"
Optional String. If True, will force the scan to use 'ping' even if 'nmap' is installed. Default: False.

#### Keyword "slow"
Optional String.  If True, and 'nmap' is being used, will limit the scan to nine packets per second. If the scanner is 'ping', this option has no effect. Default: False.

#### Keyword "threads"
Optional String.  The number of threads to use during scanning. If 'nmap' is the scanner, the default is one thread per 'nmap' process. If 'ping' is the scanner, the default is four threads per CPU.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Read a discovery

```bash
maas $PROFILE discovery read [--help] [-d] [-k] discovery_id [data ...] 
```

#### Positional arguments
- discovery_id

Read a discovery with the given discovery_id.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |
