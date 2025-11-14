Delete a DNS resource record

```bash
maas $PROFILE dnsresource-record delete [--help] [-d] [-k] id

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
Delete a DNS resource record with the given id.





Read a DNS resource record description Read a DNS resource record with the given id.

```bash
maas $PROFILE dnsresource-record read [--help] [-d] [-k] id

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






Update a DNS resource record

```bash
maas $PROFILE dnsresource-record update [--help] [-d] [-k] id [data ...]

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
Update a DNS resource record with the given id.

##### Keyword "rrtype"
Optional String. Resource type.
##### Keyword "rrdata"
Optional String. Resource data (everything to<br>the right of type.)


Note: This command accepts JSON.


Create a DNS resource record

```bash
maas $PROFILE dnsresource-records create [--help] [-d] [-k] [data ...]

```


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Create a new DNS resource record.

##### Keyword "fqdn"
Optional String. Hostname (with domain) for the<br>dnsresource. Either ``fqdn`` or ``name`` and  ``domain`` must be<br>specified. ``fqdn`` is ignored if either name or domain is given (e.g.<br>www.your-maas.maas).
##### Keyword "name"
Optional String. The name (or hostname without a<br>domain) of the DNS resource record (e.g. www.your-maas)
##### Keyword "domain"
Optional String. The domain (name or id) where<br>to create the DNS resource record (Domain (e.g. 'maas')
##### Keyword "rrtype"
Optional String. The resource record type (e.g<br>``cname``, ``mx``, ``ns``, ``srv``, ``sshfp``, ``txt``).
##### Keyword "rrdata"
Optional String. The resource record data<br>(e.g. 'your-maas', '10 mail.your-maas.maas')


Note: This command accepts JSON.


List all DNS resource records

```bash
maas $PROFILE dnsresource-records read [--help] [-d] [-k] [data ...]

```


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
List all DNS resource records.

##### Keyword "fqdn"
Optional String. Restricts the listing to<br>entries for the fqdn.
##### Keyword "domain"
Optional String. Restricts the listing to<br>entries for the domain.
##### Keyword "name"
Optional String. Restricts the listing to<br>entries of the given name.
##### Keyword "rrtype"
Optional String. Restricts the listing to<br>entries which have records of the given rrtype.


Note: This command accepts JSON.
