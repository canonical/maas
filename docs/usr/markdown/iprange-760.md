Enter keyword arguments in the form `key=value`.

## Delete an IP range

```bash
maas $PROFILE iprange delete [--help] [-d] [-k] id [data ...] 
```

#### Positional arguments
- id

Delete an IP range with the given id.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Read an IP range

```bash
maas $PROFILE iprange read [--help] [-d] [-k] id [data ...] 
```

#### Positional arguments
- id

Read an IP range with the given id.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Update an IP range

```bash
maas $PROFILE iprange update [--help] [-d] [-k] id [data ...] 
```

#### Positional arguments
- id


Update an IP range with the given id.

#### Keyword "start_ip"
Optional String. Start IP address of this range (inclusive).

#### Keyword "end_ip"
Optional String. End IP address of this range (inclusive).

#### Keyword "comment"
Optional String. A description of this range. (optional)

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Create an IP range

```bash
maas $PROFILE ipranges create [--help] [-d] [-k] [data ...] 
```

Create a new IP range.

#### Keyword "type"
Required String. Type of this range. (``dynamic`` or ``reserved``)

#### Keyword "start_ip"
Required String. Start IP address of this range (inclusive).

#### Keyword "end_ip"
Required String. End IP address of this range (inclusive).

#### Keyword "subnet"
Required Int. Subnet associated with this range.

#### Keyword "comment"
Optional String. A description of this range.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## List all IP ranges

```bash
maas $PROFILE ipranges read [--help] [-d] [-k] [data ...] 
```

List all available IP ranges. 

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |
