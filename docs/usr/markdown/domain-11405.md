Delete domain

```bash
maas $PROFILE domain delete [--help] [-d] [-k] id

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
Delete a domain with the given id.





Read domain

```bash
maas $PROFILE domain read [--help] [-d] [-k] id

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
Read a domain with the given id.





Set domain as default

```bash
maas $PROFILE domain set-default [--help] [-d] [-k] id

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
Set the specified domain to be the default.





Update a domain

```bash
maas $PROFILE domain update [--help] [-d] [-k] id [data ...]

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
Update a domain with the given id.

##### Keyword "name"
Optional String. Name of the domain.
##### Keyword "authoritative"
Optional String. True if we are<br>authoritative for this domain.
##### Keyword "ttl"
Optional String. The default TTL for this domain.
##### Keyword "forward_dns_servers"
Optional String. List of IP addresses for<br>forward DNS servers when MAAS is not authoritative for this domain.


Note: This command accepts JSON.


Create a domain

```bash
maas $PROFILE domains create [--help] [-d] [-k] [data ...]

```


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Create a domain.

##### Keyword "name"
Optional String. Name of the domain.
##### Keyword "authoritative"
Optional String. Class type of the<br>domain.
##### Keyword "forward_dns_servers"
Optional String. List of forward dns<br>server IP addresses when MAAS is not authoritative.


Note: This command accepts JSON.


List all domains

```bash
maas $PROFILE domains read [--help] [-d] [-k]

```


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
List all domains.





Set the SOA serial number

```bash
maas $PROFILE domains set-serial [--help] [-d] [-k] [data ...]

```


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Set the SOA serial number for all DNS zones.

##### Keyword "serial"
Optional Int. Serial number to use next.


Note: This command accepts JSON.
