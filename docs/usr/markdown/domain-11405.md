Enter keyword arguments in the form `key=value`.

## Delete domain

```bash
maas $PROFILE domain delete [--help] [-d] [-k] id [data ...] 
```

#### Positional arguments
- id

Delete a domain with the given id.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Read domain

```bash
maas $PROFILE domain read [--help] [-d] [-k] id [data ...] 
```

#### Positional arguments
- id

Read a domain with the given id.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Set domain as default

```bash
maas $PROFILE domain set-default [--help] [-d] [-k] id [data ...] 
```

#### Positional arguments
- id

Set the specified domain to be the default.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Update a domain

```bash
maas $PROFILE domain update [--help] [-d] [-k] id [data ...] 
```

#### Positional arguments
- id


Update a domain with the given id.

#### Keyword "name"
Required String. Name of the domain.

#### Keyword "authoritative"
Optional String. True if we are authoritative for this domain.

#### Keyword "ttl"
Optional String. The default TTL for this domain.

#### Keyword "forward_dns_servers"
Optional String. List of IP addresses for forward DNS servers when MAAS is not authoritative for this domain.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Create a domain

```bash
maas $PROFILE domains create [--help] [-d] [-k] [data ...] 
```

Create a domain.

#### Keyword "name"
Required String. Name of the domain.

#### Keyword "authoritative"
Optional String. Class type of the domain.

#### Keyword "forward_dns_servers"
Optional String. List of forward dns server IP addresses when MAAS is not authorititative.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## List all domains

```bash
maas $PROFILE domains read [--help] [-d] [-k] [data ...] 
```

List all domains. 

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Set the SOA serial number

```bash
maas $PROFILE domains set-serial [--help] [-d] [-k] [data ...] 
```

Set the SOA serial number for all DNS zones.

#### Keyword "serial"
Required Int. Serial number to use next.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |
