List all discovered devices with an unknown IP address

```bash
maas $PROFILE discoveries by-unknown-ip [--help] [-d] [-k]

```


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Lists all discovered devices with an unknown IP address. Filters the list of discovered devices by excluding any discoveries<br>where a known MAAS node is configured with the IP address of a<br>discovery, or has been observed using it after it was assigned by a<br>MAAS-managed DHCP server. Discoveries are listed in the order they were last observed on the<br>network (most recent first).





Lists all discovered devices completely unknown to MAAS

```bash
maas $PROFILE discoveries by-unknown-ip-and-mac [--help] [-d] [-k]

```


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Lists all discovered devices completely unknown to MAAS. Filters the list of discovered devices by excluding any discoveries<br>where a known MAAS node is configured with either the MAC address or<br>the IP address of a discovery. Discoveries are listed in the order they were last observed on the<br>network (most recent first).





List all discovered devices with unknown MAC

```bash
maas $PROFILE discoveries by-unknown-mac [--help] [-d] [-k]

```


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Filters the list of discovered devices by excluding any<br>discoveries where an interface known to MAAS is configured with a<br>discovered MAC address. Discoveries are listed in the order they were last observed on the<br>network (most recent first).





Delete all discovered neighbours

```bash
maas $PROFILE discoveries clear [--help] [-d] [-k] [data ...]

```


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Deletes all discovered neighbours and/or mDNS entries. Note: One of ``mdns``, ``neighbours``, or ``all`` parameters must be<br>supplied.

##### Keyword "mdns"
Optional Boolean. Delete all mDNS entries.
##### Keyword "neighbours"
Optional Boolean. Delete all neighbour<br>entries.
##### Keyword "all"
Optional Boolean. Delete all discovery data.


Note: This command accepts JSON.


Delete discoveries that match a MAC and IP

```bash
maas $PROFILE discoveries clear-by-mac-and-ip [--help] [-d] [-k] [data ...]

```


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Deletes all discovered neighbours (and associated reverse<br>DNS entries) associated with the given IP address and MAC address.

##### Keyword "ip"
Optional String. IP address
##### Keyword "mac"
Optional String. MAC address


Note: This command accepts JSON.


List all discovered devices

```bash
maas $PROFILE discoveries read [--help] [-d] [-k]

```


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Lists all the devices MAAS has discovered. Discoveries are<br>listed in the order they were last observed on the network (most recent<br>first).





Run discovery scan on rack networks

```bash
maas $PROFILE discoveries scan [--help] [-d] [-k] [data ...]

```


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Immediately run a neighbour discovery scan on all rack<br>networks. This command causes each connected rack controller to execute the<br>'maas-rack scan-network' command, which will scan all CIDRs configured<br>on the rack controller using 'nmap' (if it is installed) or 'ping'. Network discovery must not be set to 'disabled' for this command to be<br>useful. Scanning will be started in the background, and could take a long time<br>on rack controllers that do not have 'nmap' installed and are connected<br>to large networks. If the call is a success, this method will return a dictionary of<br>results with the following keys:<br><br>``result``: A human-readable string summarizing the results. ``scan_attempted_on``: A list of rack system_id values where a scan<br>was attempted. (That is, an RPC connection was successful and a<br>subsequent call was intended.)<br><br>``failed_to_connect_to``: A list of rack system_id values where the<br>RPC connection failed. ``scan_started_on``: A list of rack system_id values where a scan was<br>successfully started. ``scan_failed_on``: A list of rack system_id values where a scan was<br>attempted, but failed because a scan was already in progress. ``rpc_call_timed_out_on``: A list of rack system_id values where the<br>RPC connection was made, but the call timed out before a ten second<br>timeout elapsed.

##### Keyword "cidr"
Optional String. The subnet CIDR(s) to scan (can<br>be specified multiple times). If not specified, defaults to all<br>networks.
##### Keyword "force"
Optional Boolean. If True, will force the scan,<br>even if all networks are specified. (This may not be the best idea,<br>depending on acceptable use agreements, and the politics of the<br>organization that owns the network.) Note that this parameter is<br>required if all networks are specified. Default: False.
##### Keyword "always_use_ping"
Optional String. If True, will force<br>the scan to use 'ping' even if 'nmap' is installed. Default: False.
##### Keyword "slow"
Optional String. If True, and 'nmap' is being<br>used, will limit the scan to nine packets per second. If the scanner is<br>'ping', this option has no effect. Default: False.
##### Keyword "threads"
Optional String. The number of threads to use<br>during scanning. If 'nmap' is the scanner, the default is one thread<br>per 'nmap' process. If 'ping' is the scanner, the default is four<br>threads per CPU.


Note: This command accepts JSON.


Read a discovery

```bash
maas $PROFILE discovery read [--help] [-d] [-k] discovery_id

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| discovery_id | The discovery_id parameter |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Read a discovery with the given discovery_id.
