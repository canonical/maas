Delete a DNS resource

```bash
maas $PROFILE dnsresource delete [--help] [-d] [-k] id

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
Delete a DNS resource with the given id.





Read a DNS resource

```bash
maas $PROFILE dnsresource read [--help] [-d] [-k] id

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
Read a DNS resource by id.





Update a DNS resource

```bash
maas $PROFILE dnsresource update [--help] [-d] [-k] id [data ...]

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
Update a DNS resource with the given id.

##### Keyword "fqdn"
Optional String. Hostname (with domain) for the<br>dnsresource. Either ``fqdn`` or ``name`` and ``domain`` must be<br>specified. ``fqdn`` is ignored if either ``name`` or ``domain`` is<br>given.
##### Keyword "name"
Optional String. Hostname (without domain).
##### Keyword "domain"
Optional String. Domain (name or id).
##### Keyword "address_ttl"
Optional String. Default TTL for entries<br>in this zone.
##### Keyword "ip_addresses"
Optional String. Address (ip or id) to<br>assign to the dnsresource. This creates an A or AAAA record,<br>for each of the supplied ip_addresses, IPv4 or IPv6, respectively.


Note: This command accepts JSON.


Create a DNS resource

```bash
maas $PROFILE dnsresources create [--help] [-d] [-k] [data ...]

```


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Create a DNS resource.

##### Keyword "fqdn"
Optional String. Hostname (with domain) for the<br>dnsresource. Either ``fqdn`` or ``name`` and ``domain`` must be<br>specified. ``fqdn`` is ignored if either ``name`` or ``domain`` is<br>given.
##### Keyword "name"
Optional String. Hostname (without domain).
##### Keyword "domain"
Optional String. Domain (name or id).
##### Keyword "address_ttl"
Optional String. Default TTL for entries<br>in this zone.
##### Keyword "ip_addresses"
Optional String. Address (ip or id) to<br>assign to the dnsresource. This creates an A or AAAA record,<br>for each of the supplied ip_addresses, IPv4 or IPv6, respectively.


Note: This command accepts JSON.


List resources

```bash
maas $PROFILE dnsresources read [--help] [-d] [-k] [data ...]

```


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
List all resources for the specified criteria.

##### Keyword "fqdn"
Optional String. Restricts the listing to<br>entries for the fqdn.
##### Keyword "domain"
Optional String. Restricts the listing to<br>entries for the domain.
##### Keyword "name"
Optional String. Restricts the listing to<br>entries of the given name.
##### Keyword "rrtype"
Optional String. Restricts the listing to<br>entries which have records of the given rrtype.
##### Keyword "all"
Optional Boolean. Include implicit DNS records<br>created for nodes registered in MAAS if true.


Note: This command accepts JSON.
