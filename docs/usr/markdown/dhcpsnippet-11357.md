Delete a DHCP snippet

```bash
maas $PROFILE dhcpsnippet delete [--help] [-d] [-k] id

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
Delete a DHCP snippet with the given id.





Read a DHCP snippet

```bash
maas $PROFILE dhcpsnippet read [--help] [-d] [-k] id

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
Read a DHCP snippet with the given id.





Revert DHCP snippet to earlier version

```bash
maas $PROFILE dhcpsnippet revert [--help] [-d] [-k] id [data ...]

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
Revert the value of a DHCP snippet with the given id to an<br>earlier revision.

##### Keyword "to"
Optional Int. What revision in the DHCP snippet's<br>history to revert to. This can either be an ID or a negative number<br>representing how far back to go.


Note: This command accepts JSON.


Update a DHCP snippet

```bash
maas $PROFILE dhcpsnippet update [--help] [-d] [-k] id [data ...]

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
Update a DHCP snippet with the given id.

##### Keyword "name"
Optional String. The name of the DHCP snippet.
##### Keyword "value"
Optional String. The new value of the DHCP<br>snippet to be used in dhcpd.conf. Previous values are stored and can be<br>reverted.
##### Keyword "description"
Optional String. A description of what<br>the DHCP snippet does.
##### Keyword "enabled"
Optional Boolean. Whether or not the DHCP<br>snippet is currently enabled.
##### Keyword "node"
Optional String. The node the DHCP snippet is to<br>be used for. Can not be set if subnet is set.
##### Keyword "subnet"
Optional String. The subnet the DHCP snippet<br>is to be used for. Can not be set if node is set.
##### Keyword "global_snippet"
Optional Boolean. Set the DHCP snippet<br>to be a global option. This removes any node or subnet links.


Note: This command accepts JSON.


Create a DHCP snippet

```bash
maas $PROFILE dhcpsnippets create [--help] [-d] [-k] [data ...]

```


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Creates a DHCP snippet.

##### Keyword "name"
Optional String. The name of the DHCP snippet.
##### Keyword "value"
Optional String. The snippet of config inserted<br>into dhcpd.conf.
##### Keyword "description"
Optional String. A description of what<br>the snippet does.
##### Keyword "enabled"
Optional Boolean. Whether or not the snippet<br>is currently enabled.
##### Keyword "node"
Optional String. The node this snippet applies<br>to. Cannot be used with subnet or global_snippet.
##### Keyword "subnet"
Optional String. The subnet this snippet<br>applies to. Cannot be used with node or global_snippet.
##### Keyword "iprange"
Optional String. The iprange within a subnet<br>this snippet applies to. Must also provide a subnet value.
##### Keyword "global_snippet"
Optional Boolean. Whether or not this<br>snippet is to be applied globally. Cannot be used with node or subnet.


Note: This command accepts JSON.


List DHCP snippets

```bash
maas $PROFILE dhcpsnippets read [--help] [-d] [-k]

```


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
List all available DHCP snippets.
