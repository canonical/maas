Enter keyword arguments in the form `key=value`.

## Returns the list of MAC addresses connected to this network

```bash
maas $PROFILE network list-connected-macs [--help] [-d] [-k] name [data ...]
```

#### Positional arguments
- name

Only MAC addresses for nodes visible to the requesting user are
returned.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Read network definition

This operation has been deprecated in favour of `subnet read`.

```bash
maas $PROFILE network read [--help] [-d] [-k] name [data ...] 
```

#### Positional arguments
- name

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## List networks.

```bash
maas $PROFILE networks read [--help] [-d] [-k] [data ...] 
```

#### Keyword "node" 

Optionally, nodes which must be attached to any returned networks.  If more thanone node is given, the result will be restricted to networks that these nodes have in common.

This operation has been deprecated in favour of `subnets read`.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |
