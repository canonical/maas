Enter keyword arguments in the form `key=value`.

## Delete a DNS resource record

```bash
maas $PROFILE dnsresource-record delete [--help] [-d] [-k] id [data ...]
```

#### Positional arguments
- id

Delete a DNS resource record with the given id.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Read a DNS resource record description Read a DNS resource record with the given id.

```bash
maas $PROFILE dnsresource-record read [--help] [-d] [-k] id [data ...] 
```

#### Positional arguments
- id

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Update a DNS resource record

```bash
maas $PROFILE dnsresource-record update [--help] [-d] [-k] id [data ...]
```

#### Positional arguments
- id


Update a DNS resource record with the given id.

#### Keyword "rrtype"
Optional String. Resource type.

#### Keyword "rrdata"
Optional String. Resource data (everything to the right of type.)

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Create a DNS resource record

```bash
maas $PROFILE dnsresource-records create [--help] [-d] [-k] [data ...] 
```

Create a new DNS resource record.

#### Keyword "fqdn"
Optional String.  Hostname (with domain) for the dnsresource.  Either ``fqdn`` or ``name`` and  ``domain`` must be specified.  ``fqdn`` is ignored if either name or domain is given (e.g. www.your-maas.maas).

#### Keyword "name"
Optional String. The name (or hostname without a domain) of the DNS resource record (e.g. www.your-maas)

#### Keyword "domain"
Optional String. The domain (name or id) where to create the DNS resource record (Domain (e.g. 'maas')

#### Keyword "rrtype"
Optional String. The resource record type (e.g ``cname``, ``mx``, ``ns``, ``srv``, ``sshfp``, ``txt``).

#### Keyword "rrdata"
Optional String. The resource record data (e.g. 'your-maas', '10 mail.your-maas.maas')

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## List all DNS resource records

```bash
maas $PROFILE dnsresource-records read [--help] [-d] [-k] [data ...] 
```

List all DNS resource records.

#### Keyword "domain"
Optional String. Restricts the listing to entries for the domain.

#### Keyword "name"
Optional String. Restricts the listing to entries of the given name.

#### Keyword "rrtype"
Optional String. Restricts the listing to entries which have records of the given rrtype.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## List all DNS resource records

```bash
maas $PROFILE dnsresource-records read [--help] [-d] [-k] [data ...] 
```

List all DNS resource records.

#### Keyword "domain"
Optional String. Restricts the listing to entries for the domain.

#### Keyword "name"
Optional String. Restricts the listing to entries of the given name.

#### Keyword "rrtype"
Optional String. Restricts the listing to entries which have records of the given rrtype.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |
