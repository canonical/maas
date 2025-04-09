Enter keyword arguments in the form `key=value`.

## Delete a DNS resource

```bash
maas $PROFILE dnsresource delete [--help] [-d] [-k] id [data ...] 
```

#### Positional arguments
- id

Delete a DNS resource with the given id.

#### Command-line options
| Option         | Effect                                        |
|----------------|-----------------------------------------------|
| --help, -h     | Show this help message and exit.              |
| -d, --debug    | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check                 |

## Read a DNS resource

```bash
maas $PROFILE dnsresource read [--help] [-d] [-k] id [data ...] 
```

#### Positional arguments
- id

Read a DNS resource by id.

#### Command-line options
| Option         | Effect                                        |
|----------------|-----------------------------------------------|
| --help, -h     | Show this help message and exit.              |
| -d, --debug    | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check                 |

## Update a DNS resource

```bash
maas $PROFILE dnsresource update [--help] [-d] [-k] id [data ...] 
```

#### Positional arguments
- id


Update a DNS resource with the given id.

#### Keyword "fqdn"
Optional String.  Hostname (with domain) for the dnsresource.  Either ``fqdn`` or ``name`` and ``domain`` must be specified.  ``fqdn`` is ignored if either ``name`` or ``domain`` is given.

#### Keyword "name"
Optional String. Hostname (without domain).

#### Keyword "domain"
Optional String. Domain (name or id).

#### Keyword "address_ttl"
Optional String. Default TTL for entries in this zone.

#### Keyword "ip_addresses"
Optional String.  Address (ip or id) to assign to the dnsresource. This creates an A or AAAA record, for each of the supplied ip_addresses, IPv4 or IPv6, respectively. 

#### Command-line options
| Option         | Effect                                        |
|----------------|-----------------------------------------------|
| --help, -h     | Show this help message and exit.              |
| -d, --debug    | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check                 |

## Create a DNS resource

```bash
maas $PROFILE dnsresources create [--help] [-d] [-k] [data ...] 
```

Create a DNS resource.

#### Keyword "fqdn"
Optional String.  Hostname (with domain) for the dnsresource.  Either ``fqdn`` or ``name`` and ``domain`` must be specified.  ``fqdn`` is ignored if either ``name`` or ``domain`` is given.

#### Keyword "name"
Required String. Hostname (without domain).

#### Keyword "domain"
Required String. Domain (name or id).

#### Keyword "address_ttl"
Optional String. Default TTL for entries in this zone.

#### Keyword "ip_addresses"
Optional String.  Address (ip or id) to assign to the dnsresource. This creates an A or AAAA record, for each of the supplied ip_addresses, IPv4 or IPv6, respectively.

#### Command-line options
| Option         | Effect                                        |
|----------------|-----------------------------------------------|
| --help, -h     | Show this help message and exit.              |
| -d, --debug    | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check                 |
