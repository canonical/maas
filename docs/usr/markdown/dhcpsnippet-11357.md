Enter keyword arguments in the form `key=value`.

## Delete a DHCP snippet

```bash
maas $PROFILE dhcpsnippet delete [--help] [-d] [-k] id [data ...] 
```

#### Positional arguments
- id

Delete a DHCP snippet with the given id.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Read a DHCP snippet

```bash
maas $PROFILE dhcpsnippet read [--help] [-d] [-k] id [data ...] 
```

#### Positional arguments
- id

Read a DHCP snippet with the given id.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Revert DHCP snippet to earlier version

```bash
maas $PROFILE dhcpsnippet revert [--help] [-d] [-k] id [data ...] 
```

#### Positional arguments
- id


Revert the value of a DHCP snippet with the given id to an earlier revision.

#### Keyword "to"
Required Int.  What revision in the DHCP snippet's history to revert to.  This can either be an ID or a negative number representing how far back to go.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Update a DHCP snippet

```bash
maas $PROFILE dhcpsnippet update [--help] [-d] [-k] id [data ...] 
```

#### Positional arguments
- id


Update a DHCP snippet with the given id.

#### Keyword "name"
Optional String. The name of the DHCP snippet.

#### Keyword "value"
Optional String.  The new value of the DHCP snippet to be used in dhcpd.conf. Previous values are stored and can be reverted.
Type: String.

#### Keyword "description"
Optional String. A description of what the DHCP snippet does.

#### Keyword "enabled"
Optional Boolean. Whether or not the DHCP snippet is currently enabled.

#### Keyword "node"
Optional String. The node the DHCP snippet is to be used for. Can not be set if subnet is set.

#### Keyword "subnet"
Optional String. The subnet the DHCP snippet is to be used for. Can not be set if node is set.

#### Keyword "global_snippet"
Optional Boolean. Set the DHCP snippet to be a global option. This removes any node or subnet links.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Read a DHCP snippet

```bash
maas $PROFILE dhcpsnippet read [--help] [-d] [-k] id [data ...] 
```

#### Positional arguments
- id

Read a DHCP snippet with the given id.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |
