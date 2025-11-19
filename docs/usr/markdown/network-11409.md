Connect the given MAC addresses to this network.

```bash
maas $PROFILE network connect-macs [--help] [-d] [-k] name

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| name | The name of the resource (e.g., `my-machine`, `my-zone`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
This endpoint is no longer available. Use the 'subnet' endpoint<br>instead.





Delete network definition.

```bash
maas $PROFILE network delete [--help] [-d] [-k] name

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| name | The name of the resource (e.g., `my-machine`, `my-zone`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
This endpoint is no longer available. Use the 'subnet' endpoint<br>        instead. This operation has been deprecated in favour of 'Subnet delete'.





Disconnect the given MAC addresses from this network.

```bash
maas $PROFILE network disconnect-macs [--help] [-d] [-k] name

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| name | The name of the resource (e.g., `my-machine`, `my-zone`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
This endpoint is no longer available. Use the 'subnet' endpoint<br>instead.





Returns the list of MAC addresses connected to this network.

```bash
maas $PROFILE network list-connected-macs [--help] [-d] [-k] name

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| name | The name of the resource (e.g., `my-machine`, `my-zone`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Only MAC addresses for nodes visible to the requesting user are<br>returned.





Read network definition. This operation has been deprecated in favour of &#39;Subnet read&#39;.

```bash
maas $PROFILE network read [--help] [-d] [-k] name

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| name | The name of the resource (e.g., `my-machine`, `my-zone`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |






Update network definition.

```bash
maas $PROFILE network update [--help] [-d] [-k] name [data ...]

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| name | The name of the resource (e.g., `my-machine`, `my-zone`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
This endpoint is no longer available. Use the 'subnet' endpoint<br>        instead.

##### Keyword "name"
Optional. A simple name for the network, to make it easier to<br>refer to. Must consist only of letters, digits, dashes, and<br>underscores.
##### Keyword "ip"
Optional. Base IP address for the network, e.g. `10.1.0.0`. The host<br>bits will be zeroed.
##### Keyword "netmask"
Optional. Subnet mask to indicate which parts of an IP address<br>are part of the network address. For example, `255.255.255.0`.
##### Keyword "vlan_tag"
Optional. VLAN tag: a number between 1 and 0xffe (4094)<br>inclusive, or zero for an untagged network.
##### Keyword "description"
Optional. Detailed description of the network for the benefit<br>of users and administrators. This operation has been deprecated in favour of 'Subnet update'.


Note: This command accepts JSON.


Define a network.

```bash
maas $PROFILE networks create [--help] [-d] [-k]

```


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
This endpoint is no longer available. Use the 'subnets' endpoint<br>        instead. This operation has been deprecated in favour of 'Subnets create'.





List networks.

```bash
maas $PROFILE networks read [--help] [-d] [-k] [data ...]

```


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
##### Keyword "node"
Optional. Optionally, nodes which must be attached to any returned<br>networks. If more than one node is given, the result will be<br>restricted to networks that these nodes have in common. This operation has been deprecated in favour of 'Subnets read'.


Note: This command accepts JSON.
